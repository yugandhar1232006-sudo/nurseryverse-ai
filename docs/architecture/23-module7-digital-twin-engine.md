# Phase 6, Module 7 — Plant Digital Twin Engine

Real, running FastAPI code in `apps/api/app/`. This document explains the design decisions the module's requirements forced and records what was actually verified before calling it complete.

## Architecture: event-driven, in-process

The module's own spec draws a strict pipeline: `Plant Action -> Domain Event -> Digital Twin Event Handler -> Digital Twin Service -> Projection Update -> Database -> API`, and requires that "no API route should modify the Digital Twin directly." Both are implemented exactly, with one honest adaptation to this codebase's real infrastructure: there is no message broker or background worker anywhere in this project (no prior module introduced one), so "event-driven" here means a synchronous, in-process publish/dispatch pipeline rather than asynchronous, out-of-process messaging. `DomainEventPublisher.publish()` (Module 4's own outbox writer) now optionally carries an `EventDispatcher`; immediately after persisting an event row, it calls `dispatcher.dispatch(row)`, which fans the event out to every registered `EventHandler` whose declared `event_types` includes it. The only handler registered today is `DigitalTwinEventHandler`, a thin adapter around `DigitalTwinService.project()`.

This is still genuinely event-driven, not just "the write path calls the projector directly": no Module 6 service (`PlantService`, `GrowthService`, ...) has any reference to `DigitalTwinService` or even to the dispatcher — every one of them only ever calls `publisher.publish(event)`, the exact same call they made before this module existed. Coupling is entirely through the `domain_events` outbox and the dispatcher; swapping the in-process dispatcher for a real queue consumer later requires zero changes to any Module 6 code. And "no API route should modify the Digital Twin directly" is a structural fact, not a convention: `app/api/routes/digital_twin.py` contains nine routes and every one of them is a `GET` (verified live — a `POST` to any digital-twin path returns HTTP 405, not just "denied by permission").

Dispatch failures are caught inside the dispatcher and logged to `event_dispatch_log`, never propagated to the caller — a Digital Twin projection bug must never fail the `POST /plants` (or any other Module 6 write) request that emitted the event. This is the actual reason CQRS architectures decouple write and read sides: the read projection's health can never gate the write.

## Reconciling with Module 6's "the Plant row is the Digital Twin"

Module 6's own docs describe the `Plant` row plus its related tables as "the Digital Twin" — correct for that module's purpose, but Module 7's spec explicitly wants a separately-versioned, event-sourced projection with its own query surface (current/timeline/snapshot-by-date/version-history/event-history), which is a different thing. The resolution: Module 6's tables (`plants`, `growth_timeline`, `health_history`, ...) are the normalized, transactional **write-side source of truth** — every Plant Lifecycle write goes there, and always will. `digital_twins`/`digital_twin_versions` (this module, migration `0011`) are a derived, denormalized, versioned **read-side projection**, built exclusively by consuming the domain events those write-side tables' services already emit. This is the textbook CQRS split. No route or service outside this module ever writes to either new table.

## The three new tables (migration `0011`)

- **`digital_twins`** — one row per Plant, the *current* projection. `snapshot` (JSON) stores latest-value summaries and counts, not growing lists — full history lives in `digital_twin_versions`/`domain_events` instead. This keeps every projection update an O(1)-sized write regardless of how long a plant has been alive, directly serving the module's "minimal write amplification" performance requirement, and is why the 14-item "Include" list in the spec (Growth History, Health Timeline, Water Timeline, ...) maps to two different query shapes (current snapshot vs. timeline query), not one giant nested blob.
- **`digital_twin_versions`** — immutable, append-only, one row per projection update, each carrying a **complete** snapshot (not a diff) so "Snapshot retrieval"/"Historical playback"/"Version comparison" are all single-row reads, never a replay-from-scratch. Enforced immutable at the database level with the identical REVOKE-UPDATE/DELETE-plus-trigger technique migration `0004` already gave `audit_logs` — "No historical record may be overwritten" is this module's own named requirement, not a nicety.
- **`event_dispatch_log`** — one row per `(event_id, handler_name)` dispatch attempt; the idempotency/retry-safety/audit mechanism (see below). Deliberately *not* immutable — a retried failure updates its own row's `attempt_count` in place.

## `domain_events.sequence`: closing an ordering gap Module 4 left open

`DomainEvent.id` is a UUIDv4 (`UUIDPKMixin`), deliberately non-sortable by design (avoids leaking row-count/creation-order across tenants) — exactly right for a primary key, wrong for "process these events in the order they actually happened." Migration `0011` adds `sequence`, a real Postgres `BIGSERIAL`, backfilled for any pre-existing rows via `row_number() OVER (ORDER BY occurred_at, id)` and authoritative for every row from this migration forward. The dispatcher and `DigitalTwinService.compute_projection_from_events` (replay) both order strictly by `sequence`, never `occurred_at`. The same migration also extends `audit_logs`' immutability enforcement to `domain_events` itself — never done in Module 4, since no prior module's correctness actually depended on events being un-mutatable; Module 7's entire replay/idempotency guarantee does, so closing that gap belongs here.

## Idempotency, ordering, and retry-safety — three real, distinct mechanisms

1. **Dispatcher-level idempotency**: before invoking a handler, `EventDispatcher` checks `event_dispatch_log` for an existing `SUCCEEDED` row for `(event_id, handler_name)`; if found, it's a no-op. A retried `FAILED` row is upserted in place (`attempt_count` increments), never duplicated.
2. **Projector-level ordering guard** (belt-and-suspenders on top of #1): `DigitalTwinService.project()` compares the incoming event's `sequence` against the twin's own `last_event_sequence` and refuses to regress an already-applied projection, even if somehow called directly (bypassing the dispatcher) with a stale event.
3. **Replay as the actual recovery mechanism**: rather than a piecemeal "redispatch this one failed row" operation (which risks applying events out of the order they'd have projected in on a clean run), `DigitalTwinService.rebuild_from_scratch(plant_id)` replays a plant's *entire* event history from `domain_events` in one idempotent pass — simpler and strictly more robust. It refuses outright if a twin already exists (a `ConflictError`, backed by the real `uq_digital_twins_plant_id`/`uq_digital_twin_versions_plant_version` constraints at the database level too), so it can never corrupt or duplicate an in-progress projection.

## Verifying "event replay produces identical projections" — live, not just in tests

`DigitalTwinService.compute_projection_from_events(plant_id)` independently folds over a plant's complete `domain_events` history from scratch, applying the *exact same* per-event-type transition methods (`_on_growth_recorded`, `_on_plant_moved`, ...) the live incremental projector uses — same code, two call paths, so agreement is enforced by construction, not by coincidence. `GET /plants/{id}/digital-twin/verify` exposes this as a live diagnostic endpoint (`{"consistent": bool, "differing_keys": [...]}`), turning the module's own validation checklist item into a real, queryable feature rather than only something asserted in a test.

## Thin events, enrichment reads

Module 6's own events carry only IDs for sub-records (`GrowthRecorded.growth_entry_id`, `HealthRecorded.health_entry_id`, ...), not full payloads. The projector therefore reads the referenced row back from the relevant Module 6 repository (`GrowthTimelineRepository.get_by_id`, etc.) to build a complete `latest.*` summary — six `get_by_id` methods were added to five existing Protocols plus `TreatmentRepository` (interfaces, SQLAlchemy impls, and fakes) purely for this read-only enrichment purpose; none of them is a new write path. One event, `PlantArchived`, carries no payload fields at all — its `archived_reason` is read directly off the `Plant` row for the same reason.

## Two spec sections that are structurally inapplicable, not gaps

- **Inventory Timeline**: `inventory_adjustments.inventory_id` FKs to the bulk `inventory` table (SKU-level stock), which has no `plant_id` column at all — Module 6 already established that bulk Inventory and individually-tracked Plant are deliberately separate, non-overlapping models. There is no valid join from a Plant's Digital Twin to an Inventory adjustment; this section of the snapshot will always be empty for an individually-tracked plant, by design.
- **AI Prediction Timeline**: `ai_predictions.plant_id` *does* exist and genuinely joins (Phase 5 schema), but no module before Module 10 (AI Platform) writes to that table and no domain event announces a prediction yet. Rather than fake this section, it's simply not populated by this module — once Module 10 starts writing real rows, the join is already correct with no further change needed here.

## Authorization

Every route reuses `plants:read` rather than minting a new `digital_twin:read` permission code — a Digital Twin is another view of the same Plant a caller already needs `plants:read` for, the identical reasoning Module 5 applied reusing `species:read` for `GET /plant-categories`, and Module 6 applied reusing `watering:read`/`watering:write` for Fertilizer routes. Every by-plant route fetches the underlying Plant first (`plant_service.get_plant`) to 404 correctly and to authorize against its real `nursery_id`/`branch_id`, the same fetch-then-authorize, branch-scoped pattern `plants.py` established. `GET /digital-twins` (the org-wide list) mirrors `list_plants`'s own no-single-resource authorization shape.

## Testing

489 tests total (462 pre-existing Modules 1–6 + 27 new): 39 unit (`test_digital_twin_service.py`), 7 unit (`test_event_dispatcher.py`), 15 integration (`test_digital_twin_routes.py`).

- **Projection correctness**: one test per event type (registered, updated, status-changed to sold/deceased, moved, archived, growth/health/watering/fertilizer/environmental recorded, disease detected → confirmed, treatment applied), asserting the resulting `snapshot`/`lifecycle_state`/`operational_status`/`growth_stage`/counts.
- **Idempotency**: duplicate dispatch of the identical event row is a no-op at both the dispatcher level (`event_dispatch_log` succeeded-check, handler's own call count asserted) and the projector level (`project()` called directly on an already-applied event returns the unchanged version).
- **Ordering**: a stale non-registration event (sequence `<=` the twin's `last_event_sequence`) is ignored by `project()`.
- **Retry-safety**: a handler that fails is logged `FAILED` without raising; a retry increments `attempt_count` and can subsequently succeed.
- **Replay/projection consistency**: `compute_projection_from_events` compared against the live twin's snapshot after a multi-event lifecycle (register → grow → water → move → promote), asserted equal; `verify_consistency` asserted `True`; a full disaster-recovery scenario (`rebuild_from_scratch` after clearing the projection tables but leaving `domain_events` untouched) reproduces the identical version count and snapshot.
- **Version immutability**: structural assertion that the version repository's fake has no `update`/`delete` method (mirroring `DigitalTwinVersionRepository`'s own Protocol surface), and a source-inspection test asserting no query method ever calls `_write_version`.
- **Timeline/version-history ordering, pagination, snapshot-by-date, version comparison**: each has a dedicated unit and/or integration test.
- **Authorization**: 401 unauthenticated, 403 missing permission, 403 cross-tenant (`CROSS_TENANT_ORG`), verified both at the service layer indirectly (via the route) and directly at the HTTP layer.
- **Structural "no writes" proof**: `POST`/`PATCH`/`DELETE` to `/plants/{id}/digital-twin` all return 405 at the HTTP layer (no such route exists) — the same technique Module 6 used to prove Growth/Health/etc. records are immutable.

**Coverage**: **100%** across every file this module added (`digital_twin_service.py` — 234 stmts; `dispatcher.py` — 35 stmts; `publisher.py` — 27 stmts, including the new `set_dispatcher`/dispatch-call paths; `routes/digital_twin.py` — 73 stmts).

## Validation performed

- `bash scripts/validate_migrations_offline.sh` — `ALL OFFLINE CHECKS PASSED`: 61 tables (+3: `digital_twins`, `digital_twin_versions`, `event_dispatch_log`), 24 enums (+1: `event_dispatch_status`), 41 RLS policies (unchanged — none of the new tables carry `nursery_id`-keyed RLS; access is authorized at the service layer the same way every other by-plant-id resource already is), 20 triggers (+2: the new `digital_twin_versions` and `domain_events` immutability triggers).
- `python3 -m ruff check app/ migrations/ tests/` — 12 errors, all pre-existing and unrelated to this module (confirmed by exact line-by-line comparison against Module 6's own disclosed baseline). Zero errors in any file this module added or touched.
- `python3 -m mypy app/` — 22 errors in 10 files (86 source files checked, +5 vs. Module 6's 81 — the five new files this module adds), unchanged from the established baseline. Zero new errors.
- `python3 -m pytest tests/` — 489 passed (462 pre-existing + 27 new).
- Live `uvicorn` smoke test against a genuinely unreachable database and Redis: `/healthz` returns `{"status":"ok"}`, `/readyz` returns 503, all nine Digital Twin routes correctly return 401 for a missing bearer token without ever touching the database, a `POST` to a Digital Twin path returns 405 (proving no write route exists, live, not just via test assertion), and `/openapi.json` shows 64 total paths (+9 vs. Module 6's 55), all nine new ones `GET`-only with summaries.
- End-to-end manual verification (in addition to the automated suite): registering a plant through the real `PlantService` produces a `digital_twins` row at version 1 within the same process, in reaction to the emitted `plant.registered` event, with no direct call from `PlantService` into `DigitalTwinService` anywhere in the call stack — confirmed by reading the full call chain, not just observing the outcome.

### Pre-completion validation checklist (from the module's own spec)

- Every lifecycle event updates the Digital Twin — tested per event type (13 handlers, `PROJECTED_EVENT_TYPES`).
- Event replay produces identical projections — tested (`compute_projection_from_events` vs. live snapshot) and exposed live (`GET .../verify`).
- Version history is immutable — enforced at the database level (REVOKE + trigger, migration `0011`) and asserted structurally in tests.
- Timeline ordering is correct — tested (newest-first default, `sort_dir` parameter, chronological `event_sequence`).
- No duplicate projections exist — `uq_digital_twins_plant_id` (one twin per plant) and `uq_digital_twin_versions_plant_version` (no duplicate version number) are real, enforced database constraints, not just application-level checks; idempotent dispatch additionally prevents a duplicate version from ever being *attempted*.
- Authorization is enforced — tested extensively, reusing `plants:read`, including cross-tenant rejection.
- OpenAPI documentation is complete — confirmed live: 9 paths, all with summaries.

## What remains unverified

Same disclosed limitation as every prior module: no live PostgreSQL or Redis instance is reachable in this sandbox. The real `SqlAlchemyDigitalTwinRepository`/`SqlAlchemyDigitalTwinVersionRepository`/`SqlAlchemyEventDispatchLogRepository`/`SqlAlchemyDomainEventRepository.list_for_aggregate` implementations (including the `BIGSERIAL` sequence assignment under real concurrent inserts, the immutability triggers' actual enforcement, and the unique-constraint-based duplicate-version prevention) have been validated for correct query construction and exercised end-to-end through the app's HTTP layer against in-memory fakes, but true behavior against real concurrent writes — in particular, whether two events for the same plant dispatched in genuinely concurrent requests could ever race past the ordering guard before the database's own unique constraint catches it — remains unverified against real infrastructure. The in-memory fakes' single-threaded execution model cannot exercise that race by construction.
