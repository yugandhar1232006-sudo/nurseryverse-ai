"""Authorization denial audit trail (Phase 6 Module 3).

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-05

Why this migration exists: Module 3 requires that every authorization
*failure* generate an auditable record with the user, permission,
resource, request ID, IP, timestamp, and reason. No existing table can
hold this. `audit_logs` (Phase 5) records business-data mutations and
requires a non-null `nursery_id`, but an authorization denial can happen
before any org context is resolvable (e.g. a cross-org access attempt
where the *target* org, not the actor's own org, is what's in question).
`security_events` (Module 2, migration 0007) is authentication/session
lifecycle -- login, tokens, password/email flows -- a different shape and
a different kind of investigation than "who tried to do something they
weren't allowed to do". See app/models/authorization.py's module
docstring and docs/architecture/19-module3-authorization.md for the full
design.

Per the established process (Module 2 onward): migrations 0001-0007 are
untouched; this ships as a new migration, generated mechanically (not
hand-typed) via scripts/generate_migration_0008.py, the same
CreateTableOp/CreateIndexOp rendering technique as 0001 and 0007.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "authorization_denials",
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("permission_code", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=True),
        sa.Column("resource_id", sa.UUID(), nullable=True),
        sa.Column("nursery_id", sa.UUID(), nullable=True),
        sa.Column("branch_id", sa.UUID(), nullable=True),
        sa.Column(
            "reason",
            sa.Enum(
                "MISSING_PERMISSION",
                "CROSS_TENANT_ORG",
                "CROSS_TENANT_BRANCH",
                "NOT_OWNER",
                "ACCOUNT_INACTIVE",
                "NO_ORG_CONTEXT",
                name="authorization_denial_reason",
            ),
            nullable=False,
        ),
        sa.Column("explanation", sa.String(length=500), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default="now()", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"], name=op.f("fk_authorization_denials_branch_id_branches"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["nursery_id"],
            ["nurseries.id"],
            name=op.f("fk_authorization_denials_nursery_id_nurseries"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_authorization_denials_user_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_authorization_denials")),
    )
    op.create_index(
        "ix_authorization_denials_nursery_created",
        "authorization_denials",
        ["nursery_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_authorization_denials_reason_created",
        "authorization_denials",
        ["reason", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_authorization_denials_user_created", "authorization_denials", ["user_id", "created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_table("authorization_denials")
    op.execute("DROP TYPE IF EXISTS authorization_denial_reason")
