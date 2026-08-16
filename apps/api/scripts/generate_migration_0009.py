"""
Generates the upgrade() body for migrations/versions/0009_organization_management.py
mechanically -- same technique as 0007/0008 (AddColumnOp/CreateTableOp/
CreateIndexOp rendered via Alembic's own autogenerate renderer, no live DB
diff). Scoped to exactly what Phase 6 Module 4 (Nursery & Organization
Management) added on top of the existing schema.

Usage: python scripts/generate_migration_0009.py > /tmp/0009_body.txt
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

NEW_COLUMNS = {
    "nurseries": ["status"],
    "org_settings": ["default_currency", "default_timezone"],
    "branches": ["operating_hours", "latitude", "longitude", "phone", "email"],
    "employees": ["department", "position", "hired_at"],
}

NEW_TABLES = ["invite_branch_scopes", "domain_events"]


def main() -> None:
    mc = MigrationContext.configure(dialect_name="postgresql")
    actx = AutogenContext(mc, metadata=m.Base.metadata, opts=_RENDER_OPTS)

    for table_name, col_names in NEW_COLUMNS.items():
        print(f"# --- ALTER TABLE {table_name} ADD COLUMN ... ---")
        table = m.Base.metadata.tables[table_name]
        for col_name in col_names:
            col = table.columns[col_name]
            print(render_op_text(actx, ops.AddColumnOp(table_name, col.copy())))
        print()

    print("# --- New tables + their indexes ---")
    for table_name in NEW_TABLES:
        table = m.Base.metadata.tables[table_name]
        print(render_op_text(actx, ops.CreateTableOp.from_table(table)))
        print()
        for index in sorted(table.indexes, key=lambda i: i.name):
            print(render_op_text(actx, ops.CreateIndexOp.from_index(index)))
        print()


if __name__ == "__main__":
    main()
