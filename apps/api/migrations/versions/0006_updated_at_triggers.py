"""updated_at auto-touch triggers — the one other justified trigger set.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-05

Per the Phase 5 instruction to add triggers "only if justified": this is
the one class of trigger that earns its keep. SQLAlchemy's TimestampMixin
(app/db/base.py) already sets `updated_at` via `onupdate=` at the ORM
layer for every write that goes through a Session — but that's an
application-layer guarantee, not a database one. Anything that writes to
these tables outside the ORM's UPDATE path (a manual `psql` fix during an
incident, a future direct-SQL admin tool, a bulk migration script) would
silently leave `updated_at` stale without a database-level backstop. A
`BEFORE UPDATE` trigger is the correct tool for exactly this — it's cheap
(one column touch per row), unconditionally correct regardless of the
write path, and mirrors the same defense-in-depth philosophy already
applied to tenant isolation (RLS, migration 0003) and audit immutability
(migration 0004). No other trigger in this schema is justified by this
bar: inventory quantity non-negativity is already a CHECK constraint
(cheaper, declarative, no procedural code needed); PO
received-not-exceeding-ordered is likewise a CHECK constraint; sale/
inventory transactional consistency is enforced by explicit application
transactions (docs/architecture/05-database-architecture.md §6), not a
trigger, because the business logic involved (which service orchestrates
which tables, in what order, with what error type) belongs in
InventoryService/SalesService, not hidden in procedural SQL a future
engineer would have to know to go looking for.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

TABLES_WITH_TIMESTAMPS = [
    "nurseries",
    "users",
    "ai_assistant_conversations",
    "branches",
    "employees",
    "roles",
    "species",
    "subscriptions",
    "customers",
    "inventory",
    "invites",
    "plant_varieties",
    "role_assignments",
    "suppliers",
    "invoices",
    "plants",
    "purchase_orders",
]


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION touch_updated_at()
        RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in TABLES_WITH_TIMESTAMPS:
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_touch_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
            """
        )


def downgrade() -> None:
    for table in TABLES_WITH_TIMESTAMPS:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_touch_updated_at ON {table};")
    op.execute("DROP FUNCTION IF EXISTS touch_updated_at();")
