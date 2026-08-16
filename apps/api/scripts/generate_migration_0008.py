"""
Generates the upgrade() body for migrations/versions/0008_authorization_denials.py
mechanically -- same technique as 0001/0007 (CreateTableOp/CreateIndexOp
rendered via Alembic's own autogenerate renderer, no live DB diff).

Usage: python scripts/generate_migration_0008.py > /tmp/0008_body.txt
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

NEW_TABLES = ["authorization_denials"]


def main() -> None:
    mc = MigrationContext.configure(dialect_name="postgresql")
    actx = AutogenContext(mc, metadata=m.Base.metadata, opts=_RENDER_OPTS)

    for table_name in NEW_TABLES:
        table = m.Base.metadata.tables[table_name]
        print(render_op_text(actx, ops.CreateTableOp.from_table(table)))
        print()
        for index in sorted(table.indexes, key=lambda i: i.name):
            print(render_op_text(actx, ops.CreateIndexOp.from_index(index)))


if __name__ == "__main__":
    main()
