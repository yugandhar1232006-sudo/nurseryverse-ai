"""Notifications & Communication (Phase 6 Module 11).

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-07

Evolves the Phase 5 `notifications`/`notification_preferences` skeleton
(both already present since migration 0001, both already RLS-covered since
migration 0003 -- `notifications` as a DIRECT_TENANT_TABLES entry,
`notification_preferences` via its own user->role_assignment join policy)
into the bounded context Module 11's spec requires -- the same "first
module to actually build on a pre-existing table" pattern every prior
module in this phase has followed. See app/models/notifications.py's
module/class docstrings and docs/architecture/27-module11-notifications.md
for the full design reasoning.

Three moves:
  1. `notification_preferences` gains four columns this module's own spec
     calls for ("quiet hours", "frequency controls") that the Phase 5
     skeleton has nowhere to record: `quiet_hours_start`, `quiet_hours_end`,
     `quiet_hours_timezone` (all nullable -- most rows opt out of quiet
     hours entirely), `frequency` (not null, defaults to `immediate`).
     No RLS change needed: the existing join-based policy on this table
     already covers the full row regardless of which columns exist on it.
  2. New `notification_templates` table (versioned, multi-channel/format,
     nullable `nursery_id` for global-default vs. org-override rows -- see
     the model's own docstring for why this table is deliberately
     RLS-exempt rather than policy-covered, the same `plant_categories`/
     `knowledge_base_chunks` precedent).
  3. New `notification_deliveries` table (retry/DLQ/tracking/failure-log/
     status folded into one table rather than five, per the model's own
     docstring). RLS: join-scoped through `notifications.nursery_id`,
     the exact one-hop JOIN_TENANT_TABLES shape migration 0003 already
     uses for `ai_assistant_messages` -> `ai_assistant_conversations`.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

SESSION_VAR = "app.current_org_id"


def _enable_and_force(table: str) -> str:
    return (
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;\n"
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;"
    )


def _join_tenant_policy(table: str, fk_col: str, parent: str) -> str:
    return f"""
    CREATE POLICY tenant_isolation_{table} ON {table}
    USING (
        {fk_col} IN (
            SELECT id FROM {parent}
            WHERE nursery_id = current_setting('{SESSION_VAR}', true)::uuid
        )
    )
    WITH CHECK (
        {fk_col} IN (
            SELECT id FROM {parent}
            WHERE nursery_id = current_setting('{SESSION_VAR}', true)::uuid
        )
    );
    """


def upgrade() -> None:
    # --- new enums ---
    delivery_status = sa.Enum(
        "PENDING", "SENT", "FAILED", "DEAD_LETTER", name="notification_delivery_status"
    )
    delivery_status.create(op.get_bind(), checkfirst=True)

    frequency = sa.Enum(
        "IMMEDIATE", "DAILY_DIGEST", "WEEKLY_DIGEST", name="notification_frequency"
    )
    frequency.create(op.get_bind(), checkfirst=True)

    # NOTE: SQLAlchemy's `Enum(SomePythonEnum)` (no `values_callable`
    # override anywhere in this codebase) serializes a Python enum member
    # to its *member name* on the wire, not its `.value` — confirmed via
    # `sa.Enum(NotificationChannel, name="notification_channel").enums`,
    # which returns `['IN_APP', 'EMAIL', 'SMS', 'PUSH']`, not the lowercase
    # `.value` strings. Every `ADD VALUE` below must therefore add the
    # uppercase member *name* Postgres will actually be asked to store
    # (matching migration 0012's own correct `ADD VALUE IF NOT EXISTS
    # 'RETURN'` precedent), not the lowercase `.value` — an earlier
    # version of this migration added the lowercase values instead, which
    # would have silently broken every real-Postgres write of any of
    # these 14 new enum members the moment Module 11 shipped (never
    # caught by this sandbox's test suite, since it runs entirely against
    # in-memory Fakes, never a real Postgres enum column) until Module 12
    # discovered it while extending this same enum further. Fixed here.
    op.execute("ALTER TYPE notification_channel ADD VALUE IF NOT EXISTS 'PUSH'")
    for category in (
        "PASSWORD_RESET",
        "EMAIL_VERIFICATION",
        "PLANT_REGISTERED",
        "PLANT_READY_FOR_SALE",
        "PLANT_UNDER_TREATMENT",
        "PLANT_SOLD",
        "RESERVATION_CREATED",
        "RESERVATION_EXPIRING",
        "INVOICE_GENERATED",
        "PAYMENT_RECEIVED",
        "INVENTORY_TRANSFER",
        "SYSTEM_ALERT",
        "AI_RECOMMENDATION_READY",
    ):
        op.execute(f"ALTER TYPE notification_category ADD VALUE IF NOT EXISTS '{category}'")

    # --- notification_preferences: quiet hours + frequency ---
    op.add_column("notification_preferences", sa.Column("quiet_hours_start", sa.Time(), nullable=True))
    op.add_column("notification_preferences", sa.Column("quiet_hours_end", sa.Time(), nullable=True))
    op.add_column(
        "notification_preferences", sa.Column("quiet_hours_timezone", sa.String(length=50), nullable=True)
    )
    op.add_column(
        "notification_preferences",
        sa.Column("frequency", frequency, server_default="IMMEDIATE", nullable=False),
    )

    # --- notification_templates ---
    op.create_table(
        "notification_templates",
        sa.Column("nursery_id", sa.UUID(), nullable=True),
        sa.Column("category", sa.Enum(name="notification_category"), nullable=False),
        sa.Column("channel", sa.Enum(name="notification_channel"), nullable=False),
        sa.Column("format", sa.String(length=20), server_default="text", nullable=False),
        sa.Column("locale", sa.String(length=10), server_default="en", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("subject_template", sa.String(length=500), nullable=True),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["nursery_id"], ["nurseries.id"], name=op.f("fk_notification_templates_nursery_id_nurseries"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_templates")),
        sa.UniqueConstraint(
            "nursery_id", "category", "channel", "format", "locale", "version",
            name="uq_notification_templates_org_variant_version",
        ),
    )
    op.create_index(
        "ix_notification_templates_lookup",
        "notification_templates",
        ["nursery_id", "category", "channel", "format", "locale", "is_active"],
        unique=False,
    )

    # --- notification_deliveries ---
    op.create_table(
        "notification_deliveries",
        sa.Column("notification_id", sa.UUID(), nullable=False),
        sa.Column("channel", sa.Enum(name="notification_channel"), nullable=False),
        sa.Column("status", delivery_status, server_default="PENDING", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("last_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["notification_id"], ["notifications.id"],
            name=op.f("fk_notification_deliveries_notification_id_notifications"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_deliveries")),
    )
    op.create_index(
        "ix_notification_deliveries_notification_channel",
        "notification_deliveries", ["notification_id", "channel"], unique=False,
    )
    op.create_index(
        "ix_notification_deliveries_status_retry",
        "notification_deliveries", ["status", "next_retry_at"], unique=False,
    )

    # --- RLS: notification_deliveries is join-scoped through notifications.
    # notification_templates is deliberately RLS-exempt (see module
    # docstring) -- app-layer-filtered like plant_categories/knowledge_base_chunks.
    op.execute(_enable_and_force("notification_deliveries"))
    op.execute(_join_tenant_policy("notification_deliveries", "notification_id", "notifications"))


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_notification_deliveries ON notification_deliveries;")

    op.drop_index("ix_notification_deliveries_status_retry", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_notification_channel", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")

    op.drop_index("ix_notification_templates_lookup", table_name="notification_templates")
    op.drop_table("notification_templates")

    op.drop_column("notification_preferences", "frequency")
    op.drop_column("notification_preferences", "quiet_hours_timezone")
    op.drop_column("notification_preferences", "quiet_hours_end")
    op.drop_column("notification_preferences", "quiet_hours_start")

    sa.Enum(name="notification_frequency").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="notification_delivery_status").drop(op.get_bind(), checkfirst=True)
    # Note: 'push' value added to notification_channel and the 13 new
    # notification_category values are not removed on downgrade --
    # PostgreSQL does not support ALTER TYPE ... DROP VALUE, the same
    # documented limitation every prior ADD VALUE migration in this
    # project accepts (see migration 0012's own downgrade note).
