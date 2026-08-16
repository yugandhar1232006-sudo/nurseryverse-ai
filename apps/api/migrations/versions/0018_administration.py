"""Administration & System Management (Phase 6 Module 13).

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-13

Five moves, each additive on top of the existing schema per this
project's "extend, never rewrite a shipped migration" rule:

  1. New permission codes (`feature_flags:read`/`feature_flags:manage`,
     `admin:read`/`admin:manage`), seeded the exact same mechanical way
     migration 0002 seeded the full permission matrix -- granted to
     owner/org_admin (feature flags, org/branch scoped) and to
     `platform_admin` (admin:*, the internal cross-tenant role migration
     0002 already created but never granted a single permission to until
     now). No permission is hardcoded anywhere in application code; this
     migration is the one place any of them come from.
  2. `feature_flags` table -- three-tier (platform/org/branch) scope in
     one table, RLS-exempt (mirrors `notification_templates`), see the
     model's own docstring for the full resolution-order rationale.
  3. `system_config` table -- platform-wide, non-secret operational
     settings only. RLS-exempt for the same reason.
  4. `ai_inference_failures` table -- the failure-path counterpart to the
     existing `ai_predictions` success-path table (RLS-protected, same as
     `ai_predictions`, since it IS tenant business data -- which AI calls
     an org's own operations triggered and failed).
  5. Two additive column sets: `audit_logs.branch_id`/`audit_logs.result`
     (Section 12's "every sensitive operation must record Branch/Result",
     the two fields this table didn't already carry) and
     `ai_predictions.latency_ms` (Section 10's "inference latency").
     `security_event_type` gains two new enum values
     (`account_activated_by_admin`/`account_deactivated_by_admin`) for the
     two account-lifecycle states with no existing self-service
     equivalent to reuse (every other admin action reuses an existing
     `SecurityEventType` value with `event_metadata` distinguishing "an
     admin did this" -- see that enum's own updated docstring).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

SESSION_VAR = "app.current_org_id"

# --- Existing role ids from migration 0002 (reused, never re-declared there) ---
OWNER_ROLE_ID = "78aa029b-5b4c-4567-9151-c0e7a557aa60"
ORG_ADMIN_ROLE_ID = "e02a98c2-cecf-4e91-9ba0-a3a0959fda5f"
BRANCH_MANAGER_ROLE_ID = "bf81d3f8-e8d5-423f-b1f5-b760df60ba4e"
PLATFORM_ADMIN_ROLE_ID = "2756c55e-3bc4-4cee-941f-4d23bae473a5"

# --- New permission ids, this migration's own ---
PERM_FEATURE_FLAGS_READ = "43da8f48-a6ad-4103-a642-f1474b39f02d"
PERM_FEATURE_FLAGS_MANAGE = "76f74047-f87a-4f2f-88e4-f9d2ff14fa0d"
PERM_ADMIN_READ = "08d465ea-0ef0-4d23-9592-bb40fbed7682"
PERM_ADMIN_MANAGE = "9605f6e8-402b-4bdb-840c-1a2276c95448"

permissions_table = sa.table(
    "permissions",
    sa.column("id", sa.UUID()),
    sa.column("code", sa.String()),
    sa.column("module", sa.String()),
    sa.column("action", sa.String()),
    sa.column("description", sa.String()),
)

role_permissions_table = sa.table(
    "role_permissions",
    sa.column("role_id", sa.UUID()),
    sa.column("permission_id", sa.UUID()),
    sa.column("scope", sa.String()),
)


def _enable_and_force(table: str) -> str:
    return (
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;\n"
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;"
    )


def upgrade() -> None:
    # --- 1. New permission codes + grants ---
    op.bulk_insert(
        permissions_table,
        [
            {
                "id": PERM_FEATURE_FLAGS_READ, "code": "feature_flags:read", "module": "feature_flags",
                "action": "read", "description": "Read access for the feature flags module",
            },
            {
                "id": PERM_FEATURE_FLAGS_MANAGE, "code": "feature_flags:manage", "module": "feature_flags",
                "action": "manage", "description": "Manage access for the feature flags module",
            },
            {
                "id": PERM_ADMIN_READ, "code": "admin:read", "module": "admin",
                "action": "read", "description": "Platform-wide read access for system administration",
            },
            {
                "id": PERM_ADMIN_MANAGE, "code": "admin:manage", "module": "admin",
                "action": "manage", "description": "Platform-wide manage access for system administration",
            },
        ],
    )
    op.bulk_insert(
        role_permissions_table,
        [
            {"role_id": OWNER_ROLE_ID, "permission_id": PERM_FEATURE_FLAGS_READ, "scope": "F"},
            {"role_id": ORG_ADMIN_ROLE_ID, "permission_id": PERM_FEATURE_FLAGS_READ, "scope": "F"},
            {"role_id": BRANCH_MANAGER_ROLE_ID, "permission_id": PERM_FEATURE_FLAGS_READ, "scope": "B"},
            {"role_id": OWNER_ROLE_ID, "permission_id": PERM_FEATURE_FLAGS_MANAGE, "scope": "F"},
            {"role_id": ORG_ADMIN_ROLE_ID, "permission_id": PERM_FEATURE_FLAGS_MANAGE, "scope": "F"},
            {"role_id": PLATFORM_ADMIN_ROLE_ID, "permission_id": PERM_ADMIN_READ, "scope": "F"},
            {"role_id": PLATFORM_ADMIN_ROLE_ID, "permission_id": PERM_ADMIN_MANAGE, "scope": "F"},
        ],
    )

    # --- security_event_type: two new values (see module docstring) ---
    op.execute("ALTER TYPE security_event_type ADD VALUE IF NOT EXISTS 'account_activated_by_admin'")
    op.execute("ALTER TYPE security_event_type ADD VALUE IF NOT EXISTS 'account_deactivated_by_admin'")

    # --- 2. feature_flags ---
    op.create_table(
        "feature_flags",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("nursery_id", UUID(as_uuid=True), sa.ForeignKey("nurseries.id", ondelete="CASCADE"), nullable=True),
        sa.Column("branch_id", UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("updated_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("key", "nursery_id", "branch_id", name="uq_feature_flags_key_nursery_branch"),
    )
    op.create_index("ix_feature_flags_key", "feature_flags", ["key"])

    # --- 3. system_config ---
    op.create_table(
        "system_config",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("value_type", sa.String(length=20), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("updated_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("key", name="uq_system_config_key"),
    )
    op.create_index("ix_system_config_category", "system_config", ["category"])

    # --- 4. ai_inference_failures (tenant-scoped -- RLS, same as ai_predictions) ---
    op.create_table(
        "ai_inference_failures",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("nursery_id", UUID(as_uuid=True), sa.ForeignKey("nurseries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=True),
        sa.Column("capability", sa.String(length=50), nullable=False),
        sa.Column("prediction_type", sa.String(length=50), nullable=False),
        sa.Column("error_type", sa.String(length=200), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_ai_inference_failures_nursery_created", "ai_inference_failures", ["nursery_id", "created_at"])
    op.execute(_enable_and_force("ai_inference_failures"))
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_ai_inference_failures ON ai_inference_failures
        USING (nursery_id = current_setting('{SESSION_VAR}', true)::uuid)
        WITH CHECK (nursery_id = current_setting('{SESSION_VAR}', true)::uuid);
        """
    )

    # --- 5. Additive columns ---
    op.add_column(
        "audit_logs",
        sa.Column("branch_id", UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "audit_logs",
        sa.Column("result", sa.String(length=20), nullable=False, server_default="success"),
    )
    op.add_column("ai_predictions", sa.Column("latency_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_predictions", "latency_ms")
    op.drop_column("audit_logs", "result")
    op.drop_column("audit_logs", "branch_id")

    op.execute("DROP POLICY IF EXISTS tenant_isolation_ai_inference_failures ON ai_inference_failures;")
    op.drop_index("ix_ai_inference_failures_nursery_created", table_name="ai_inference_failures")
    op.drop_table("ai_inference_failures")

    op.drop_index("ix_system_config_category", table_name="system_config")
    op.drop_table("system_config")

    op.drop_index("ix_feature_flags_key", table_name="feature_flags")
    op.drop_table("feature_flags")

    # PostgreSQL does not support ALTER TYPE ... DROP VALUE -- the two new
    # security_event_type values are not removed on downgrade, the same
    # documented limitation every prior ADD VALUE migration in this
    # project accepts.

    op.execute(
        f"DELETE FROM role_permissions WHERE permission_id IN "
        f"('{PERM_FEATURE_FLAGS_READ}', '{PERM_FEATURE_FLAGS_MANAGE}', '{PERM_ADMIN_READ}', '{PERM_ADMIN_MANAGE}');"
    )
    op.execute(
        f"DELETE FROM permissions WHERE id IN "
        f"('{PERM_FEATURE_FLAGS_READ}', '{PERM_FEATURE_FLAGS_MANAGE}', '{PERM_ADMIN_READ}', '{PERM_ADMIN_MANAGE}');"
    )
