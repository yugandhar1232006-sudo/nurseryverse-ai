"""
Generates migrations/versions/0001_initial_schema.py mechanically from
app.models' SQLAlchemy metadata, using Alembic's own autogenerate
rendering functions (not a live-DB diff, since none is reachable in this
sandbox — see docs/architecture/14-phase5-database-implementation.md).

This is what actually produced 0001_initial_schema.py; re-run it after any
model change instead of hand-editing the generated CREATE TABLE blocks, to
guarantee the migration never drifts from the ORM models. Hand-edit only
the header docstring / extension statements section.

IMPORTANT (fixed by the Production Database Readiness Review — see
docs/architecture/17-production-database-readiness-review.md §1/§2):
`ops.CreateTableOp.from_table(table)` captures columns, the primary key,
foreign keys, and inline column-level uniques/checks, but it does NOT
capture standalone `Index(...)` objects declared in a model's
`__table_args__`. Those live in `table.indexes`, a separate collection —
Alembic's normal live-DB diff flow emits them as their own
`CreateIndexOp`s during comparison, a step this generator does not run
(no live DB to diff against). Earlier runs of this script silently
produced a migration with zero of the 38 explicitly-declared composite/
tenant-scoping indexes actually created. This version renders a
`CreateIndexOp` for every table's `.indexes` explicitly, so that gap
cannot recur.

Usage: python scripts/generate_initial_migration.py > /tmp/body.txt
       (then splice into the migration file's upgrade()/downgrade())
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from alembic.autogenerate.api import AutogenContext
from alembic.autogenerate.render import render_op_text
from alembic.migration import MigrationContext
from alembic.operations import ops

import app.models as m

_RENDER_OPTS = {
    "sqlalchemy_module_prefix": "sa.",
    "alembic_module_prefix": "op.",
    "render_item": None,
    "render_as_batch": False,
    "user_module_prefix": None,
}


def render_create_tables_and_indexes() -> str:
    mc = MigrationContext.configure(dialect_name="postgresql")
    actx = AutogenContext(mc, metadata=m.Base.metadata, opts=_RENDER_OPTS)
    blocks: list[str] = []
    for table in m.Base.metadata.sorted_tables:
        blocks.append(render_op_text(actx, ops.CreateTableOp.from_table(table)))
        # Standalone Index() objects are NOT part of CreateTableOp — render
        # each one as its own CreateIndexOp, immediately after its table.
        for index in sorted(table.indexes, key=lambda i: i.name):
            blocks.append(render_op_text(actx, ops.CreateIndexOp.from_index(index)))
    return "\n\n".join(blocks)


def render_drop_tables() -> str:
    names = [t.name for t in m.Base.metadata.sorted_tables]
    return "\n".join(f"    op.drop_table('{name}')" for name in reversed(names))


if __name__ == "__main__":
    print("# --- upgrade() CREATE TABLE + CREATE INDEX blocks ---")
    print(render_create_tables_and_indexes())
    print()
    print("# --- downgrade() DROP TABLE statements (reverse order; indexes drop with their table) ---")
    print(render_drop_tables())
