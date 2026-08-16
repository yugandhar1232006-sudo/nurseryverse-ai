"""Plant Digital Twin Engine (Phase 6 Module 7).

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-06

Three new tables plus one additive column on the existing `domain_events`
outbox (Module 4). No changes to any Module 6 table -- this module is a
pure, additive read-side projection layer built entirely by *consuming*
events Module 6 already emits; see app/models/digital_twin.py's module
docstring for the full CQRS-split reasoning, and
docs/architecture/23-module7-digital-twin-engine.md for how this
reconciles with Module 6's own "the Plant row is the Digital Twin" framing
(short version: Module 6's tables are the write-side source of truth,
these tables are the derived, versioned, event-sourced read projection).

`domain_events.sequence` (BIGSERIAL): `id` is a UUIDv4, deliberately
non-orderable by design (docs/architecture/05-database-architecture.md
§4). The event-driven projector needs a true, gap-tolerant total order to
satisfy "Events must be Ordered" and to make replay deterministic --
`sequence` is a real Postgres auto-incrementing integer, assigned at
insert time, and every existing row is backfilled in insertion order via
`row_number() OVER (ORDER BY occurred_at, id)` (an approximation for
*pre-existing* rows only -- from this migration forward, every new row's
`sequence` is authoritative and assigned atomically by the database
itself, which is what actually matters for ordering going forward).

Immutability: `digital_twin_versions` gets the same DB-level
REVOKE-UPDATE/DELETE-and-trigger enforcement migration 0004 already gave
`audit_logs`, because "No historical record may be overwritten" is this
module's own explicit, named requirement, not a general nicety. This
migration also extends that same enforcement to `domain_events` itself
(never done in Module 4, since no prior module's correctness depended on
it) -- Module 7 is the first module whose entire replay/idempotency
guarantee assumes a domain event, once persisted, never changes, so
closing that gap belongs here.

`event_dispatch_log` is deliberately NOT made immutable -- see
app/models/digital_twin.py's `EventDispatchLog` docstring: a failed
dispatch attempt is upserted in place on retry, which requires UPDATE.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

APP_ROLE = "nurseryverse_api"


def upgrade() -> None:
    # --- domain_events: add the authoritative ordering column ---
    op.add_column("domain_events", sa.Column("sequence", sa.BigInteger(), nullable=True))
    op.execute("CREATE SEQUENCE IF NOT EXISTS domain_events_sequence_seq OWNED BY domain_events.sequence;")
    op.execute("ALTER TABLE domain_events ALTER COLUMN sequence SET DEFAULT nextval('domain_events_sequence_seq');")
    # Backfill any pre-existing rows (none in a fresh environment, but
    # this migration must be correct against a database that already has
    # Module 4/5/6 traffic in it) in the best available approximation of
    # true insertion order.
    op.execute(
        """
        UPDATE domain_events
        SET sequence = sub.rn
        FROM (
            SELECT id, row_number() OVER (ORDER BY occurred_at, id) AS rn
            FROM domain_events
            WHERE sequence IS NULL
        ) AS sub
        WHERE domain_events.id = sub.id;
        """
    )
    op.execute(
        "SELECT setval('domain_events_sequence_seq', COALESCE((SELECT MAX(sequence) FROM domain_events), 0));"
    )
    op.alter_column("domain_events", "sequence", nullable=False)
    op.create_index(
        "ix_domain_events_aggregate_sequence", "domain_events", ["aggregate_id", "sequence"], unique=False
    )
    op.create_unique_constraint("uq_domain_events_sequence", "domain_events", ["sequence"])

    # --- domain_events: close the immutability gap Module 4 left open ---
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                REVOKE UPDATE, DELETE ON TABLE domain_events FROM {APP_ROLE};
                GRANT INSERT, SELECT ON TABLE domain_events TO {APP_ROLE};
            ELSE
                RAISE NOTICE 'Role % does not exist in this environment — skipping domain_events grant revocation (expected in local dev connecting as superuser).', '{APP_ROLE}';
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION reject_domain_event_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'domain_events is immutable — % is not permitted (Module 7 replay/idempotency guarantee)', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_domain_events_immutable
        BEFORE UPDATE OR DELETE ON domain_events
        FOR EACH ROW EXECUTE FUNCTION reject_domain_event_mutation();
        """
    )

    # --- event_dispatch_status enum ---
    event_dispatch_status = sa.Enum("SUCCEEDED", "FAILED", name="event_dispatch_status")
    event_dispatch_status.create(op.get_bind(), checkfirst=True)

    # --- digital_twins: current projection, one row per Plant ---
    op.create_table(
        "digital_twins",
        sa.Column("plant_id", sa.UUID(), nullable=False),
        sa.Column("nursery_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=True),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("lifecycle_state", sa.String(length=50), nullable=False),
        sa.Column("operational_status", sa.String(length=50), nullable=False),
        sa.Column("growth_stage", sa.String(length=50), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("last_event_id", sa.UUID(), nullable=True),
        sa.Column("last_event_type", sa.String(length=100), nullable=True),
        sa.Column("last_event_sequence", sa.Integer(), nullable=True),
        sa.Column("last_projected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["plant_id"], ["plants.id"], name=op.f("fk_digital_twins_plant_id_plants"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["nursery_id"], ["nurseries.id"], name=op.f("fk_digital_twins_nursery_id_nurseries"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"], name=op.f("fk_digital_twins_branch_id_branches"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["last_event_id"],
            ["domain_events.id"],
            name=op.f("fk_digital_twins_last_event_id_domain_events"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_digital_twins")),
        sa.UniqueConstraint("plant_id", name="uq_digital_twins_plant_id"),
    )
    op.create_index("ix_digital_twins_nursery_id", "digital_twins", ["nursery_id"], unique=False)
    op.create_index("ix_digital_twins_branch_id", "digital_twins", ["branch_id"], unique=False)
    op.create_index("ix_digital_twins_lifecycle_state", "digital_twins", ["lifecycle_state"], unique=False)

    # --- digital_twin_versions: immutable, append-only version history ---
    op.create_table(
        "digital_twin_versions",
        sa.Column("plant_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("event_sequence", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["plant_id"],
            ["plants.id"],
            name=op.f("fk_digital_twin_versions_plant_id_plants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["domain_events.id"],
            name=op.f("fk_digital_twin_versions_event_id_domain_events"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_digital_twin_versions")),
        sa.UniqueConstraint("plant_id", "version", name="uq_digital_twin_versions_plant_version"),
    )
    op.create_index(
        "ix_digital_twin_versions_plant_sequence", "digital_twin_versions", ["plant_id", "event_sequence"],
        unique=False,
    )
    op.create_index(
        "ix_digital_twin_versions_plant_occurred", "digital_twin_versions", ["plant_id", "occurred_at"],
        unique=False,
    )

    # --- event_dispatch_log: idempotency / retry-safety / audit for the dispatcher ---
    op.create_table(
        "event_dispatch_log",
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("handler_name", sa.String(length=100), nullable=False),
        sa.Column("status", event_dispatch_status, nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("resulting_version", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(length=2000), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["domain_events.id"],
            name=op.f("fk_event_dispatch_log_event_id_domain_events"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_dispatch_log")),
        sa.UniqueConstraint("event_id", "handler_name", name="uq_event_dispatch_log_event_handler"),
    )
    op.create_index(
        "ix_event_dispatch_log_handler_status", "event_dispatch_log", ["handler_name", "status"], unique=False
    )

    # --- digital_twin_versions: immutability, same enforcement as audit_logs (migration 0004) ---
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                REVOKE UPDATE, DELETE ON TABLE digital_twin_versions FROM {APP_ROLE};
                GRANT INSERT, SELECT ON TABLE digital_twin_versions TO {APP_ROLE};
            ELSE
                RAISE NOTICE 'Role % does not exist in this environment — skipping digital_twin_versions grant revocation (expected in local dev connecting as superuser).', '{APP_ROLE}';
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION reject_digital_twin_version_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'digital_twin_versions is immutable — % is not permitted (no historical record may be overwritten)', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_digital_twin_versions_immutable
        BEFORE UPDATE OR DELETE ON digital_twin_versions
        FOR EACH ROW EXECUTE FUNCTION reject_digital_twin_version_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_digital_twin_versions_immutable ON digital_twin_versions;")
    op.execute("DROP FUNCTION IF EXISTS reject_digital_twin_version_mutation();")
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                GRANT UPDATE, DELETE ON TABLE digital_twin_versions TO {APP_ROLE};
            END IF;
        END
        $$;
        """
    )

    op.drop_index("ix_event_dispatch_log_handler_status", table_name="event_dispatch_log")
    op.drop_table("event_dispatch_log")

    op.drop_index("ix_digital_twin_versions_plant_occurred", table_name="digital_twin_versions")
    op.drop_index("ix_digital_twin_versions_plant_sequence", table_name="digital_twin_versions")
    op.drop_table("digital_twin_versions")

    op.drop_index("ix_digital_twins_lifecycle_state", table_name="digital_twins")
    op.drop_index("ix_digital_twins_branch_id", table_name="digital_twins")
    op.drop_index("ix_digital_twins_nursery_id", table_name="digital_twins")
    op.drop_table("digital_twins")

    sa.Enum(name="event_dispatch_status").drop(op.get_bind(), checkfirst=True)

    op.execute("DROP TRIGGER IF EXISTS trg_domain_events_immutable ON domain_events;")
    op.execute("DROP FUNCTION IF EXISTS reject_domain_event_mutation();")
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                GRANT UPDATE, DELETE ON TABLE domain_events TO {APP_ROLE};
            END IF;
        END
        $$;
        """
    )

    op.drop_constraint("uq_domain_events_sequence", "domain_events", type_="unique")
    op.drop_index("ix_domain_events_aggregate_sequence", table_name="domain_events")
    op.drop_column("domain_events", "sequence")
    op.execute("DROP SEQUENCE IF EXISTS domain_events_sequence_seq;")
