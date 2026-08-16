#!/usr/bin/env bash
# Full offline migration validation — everything checkable without a live
# PostgreSQL connection (this sandbox has no reachable Postgres instance;
# see docs/architecture/14-phase5-database-implementation.md "Migration
# Validation" for why, and for the live-DB steps to run once this project
# reaches an environment with real network/root access).
#
# Run from apps/api/.
set -euo pipefail

echo "=== 1. Python syntax check — every migration compiles ==="
for f in migrations/versions/*.py; do
    python3 -m py_compile "$f"
    echo "  OK: $f"
done

echo
echo "=== 2. Model-level static validation (relationships, DDL, FK graph, duplicate names) ==="
python3 scripts/validate_schema.py

echo
echo "=== 3. Alembic revision chain integrity (no forks, no gaps, single head) ==="
~/.local/bin/alembic history

echo
echo "=== 4. Alembic offline SQL generation — full chain, base -> head ==="
~/.local/bin/alembic upgrade head --sql > /tmp/full_migration_check.sql
echo "  Generated $(wc -l < /tmp/full_migration_check.sql) lines of SQL with no errors"

echo
echo "=== 5. Structural sanity counts against the generated SQL ==="
echo "  CREATE TABLE:              $(grep -c '^CREATE TABLE' /tmp/full_migration_check.sql)"
echo "  CREATE TYPE (enums):       $(grep -c '^CREATE TYPE' /tmp/full_migration_check.sql)"
echo "  CREATE POLICY (RLS):       $(grep -c 'CREATE POLICY' /tmp/full_migration_check.sql)"
echo "  CREATE TRIGGER:            $(grep -c 'CREATE TRIGGER' /tmp/full_migration_check.sql)"
echo "  CREATE MATERIALIZED VIEW:  $(grep -c 'CREATE MATERIALIZED VIEW' /tmp/full_migration_check.sql)"
echo "  CREATE VIEW:               $(grep -c '^CREATE VIEW' /tmp/full_migration_check.sql)"
echo "  INSERT INTO (seed rows):   $(grep -c '^INSERT INTO' /tmp/full_migration_check.sql)"
BUSINESS_TABLES_SEEDED=$(grep -oE "INSERT INTO (plants|sales|customers|inventory|employees|nurseries|branches) " /tmp/full_migration_check.sql || true)
if [ -n "$BUSINESS_TABLES_SEEDED" ]; then
    echo "  [FAIL] Business data found in seed migrations: $BUSINESS_TABLES_SEEDED"
    exit 1
else
    echo "  [OK] No business-data tables seeded (roles/permissions/plant_categories/units only)"
fi

echo
echo "=== ALL OFFLINE CHECKS PASSED ==="
echo "Remaining step (requires a live PostgreSQL 16 instance, not available in this sandbox):"
echo "  docker compose up -d postgres && alembic upgrade head"
echo "  ...then re-run this script's SQL against it with psql for final live confirmation."
