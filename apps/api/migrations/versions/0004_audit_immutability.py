"""Audit log immutability — enforced at the database grant level.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-05

FR-19.3: "Audit log entries are immutable (no update/delete path exists,
including for Org Admins)." app/models/platform.py's AuditLog docstring
promises this is enforced "below the application layer, not just by
omitting an endpoint" — this migration is that enforcement. REVOKE UPDATE,
DELETE on audit_logs from the application's runtime database role, so even
a future bug that adds an UPDATE/DELETE code path against this table would
fail at the database, not just at code review.

The application connects as role `nurseryverse_api` in every deployed
environment (docs/architecture/09-infrastructure.md; the role itself is
provisioned by infra, not by this migration — creating database roles is
an environment-specific ops concern, not schema). Local development
without that role configured (e.g. connecting as the Postgres superuser)
is handled gracefully below: the REVOKE is skipped with a notice rather
than failing the migration, since a superuser connection can't have
privileges revoked from itself in a way that would still let local
`docker-compose` development work.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

APP_ROLE = "nurseryverse_api"


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                REVOKE UPDATE, DELETE ON TABLE audit_logs FROM {APP_ROLE};
                -- INSERT and SELECT remain granted — the app still needs to
                -- write new entries and read the Audit Log Viewer (PG-54).
                GRANT INSERT, SELECT ON TABLE audit_logs TO {APP_ROLE};
            ELSE
                RAISE NOTICE 'Role % does not exist in this environment — skipping audit_logs grant revocation (expected in local dev connecting as superuser).', '{APP_ROLE}';
            END IF;
        END
        $$;
        """
    )
    # Belt-and-suspenders, independent of role-based grants: reject any
    # UPDATE/DELETE at the statement level for *any* role via a trigger,
    # since REVOKE alone doesn't stop a connection that owns the table
    # (table owners bypass grants). This is the actual hard guarantee.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION reject_audit_log_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is immutable — % is not permitted (FR-19.3)', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_logs_immutable
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION reject_audit_log_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_immutable ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS reject_audit_log_mutation();")
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                GRANT UPDATE, DELETE ON TABLE audit_logs TO {APP_ROLE};
            END IF;
        END
        $$;
        """
    )
