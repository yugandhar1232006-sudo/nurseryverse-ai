"""Authentication & security tables (Phase 6 Module 2).

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-05

Why this migration exists: Phase 5's schema was built against the
architecture docs' *conceptual* description of JWT/RBAC auth
(docs/architecture/08-security-architecture.md), which never enumerated
implementation-level persistence needs like refresh-token rotation,
device/session tracking, replay-attack detection, email verification, or
account lockout. Building the actual Module 2 login/session/reset flow
surfaced that none of these had anywhere to live:

  - `users` had no columns for email-verification state or failed-login
    tracking at all.
  - No table existed to persist refresh tokens server-side, which is a
    hard requirement for revocation, rotation, and "logout from all
    devices" -- a JWT that's merely *signed* can't be invalidated before
    its natural expiry without a server-side record of which tokens are
    still valid.
  - No table existed for password-reset or email-verification tokens.
  - `audit_logs` cannot record authentication events: it requires a
    non-null `nursery_id` (migrations 0001/0004), but login attempts
    happen before any org context is known and may not even resolve to a
    real user.

Per Module 2's explicit instruction, migrations 0001-0006 are untouched;
this ships as a new migration. Generated mechanically (not hand-typed) via
the same Alembic autogenerate-rendering technique as migration 0001 --
scripts/generate_migration_0007.py -- so it's guaranteed to match
app/models/auth.py and the new columns on app/models/identity.py's `User`
exactly. See docs/architecture/18-module2-authentication.md for the full
design writeup.

None of the four new tables are added to Row-Level Security (migration
0003's policy set) or to the updated_at trigger list (migration 0006) --
`users` already has an updated_at trigger from migration 0006, which
automatically covers the three new columns added to it here (a
whole-row trigger, not a column-list-specific one) without any change to
that migration. See app/models/auth.py's module docstring for why the four
new tables are deliberately RLS-exempt and do not carry created_at/
updated_at pairs (they use `issued_at`/`created_at` + explicit
revocation/expiry timestamps instead, since these rows are never
"updated" in the mutate-in-place sense -- they're superseded by a new row
or marked revoked/used).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # --- users: new columns for email verification + account lockout ---
    op.add_column(
        "users",
        sa.Column("is_email_verified", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("failed_login_attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))

    # --- refresh_tokens: server-side session/device record backing every issued refresh token ---
    op.create_table(
        "refresh_tokens",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("family_id", sa.UUID(), nullable=False),
        sa.Column("device_name", sa.String(length=255), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default="now()", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["replaced_by_id"],
            ["refresh_tokens.id"],
            name=op.f("fk_refresh_tokens_replaced_by_id_refresh_tokens"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_refresh_tokens_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"], unique=False)
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"], unique=False)

    # --- email_verification_tokens ---
    op.create_table(
        "email_verification_tokens",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default="now()", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_email_verification_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_verification_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_email_verification_tokens_token_hash")),
    )
    op.create_index(
        "ix_email_verification_tokens_user_id", "email_verification_tokens", ["user_id"], unique=False
    )

    # --- password_reset_tokens ---
    op.create_table(
        "password_reset_tokens",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_ip", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default="now()", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_password_reset_tokens_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_password_reset_tokens_token_hash")),
    )
    op.create_index(
        "ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"], unique=False
    )

    # --- security_events: global auth/security audit trail (see module docstring) ---
    op.create_table(
        "security_events",
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column(
            "event_type",
            sa.Enum(
                "LOGIN_SUCCESS",
                "LOGIN_FAILED",
                "ACCOUNT_LOCKED",
                "ACCOUNT_UNLOCKED",
                "PASSWORD_RESET_REQUESTED",
                "PASSWORD_RESET_COMPLETED",
                "PASSWORD_CHANGED",
                "EMAIL_VERIFICATION_SENT",
                "EMAIL_VERIFIED",
                "LOGOUT",
                "LOGOUT_ALL",
                "TOKEN_REFRESHED",
                "TOKEN_REUSE_DETECTED",
                "RATE_LIMITED",
                name="security_event_type",
            ),
            nullable=False,
        ),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("event_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default="now()", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_security_events_user_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_security_events")),
    )
    op.create_index(
        "ix_security_events_email_created", "security_events", ["email", "created_at"], unique=False
    )
    op.create_index(
        "ix_security_events_type_created", "security_events", ["event_type", "created_at"], unique=False
    )
    op.create_index(
        "ix_security_events_user_created", "security_events", ["user_id", "created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_table("security_events")
    op.drop_table("password_reset_tokens")
    op.drop_table("email_verification_tokens")
    op.drop_table("refresh_tokens")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
    op.drop_column("users", "is_email_verified")
    op.execute("DROP TYPE IF EXISTS security_event_type")
