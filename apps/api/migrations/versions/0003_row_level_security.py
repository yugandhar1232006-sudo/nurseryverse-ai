"""Row-Level Security policies — defense-in-depth tenant isolation.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-05

Implements docs/architecture/05-database-architecture.md §9's "two
enforcement layers" guarantee: even if the application-layer tenant
scoping middleware (docs/architecture/03-backend-architecture.md §8) had a
bug and forgot to filter a query by org, PostgreSQL itself blocks
cross-tenant reads/writes here. The API's runtime database role executes
every request-scoped query with `app.current_org_id` set via
`SET LOCAL` (done by the middleware at the start of each request); RLS
policies below key off that session variable.

Two policy shapes are used:
  1. Direct — the table has its own nursery_id column (most tables).
  2. Join-based — child/history tables with no nursery_id of their own
     (plant_images, growth_timeline, disease_reports, sale_items, etc.)
     are scoped through a subquery to their parent, exactly as flagged in
     the relevant model docstrings (e.g. app/models/plants.py's
     PlantImage).

Deliberately EXEMPT from RLS, documented here rather than left as a silent
gap:
  - `users` — authentication (login-by-email) happens before any org
    context exists; a user is not itself tenant-scoped (their org
    affiliation is via role_assignments). Login queries are inherently
    cross-tenant lookups by unique email, which is safe without an RLS
    filter.
  - `invites` — looked up by a unique, unguessable token during
    invite-accept, before the accepting user has an established session/
    org context. Token uniqueness is the access control here, not RLS.
  - `passports` — the public tokenized read path
    (GET /passport/public/{token}, docs/ux/15-plant-passport-workflow.md)
    is intentionally unauthenticated and has no org context at all;
    access control is the signed, time-scoped token itself. Internal
    (authenticated) passport reads still go through the normal
    tenant-scoping middleware at the application layer even though the
    table has no RLS policy.
  - `roles`, `permissions`, `role_permissions` — system roles/permissions
    (nursery_id IS NULL) must be visible to every tenant; custom roles'
    org-scoping is enforced at the application layer (RoleManagementService)
    rather than RLS, since a single blanket policy can't cleanly express
    "NULL nursery_id rows are global, non-NULL rows are tenant-scoped" as
    a simple equality check without a NULL-handling branch that would
    undermine the defense-in-depth argument for using RLS here in the
    first place — application enforcement plus this documented exception
    is the honest tradeoff.
  - `plant_categories`, `units` — global reference data, not tenant data.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# Tables with a direct nursery_id column — straightforward equality policy.
DIRECT_TENANT_TABLES = [
    "branches",
    "employees",
    "role_assignments",
    "species",
    "plant_varieties",
    "plants",
    "inventory",
    "customers",
    "sales",
    "invoices",
    "suppliers",
    "purchase_orders",
    "reports",
    "org_settings",
    "subscriptions",
    "usage_counters",
    "attachments",
    "ai_predictions",
    "ai_recommendations",
    "ai_assistant_conversations",
    "audit_logs",
    "notifications",
    "plant_transfers",
]

# (table, fk_column, parent_table) — one-hop join-based policies.
JOIN_TENANT_TABLES = [
    ("plant_images", "plant_id", "plants"),
    ("growth_timeline", "plant_id", "plants"),
    ("health_history", "plant_id", "plants"),
    ("disease_reports", "plant_id", "plants"),
    ("environmental_readings", "branch_id", "branches"),
    ("watering_logs", "branch_id", "branches"),
    ("fertilizer_logs", "branch_id", "branches"),
    ("sale_items", "sale_id", "sales"),
    ("invoice_items", "invoice_id", "invoices"),
    ("payments", "invoice_id", "invoices"),
    ("purchase_order_items", "purchase_order_id", "purchase_orders"),
    ("inventory_adjustments", "inventory_id", "inventory"),
    ("ai_assistant_messages", "conversation_id", "ai_assistant_conversations"),
]

# Two-hop join (child of a join-scoped table): treatments -> disease_reports -> plants.
TWO_HOP_TENANT_TABLES = [
    ("treatments", "disease_report_id", "disease_reports", "id"),
]

SESSION_VAR = "app.current_org_id"


def _enable_and_force(table: str) -> str:
    return (
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;\n"
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;"
    )


def upgrade() -> None:
    for table in DIRECT_TENANT_TABLES:
        op.execute(_enable_and_force(table))
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            USING (nursery_id = current_setting('{SESSION_VAR}', true)::uuid)
            WITH CHECK (nursery_id = current_setting('{SESSION_VAR}', true)::uuid);
            """
        )

    for table, fk_col, parent in JOIN_TENANT_TABLES:
        op.execute(_enable_and_force(table))
        op.execute(
            f"""
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
        )

    for table, fk_col, parent, parent_pk in TWO_HOP_TENANT_TABLES:
        op.execute(_enable_and_force(table))
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            USING (
                {fk_col} IN (
                    SELECT dr.{parent_pk} FROM {parent} dr
                    JOIN plants p ON p.id = dr.plant_id
                    WHERE p.nursery_id = current_setting('{SESSION_VAR}', true)::uuid
                )
            )
            WITH CHECK (
                {fk_col} IN (
                    SELECT dr.{parent_pk} FROM {parent} dr
                    JOIN plants p ON p.id = dr.plant_id
                    WHERE p.nursery_id = current_setting('{SESSION_VAR}', true)::uuid
                )
            );
            """
        )

    # role_assignment_branch_scopes and invoice_sales: narrow join-based
    # policies through their single owning parent (role_assignments,
    # invoices respectively) — same one-hop shape as JOIN_TENANT_TABLES,
    # listed separately since their FK column name differs.
    op.execute(_enable_and_force("role_assignment_branch_scopes"))
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_role_assignment_branch_scopes
        ON role_assignment_branch_scopes
        USING (
            role_assignment_id IN (
                SELECT id FROM role_assignments
                WHERE nursery_id = current_setting('{SESSION_VAR}', true)::uuid
            )
        )
        WITH CHECK (
            role_assignment_id IN (
                SELECT id FROM role_assignments
                WHERE nursery_id = current_setting('{SESSION_VAR}', true)::uuid
            )
        );
        """
    )

    op.execute(_enable_and_force("invoice_sales"))
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_invoice_sales ON invoice_sales
        USING (
            invoice_id IN (
                SELECT id FROM invoices
                WHERE nursery_id = current_setting('{SESSION_VAR}', true)::uuid
            )
        )
        WITH CHECK (
            invoice_id IN (
                SELECT id FROM invoices
                WHERE nursery_id = current_setting('{SESSION_VAR}', true)::uuid
            )
        );
        """
    )

    # notification_preferences: scoped via the owning user's role_assignment
    # to the current org (a user's preferences are meaningful per-org since
    # v1 constrains one org per user, per SRS §2.6 — this still expresses
    # it as an explicit join rather than assuming that constraint).
    op.execute(_enable_and_force("notification_preferences"))
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_notification_preferences
        ON notification_preferences
        USING (
            user_id IN (
                SELECT user_id FROM role_assignments
                WHERE nursery_id = current_setting('{SESSION_VAR}', true)::uuid
            )
        )
        WITH CHECK (
            user_id IN (
                SELECT user_id FROM role_assignments
                WHERE nursery_id = current_setting('{SESSION_VAR}', true)::uuid
            )
        );
        """
    )


def downgrade() -> None:
    all_tables = (
        DIRECT_TENANT_TABLES
        + [t for t, _, _ in JOIN_TENANT_TABLES]
        + [t for t, _, _, _ in TWO_HOP_TENANT_TABLES]
        + ["role_assignment_branch_scopes", "invoice_sales", "notification_preferences"]
    )
    for table in all_tables:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table};")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
