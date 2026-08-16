"""Mechanically generate the full data dictionary from live SQLAlchemy metadata.

Part of the Phase 5 -> Phase 6 Production Database Readiness Review
(docs/architecture/15-production-database-readiness-review.md, section 8).

Rationale: with 49 tables and ~500 columns, hand-transcribing a data
dictionary risks drift from the actual models the moment either changes.
This script reads directly from `app.models.Base.metadata` -- the same
source of truth the migrations are generated from (see
scripts/generate_initial_migration.py) -- so the dictionary this produces
is guaranteed to match the real schema at generation time.

Usage:
    python3 scripts/generate_data_dictionary.py > /tmp/data_dictionary.md
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.dialects import postgresql  # noqa: E402

import app.models as m  # noqa: E402

_PG = postgresql.dialect()


def col_flags(col, table) -> list[str]:
    flags = []
    if col.primary_key:
        flags.append("PK")
    if col.foreign_keys:
        for fk in col.foreign_keys:
            flags.append(f"FK -> {fk.column.table.name}.{fk.column.name}")
    if col.unique:
        flags.append("UNIQUE")
    if not col.nullable:
        flags.append("NOT NULL")
    if col.default is not None:
        flags.append(f"DEFAULT {col.default.arg!r}" if hasattr(col.default, "arg") else "DEFAULT")
    if col.server_default is not None:
        flags.append(f"SERVER_DEFAULT {col.server_default.arg}")
    return flags


def main() -> None:
    tables = sorted(m.Base.metadata.tables.values(), key=lambda t: t.name)
    print("<!-- Generated mechanically by scripts/generate_data_dictionary.py -->")
    print(f"<!-- Total tables: {len(tables)} -->\n")

    for table in tables:
        print(f"### `{table.name}`\n")
        # Table comment (from docstring convention if present in info dict)
        if table.comment:
            print(f"{table.comment}\n")

        print("| Column | Type | Flags |")
        print("|---|---|---|")
        for col in table.columns:
            flags = col_flags(col, table)
            pg_type = col.type.compile(dialect=_PG)
            print(f"| `{col.name}` | `{pg_type}` | {', '.join(flags) if flags else '-'} |")

        # Composite unique constraints
        uniques = [c for c in table.constraints if c.__class__.__name__ == "UniqueConstraint"]
        if uniques:
            print("\n**Composite unique constraints:**")
            for u in uniques:
                cols = ", ".join(c.name for c in u.columns)
                print(f"- `({cols})`")

        # Check constraints
        checks = [c for c in table.constraints if c.__class__.__name__ == "CheckConstraint"]
        if checks:
            print("\n**Check constraints:**")
            for c in checks:
                print(f"- `{c.sqltext}`")

        # Indexes
        if table.indexes:
            print("\n**Indexes:**")
            for ix in sorted(table.indexes, key=lambda i: i.name):
                cols = ", ".join(c.name for c in ix.columns)
                uniq = " UNIQUE" if ix.unique else ""
                print(f"- `{ix.name}`{uniq} ({cols})")

        print()


if __name__ == "__main__":
    main()
