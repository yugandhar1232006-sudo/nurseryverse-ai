# Phase 6, Module 5 — Species Catalog (Plant Catalog)

Real, running FastAPI code in `apps/api/app/`. This document explains the design decisions the module's requirements forced and records what was actually verified before calling it complete.

## No new migration

Unlike every prior module, Module 5 required **zero schema changes**. `plant_categories`, `units`, `species`, and `plant_varieties` were all created in Phase 5's initial schema (`migrations/versions/0001_initial_schema.py`), `plant_categories`/`units` were seeded as global system metadata in `0002_seed_system_metadata.py`, and the `species:read`/`species:write`/`species:delete` permissions were seeded in that same migration. The `PlantCategory`, `Species`, and `PlantVariety` SQLAlchemy models (`app/models/catalog.py`) already existed too — this module is the first to actually build the repository/service/API layers on top of that pre-existing schema, not the first to define it.

One small, mechanical model fix was needed along the way: `Species.temperature_min_celsius`/`temperature_max_celsius` were typed `Mapped[Numeric | None]` — `Numeric` is the SQLAlchemy *column type* passed to `mapped_column()`, not a Python value type, and using it as the `Mapped[...]` annotation surfaced real mypy errors the moment this module's service code first touched those attributes (nothing had, until now). Corrected to `Mapped[float | None]`, matching the identical `Numeric(...)` column / `float` attribute pattern Module 4's `Branch.latitude`/`longitude` already established. Annotation-only — no migration, no runtime behavior change, verified by re-running the full offline migration validation (still 58 tables, 22 enums, 41 RLS policies, zero errors) and the full test suite (unchanged pass count) before and after.

## Scope: what "Plant Catalog" means here

The user-facing module name ("Plant Catalog") maps to `docs/architecture/02-low-level-design.md`'s "Module: Species Catalog" and `docs/product/04-functional-requirements.md`'s FR-4. Per FR-4: species records (common name, botanical name, category, care requirements, growth curve, disease susceptibilities) are **per-Org, not branch-scoped** — FR-4.2 explicitly: "shared/reusable across all Branches within an Org." Every service method takes `nursery_id`, never `branch_id`, and no `require_branch_match`-style check appears anywhere in this module's routes.

Two extensions beyond `docs/architecture/07-api-design.md`'s minimal Species endpoint list (`GET/POST /species`, `GET/PATCH /species/{id}`, `DELETE /species/{id}`), same justification pattern Module 4 already established for its own documented extensions:

- **`GET /plant-categories`** — the doc doesn't list it, but the Species create/edit form needs the global category taxonomy for its dropdown, and building that lookup is a prerequisite for `POST /species` (which validates `category_id` against it) to be usable at all.
- **`GET/POST /plant-varieties`, `GET/PATCH/DELETE /plant-varieties/{id}`** — the `PlantCategory -> Species -> PlantVariety` hierarchy already exists in the schema (Phase 5's own docstring for `PlantVariety` describes it), and cultivar/variety management is a natural part of "species reference data CRUD" (the LLD's own module responsibility statement) even though the doc's abbreviated table only spells out `/species`.

## Referential-integrity delete guard, ahead of the DB's own RESTRICT

Both `plants.species_id` and `plants.variety_id` carry `ON DELETE RESTRICT` (Phase 5's migration 0001) — the database will refuse a delete that would orphan a Plant row. Per the LLD's explicit instruction ("blocked with a `409 conflict` if any plant references it — service-layer referential check ahead of the DB's `ON DELETE RESTRICT` backstop"), `SpeciesService.delete_species`/`PlantVarietyService.delete_variety` query the `plants` table's row count directly (`SpeciesRepository.count_plants_referencing`/`PlantVarietyRepository.count_plants_referencing`) and raise a friendly `ConflictError` before ever attempting the delete — a real, if minimal, use of a table Module 6 (Plant Lifecycle Management, not yet built) will eventually own the full service/API layer for. Reading its row count for this one check doesn't require that layer to exist yet, and this module writes nothing to `plants` — read-only, one query, one purpose.

## Validation: real shape checks, not placeholders

`app/services/validation.py` (shared with Module 4, extended here) gained two new validators, consistent with the project's rule against placeholder validation logic:

- **`validate_growth_curve_baseline`**: `Species.growth_curve_baseline` is `[{"days_since_planting": int, "expected_height_cm": number}, ...]` — every point's two fields are checked for presence, type, and non-negativity (a negative day offset or height is never meaningful, only a caller bug).
- **`validate_disease_susceptibility`**: a flat list of non-empty disease-code strings.
- **Temperature range** (`_validate_temperature_range`, species_service.py-local): `temperature_min_celsius <= temperature_max_celsius`, re-validated on a *partial* update too — updating only `temperature_max_celsius` still checks it against whatever `temperature_min_celsius` currently holds, not just against the value the caller happened to also submit in the same request.
- **Category existence**: `category_id` is checked against the real `PlantCategory` repository on both create and update, not just FK-shaped (a `422`, not a raw DB `IntegrityError`, on an unknown category).

## Search and filtering (FR-4.4)

`GET /species` supports `search` (case-insensitive substring match against `common_name` OR `botanical_name` — `ILIKE` in the real SQLAlchemy repository, `.lower()`-based substring matching in the in-memory fake), `category_id`, and `light_requirement` — exactly the three axes FR-4.4 names ("searched/filtered by name, category, and care attributes"). Offset-based pagination (`?page=&page_size=`), matching `docs/architecture/07-api-design.md` §6's convention for standard bounded lists like this one (species catalogs don't see the high write-rate/concurrent-insert pattern that would justify cursor pagination).

## Update semantics: `None` means "leave unchanged," consistent with Module 4

Several Species fields (`light_requirement`, `soil_type`, the temperature bounds, the two JSON fields) are legitimately nullable — but `update_species`/`update_variety` treat `None` as "the caller didn't touch this field," not "clear it," the exact same tradeoff Module 4's `update_branch` already made and documented for `Branch`'s own nullable contact fields (`address_line2`, `phone`, `email`, ...). A field can be overwritten with a new value through `PATCH`, but not explicitly nulled out — if a future requirement needs that, it gets a dedicated mechanism rather than overloading `None` here.

## Testing

All from `apps/api/`. 53 new tests across four files, all passing alongside the 263 pre-existing Module 1-4 tests (**316 total**):

- `tests/unit/test_species_service.py` (22 tests) — categories listing, create (unknown category, duplicate botanical name, blank name, temperature-range validation, invalid growth-curve/disease-susceptibility shape, full valid payload round-trip), get (not found), list (search filter, category filter), update (every field, botanical-name rename conflict, no-op skips audit, unknown category on update, partial-update temperature re-validation, blank botanical name), delete (success, blocked-when-referenced with the block actually verified to prevent the delete).
- `tests/unit/test_plant_variety_service.py` (12 tests) — create (foreign-species rejection, duplicate name-per-species conflict, blank name), get (not found), list (species filter, whole-org listing with no filter), update (rename, rename-conflict, no-op skips audit), delete (success, blocked-when-referenced).
- `tests/integration/test_species_routes.py` (10 tests) — 401 unauthenticated, categories listing, species list scoped to caller's org (a second org's species verified absent), search filter through HTTP, create, create denied without `species:write`, cross-tenant `GET` rejected with `CROSS_TENANT_ORG`, update, delete (success and referenced-block, both verified end-to-end through a follow-up `GET`).
- `tests/integration/test_plant_variety_routes.py` (9 tests) — 401 unauthenticated, list scoped to org, list filtered by `species_id`, create, create-for-foreign-species rejected (422), cross-tenant `GET` rejected, update, delete (success and referenced-block).

**Coverage**: aggregate across every Module 5 file (`species_service.py`, `plant_variety_service.py`, `routes/species.py`, `routes/plant_varieties.py`) is **96%** (287 statements, 11 missed) — comfortably above the 90% target. `species_service.py` alone is 99% (one unreachable defensive branch); the small remaining gaps in the two route files are the "authenticated but no org membership yet" branches on the collection endpoints, the same low-value-to-test edge case already disclosed in Module 4's own coverage note.

## Validation performed

- `bash scripts/validate_migrations_offline.sh` — unchanged: 58 tables, 22 enums, 41 RLS policies, 18 triggers, 291 seed rows, zero errors (confirms the `Numeric`→`float` annotation fix altered no schema).
- `ruff check` — zero errors across every file this module touched or added.
- `mypy` — zero new type errors; the full-codebase run is still at 22 pre-existing errors (same baseline disclosed in Module 4's doc), one category of which (the `Numeric`/`float` mismatch on `Species`'s two temperature columns) this module's own work actually *fixed* rather than added to.
- `python3 -m pytest` — 316 tests passing (263 pre-existing + 53 new: 34 unit, 19 integration).
- Every route is protected: all seven Module 5 endpoints require authentication (verified live) and the correct `species:read`/`species:write`/`species:delete` permission code from `docs/ux/07-role-permission-matrix.md`, verified both by direct 403 HTTP tests and unit-level service calls.
- Tenant isolation verified: cross-tenant `GET` on both `/species/{id}` and `/plant-varieties/{id}` returns 403 with `CROSS_TENANT_ORG`, asserted directly against the denial's `reason` field.
- Referential-integrity delete guard verified both ways: deleting an unreferenced Species/PlantVariety succeeds (confirmed via a follow-up 404 `GET`); deleting a referenced one is blocked with 409 (confirmed the row still exists afterward, not just that the response code was right).
- Audit logs and domain events generated for every mutation: `species.created/updated/deleted`, `plant_variety.created/updated/deleted` — six new event types, all published through the same `DomainEventPublisher` Module 4 built, all covered by the 96% aggregate coverage figure above.
- OpenAPI documentation is live: booted the real app under `uvicorn` and fetched `/openapi.json` — all seven endpoints appear with summaries, descriptions, and response models; total path count is now 34.
- Booted the real app under actual `uvicorn` against a genuinely unreachable database and Redis: `/healthz` stays up, `/readyz` reports 503, every Module 5 route correctly returns 401 for a missing or garbage bearer token without ever touching the unreachable database, and the server keeps serving subsequent requests throughout.

## What remains unverified

Same disclosed limitation as every prior module: no live PostgreSQL or Redis instance is reachable in this sandbox. `SqlAlchemyPlantCategoryRepository`/`SqlAlchemySpeciesRepository`/`SqlAlchemyPlantVarietyRepository` (the real production implementations, including the `ILIKE` search query and the `plants` table referential-count query) have been validated for correct query construction and exercised end-to-end through the app's HTTP layer against in-memory fakes, but true query-time behavior — search performance/correctness against real data volume, and the `plants` table referential check against actual Plant rows once Module 6 exists — remains unverified against real infrastructure and real Plant data. This should be exercised together with Module 6's own live-database validation, since the two modules' data now genuinely interact (a Plant row is the first real-world thing that can make a Species/PlantVariety delete actually get blocked).
