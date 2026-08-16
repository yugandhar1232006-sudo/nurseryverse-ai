# Phase 5 — Production Database Implementation

Implements `05-database-architecture.md`'s blueprint as a real, runnable PostgreSQL 16 schema. Code lives in `apps/api/app/models/` (SQLAlchemy 2.x) and `apps/api/migrations/versions/` (Alembic). Nothing in this phase is a stub — every model, constraint, index, RLS policy, view, and trigger below is real and has been mechanically validated (see "Migration Validation").

## 1–9. Schema, Models, Migrations, Constraints

49 tables across 11 model files (`apps/api/app/models/`), organized by bounded context exactly matching `05-database-architecture.md` §2 and the Phase 5 consistency-validation check #10: `identity.py` (Users, Roles, Permissions, RoleAssignment), `organization.py` (Nursery, Branch, Employee), `catalog.py` (PlantCategory, Unit, Species, PlantVariety), `plants.py` (Plant, PlantImage, PlantTransfer), `digital_twin_records.py` (GrowthTimeline, HealthHistory, EnvironmentalReading, WateringLog, FertilizerLog), `disease.py` (DiseaseReport, Treatment), `ai.py` (AIPrediction, AIRecommendation, AIAssistantConversation/Message), `inventory.py`, `commerce.py` (Customer, Sale, Invoice, Payment), `purchasing.py` (Supplier, PurchaseOrder), `notifications.py`, `reports.py` (Report, Passport), `attachments.py`, `platform.py` (AuditLog, OrgSettings, Subscription, UsageCounter).

Six tables were added beyond the Phase 1–4 documents at this phase's explicit request (PlantCategory, PlantVariety, Unit, FertilizerLog, Payment, Attachment) — each is cross-referenced back to the requirement that introduced it in its model docstring, and `Species` was restructured from a flat `category` string to a proper `PlantCategory` FK to match the requested Category → Species → Variety hierarchy.

**Migration chain** (`apps/api/migrations/versions/`):
- `0001_initial_schema.py` — all 49 tables, 20 native ENUM types, every FK/PK/unique/check constraint and index. Generated mechanically from the SQLAlchemy models via Alembic's own autogenerate renderer (not hand-typed — see `scripts/generate_initial_migration.py`), so it cannot drift from the ORM definitions.
- `0002_seed_system_metadata.py` — 6 system roles, 58 permissions, 202 role↔permission grants (mechanically parsed from `docs/ux/07-role-permission-matrix.md`), 12 plant categories, 12 units. System metadata only, per the Phase 5 seed-data rule — verified by `scripts/validate_migrations_offline.sh`'s check that no business-data table appears in any `INSERT`.
- `0003_row_level_security.py` — 40 RLS policies (see §15).
- `0004_audit_immutability.py` — audit log immutability (see §13).
- `0005_views_and_materialized_views.py` — see §10–11.
- `0006_updated_at_triggers.py` — see §12.

**Foreign keys:** 103 across the schema, all `RESTRICT` by default (soft-delete-preserving entities: Branch, Species, Supplier) or `CASCADE`/`SET NULL` where the child record has no independent meaning without its parent (PlantImage, GrowthTimeline, etc. cascade; DiseaseReport's `source_ai_prediction_id` sets null so a prediction can be pruned without losing the report).

**Composite & unique indexes:** every tenant-scoped table is indexed `(nursery_id, branch_id)` leading (or `nursery_id` alone), per `05-database-architecture.md` §5; high-traffic query patterns get dedicated composite indexes (`ai_predictions(plant_id, prediction_type, created_at)` for "latest prediction per module," `sales(branch_id, created_at)` for Sales History's default sort, `disease_reports(status, severity)` for triage). Unique constraints enforce every real-world uniqueness rule: one species per botanical name per org, one QR token globally, one idempotency key per branch per sale, one invoice number per org, and more — 216 named constraints/indexes total, zero duplicates (verified, §"Migration Validation").

**Check constraints:** non-negative inventory quantity, non-negative sale total, PO received-quantity-cannot-exceed-ordered, and a sale line item must reference exactly one of `plant_id`/`inventory_id` (never both, never neither).

**ENUM definitions:** 20 native PostgreSQL enums (`apps/api/app/db/enums.py`) back every lifecycle/status column — an invalid status value is a database-level impossibility, not an application bug waiting to happen.

## 10. Views

`v_plant_latest_predictions` — the "latest prediction per module per plant" `DISTINCT ON` pattern, reused by every plant-detail query instead of duplicated per repository method. `v_low_stock_inventory` — a thin filter view backing the Inventory dashboard's attention banner.

## 11. Materialized Views

`mv_branch_dashboard_summary` (revenue today/MTD, at-risk plant count, low-stock count, pending disease reports — per branch) and `mv_org_revenue_rollup` (daily revenue per org). Both implement `docs/ux/18-analytics-workflow.md`'s pre-aggregation strategy: dashboards read these instead of live-aggregating `sales`/`ai_predictions` on every page load, which is what makes NFR-1.3's 2-second dashboard budget achievable at scale. Refresh is a scheduled Celery Beat job (`REFRESH MATERIALIZED VIEW CONCURRENTLY`, Phase 6), not a trigger — refreshing on every write would defeat the purpose of pre-aggregating in the first place. Both views have the unique index `CONCURRENTLY` refresh requires.

## 12. Triggers

Exactly two trigger classes exist, each independently justified in its migration's docstring (per the Phase 5 instruction to add triggers "only if justified"): the `updated_at` auto-touch trigger (17 tables) as a database-level backstop behind the ORM's `onupdate=`, and the audit-log immutability trigger (§13). No other trigger exists — quantity/received-quantity bounds are check constraints (cheaper, declarative), and cross-table transactional consistency (sale ↔ inventory ↔ plant status) is explicit application-layer transaction logic (`05-database-architecture.md` §6), not hidden procedural SQL.

## 13. Audit Tables

`audit_logs` is genuinely immutable, not just "no endpoint exists": migration `0004` both revokes UPDATE/DELETE from the application's database role and — the actual hard guarantee, since table owners bypass grants — installs a `BEFORE UPDATE OR DELETE` trigger that unconditionally raises an exception. FR-19.3 is enforced below the ORM, below the API, at the database itself.

## 14. Soft Delete Strategy

Branches, Species (referenced), and Suppliers (referenced) never hard-delete when referenced by other data — `ON DELETE RESTRICT` is the backstop, with the service layer (Phase 6) providing the friendlier "this is referenced, can't remove it" error ahead of the raw constraint violation. Branch additionally carries an explicit `status` enum (`active`/`inactive`) as its true soft-delete mechanism (FR-2.5). Plants are never deleted at all — the Digital Twin lifecycle (`docs/ux/13-digital-twin-lifecycle.md`) only moves `status` forward to `sold`/`deceased`; this is why the Phase 5 consistency check removed the orphan `plants:delete` permission rather than adding a delete endpoint. Digital-twin history tables (growth, health, environmental, watering, fertilizer) are append-only by construction — no delete path exists at any layer, which is the strongest form of "soft delete" (there was never a delete to soften).

## 15. Row-Level Security Policies

40 policies across three shapes (direct nursery_id equality, one-hop join through a parent table, one two-hop join for `treatments`), all keyed on the `app.current_org_id` session variable the tenant-scoping middleware sets per request (`03-backend-architecture.md` §8). This is the database-layer half of the two-layer defense-in-depth model from `05-database-architecture.md` §9 — the application-layer tenant filter is layer one, RLS is layer two, and both must agree for data to flow. Three deliberate, documented exceptions exist (`users`, `invites`, `passports`' public path) where RLS is structurally the wrong tool because the query happens before any org context exists; `roles`/`permissions`/`role_permissions` are exempt because system roles must be globally visible. All exceptions are explained in `0003_row_level_security.py`'s docstring, not left as silent gaps.

## 16. Optimized Query Strategy

Every tenant-scoped repository query leads with the `(nursery_id, branch_id)` composite index (§"Composite & unique indexes"). The "latest AI prediction" pattern — the single most repeated query shape in the product, appearing on the Plant Twin, the AI Predictions Dashboard, and the Branch Dashboard — is centralized in one indexed view (`v_plant_latest_predictions`) rather than five different `DISTINCT ON` queries scattered across repositories that could drift out of sync. Dashboard reads hit materialized views, not live aggregates (§11). `pg_trgm` (enabled in `0001`) backs fuzzy search on customer/plant names for the global search and duplicate-customer-detection features.

## 17. Transaction Strategy

Matches `05-database-architecture.md` §6 exactly: `READ COMMITTED` isolation for standard operations, with `SELECT ... FOR UPDATE` row locks specifically on the availability-check-then-decrement path in Sales (closing the race-condition window between two POS terminals at the same branch checking the same plant's availability). Every multi-table write that must be all-or-nothing (sale completion, PO receiving, plant transfer, employee deactivation) is a single explicit service-layer transaction — this is a Phase 6 (backend) responsibility to *implement*, but the schema is shaped to make it natural: `InventoryService.apply_change()` is the only path that writes to `inventory`, so every caller (Sales, Purchasing) goes through one transactional chokepoint rather than each reimplementing consistency.

## 18. Backup Strategy

Restated and made concrete from `05-database-architecture.md` §8 / `10-devops.md` §5 for this specific schema: daily logical `pg_dump` plus continuous WAL archiving, 30-day rolling + 12-month monthly retention. Two schema-specific notes: (1) the materialized views (§11) are derived data — a restore only needs to `REFRESH MATERIALIZED VIEW` after restoring the base tables, not back up the views' contents separately; (2) `audit_logs`' immutability trigger means a restored audit log is provably identical to what existed at backup time (no possibility a "restore" silently included a tampered row, since tampering was never possible in the first place).

## 19. Partitioning Strategy

Not implemented in v1 — the launch-scale target (NFR-2.1: 50 orgs, 500 users) doesn't produce enough volume in any single table to need it yet. The plan for when it does: range-partition by month on `created_at` for the highest-growth append-only tables — `audit_logs`, `ai_predictions`, `notifications`, and the four Digital Twin history tables (`growth_timeline`, `health_history`, `environmental_readings`, `watering_logs`) — since these are the tables that grow unboundedly with usage rather than with the number of orgs. This is a documented future migration, not a v1 gap: partitioning these tables today, before there's data to justify it, would add operational complexity (partition-maintenance jobs, more complex index management) for no present benefit — a YAGNI call consistent with the modular-monolith reasoning in `01-high-level-architecture.md` §1.

## 20. Database Performance Considerations

Connection pooling via PgBouncer in front of Postgres (`09-infrastructure.md` §5) — necessary because the async API plus multiple Celery workers would otherwise each hold their own pool. `pool_pre_ping=True` on the SQLAlchemy engine (`app/db/session.py`) avoids serving requests against a connection PgBouncer has silently dropped. Materialized-view refresh runs `CONCURRENTLY` (requires the unique indexes created alongside each view) so dashboard reads are never blocked while a refresh is in progress. RLS policies use subqueries against already-indexed columns (`nursery_id` on the parent, joined via an indexed FK) rather than a full scan, keeping the isolation guarantee close to free in query-plan terms.

## Migration Validation

This sandbox environment has no reachable PostgreSQL instance and no root/apt/outbound-package access broad enough to provision one (confirmed by exhausting the reasonable options: `apt-get install postgresql` — no root; `apt-get download` — proxy blocks the Ubuntu package mirrors; `pip install` embedded-postgres packages — none exist for this platform; direct binary download from GitHub releases — proxy blocks everything except `pypi.org` and the `github.com` root page itself, not release asset downloads). Rather than skip validation or claim untested code works, everything checkable **without** a live database was actually run, not just asserted:

- `scripts/validate_schema.py` — imports every model, calls `sqlalchemy.orm.configure_mappers()` (fails loudly on any bad `relationship()`), compiles every table's `CREATE TABLE` DDL against the real PostgreSQL dialect, checks all 103 foreign keys resolve to a real table+column (zero orphans), topologically sorts the FK graph (zero cycles — confirmed a valid DAG), and checks for duplicate index/constraint names across all 216 named constraints (zero duplicates).
- `alembic upgrade head --sql` — Alembic's own offline mode, run against the full 6-migration chain, produces 2,043 lines of real PostgreSQL DDL/DML with zero errors: `CREATE TYPE` statements for all 20 enums land immediately before their first table use (verified by line-number inspection, not just trusted), all 50 `CREATE TABLE` statements (49 + Alembic's own version table) appear in dependency-safe order, all 40 RLS policies, 18 triggers, 2 materialized views, and 2 views compile, and all 291 seed `INSERT` statements target only the six allowed system-metadata tables.
- `scripts/validate_migrations_offline.sh` bundles all of the above into one repeatable command with pass/fail output, including an explicit check that no business-data table appears in any seed `INSERT`.

**What this does not prove:** that PostgreSQL 16 itself will accept this SQL without a runtime error I haven't anticipated (a real server does more validation than dialect-compilation does — e.g., actual RLS policy semantics under concurrent sessions, actual trigger execution behavior, actual constraint enforcement under real data). The required final step — `docker compose up -d postgres && alembic upgrade head` against a real instance, per `docker-compose.yml` once Phase 10 exists, or any local Postgres 16 in the meantime — has not been run and should be treated as outstanding until it has been. Given how much of this chain is mechanically generated directly from validated metadata (§"Schema, Models, Migrations") rather than hand-typed, the risk of a live-only failure is low, but it is not zero, and Phase 6 (Backend) should not be treated as unblocked from a database standpoint until that live run has actually happened.
