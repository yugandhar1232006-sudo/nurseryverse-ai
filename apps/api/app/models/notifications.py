"""
Notifications bounded context.

Maps to docs/architecture/02-low-level-design.md "Module: Notifications"
and docs/ux/14-notification-workflow.md's Trigger Catalog / recipient
resolution rules. `Notification`/`NotificationPreference` are the Phase 5
skeleton (already present since migration 0001, already RLS-covered since
migration 0003) -- Phase 6 Module 11 is the first module to actually build
on them (the same "first module to build on a pre-existing table" pattern
Module 5 applied to species/categories, Module 9 to customers/sales, etc.),
adding `NotificationTemplate`/`NotificationDelivery` and four new columns
on `NotificationPreference` (migration 0016). See
docs/architecture/27-module11-notifications.md for the full design.
"""
from __future__ import annotations

import uuid
from datetime import datetime, time

from sqlalchemy import Enum as PgEnum
from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.enums import (
    NotificationCategory,
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationFrequency,
)


class Notification(UUIDPKMixin, Base):
    """FR-17.1. In-app record always created first, regardless of channel preferences."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_recipient_read", "recipient_user_id", "read_at"),
    )

    nursery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nurseries.id", ondelete="CASCADE"), nullable=False
    )
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[NotificationCategory] = mapped_column(
        PgEnum(NotificationCategory, name="notification_category"), nullable=False
    )
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    deep_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)

    deliveries: Mapped[list["NotificationDelivery"]] = relationship(
        back_populates="notification", cascade="all, delete-orphan"
    )


class NotificationPreference(Base):
    """
    FR-17.4. One row per (user, category, channel). `quiet_hours_*`/
    `frequency` (added by migration 0016, Phase 6 Module 11) apply per-row
    -- a user can, for example, want immediate SMS for Disease Confirmed
    but only a daily digest of Low Stock emails. `frequency` is honored by
    suppressing immediate dispatch for non-`IMMEDIATE` rows (the actual
    digest-compilation-and-send job is a disclosed on-demand-only capability,
    same as `NotificationService.check_expiring_reservations` -- see that
    method's own docstring and docs/architecture/27-module11-notifications.md
    for why: no Celery/scheduled-job infrastructure exists anywhere in this
    codebase through Module 10).
    """

    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "category", "channel", name="uq_notification_preferences_user_cat_channel"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default="gen_random_uuid()"
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[NotificationCategory] = mapped_column(
        PgEnum(NotificationCategory, name="notification_category"), nullable=False
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        PgEnum(NotificationChannel, name="notification_channel"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # --- Added by migration 0016 (Phase 6 Module 11) ---
    quiet_hours_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    quiet_hours_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    quiet_hours_timezone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    frequency: Mapped[NotificationFrequency] = mapped_column(
        PgEnum(NotificationFrequency, name="notification_frequency"),
        nullable=False,
        default=NotificationFrequency.IMMEDIATE,
    )


class NotificationTemplate(UUIDPKMixin, TimestampMixin, Base):
    """
    Added by migration 0016 (Phase 6 Module 11). Versioned, multi-channel
    templates rendered by `app/notifications/templates.py`'s `TemplateService`
    (real Jinja2 rendering, not string concatenation). `nursery_id IS NULL`
    rows are the platform's own default templates (shipped for every
    category/channel combination this module supports); `nursery_id` set is
    an org's own override, resolved preferentially over the global default
    -- the identical "global row + org override, org wins" precedent
    `knowledge_base_chunks` (Module 10) already established for shared vs.
    tenant-specific content, though for a different reason there (RLS
    exemption vs. here, template resolution precedence).

    `format` only varies for `channel="email"` (`"html"` vs `"text"` --
    the module's own "HTML Email, Plain Text Email" requirement); every
    other channel has exactly one format ("text") and the column is
    present for uniform lookup keying rather than a channel-conditional
    schema. `locale` defaults to `"en"` -- the one column this table adds
    purely so a future localization pass has somewhere to write without a
    schema change, per this module's own "must support localization in
    the future" requirement; no non-English template is seeded in this
    version.

    RLS: same "global rows readable to every tenant, org rows scoped to
    their own tenant" shape `plant_categories`/`units`/`knowledge_base_chunks`
    already require, which a single equality-based RLS policy cannot cleanly
    express for a nullable `nursery_id` column (identical reasoning
    `roles`/`permissions`/`role_permissions` documented in migration 0003) --
    this table is therefore deliberately RLS-exempt; org-scoped visibility
    is enforced at the application layer (`TemplateService` always filters
    `nursery_id = :current_org OR nursery_id IS NULL` explicitly).
    """

    __tablename__ = "notification_templates"
    __table_args__ = (
        UniqueConstraint(
            "nursery_id", "category", "channel", "format", "locale", "version",
            name="uq_notification_templates_org_variant_version",
        ),
        Index(
            "ix_notification_templates_lookup", "nursery_id", "category", "channel", "format", "locale", "is_active"
        ),
    )

    nursery_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nurseries.id", ondelete="CASCADE"), nullable=True
    )
    category: Mapped[NotificationCategory] = mapped_column(
        PgEnum(NotificationCategory, name="notification_category"), nullable=False
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        PgEnum(NotificationChannel, name="notification_channel"), nullable=False
    )
    format: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    subject_template: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class NotificationDelivery(UUIDPKMixin, TimestampMixin, Base):
    """
    Added by migration 0016 (Phase 6 Module 11). One row per (notification,
    channel) delivery attempt -- the module's required "retry policy",
    "dead-letter queue strategy", "delivery tracking", "failure logging",
    and "delivery status" all live in this single table rather than five
    separate ones: a DLQ is a `status="dead_letter"` row, retry state is
    `attempt_count`/`next_retry_at`, failure logging is `error_message`,
    delivery status is just `status` itself -- all queryable/reprocessable
    through the same rows, not a parallel bookkeeping structure.
    """

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        Index("ix_notification_deliveries_notification_channel", "notification_id", "channel"),
        Index("ix_notification_deliveries_status_retry", "status", "next_retry_at"),
    )

    notification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        PgEnum(NotificationChannel, name="notification_channel"), nullable=False
    )
    status: Mapped[NotificationDeliveryStatus] = mapped_column(
        PgEnum(NotificationDeliveryStatus, name="notification_delivery_status"),
        nullable=False,
        default=NotificationDeliveryStatus.PENDING,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_attempted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    notification: Mapped["Notification"] = relationship(back_populates="deliveries")
