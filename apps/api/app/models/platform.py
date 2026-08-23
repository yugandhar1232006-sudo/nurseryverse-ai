"""
Platform bounded context: AuditLog (immutable, FR-19), OrgSettings,
Subscription, UsageCounter (billing/plan, FR-20 / BRD §5).

Maps to docs/architecture/02-low-level-design.md "Module: Audit Log" and
"Module: Settings".
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Enum as PgEnum
from sqlalchemy import Boolean, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPKMixin
from app.db.enums import SubscriptionPlan, SubscriptionStatus


class AuditLog(UUIDPKMixin, Base):
    """
    FR-19. Immutable at the database-grant level (see migration
    0004_audit_immutability.py, which REVOKEs UPDATE/DELETE on this table
    from the application role entirely — FR-19.3 enforced below the
    application layer, not just by omitting an endpoint).
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_nursery_created_at", "nursery_id", "created_at"),
        Index("ix_audit_logs_actor_id", "actor_user_id"),
    )

    nursery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nurseries.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "plant.status_changed"
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    diff: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {before: {...}, after: {...}}
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)

    # --- Added by Phase 6 Module 13 (Administration & System Management) ---
    # Section 12's "every sensitive operation must record: Actor,
    # Organization, Branch, Action, Target, Timestamp, Request ID, Result"
    # is otherwise fully satisfied by this table's existing columns
    # (nursery_id=Organization, actor_user_id=Actor, action=Action,
    # entity_id=Target, created_at=Timestamp, request_id=Request ID) --
    # `branch_id`/`result` are the two genuinely missing fields, added here
    # rather than as a parallel "admin_actions" table so every existing
    # writer (Organization/Branch/Employee/Inventory/... services'
    # `_log_audit` helpers) and this module's new admin services share the
    # exact same immutable trail (REVOKE UPDATE/DELETE, migration 0004)
    # instead of splitting "business audit" from "admin audit" into two
    # tables a security review would have to cross-reference. Both are
    # nullable with a safe default so every pre-existing `_log_audit` call
    # site across Modules 4-12 continues to compile and insert unchanged
    # (`branch_id=NULL` = "not a branch-scoped action", `result="success"`
    # = the only outcome every pre-Module-13 writer ever actually logs --
    # none of them had a failure path that still reached `_log_audit`).
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    result: Mapped[str] = mapped_column(String(20), nullable=False, default="success", server_default="success")


class OrgSettings(UUIDPKMixin, TenantMixin, Base):
    """FR-20.1/20.3. One row per Org."""

    __tablename__ = "org_settings"
    __table_args__ = (UniqueConstraint("nursery_id", name="uq_org_settings_nursery"),)

    sms_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sms_provider_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    email_sender_identity: Mapped[str | None] = mapped_column(String(255), nullable=True)
    branding_primary_color: Mapped[str | None] = mapped_column(String(7), nullable=True)

    # Added by Phase 6 Module 4 (Nursery & Organization Management)'s
    # "Currency"/"Timezone" org-settings requirement. Homed here rather
    # than on `Nursery` itself, consistent with this table's existing role
    # as the one-row-per-org settings bag (branding, SMS, email identity)
    # — `Nursery` stays the tenant-identity/lifecycle record, `OrgSettings`
    # stays the mutable-preferences record, and nothing here needed a new
    # table the way `status` (a lifecycle concern) needed to live on
    # `Nursery` directly.
    default_currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="INR", server_default="INR"
    )  # ISO 4217
    default_timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="UTC", server_default="UTC"
    )  # IANA tz name


class Subscription(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """BRD §5 pricing model. One row per Org."""

    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("nursery_id", name="uq_subscriptions_nursery"),)

    plan: Mapped[SubscriptionPlan] = mapped_column(
        PgEnum(SubscriptionPlan, name="subscription_plan"),
        nullable=False,
        default=SubscriptionPlan.STARTER,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        PgEnum(SubscriptionStatus, name="subscription_status"),
        nullable=False,
        default=SubscriptionStatus.ACTIVE,
    )
    branch_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    seat_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)  # null = unlimited
    ai_credit_monthly_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(nullable=True)


class FeatureFlag(UUIDPKMixin, Base):
    """
    Added by Phase 6 Module 13 (Administration & System Management,
    "Feature Flags"). Three-tier scope in ONE table, distinguished by which
    of `nursery_id`/`branch_id` are set, mirroring `NotificationTemplate`'s
    already-established three-tier org-override/global-default resolution
    (Module 11) rather than inventing a new pattern:

        nursery_id IS NULL, branch_id IS NULL  -> platform-wide default
        nursery_id = X,     branch_id IS NULL  -> org-level override for X
        nursery_id = X,     branch_id = Y      -> branch-level override for Y (must belong to X)

    Resolution (`FeatureFlagService.is_enabled`) checks branch -> org ->
    platform-default -> hardcoded `False` in that order, so a KEY WITH NO
    ROW AT ALL resolves to disabled rather than raising -- "feature flags
    must fail safely" (Module 13's own requirement) is a property of the
    resolution algorithm, not something every call site has to remember to
    check for itself.

    No FK to `nurseries`/`branches` uses `ondelete="RESTRICT"` here (unlike
    most tenant-scoped tables) -- deliberately `CASCADE`: a flag override
    for an org/branch that no longer exists is meaningless clutter, not
    data worth blocking a deletion over.

    Deliberately NOT RLS-protected (same reasoning as `notification_templates`,
    Module 11's own docstring): a platform-wide default row (`nursery_id
    IS NULL`) must be readable by every tenant's resolution query, which
    RLS's per-session `app.current_org_id` filter cannot express alongside
    "and also see this org's own override" in one policy without a second,
    more complex policy shape no other table in this schema needed yet.
    Tenant isolation for an org-scoped override row is enforced at the
    application/query layer instead (`FeatureFlagRepository` always filters
    `nursery_id = :caller_org OR nursery_id IS NULL` explicitly, mirroring
    `KnowledgeBaseChunk`'s identical `org_data OR knowledge_article` split).
    """

    __tablename__ = "feature_flags"
    __table_args__ = (
        UniqueConstraint("key", "nursery_id", "branch_id", name="uq_feature_flags_key_nursery_branch"),
    )

    key: Mapped[str] = mapped_column(String(100), nullable=False)
    nursery_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nurseries.id", ondelete="CASCADE"), nullable=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=True
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)


class SystemConfig(UUIDPKMixin, Base):
    """
    Added by Phase 6 Module 13 ("System Configuration"). Platform-wide,
    non-tenant-scoped, non-secret operational settings only -- application/
    feature/notification/AI/report configuration a platform admin can
    safely tune at runtime (e.g. a default report-retention window, an AI
    Assistant response-length cap, a notification digest hour) without a
    deploy. `SystemConfigRepository`/`SystemConfigService` never accept a
    `category="secret"` or any credential-shaped value -- there is
    deliberately no `is_secret`/`is_encrypted` column offering a false
    sense of safety for a "secret" stored here anyway: real secrets
    (`ANTHROPIC_API_KEY`, `SMTP_*`, `CLOUDINARY_*`, database credentials,
    ...) live ONLY in `app/core/config.py`'s `Settings` (environment
    variables / the deployment platform's secret manager), are never read
    from or written to this table, and this module's AI/health admin
    routes only ever expose a boolean "configured: true/false" for any of
    them (see `AIAdminService`/`HealthCheckService`) -- never the value.

    RLS-exempt for the same reason `notification_templates`/`feature_flags`
    (this file) are: system-metadata, not per-tenant business data.
    """

    __tablename__ = "system_config"
    __table_args__ = (UniqueConstraint("key", name="uq_system_config_key"),)

    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)  # always {"value": <the actual scalar/object>} -- see schema layer
    value_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "bool" | "int" | "str" | "json"
    category: Mapped[str] = mapped_column(String(30), nullable=False)  # "application" | "feature" | "notification" | "ai" | "report"
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)


class UsageCounter(UUIDPKMixin, TenantMixin, Base):
    """
    Rolling usage against plan limits (branches, seats, AI credits) — read
    by BillingService.change_plan() to block a downgrade that would exceed
    the target plan's limits (docs/architecture/02-low-level-design.md
    "Module: Settings").
    """

    __tablename__ = "usage_counters"
    __table_args__ = (
        UniqueConstraint("nursery_id", "metric", "period_start", name="uq_usage_counters_nursery_metric_period"),
    )

    metric: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "ai_inference_calls"
    period_start: Mapped[datetime] = mapped_column(nullable=False)
    period_end: Mapped[datetime] = mapped_column(nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
