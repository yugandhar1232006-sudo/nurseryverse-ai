"""
Generates the upgrade() body for migrations/versions/0007_authentication_security.py
mechanically, the same way migration 0001 and its indexes were generated
(scripts/generate_initial_migration.py) -- CreateTableOp/CreateIndexOp
rendered via Alembic's own autogenerate renderer, no live DB diff. This
script is scoped to exactly the tables/columns Module 2 (Authentication)
added on top of the existing Phase 5 schema, so re-running
generate_initial_migration.py (which would try to re-render all 54 tables
into migration 0001) is not the right tool here -- migration 0001 is not
to be touched, per Module 2's explicit instruction.

Usage: python scripts/generate_migration_0007.py > /tmp/0007_body.txt
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

NEW_TABLES = [
    "refresh_tokens",
    "email_verification_tokens",
    "password_reset_tokens",
    "security_events",
]

NEW_USER_COLUMNS = [
    "is_email_verified",
    "failed_login_attempts",
    "locked_until",
]


def main() -> None:
    mc = MigrationContext.configure(dialect_name="postgresql")
    actx = AutogenContext(mc, metadata=m.Base.metadata, opts=_RENDER_OPTS)

    print("# --- ALTER TABLE users ADD COLUMN ... ---")
    users_table = m.Base.metadata.tables["users"]
    for col_name in NEW_USER_COLUMNS:
        col = users_table.columns[col_name]
        print(render_op_text(actx, ops.AddColumnOp("users", col.copy())))
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
