"""
Delivery/retry/DLQ tracking -- this module's own "Retry policy",
"Dead-letter queue strategy", "Delivery tracking", "Failure logging",
"Delivery status" requirements, all served by one
`NotificationDeliveryService` writing one `notification_deliveries` row
per (notification, channel) attempt sequence (see that model's own
docstring on why a DLQ is folded into this table rather than a second
one).

Retry policy: a fixed backoff schedule (`RETRY_BACKOFF_SECONDS`),
attempted up to `NotificationDelivery.max_attempts` times (3 by default,
set at creation); the attempt that would exceed `max_attempts` instead
transitions the row straight to `DEAD_LETTER`.

No background worker retries these automatically -- no Celery worker
infrastructure exists anywhere in this codebase (the same
infrastructure-not-code gap `celery`/`redis` sit unused in
requirements/base.txt for, disclosed consistently since Module 4's own
domain-events work). `retry_due` is instead reachable on demand, the
same `POST /ai/recommendations/refresh`-style disclosed pattern Module
10 used for a job with no scheduler behind it -- see
`NotificationService.retry_due_deliveries` (notification_service.py) and
the `POST /notifications/retry-due` route.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.logging import get_logger
from app.db.enums import NotificationChannel, NotificationDeliveryStatus
from app.models.notifications import Notification, NotificationDelivery
from app.notifications.providers import EmailProvider, ProviderSendResult, PushProvider, SmsProvider
from app.notifications.templates import RenderedTemplate
from app.repositories.interfaces import NotificationDeliveryRepository

logger = get_logger(__name__)

# Fixed backoff schedule: 1 min, 5 min, 30 min before the next attempt.
RETRY_BACKOFF_SECONDS: tuple[int, ...] = (60, 300, 1800)


class NotificationDeliveryService:
    def __init__(
        self,
        *,
        delivery_repo: NotificationDeliveryRepository,
        email_provider: EmailProvider,
        sms_provider: SmsProvider,
        push_provider: PushProvider,
    ) -> None:
        self._deliveries = delivery_repo
        self._email = email_provider
        self._sms = sms_provider
        self._push = push_provider

    async def dispatch(
        self,
        *,
        notification: Notification,
        channel: NotificationChannel,
        rendered: RenderedTemplate,
        html_body: str | None = None,
        recipient_email: str | None = None,
        recipient_phone: str | None = None,
        recipient_device_token: str | None = None,
        max_attempts: int = 3,
    ) -> NotificationDelivery:
        """
        Creates the delivery row and makes the first attempt synchronously
        (no background worker -- see module docstring). A failed first
        attempt is not retried inline; it's left `FAILED` with
        `next_retry_at` set, for a later `retry_due_deliveries` sweep to
        pick up.
        """
        delivery = NotificationDelivery(
            notification_id=notification.id,
            channel=channel,
            status=NotificationDeliveryStatus.PENDING,
            attempt_count=0,
            max_attempts=max_attempts,
        )
        delivery = await self._deliveries.add(delivery)
        await self._attempt(
            delivery,
            rendered=rendered,
            html_body=html_body,
            recipient_email=recipient_email,
            recipient_phone=recipient_phone,
            recipient_device_token=recipient_device_token,
        )
        return delivery

    async def list_due_for_retry(self, *, now: datetime | None = None, limit: int = 100) -> list[NotificationDelivery]:
        return await self._deliveries.list_due_for_retry(now=now or datetime.now(timezone.utc), limit=limit)

    async def retry_delivery(
        self,
        delivery: NotificationDelivery,
        *,
        rendered: RenderedTemplate,
        html_body: str | None = None,
        recipient_email: str | None = None,
        recipient_phone: str | None = None,
        recipient_device_token: str | None = None,
    ) -> NotificationDelivery:
        """Re-attempts one due `FAILED` delivery. The caller (`NotificationService.retry_due_deliveries`) is responsible for re-rendering the template and re-resolving the recipient's current contact details."""
        await self._attempt(
            delivery,
            rendered=rendered,
            html_body=html_body,
            recipient_email=recipient_email,
            recipient_phone=recipient_phone,
            recipient_device_token=recipient_device_token,
        )
        return delivery

    async def _attempt(
        self,
        delivery: NotificationDelivery,
        *,
        rendered: RenderedTemplate,
        html_body: str | None,
        recipient_email: str | None,
        recipient_phone: str | None,
        recipient_device_token: str | None,
    ) -> None:
        attempt_count = delivery.attempt_count + 1
        now = datetime.now(timezone.utc)

        result = await self._send(
            delivery.channel,
            rendered=rendered,
            html_body=html_body,
            recipient_email=recipient_email,
            recipient_phone=recipient_phone,
            recipient_device_token=recipient_device_token,
        )

        if result.sent:
            await self._deliveries.update_status(
                delivery,
                status=NotificationDeliveryStatus.SENT,
                attempt_count=attempt_count,
                last_attempted_at=now,
                next_retry_at=None,
                delivered_at=now,
                error_message=None,
                provider_message_id=result.provider_message_id,
            )
            return

        if attempt_count >= delivery.max_attempts:
            await self._deliveries.update_status(
                delivery,
                status=NotificationDeliveryStatus.DEAD_LETTER,
                attempt_count=attempt_count,
                last_attempted_at=now,
                next_retry_at=None,
                delivered_at=None,
                error_message=result.error,
                provider_message_id=None,
            )
            logger.warning(
                "notification_delivery_dead_lettered",
                delivery_id=str(delivery.id),
                channel=delivery.channel.value,
                attempt_count=attempt_count,
            )
            return

        backoff_index = min(attempt_count - 1, len(RETRY_BACKOFF_SECONDS) - 1)
        next_retry_at = now + timedelta(seconds=RETRY_BACKOFF_SECONDS[backoff_index])
        await self._deliveries.update_status(
            delivery,
            status=NotificationDeliveryStatus.FAILED,
            attempt_count=attempt_count,
            last_attempted_at=now,
            next_retry_at=next_retry_at,
            delivered_at=None,
            error_message=result.error,
            provider_message_id=None,
        )
        logger.warning(
            "notification_delivery_failed",
            delivery_id=str(delivery.id),
            channel=delivery.channel.value,
            attempt_count=attempt_count,
            next_retry_at=next_retry_at.isoformat(),
            error=result.error,
        )

    async def _send(
        self,
        channel: NotificationChannel,
        *,
        rendered: RenderedTemplate,
        html_body: str | None,
        recipient_email: str | None,
        recipient_phone: str | None,
        recipient_device_token: str | None,
    ) -> ProviderSendResult:
        if channel == NotificationChannel.IN_APP:
            # The in-app "delivery" already happened the moment the owning
            # Notification row was inserted (Notification model's own
            # docstring) -- this row exists purely for uniform delivery-
            # status tracking across every channel, not a second network
            # call.
            return ProviderSendResult(sent=True)
        if channel == NotificationChannel.EMAIL:
            if not recipient_email:
                return ProviderSendResult(sent=False, error="No recipient email on file")
            return await self._email.send(
                to=recipient_email, subject=rendered.subject or "Notification", html_body=html_body, text_body=rendered.body
            )
        if channel == NotificationChannel.SMS:
            if not recipient_phone:
                return ProviderSendResult(sent=False, error="No recipient phone on file")
            return await self._sms.send(to=recipient_phone, body=rendered.body)
        if channel == NotificationChannel.PUSH:
            if not recipient_device_token:
                return ProviderSendResult(sent=False, error="No device token on file")
            return await self._push.send(
                device_token=recipient_device_token, title=rendered.subject or "Notification", body=rendered.body
            )
        return ProviderSendResult(sent=False, error=f"Unknown channel {channel}")
