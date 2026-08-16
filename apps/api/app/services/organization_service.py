"""
Module 4 (Nursery & Organization Management) — Organization Management:
create/update/archive a Nursery, and its Settings (branding, currency,
timezone, contact information).

Same layering discipline as Module 2/3's services: takes only repository
Protocols (app/repositories/interfaces.py) and pure data, no FastAPI/
SQLAlchemy-session concerns. Authorization is *not* checked here -- by the
time a service method runs, the route's `require_permission`/
`require_org_match` dependency (app/api/deps.py, Module 3) has already
verified the caller may perform this action; re-checking here would be
duplicated business logic, not defense in depth (a service has no
independent way to learn who the caller is other than what the route
already resolved and passed in as `actor_user_id`).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.exceptions import ConflictError, NotFoundError
from app.db.enums import NurseryStatus
from app.domain_events import DomainEventPublisher, NurseryArchived, NurseryCreated, NurseryUpdated
from app.models.organization import Nursery
from app.models.platform import AuditLog, OrgSettings
from app.repositories.interfaces import AuditLogRepository, NurseryRepository
from app.services.validation import validate_currency_code, validate_hex_color, validate_timezone


class OrganizationService:
    def __init__(
        self,
        *,
        nursery_repo: NurseryRepository,
        audit_repo: AuditLogRepository,
        event_publisher: DomainEventPublisher,
    ) -> None:
        self._nurseries = nursery_repo
        self._audit = audit_repo
        self._events = event_publisher

    # ------------------------------------------------------------------
    # Nursery lifecycle
    # ------------------------------------------------------------------
    async def create_nursery(
        self,
        *,
        name: str,
        contact_email: str,
        actor_user_id: uuid.UUID,
        contact_phone: str | None = None,
        logo_url: str | None = None,
        request_id: str | None = None,
    ) -> Nursery:
        nursery = Nursery(
            name=name.strip(),
            contact_email=contact_email.strip().lower(),
            contact_phone=contact_phone,
            logo_url=logo_url,
            status=NurseryStatus.ACTIVE,
        )
        await self._nurseries.add(nursery)
        # Every Nursery gets exactly one OrgSettings row at creation time
        # (defaults: USD/UTC) -- callers never have to remember to
        # separately provision it, and `get_settings` can assume it always
        # exists rather than treating "no settings yet" as a valid state.
        await self._nurseries.create_settings(OrgSettings(nursery_id=nursery.id))

        await self._log_audit(
            nursery_id=nursery.id,
            actor_user_id=actor_user_id,
            action="nursery.created",
            entity_id=nursery.id,
            diff={"after": {"name": nursery.name, "contact_email": nursery.contact_email}},
            request_id=request_id,
        )
        await self._events.publish(
            NurseryCreated(
                aggregate_id=nursery.id,
                nursery_id=nursery.id,
                actor_user_id=actor_user_id,
                name=nursery.name,
                contact_email=nursery.contact_email,
            ),
            request_id=request_id,
        )
        return nursery

    async def get_nursery(self, nursery_id: uuid.UUID) -> Nursery:
        nursery = await self._nurseries.get_by_id(nursery_id)
        if nursery is None:
            raise NotFoundError("Nursery not found.")
        return nursery

    async def update_nursery(
        self,
        *,
        nursery_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        name: str | None = None,
        contact_email: str | None = None,
        contact_phone: str | None = None,
        logo_url: str | None = None,
        request_id: str | None = None,
    ) -> Nursery:
        nursery = await self.get_nursery(nursery_id)
        before = {
            "name": nursery.name,
            "contact_email": nursery.contact_email,
            "contact_phone": nursery.contact_phone,
            "logo_url": nursery.logo_url,
        }
        changed: list[str] = []

        if name is not None and name.strip() != nursery.name:
            nursery.name = name.strip()
            changed.append("name")
        if contact_email is not None and contact_email.strip().lower() != nursery.contact_email:
            nursery.contact_email = contact_email.strip().lower()
            changed.append("contact_email")
        if contact_phone is not None and contact_phone != nursery.contact_phone:
            nursery.contact_phone = contact_phone
            changed.append("contact_phone")
        if logo_url is not None and logo_url != nursery.logo_url:
            nursery.logo_url = logo_url
            changed.append("logo_url")

        if not changed:
            return nursery  # No-op update -- no audit/event noise for a request that changed nothing.

        after = {
            "name": nursery.name,
            "contact_email": nursery.contact_email,
            "contact_phone": nursery.contact_phone,
            "logo_url": nursery.logo_url,
        }
        await self._log_audit(
            nursery_id=nursery.id,
            actor_user_id=actor_user_id,
            action="nursery.updated",
            entity_id=nursery.id,
            diff={"before": before, "after": after},
            request_id=request_id,
        )
        await self._events.publish(
            NurseryUpdated(
                aggregate_id=nursery.id,
                nursery_id=nursery.id,
                actor_user_id=actor_user_id,
                changed_fields=tuple(changed),
            ),
            request_id=request_id,
        )
        return nursery

    async def archive_nursery(
        self, *, nursery_id: uuid.UUID, actor_user_id: uuid.UUID, request_id: str | None = None
    ) -> Nursery:
        nursery = await self.get_nursery(nursery_id)
        if nursery.status == NurseryStatus.ARCHIVED:
            raise ConflictError("This organization is already archived.")

        nursery.status = NurseryStatus.ARCHIVED
        await self._log_audit(
            nursery_id=nursery.id,
            actor_user_id=actor_user_id,
            action="nursery.archived",
            entity_id=nursery.id,
            diff={"before": {"status": "active"}, "after": {"status": "archived"}},
            request_id=request_id,
        )
        await self._events.publish(
            NurseryArchived(aggregate_id=nursery.id, nursery_id=nursery.id, actor_user_id=actor_user_id),
            request_id=request_id,
        )
        return nursery

    # ------------------------------------------------------------------
    # Settings: branding, currency, timezone
    # ------------------------------------------------------------------
    async def get_settings(self, nursery_id: uuid.UUID) -> OrgSettings:
        settings = await self._nurseries.get_settings(nursery_id)
        if settings is None:
            # Should be unreachable in practice (create_nursery always
            # provisions one) -- surfaced as 404 rather than a raw
            # AttributeError if it somehow isn't there (e.g. a row created
            # before this invariant existed).
            raise NotFoundError("Organization settings not found.")
        return settings

    async def update_settings(
        self,
        *,
        nursery_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        currency: str | None = None,
        timezone_name: str | None = None,
        branding_primary_color: str | None = None,
        email_sender_identity: str | None = None,
        sms_enabled: bool | None = None,
        request_id: str | None = None,
    ) -> OrgSettings:
        settings = await self.get_settings(nursery_id)
        before = {
            "default_currency": settings.default_currency,
            "default_timezone": settings.default_timezone,
            "branding_primary_color": settings.branding_primary_color,
            "email_sender_identity": settings.email_sender_identity,
            "sms_enabled": settings.sms_enabled,
        }
        changed: list[str] = []

        if currency is not None:
            new_currency = validate_currency_code(currency)
            if new_currency != settings.default_currency:
                settings.default_currency = new_currency
                changed.append("default_currency")
        if timezone_name is not None:
            new_tz = validate_timezone(timezone_name)
            if new_tz != settings.default_timezone:
                settings.default_timezone = new_tz
                changed.append("default_timezone")
        if branding_primary_color is not None:
            new_color = validate_hex_color(branding_primary_color)
            if new_color != settings.branding_primary_color:
                settings.branding_primary_color = new_color
                changed.append("branding_primary_color")
        if email_sender_identity is not None and email_sender_identity != settings.email_sender_identity:
            settings.email_sender_identity = email_sender_identity
            changed.append("email_sender_identity")
        if sms_enabled is not None and sms_enabled != settings.sms_enabled:
            settings.sms_enabled = sms_enabled
            changed.append("sms_enabled")

        if not changed:
            return settings

        after = {
            "default_currency": settings.default_currency,
            "default_timezone": settings.default_timezone,
            "branding_primary_color": settings.branding_primary_color,
            "email_sender_identity": settings.email_sender_identity,
            "sms_enabled": settings.sms_enabled,
        }
        await self._log_audit(
            nursery_id=nursery_id,
            actor_user_id=actor_user_id,
            action="nursery.settings_updated",
            entity_id=settings.id,
            diff={"before": before, "after": after},
            request_id=request_id,
        )
        await self._events.publish(
            NurseryUpdated(
                aggregate_id=nursery_id,
                nursery_id=nursery_id,
                actor_user_id=actor_user_id,
                changed_fields=tuple(f"settings.{f}" for f in changed),
            ),
            request_id=request_id,
        )
        return settings

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    async def _log_audit(
        self,
        *,
        nursery_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        action: str,
        entity_id: uuid.UUID,
        diff: dict,
        request_id: str | None,
    ) -> None:
        await self._audit.log(
            AuditLog(
                nursery_id=nursery_id,
                actor_user_id=actor_user_id,
                action=action,
                entity_type="Nursery",
                entity_id=entity_id,
                diff=diff,
                request_id=request_id,
                created_at=datetime.now(timezone.utc),
            )
        )
