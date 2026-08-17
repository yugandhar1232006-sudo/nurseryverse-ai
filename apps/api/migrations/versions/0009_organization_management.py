"""Nursery & Organization Management (Phase 6 Module 4).

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-05

Why this migration exists: building the actual Nursery/Branch/Employee
management endpoints surfaced four gaps Phase 5's schema (and Module 2's
`invites` table) had no columns or tables for:

  - `nurseries` had no lifecycle/soft-delete concept at all -- "Archive
    Nursery" had nowhere to record itself, and every child table already
    carries `ondelete="RESTRICT"` back to `nurseries`, so a hard DELETE
    was never actually viable. See db/enums.py's `NurseryStatus`
    docstring. "Archive Branch" needed no schema change: `BranchStatus`
    already models exactly this soft-delete transition (`INACTIVE`), a
    third `ARCHIVED` value would have been unjustified scope creep.
  - `org_settings` had no currency or timezone -- Module 4's "Currency"/
    "Timezone" org-settings requirement. Homed on `org_settings` (the
    existing one-row-per-org preferences table), not `nurseries` (which
    stays the tenant-identity/lifecycle record).
  - `branches` had no operating hours or geolocation -- "Operating Hours"/
    "Location" requirements.
  - `employees` had no department/position/hire-date -- "Department"/
    "Position"/"Employment Lifecycle" requirements.
  - `invites` (migration 0007) carried only a single `role_id`, with no
    way to record which branches a branch-scoped invited role should be
    assigned to on acceptance -- because at the time, `accept_invite`
    only provisioned the `User` row. Module 4 completes `accept_invite` to
    also provision `Employee` + `RoleAssignment` (+ branch scopes), so the
    *intended* branches need somewhere to live between invite creation and
    acceptance: `invite_branch_scopes`, mirroring
    `role_assignment_branch_scopes` exactly.
  - No table existed for structured domain events (`NurseryCreated`,
    `BranchUpdated`, `EmployeeInvited`, ...), which Module 4's spec
    explicitly requires to be generated -- `domain_events`, a new
    append-only outbox distinct from `audit_logs` (human-mutation-review
    shaped, requires a human actor) and `security_events`/
    `authorization_denials` (auth-lifecycle, unrelated to business-domain
    state). See app/models/events.py's module docstring.

Per the established process (Module 2 onward): migrations 0001-0008 are
untouched; this ships as a new migration, generated mechanically (not
hand-typed) for the AddColumnOp/CreateTableOp/CreateIndexOp portions via
scripts/generate_migration_0009.py, the same technique as every prior
migration since 0001.

Note on enum handling: `nursery_status` is a brand-new Postgres ENUM type,
created inline as part of the `ADD COLUMN` statement on `nurseries` --
that's transaction-safe, since the type doesn't exist yet. This migration
does *not* add a value to an already-existing enum type
(`ALTER TYPE ... ADD VALUE`) anywhere -- `BranchStatus`/`EmployeeStatus`
were deliberately left unchanged (see above, "Archive Branch" reuses the
existing `INACTIVE` value). That operation is a different, harder case:
Postgres cannot run `ALTER TYPE ... ADD VALUE` inside a transaction block,
which Alembic normally wraps every migration in, so it would require
`op.get_context().autocommit_block()`. Noted here as a forward reference
for whichever future migration is the first to actually need it.

`invite_branch_scopes` is deliberately RLS-exempt, for the same reason
`invites` itself already is (migration 0003's docstring): it's looked up
transiently during the invite-creation/accept flow, always scoped by the
inviting employee's own already-authorized org context at the application
layer, never queried standalone. `domain_events` *does* get RLS (below,
hand-written since migration 0003's table lists are not to be touched) --
it has a direct, real `nursery_id` and is exactly the kind of tenant
business data the multi-tenancy defense-in-depth principle exists to
protect, even though it's primarily read by internal consumers (e.g. the
future Module 11 Notifications dispatcher) rather than directly exposed to
every tenant-scoped API route.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # --- nurseries: lifecycle status ---
    # `nursery_status` is a brand-new Postgres ENUM type. Alembic's
    # op.add_column() only references the type by name, so it must be
    # created explicitly before the column is added.
    nursery_status = sa.Enum("ACTIVE", "ARCHIVED", name="nursery_status")
    nursery_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "nurseries",
        sa.Column(
            "status",
            nursery_status,
            server_default=sa.text("'ACTIVE'"),
            nullable=False,
        ),
    )

    # --- org_settings: currency + timezone ---
    op.add_column(
        "org_settings",
        sa.Column("default_currency", sa.String(length=3), server_default="USD", nullable=False),
    )
    op.add_column(
        "org_settings",
        sa.Column("default_timezone", sa.String(length=64), server_default="UTC", nullable=False),
    )

    # --- branches: operating hours + location + contact ---
    op.add_column("branches", sa.Column("operating_hours", sa.JSON(), nullable=True))
    op.add_column("branches", sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True))
    op.add_column("branches", sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True))
    op.add_column("branches", sa.Column("phone", sa.String(length=50), nullable=True))
    op.add_column("branches", sa.Column("email", sa.String(length=320), nullable=True))

    # --- employees: department/position/hire date ---
    op.add_column("employees", sa.Column("department", sa.String(length=100), nullable=True))
    op.add_column("employees", sa.Column("position", sa.String(length=100), nullable=True))
    op.add_column("employees", sa.Column("hired_at", sa.Date(), nullable=True))

    # --- invite_branch_scopes: intended branch(es) for a pending branch-scoped invite ---
    op.create_table(
        "invite_branch_scopes",
        sa.Column("invite_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["branches.id"],
            name=op.f("fk_invite_branch_scopes_branch_id_branches"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invite_id"],
            ["invites.id"],
            name=op.f("fk_invite_branch_scopes_invite_id_invites"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("invite_id", "branch_id", name=op.f("pk_invite_branch_scopes")),
    )

    # --- domain_events: append-only structured event outbox ---
    op.create_table(
        "domain_events",
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", sa.UUID(), nullable=False),
        sa.Column("nursery_id", sa.UUID(), nullable=True),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], name=op.f("fk_domain_events_actor_user_id_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["nursery_id"],
            ["nurseries.id"],
            name=op.f("fk_domain_events_nursery_id_nurseries"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_domain_events")),
    )
    op.create_index(
        "ix_domain_events_nursery_occurred", "domain_events", ["nursery_id", "occurred_at"], unique=False
    )
    op.create_index("ix_domain_events_type_occurred", "domain_events", ["event_type", "occurred_at"], unique=False)

    # --- RLS for domain_events (migration 0003's policy-table lists are not touched) ---
    op.execute("ALTER TABLE domain_events ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE domain_events FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY tenant_isolation_domain_events ON domain_events
        USING (nursery_id = current_setting('app.current_org_id', true)::uuid)
        WITH CHECK (nursery_id = current_setting('app.current_org_id', true)::uuid);
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_domain_events ON domain_events;")
    op.drop_index("ix_domain_events_type_occurred", table_name="domain_events")
    op.drop_index("ix_domain_events_nursery_occurred", table_name="domain_events")
    op.drop_table("domain_events")
    op.drop_table("invite_branch_scopes")
    op.drop_column("employees", "hired_at")
    op.drop_column("employees", "position")
    op.drop_column("employees", "department")
    op.drop_column("branches", "email")
    op.drop_column("branches", "phone")
    op.drop_column("branches", "longitude")
    op.drop_column("branches", "latitude")
    op.drop_column("branches", "operating_hours")
    op.drop_column("org_settings", "default_timezone")
    op.drop_column("org_settings", "default_currency")
    op.drop_column("nurseries", "status")
    op.execute("DROP TYPE IF EXISTS nursery_status")
