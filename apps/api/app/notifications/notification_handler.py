"""
`NotificationService` (the only code path that ever creates a
`Notification` row or drives a delivery) and `NotificationEventHandler`
(the `EventDispatcher`-registered subscriber that makes this module
event-driven, per its own ARCHITECTURE requirement: "No business module
may send notifications directly. Business modules publish domain events.
Notification handlers decide: whether to notify, who to notify, which
channel, when to retry").

Recipient resolution follows Module 9/10's own "payload carries only an
id, service fetches the row" pattern documented on
`app/services/digital_twin_service.py`: most event payloads don't carry
`branch_id` directly, so `NotificationEventHandler` fetches the owning
Plant/Inventory/Invoice/SalesOrder row to resolve branch-scoped
recipients via `PermissionRepository.list_users_with_permission` (added
by this module).

Two narrow, disclosed exceptions to "every business event produces a
Notification": `employee.invited`'s actual invitee has no `User` row yet
(nothing to set `Notification.recipient_user_id` to) -- this handler
instead confirms the *inviter* got their invite sent; `auth.
password_reset_requested`/`auth.email_verification_requested` create an
in-app-only audit record (`IN_APP` is the only candidate channel) since
the real token-bearing email is already sent directly by `AuthService`
through the narrower `EmailSender` path, never through this pipeline --
see `app/domain_events/events.py`'s docstrings on those two event
classes for the full security reasoning.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.logging import get_logger
from app.db.enums import EmployeeStatus, NotificationCategory, NotificationChannel
from app.models.events import DomainEvent
from app.models.notifications import Notification
from app.notifications.delivery import NotificationDeliveryService
from app.notifications.hub import NotificationHub
from app.notifications.preferences import PreferenceService
from app.notifications.templates import RenderedTemplate, TemplateNotFoundError, TemplateService
from app.repositories.interfaces import (
    EmployeeRepository,
    InventoryRepository,
    InvoiceRepository,
    NotificationRepository,
    PermissionRepository,
    PlantRepository,
    SalesOrderRepository,
    UserRepository,
)

logger = get_logger(__name__)

# Every channel a Notification is a *candidate* for, before preferences
# narrow it down. IN_APP is not optional -- it's always created first,
# regardless of preferences (Notification model's own docstring) -- so it
# is deliberately excluded from `_OTHER_CHANNELS` and handled unconditionally.
_OTHER_CHANNELS: tuple[NotificationChannel, ...] = (
    NotificationChannel.EMAIL,
    NotificationChannel.SMS,
    NotificationChannel.PUSH,
)


def _uid(value: object) -> uuid.UUID:
    """Event payloads are JSON-safe (`DomainEventPublisher._json_safe` stringifies every UUID before persisting) -- the same helper `digital_twin_service.py` already established as `_maybe_uuid`, non-optional here."""
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


class NotificationService:
    """
    Owns the `Notification` write path end to end: create the in-app
    record, fan out to whichever other channels the recipient's
    preferences allow, track delivery, and serve the read-side (list,
    unread count, mark read) this module's REALTIME section requires.
    """

    def __init__(
        self,
        *,
        notification_repo: NotificationRepository,
        delivery_service: NotificationDeliveryService,
        preference_service: PreferenceService,
        template_service: TemplateService,
        hub: NotificationHub,
        user_repo: UserRepository,
    ) -> None:
        self._notifications = notification_repo
        self._delivery = delivery_service
        self._preferences = preference_service
        self._templates = template_service
        self._hub = hub
        self._users = user_repo

    async def notify(
        self,
        *,
        nursery_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
        category: NotificationCategory,
        context: dict,
        deep_link: str | None = None,
    ) -> Notification:
        in_app = await self._templates.render(
            nursery_id=nursery_id, category=category, channel=NotificationChannel.IN_APP, context=context
        )
        notification = Notification(
            nursery_id=nursery_id,
            recipient_user_id=recipient_user_id,
            category=category,
            message=in_app.body[:500],
            deep_link=deep_link,
        )
        notification = await self._notifications.add(notification)

        # The in-app "delivery" is unconditional and instantaneous -- see
        # NotificationDeliveryService._send's own IN_APP branch.
        await self._delivery.dispatch(
            notification=notification, channel=NotificationChannel.IN_APP, rendered=in_app
        )

        unread = await self.unread_count(recipient_user_id, nursery_id)
        await self._hub.push_to_user(
            recipient_user_id,
            {
                "type": "notification",
                "notification": {
                    "id": str(notification.id),
                    "category": category.value,
                    "message": notification.message,
                    "deep_link": notification.deep_link,
                    "created_at": notification.created_at.isoformat() if notification.created_at else None,
                },
                "unread_count": unread,
            },
        )

        decisions = await self._preferences.resolve_channels(
            user_id=recipient_user_id, category=category, candidate_channels=list(_OTHER_CHANNELS)
        )
        for decision in decisions:
            if not decision.should_send:
                logger.info(
                    "notification_channel_suppressed",
                    notification_id=str(notification.id),
                    channel=decision.channel.value,
                    reason=decision.reason,
                )
                continue
            await self._dispatch_other_channel(
                notification=notification, nursery_id=nursery_id, recipient_user_id=recipient_user_id,
                channel=decision.channel, category=category, context=context,
            )

        return notification

    async def _dispatch_other_channel(
        self,
        *,
        notification: Notification,
        nursery_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
        channel: NotificationChannel,
        category: NotificationCategory,
        context: dict,
    ) -> None:
        html_body: str | None = None
        try:
            if channel == NotificationChannel.EMAIL:
                text_rendered = await self._templates.render(
                    nursery_id=nursery_id, category=category, channel=channel, format="text", context=context
                )
                try:
                    html_rendered = await self._templates.render(
                        nursery_id=nursery_id, category=category, channel=channel, format="html", context=context
                    )
                    html_body = html_rendered.body
                except TemplateNotFoundError:
                    html_body = None
                rendered = text_rendered
            else:
                rendered = await self._templates.render(
                    nursery_id=nursery_id, category=category, channel=channel, context=context
                )
        except TemplateNotFoundError:
            logger.warning(
                "notification_no_template", category=category.value, channel=channel.value
            )
            return

        recipient_email: str | None = None
        if channel == NotificationChannel.EMAIL:
            user = await self._users.get_by_id(recipient_user_id)
            recipient_email = user.email if user is not None else None

        # SMS/Push have no contact-detail column on `User` yet (no phone
        # number / device token field exists on the Module 2 User model --
        # an infrastructure/data gap for a future Profile module, not this
        # one's to add). `NotificationDeliveryService` records the
        # resulting "no contact info on file" as a normal FAILED/DEAD_LETTER
        # delivery, not a silent drop -- see that service's own `_send`.
        await self._delivery.dispatch(
            notification=notification,
            channel=channel,
            rendered=rendered,
            html_body=html_body,
            recipient_email=recipient_email,
            recipient_phone=None,
            recipient_device_token=None,
        )

    async def list_notifications(
        self,
        *,
        user_id: uuid.UUID,
        nursery_id: uuid.UUID,
        unread_only: bool = False,
        category: NotificationCategory | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Notification], int]:
        return await self._notifications.list_for_user(
            user_id, nursery_id, unread_only=unread_only, category=category, offset=offset, limit=limit
        )

    async def unread_count(self, user_id: uuid.UUID, nursery_id: uuid.UUID) -> int:
        return await self._notifications.count_unread(user_id, nursery_id)

    async def mark_read(self, notification: Notification) -> None:
        await self._notifications.mark_read(notification, now=datetime.now(timezone.utc))
        unread = await self.unread_count(notification.recipient_user_id, notification.nursery_id)
        await self._hub.push_to_user(
            notification.recipient_user_id, {"type": "unread_count", "unread_count": unread}
        )

    async def mark_all_read(self, user_id: uuid.UUID, nursery_id: uuid.UUID) -> int:
        count = await self._notifications.mark_all_read(user_id, nursery_id, now=datetime.now(timezone.utc))
        await self._hub.push_to_user(user_id, {"type": "unread_count", "unread_count": 0})
        return count

    async def retry_due_deliveries(self, *, now: datetime | None = None, limit: int = 100) -> list[dict]:
        """
        On-demand retry sweep (no scheduler exists in this codebase -- see
        `app/notifications/delivery.py`'s own module docstring). Re-sends
        using the already-persisted `Notification.message` as the body --
        this codebase doesn't persist the original per-channel template
        context past the first render, so a retry re-renders from the
        stored in-app text rather than the original structured context.
        This is a deliberate scope simplification: it's a strictly
        adequate retry (the recipient gets the same information), just
        not a byte-for-byte replay of the original channel-specific
        formatting.
        """
        due = await self._delivery.list_due_for_retry(now=now, limit=limit)
        results = []
        for delivery in due:
            notification = await self._notifications.get_by_id(delivery.notification_id)
            if notification is None:
                continue
            rendered = RenderedTemplate(subject=None, body=notification.message)
            recipient_email: str | None = None
            if delivery.channel == NotificationChannel.EMAIL:
                user = await self._users.get_by_id(notification.recipient_user_id)
                recipient_email = user.email if user is not None else None
            await self._delivery.retry_delivery(
                delivery, rendered=rendered, recipient_email=recipient_email
            )
            results.append({"delivery_id": delivery.id, "notification_id": notification.id, "status": delivery.status})
        return results


class NotificationEventHandler:
    """
    The `EventDispatcher`-registered subscriber (`app/domain_events/dispatcher.py`'s
    `EventHandler` Protocol) that is this module's whole event-driven
    architecture: every category this module's EVENTS section requires is
    wired here, and *only* here -- no business service constructs a
    `Notification` directly (grep the codebase for `Notification(` outside
    this file: there is exactly one other hit, `NotificationService.notify`
    itself, which this class is the sole caller of).
    """

    name = "notification_dispatcher"
    event_types: frozenset[str] = frozenset(
        {
            "employee.invited",
            "auth.password_reset_requested",
            "auth.email_verification_requested",
            "plant.registered",
            "plant.status_changed",
            "plant.disease_detected",
            "plant.sold",
            "plant.moved",
            "sales_order.reservation_created",
            "inventory.reservation_expiring_soon",
            "invoice.generated",
            "invoice.payment_received",
            "inventory.stock_transferred",
            "inventory.stock_received",
            "inventory.stock_sold",
            "notification.system_alert_raised",
            "ai.recommendation_generated",
            "ai.prediction_generated",
            # --- Added by Phase 6 Module 12 (Reports & Analytics) ---
            "report.generated",
            "report.failed",
        }
    )

    def __init__(
        self,
        *,
        notification_service: NotificationService,
        permission_repo: PermissionRepository,
        plant_repo: PlantRepository,
        inventory_repo: InventoryRepository,
        invoice_repo: InvoiceRepository,
        sales_order_repo: SalesOrderRepository,
        employee_repo: EmployeeRepository,
    ) -> None:
        self._service = notification_service
        self._permissions = permission_repo
        self._plants = plant_repo
        self._inventory = inventory_repo
        self._invoices = invoice_repo
        self._sales_orders = sales_order_repo
        self._employees = employee_repo
        self._handlers = {
            "employee.invited": self._on_employee_invited,
            "auth.password_reset_requested": self._on_password_reset_requested,
            "auth.email_verification_requested": self._on_email_verification_requested,
            "plant.registered": self._on_plant_registered,
            "plant.status_changed": self._on_plant_status_changed,
            "plant.disease_detected": self._on_disease_detected,
            "plant.sold": self._on_plant_sold,
            "plant.moved": self._on_plant_moved,
            "sales_order.reservation_created": self._on_reservation_created,
            "inventory.reservation_expiring_soon": self._on_reservation_expiring_soon,
            "invoice.generated": self._on_invoice_generated,
            "invoice.payment_received": self._on_payment_received,
            "inventory.stock_transferred": self._on_stock_transferred,
            "inventory.stock_received": self._on_stock_received,
            "inventory.stock_sold": self._on_stock_sold,
            "notification.system_alert_raised": self._on_system_alert_raised,
            "ai.recommendation_generated": self._on_ai_recommendation_generated,
            "ai.prediction_generated": self._on_ai_prediction_generated,
            # --- Added by Phase 6 Module 12 (Reports & Analytics) ---
            "report.generated": self._on_report_generated,
            "report.failed": self._on_report_failed,
        }

    async def handle(self, event: DomainEvent) -> int | None:
        handler = self._handlers.get(event.event_type)
        if handler is None:
            return None  # Registered with exactly `event_types` above -- unreachable in practice.
        await handler(event)
        return None

    # ------------------------------------------------------------------
    # Recipient resolution helpers
    # ------------------------------------------------------------------

    async def _recipients_with_permission(
        self, nursery_id: uuid.UUID, permission_code: str, *, branch_id: uuid.UUID | None
    ) -> list[uuid.UUID]:
        return await self._permissions.list_users_with_permission(
            nursery_id, permission_code, branch_id=branch_id
        )

    async def _notify_many(
        self,
        *,
        nursery_id: uuid.UUID,
        category: NotificationCategory,
        recipient_user_ids: list[uuid.UUID],
        context: dict,
        exclude_actor: uuid.UUID | None = None,
    ) -> None:
        for user_id in set(recipient_user_ids):
            if exclude_actor is not None and user_id == exclude_actor:
                continue
            await self._service.notify(
                nursery_id=nursery_id, recipient_user_id=user_id, category=category, context=context
            )

    # ------------------------------------------------------------------
    # Per-event-type handlers
    # ------------------------------------------------------------------

    async def _on_employee_invited(self, event: DomainEvent) -> None:
        # The invitee has no User row yet -- nothing to set
        # Notification.recipient_user_id to. Confirm to the inviter
        # instead; the actual invite email is already sent directly by
        # EmployeeService through EmailProvider (a disclosed, narrow
        # exception -- see this file's module docstring).
        if event.actor_user_id is None or event.nursery_id is None:
            return
        await self._service.notify(
            nursery_id=event.nursery_id,
            recipient_user_id=event.actor_user_id,
            category=NotificationCategory.EMPLOYEE_INVITE,
            context={"email": event.payload.get("email"), "role_code": event.payload.get("role_code")},
        )

    async def _on_password_reset_requested(self, event: DomainEvent) -> None:
        if event.nursery_id is None:
            return
        await self._service.notify(
            nursery_id=event.nursery_id,
            recipient_user_id=event.aggregate_id,
            category=NotificationCategory.PASSWORD_RESET,
            context={},
        )

    async def _on_email_verification_requested(self, event: DomainEvent) -> None:
        if event.nursery_id is None:
            return
        await self._service.notify(
            nursery_id=event.nursery_id,
            recipient_user_id=event.aggregate_id,
            category=NotificationCategory.EMAIL_VERIFICATION,
            context={},
        )

    async def _on_plant_registered(self, event: DomainEvent) -> None:
        if event.nursery_id is None:
            return
        branch_id = _uid(event.payload["branch_id"])
        plant = await self._plants.get_by_id(event.aggregate_id)
        context = {"common_label": (plant.common_label if plant else None) or "A plant", "branch_name": ""}
        recipients = await self._recipients_with_permission(event.nursery_id, "plants:write", branch_id=branch_id)
        await self._notify_many(
            nursery_id=event.nursery_id, category=NotificationCategory.PLANT_REGISTERED,
            recipient_user_ids=recipients, context=context, exclude_actor=event.actor_user_id,
        )

    async def _on_plant_status_changed(self, event: DomainEvent) -> None:
        if event.nursery_id is None:
            return
        to_status = event.payload.get("to_status")
        if to_status is None:
            return
        category_by_status = {
            "ready_for_sale": NotificationCategory.PLANT_READY_FOR_SALE,
            "under_treatment": NotificationCategory.PLANT_UNDER_TREATMENT,
        }
        category = category_by_status.get(str(to_status))
        if category is None:
            return
        plant = await self._plants.get_by_id(event.aggregate_id)
        if plant is None:
            return
        context = {"common_label": plant.common_label or "A plant"}
        recipients = await self._recipients_with_permission(event.nursery_id, "plants:write", branch_id=plant.branch_id)
        await self._notify_many(
            nursery_id=event.nursery_id, category=category, recipient_user_ids=recipients, context=context,
            exclude_actor=event.actor_user_id,
        )

    async def _on_disease_detected(self, event: DomainEvent) -> None:
        if event.nursery_id is None:
            return
        plant = await self._plants.get_by_id(event.aggregate_id)
        if plant is None:
            return
        context = {
            "common_label": plant.common_label or "A plant",
            "condition_name": event.payload.get("condition_name"),
            "severity": event.payload.get("severity"),
        }
        recipients = await self._recipients_with_permission(event.nursery_id, "disease:write", branch_id=plant.branch_id)
        await self._notify_many(
            nursery_id=event.nursery_id, category=NotificationCategory.DISEASE_CONFIRMED,
            recipient_user_ids=recipients, context=context, exclude_actor=event.actor_user_id,
        )

    async def _on_plant_sold(self, event: DomainEvent) -> None:
        if event.nursery_id is None:
            return
        plant = await self._plants.get_by_id(event.aggregate_id)
        if plant is None:
            return
        context = {"common_label": plant.common_label or "A plant", "unit_price": event.payload.get("unit_price")}
        recipients = await self._recipients_with_permission(event.nursery_id, "sales:read", branch_id=plant.branch_id)
        await self._notify_many(
            nursery_id=event.nursery_id, category=NotificationCategory.PLANT_SOLD,
            recipient_user_ids=recipients, context=context, exclude_actor=event.actor_user_id,
        )

    async def _on_plant_moved(self, event: DomainEvent) -> None:
        if event.nursery_id is None:
            return
        plant = await self._plants.get_by_id(event.aggregate_id)
        to_branch_id = _uid(event.payload["to_branch_id"])
        context = {"common_label": (plant.common_label if plant else None) or "A plant"}
        recipients = await self._recipients_with_permission(event.nursery_id, "plants:write", branch_id=to_branch_id)
        await self._notify_many(
            nursery_id=event.nursery_id, category=NotificationCategory.PLANT_TRANSFERRED,
            recipient_user_ids=recipients, context=context, exclude_actor=event.actor_user_id,
        )

    async def _on_reservation_created(self, event: DomainEvent) -> None:
        if event.nursery_id is None:
            return
        order = await self._sales_orders.get_by_id(event.aggregate_id)
        if order is None:
            return
        context = {"order_item_id": event.payload.get("order_item_id"), "quantity": event.payload.get("quantity")}
        recipients = await self._recipients_with_permission(event.nursery_id, "sales:write", branch_id=order.branch_id)
        await self._notify_many(
            nursery_id=event.nursery_id, category=NotificationCategory.RESERVATION_CREATED,
            recipient_user_ids=recipients, context=context, exclude_actor=event.actor_user_id,
        )

    async def _on_reservation_expiring_soon(self, event: DomainEvent) -> None:
        if event.nursery_id is None:
            return
        inventory = await self._inventory.get_by_id(event.aggregate_id)
        if inventory is None:
            return
        context = {
            "minutes_remaining": event.payload.get("minutes_remaining"),
            "product_name": inventory.name,
        }
        recipients = await self._recipients_with_permission(event.nursery_id, "inventory:write", branch_id=inventory.branch_id)
        await self._notify_many(
            nursery_id=event.nursery_id, category=NotificationCategory.RESERVATION_EXPIRING,
            recipient_user_ids=recipients, context=context,
        )

    async def _on_invoice_generated(self, event: DomainEvent) -> None:
        if event.nursery_id is None:
            return
        branch_id = _uid(event.payload["branch_id"])
        context = {"total_amount": event.payload.get("total_amount")}
        recipients = await self._recipients_with_permission(event.nursery_id, "invoices:read", branch_id=branch_id)
        await self._notify_many(
            nursery_id=event.nursery_id, category=NotificationCategory.INVOICE_GENERATED,
            recipient_user_ids=recipients, context=context, exclude_actor=event.actor_user_id,
        )

    async def _on_payment_received(self, event: DomainEvent) -> None:
        if event.nursery_id is None:
            return
        invoice = await self._invoices.get_by_id(event.aggregate_id)
        if invoice is None:
            return
        context = {"amount": event.payload.get("amount"), "method": event.payload.get("method")}
        recipients = await self._recipients_with_permission(event.nursery_id, "invoices:read", branch_id=invoice.branch_id)
        await self._notify_many(
            nursery_id=event.nursery_id, category=NotificationCategory.PAYMENT_RECEIVED,
            recipient_user_ids=recipients, context=context, exclude_actor=event.actor_user_id,
        )

    async def _on_stock_transferred(self, event: DomainEvent) -> None:
        if event.nursery_id is None:
            return
        inventory = await self._inventory.get_by_id(event.aggregate_id)
        if inventory is None:
            return
        context = {"quantity": event.payload.get("quantity")}
        recipients = await self._recipients_with_permission(event.nursery_id, "inventory:write", branch_id=inventory.branch_id)
        await self._notify_many(
            nursery_id=event.nursery_id, category=NotificationCategory.INVENTORY_TRANSFER,
            recipient_user_ids=recipients, context=context, exclude_actor=event.actor_user_id,
        )
        await self._maybe_low_stock_alert(event.nursery_id, inventory, actor=event.actor_user_id)

    async def _on_stock_received(self, event: DomainEvent) -> None:
        if event.nursery_id is None or not event.payload.get("reference_purchase_order_id"):
            return
        inventory = await self._inventory.get_by_id(event.aggregate_id)
        if inventory is None:
            return
        context = {"quantity": event.payload.get("quantity")}
        recipients = await self._recipients_with_permission(event.nursery_id, "purchase_orders:receive", branch_id=inventory.branch_id)
        await self._notify_many(
            nursery_id=event.nursery_id, category=NotificationCategory.PURCHASE_ORDER_RECEIVED,
            recipient_user_ids=recipients, context=context, exclude_actor=event.actor_user_id,
        )

    async def _on_stock_sold(self, event: DomainEvent) -> None:
        if event.nursery_id is None:
            return
        inventory = await self._inventory.get_by_id(event.aggregate_id)
        if inventory is None:
            return
        await self._maybe_low_stock_alert(event.nursery_id, inventory, actor=event.actor_user_id)

    async def _maybe_low_stock_alert(self, nursery_id: uuid.UUID, inventory, *, actor: uuid.UUID | None) -> None:
        """
        Low Stock Alert has no dedicated domain event -- it's a live-row
        threshold check run after any event that can decrease available
        stock (a sale or an outbound transfer), per this module's own
        design decision to avoid a redundant "low stock" event duplicating
        state `Inventory` already holds authoritatively.
        """
        available = inventory.quantity - inventory.reserved_quantity - inventory.damaged_quantity
        if available > inventory.low_stock_threshold:
            return
        context = {
            "product_name": inventory.name,
            "quantity_available": available,
            "threshold": inventory.low_stock_threshold,
        }
        recipients = await self._recipients_with_permission(nursery_id, "inventory:write", branch_id=inventory.branch_id)
        await self._notify_many(
            nursery_id=nursery_id, category=NotificationCategory.LOW_STOCK,
            recipient_user_ids=recipients, context=context, exclude_actor=actor,
        )

    async def _on_system_alert_raised(self, event: DomainEvent) -> None:
        if event.nursery_id is None:
            return
        context = {"title": event.payload.get("title"), "message": event.payload.get("message")}
        employees, _total = await self._employees.list_for_nursery(
            event.nursery_id, offset=0, limit=1000, status=EmployeeStatus.ACTIVE
        )
        recipients = [e.user_id for e in employees]
        await self._notify_many(
            nursery_id=event.nursery_id, category=NotificationCategory.SYSTEM_ALERT,
            recipient_user_ids=recipients, context=context, exclude_actor=event.actor_user_id,
        )

    async def _on_ai_recommendation_generated(self, event: DomainEvent) -> None:
        if event.nursery_id is None:
            return
        branch_id = event.aggregate_id  # AIRecommendationGenerated: aggregate_type="Branch", aggregate_id=branch_id.
        context = {"priority": event.payload.get("priority")}
        recipients = await self._recipients_with_permission(event.nursery_id, "ai_predictions:read", branch_id=branch_id)
        await self._notify_many(
            nursery_id=event.nursery_id, category=NotificationCategory.AI_RECOMMENDATION_READY,
            recipient_user_ids=recipients, context=context,
        )

    async def _on_ai_prediction_generated(self, event: DomainEvent) -> None:
        if event.nursery_id is None:
            return
        plant = await self._plants.get_by_id(event.aggregate_id)
        if plant is None:
            return
        context = {
            "prediction_type": event.payload.get("prediction_type"),
            "confidence": event.payload.get("confidence") or "unknown",
        }
        recipients = await self._recipients_with_permission(event.nursery_id, "ai_predictions:read", branch_id=plant.branch_id)
        await self._notify_many(
            nursery_id=event.nursery_id, category=NotificationCategory.AI_PREDICTION_READY,
            recipient_user_ids=recipients, context=context,
        )

    # --- Added by Phase 6 Module 12 (Reports & Analytics) ---

    async def _on_report_generated(self, event: DomainEvent) -> None:
        """Notifies the requester only (`event.actor_user_id`) -- a generated report is a personal artifact, not an org-wide broadcast, the same one-recipient shape `_on_employee_invited`'s inviter-confirmation uses."""
        if event.nursery_id is None or event.actor_user_id is None:
            return
        context = {
            "report_type": event.payload.get("report_type"),
            "format": event.payload.get("format"),
            "file_url": event.payload.get("file_url"),
        }
        await self._service.notify(
            nursery_id=event.nursery_id, recipient_user_id=event.actor_user_id,
            category=NotificationCategory.REPORT_READY, context=context,
        )

    async def _on_report_failed(self, event: DomainEvent) -> None:
        """Same REPORT_READY category as success -- the template's `{% if file_url %}` branch (app/notifications/templates.py) is what distinguishes success from failure in the rendered message; a dedicated failure category would double this module's template count for no consumer-facing benefit (nothing filters notifications by success/failure sub-type)."""
        if event.nursery_id is None or event.actor_user_id is None:
            return
        context = {
            "report_type": event.payload.get("report_type"),
            "file_url": None,
            "error_message": event.payload.get("error_message"),
        }
        await self._service.notify(
            nursery_id=event.nursery_id, recipient_user_id=event.actor_user_id,
            category=NotificationCategory.REPORT_READY, context=context,
        )
