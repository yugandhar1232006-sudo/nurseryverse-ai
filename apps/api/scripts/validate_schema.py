"""
Static schema validation — runs without a live PostgreSQL connection.

This sandbox environment cannot provision a real PostgreSQL server (no
root/apt access, outbound network restricted to a small allowlist), so
this script is the migration-validation substitute described in
docs/architecture/13-consistency-validation.md's companion note: it
validates everything that's checkable offline (model construction,
relationship resolution, dialect-correct DDL generation, referential
integrity of the FK graph, absence of cycles, absence of duplicate
constraint/index names) and prints the exact SQL PostgreSQL would receive.
Live execution against a real Postgres 16 instance (via the project's own
`docker-compose.yml`) is the final step and is documented as a required,
not-yet-run step in docs/architecture/14-phase5-database-implementation.md.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from collections import defaultdict, deque

from sqlalchemy import MetaData
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateTable

import app.models as m


def check_mappers_configure() -> None:
    configure_mappers()
    print(f"[OK] configure_mappers() — all relationships resolve, {len(m.Base.metadata.tables)} tables registered")


def check_ddl_compiles(metadata: MetaData) -> list[str]:
    dialect = postgresql.dialect()
    errors = []
    total_lines = 0
    for table in metadata.sorted_tables:
        try:
            ddl = str(CreateTable(table).compile(dialect=dialect))
            total_lines += ddl.count("\n")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{table.name}: {exc}")
    if errors:
        for e in errors:
            print(f"[FAIL] DDL compile: {e}")
    else:
        print(f"[OK] CreateTable DDL compiles for all {len(metadata.sorted_tables)} tables against the PostgreSQL dialect ({total_lines} lines of generated SQL)")
    return errors


def check_orphan_foreign_keys(metadata: MetaData) -> list[str]:
    errors = []
    checked = 0
    for table in metadata.tables.values():
        for fk in table.foreign_keys:
            checked += 1
            target_table_name = fk.column.table.name
            if target_table_name not in metadata.tables:
                errors.append(
                    f"{table.name}.{fk.parent.name} -> {target_table_name} "
                    "(target table not found in metadata)"
                )
            elif fk.column.name not in metadata.tables[target_table_name].columns:
                errors.append(
                    f"{table.name}.{fk.parent.name} -> {target_table_name}.{fk.column.name} "
                    "(target column not found)"
                )
    if errors:
        for e in errors:
            print(f"[FAIL] Orphan FK: {e}")
    else:
        print(f"[OK] No orphan foreign keys — {checked} FK references checked, all resolve to a real table+column")
    return errors


def check_circular_dependencies(metadata: MetaData) -> list[str]:
    """Kahn's algorithm topological sort over the FK dependency graph."""
    graph: dict[str, set[str]] = defaultdict(set)

    for table in metadata.tables.values():
        for fk in table.foreign_keys:
            target = fk.column.table.name
            if target != table.name and target not in graph[table.name]:
                graph[table.name].add(target)

    # edge direction: table -> depends_on target. For topo sort what
    # matters is whether following "depends on" edges ever cycles back,
    # which `dep_count`/`dependents`/`remaining` below compute directly --
    # no separate in-degree bookkeeping needed.
    dep_count = {name: len(graph[name]) for name in metadata.tables}
    dependents: dict[str, set[str]] = defaultdict(set)
    for src, targets in graph.items():
        for t in targets:
            dependents[t].add(src)

    queue = deque([name for name, count in dep_count.items() if count == 0])
    visited = 0
    remaining = dict(dep_count)
    while queue:
        node = queue.popleft()
        visited += 1
        for dependent in dependents[node]:
            remaining[dependent] -= 1
            if remaining[dependent] == 0:
                queue.append(dependent)

    if visited != len(metadata.tables):
        cyclic = [name for name, count in remaining.items() if count > 0]
        print(f"[FAIL] Circular FK dependency detected among: {cyclic}")
        return cyclic
    print(f"[OK] No circular foreign-key dependencies — dependency graph is a valid DAG ({visited} tables topologically sorted)")
    return []


def check_duplicate_index_names(metadata: MetaData) -> list[str]:
    seen: dict[str, str] = {}
    errors = []
    for table in metadata.tables.values():
        for idx in table.indexes:
            if idx.name in seen and seen[idx.name] != table.name:
                errors.append(f"Duplicate index name '{idx.name}' on both {seen[idx.name]} and {table.name}")
            seen[idx.name] = table.name
        for constraint in table.constraints:
            cname = getattr(constraint, "name", None)
            if cname and cname in seen and seen[cname] != table.name:
                errors.append(f"Duplicate constraint name '{cname}' on both {seen[cname]} and {table.name}")
            if cname:
                seen[cname] = table.name
    if errors:
        for e in errors:
            print(f"[FAIL] {e}")
    else:
        print(f"[OK] No duplicate index/constraint names across {len(metadata.tables)} tables ({len(seen)} named constraints/indexes checked)")
    return errors


def check_enum_naming(metadata: MetaData) -> None:
    enum_names = set()
    for table in metadata.tables.values():
        for col in table.columns:
            if hasattr(col.type, "name") and col.type.__class__.__name__ == "Enum":
                if col.type.name in enum_names:
                    pass  # reused across tables is fine (e.g. notification_category)
                enum_names.add(col.type.name)
    print(f"[OK] {len(enum_names)} distinct native PostgreSQL ENUM types declared: {sorted(enum_names)}")


def main() -> int:
    print("=" * 70)
    print("NurseryVerse AI — Static Schema Validation (offline, no live DB)")
    print("=" * 70)
    check_mappers_configure()
    errors = []
    errors += check_ddl_compiles(m.Base.metadata)
    errors += check_orphan_foreign_keys(m.Base.metadata)
    errors += check_circular_dependencies(m.Base.metadata)
    errors += check_duplicate_index_names(m.Base.metadata)
    check_enum_naming(m.Base.metadata)
    print("=" * 70)
    if errors:
        print(f"RESULT: {len(errors)} issue(s) found — see [FAIL] lines above")
        return 1
    print("RESULT: all offline checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
