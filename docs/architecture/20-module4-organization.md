# Phase 6, Module 4 — Nursery & Organization Management

Real, running FastAPI code in `apps/api/app/`. This document explains the design decisions the module's requirements forced and records what was actually verified before calling it complete.

## Schema change: migration 0009

Phase 5's schema had `Nursery`/`Branch`/`Employee` tables but no lifecycle status on `Nursery`, no operating-hours/location/contact columns on `Branch`, no department/position/hired_at on `Employee`, no currency/timezone on `OrgSettings`, and no branch-scoping table for `Invite` (Module 2 built invites without ever exercising branch-scoped ones — that was deliberately deferred to this module). Per the project's migration-immutability rule, migrations 0001-0008 were never touched; everything new is `migrations/versions/0009_organization_management.py`:

- `nurseries.status` (new `nursery_status` enum: `active`/`archived`) — the tenant root had no soft-delete concept at all; "Archive Nursery" surfaced the gap.
- `branches.operating_hours` (JSON), `latitude`/`longitude` (`Numeric(9,6)`), `phone`, `email`.
- `employees.department`, `employees.position` (free text, not enums — no fixed product-wide vocabulary), `employees.hired_at` (date).
- `org_settings.default_currency` (ISO 4217, default `USD`), `org_settings.default_timezone` (IANA, default `UTC`).
- `invite_branch_scopes` — mirrors `role_assignment_branch_scopes`' shape, so an invitation can carry the same "which branches" grant its resulting `RoleAssignment` will get once accepted.
- `domain_events` — an append-only outbox table (`event_type`, `aggregate_type`, `aggregate_id`, `nursery_id`, `actor_user_id`, `payload` JSON, `request_id`, `occurred_at`), distinct from `audit_logs` (human-mutation review) and `security_events`/`authorization_denials` (auth lifecycle) — this is the "what happened" stream a future notifications/analytics consumer subscribes to, not a UI-facing table. RLS policy hand-added for it (migration 0003 isn't touched).

Generated the same mechanical way as every prior migration (`scripts/generate_migration_0009.py`), re-validated with the full offline chain: **58 tables, 22 enums, 41 RLS policies, 18 triggers, 291 seed rows, zero errors across 2,313 lines of generated SQL** (0001→0009).

## A defect found and fixed before this module could be trusted: `get_db_session` never committed

While building this module's first real-database write path, `apps/api/app/db/session.py`'s `get_db_session()` was discovered to `yield` a session and then simply `close()` on clean exit — **never calling `commit()`**. `AsyncSession.close()` implicitly rolls back any pending transaction. Every write issued by every route in Modules 1-3 (signup, login, invite creation, refresh-token rotation, everything) was, against a real Postgres connection, silently discarded at the end of the request. This was invisible until now because every prior module's test suite ran exclusively against in-memory fake repositories, which have no transaction to roll back.

Fixed to `try: yield session; await session.commit() except Exception: await session.rollback(); raise`, with a regression test (`tests/unit/test_db_session.py`) that exercises the *real* SQLAlchemy commit/rollback semantics against a throwaway model and an in-memory `sqlite+aiosqlite:///:memory:` engine (added `aiosqlite` to `requirements/dev.txt` for this — the only place in the test suite that touches a real, if disposable, database rather than a fake repository). Three tests: commits on clean completion, rolls back on exception, yields a usable session in between. This fix is a prerequisite for this module's `POST /orgs` route, which orchestrates two service calls (`OrganizationService.create_nursery` then `EmployeeService.provision_owner`) in one request and depends on both succeeding or both rolling back together.

## Domain events: an outbox, not a new audit trail

The module's requirement to "Generate Domain Events: NurseryCreated, NurseryUpdated, BranchCreated, ..." is a distinct concern from `audit_logs` (which already exists and which every service method also writes to for its own reason — human-readable before/after diffs for the admin UI). `app/domain_events/events.py` defines frozen dataclasses (`BaseDomainEvent` subclasses) carrying only the facts of what changed; `app/domain_events/publisher.py`'s `DomainEventPublisher.publish()` is the single place an event dataclass becomes a persisted `domain_events` row. Services never write to that table directly — they build an event and call `publisher.publish(event, request_id=...)`, so "how an event gets JSON-serialized and timestamped" is defined exactly once. Ten event types were implemented: `NurseryCreated/Updated/Archived`, `BranchCreated/Updated/Archived`, `EmployeeInvited/Activated/Transferred/Removed`.

## Real validation, not placeholders

Per the project's explicit rule against placeholder/fake validation logic, `app/services/validation.py` implements genuine checks, not stubs:

- **Timezone**: `zoneinfo.available_timezones()` (Python's stdlib IANA tzdata) — 599 real timezone names available in this sandbox, not a hardcoded allow-list.
- **Currency**: regex-shaped ISO 4217 check (three uppercase letters) — a full currency-code registry is a product decision for a future settings-management module, not this one; the shape check is what prevents garbage input today.
- **Country**: regex-shaped ISO 3166-1 alpha-2 check, same reasoning.
- **Hex color**: `#RRGGBB` regex, for `branding_primary_color`.
- **Operating hours**: structural JSON validation — each day key (`mon`...`sun`) is either `null` (closed) or `{"open": "HH:MM", "close": "HH:MM"}` with `open < close`, enforced by `app/services/branch_service.py` at the service layer (not a Postgres CHECK constraint — the shape is an application concern and JSON CHECK constraints are painful to evolve).

## Multi-tenancy: no hardcoded role names in business logic

Consistent with Module 3's RBAC principle, `EmployeeService` never special-cases `"owner"` or `"branch_manager"` by name in its actual business logic (only in an explanation string and in the two callers — `provision_owner` and `transfer_ownership` — that must resolve a *specific* system role by code, which is a legitimate, product-defined operation, not a business-logic shortcut). `branch_ids` is accepted exactly as the caller provides it: zero branch IDs means an org-wide grant (no `RoleAssignmentBranchScope` rows — matching `ResolvedAccess.is_org_wide()`'s "absent rows == every branch" semantics from Module 3), one or more means branch-scoped. Which shape is "correct" for a given role is a product/UI convention the inviting admin follows, not something this service enforces by name-matching.

## REST API design: matching the pre-approved shape, not inventing one

`docs/architecture/07-api-design.md` (approved in Phase 4) specifies flat collections, not nested ones: `GET/PATCH /orgs/{id}`, `GET/POST /branches`, `GET/PATCH/DELETE /branches/{id}`, `GET /employees`, `POST /employees/invite`, `GET/PATCH /employees/{id}`, `POST /employees/{id}/deactivate`. Three extensions beyond that minimal list, each a genuine requirement the doc's endpoint list simply didn't spell out:

- **`POST /orgs`** — the doc lists no org-creation endpoint at all, but "Create Nursery" is an explicit Module 4 requirement and the normal onboarding flow (`POST /auth/signup` then `POST /orgs`) needs one. The caller must have no existing org membership (v1's one-org-per-user constraint) and becomes the new org's Owner in the same request/transaction via `EmployeeService.provision_owner`.
- **`POST /employees/{id}/transfer-branches`** — "Transfer Staff / Branch Reassignment" is an explicit requirement that doesn't fit a plain `PATCH` (it has its own domain event and its own immediate-cache-invalidation side effect, not just a field update).
- **`POST /orgs/{id}/transfer-ownership`** — "Ownership Transfer" is explicit; it lives on the Orgs resource (it changes who holds the org's single Owner role — a whole-org operation) rather than on Employees.

`GET /orgs/{id}/dashboard-summary` and `GET /branches/{id}/dashboard-summary` (also in the doc) are out of scope — they depend on plant/inventory/sales data that doesn't exist until Modules 5+.

### The flat-resource authorization problem, and how it's solved

`/branches/{id}` and `/employees/{id}` carry no `nursery_id` in their path — Module 3's `require_org_match`/`require_branch_match` dependencies assume the tenant id is already sitting in `request.path_params`, which a flat resource route doesn't have. Rather than build a parallel authorization mechanism, `app/api/deps.py` exposes two existing internals as public aliases — `request_context` and `raise_if_denied` — and each by-id route handler in `branches.py`/`employees.py` does fetch-then-authorize: load the resource first (which reveals its real `nursery_id`), then make one manual `AuthorizationService.authorize()` call with that value. A cross-tenant branch or employee id is rejected with exactly the same `CROSS_TENANT_ORG` denial and audit trail as every path-scoped route in the system — just constructed one step later. The collection routes (`GET`/`POST /branches`, `GET /employees`, `POST /employees/invite`) don't have this problem at all: their org is always the caller's own (`TenantContext.org_id`), resolved via the ordinary `require_permission` dependency, with no path parameter to reconcile.

`POST /orgs` has the opposite shape problem (no `{id}` because none exists yet) and is handled with a direct `PermissionService.resolve_for_user` check for "does this caller already belong to an org" rather than any `require_*` dependency.

## Testing

All from `apps/api/`. 86 new tests across six files, all passing alongside the 177 pre-existing Module 1-3 tests (**263 total**):

- `tests/unit/test_organization_service.py` (14 tests) — create/get/update/archive Nursery (including the no-op-update-skips-audit case and updating every field), get/update Settings, currency/timezone validation rejecting bad input.
- `tests/unit/test_branch_service.py` (21 tests) — create (nursery-not-found, duplicate name, blank name, bad country/timezone/coordinates/operating-hours), get, update (every field, coordinate re-validation on a partial update, rename conflict, rename-to-self is safe), archive (including double-archive conflict), list (active-only default, `include_inactive`, scoped to nursery).
- `tests/unit/test_employee_service.py` (18 tests) — invite (unknown role, foreign branch, duplicate pending invite, already-active-member conflict), `provision_owner`/`provision_from_invite` (org-wide vs. branch-scoped grants verified against `PermissionService.resolve_for_user`, not just the returned `Employee` row), transfer-branches (inactive-employee rejection, actual scope change verified through the permission resolver), remove (immediate access revocation verified the same way), transfer-ownership (role swap, same-user rejection, current-owner mismatch, new-owner-must-already-be-employee).
- `tests/integration/test_organization_routes.py` (11 tests) — 401 unauthenticated, `POST /orgs` making the caller Owner (verified via the permission resolver, not just the response body), 409 on double-org-creation, 403 without `org:read`/cross-tenant, settings round-trip, `org:delete`-gated archive and ownership-transfer (verified Org Admin *cannot* archive or transfer ownership, only Owner can).
- `tests/integration/test_branch_routes.py` (11 tests) — list scoped to caller's org (a second org's branch is verified absent), create, cross-tenant `GET` rejected with `CROSS_TENANT_ORG`, 404 for a real-but-nonexistent id, a branch-scoped role reading its own assigned branch, update denied for a read-only role, archive denied without `branch:delete`.
- `tests/integration/test_employee_routes.py` (11 tests) — list scoped to org, invite (success, permission-denied, unknown-role 422), cross-tenant get rejected, profile update, transfer-branches (end-to-end through the permission resolver), deactivate (end-to-end access revocation verified), deactivate denied without `employees:delete`.

**Coverage**: `app/services/organization_service.py`, `app/services/branch_service.py`, and `app/domain_events/` are at **100%** line coverage. `app/api/routes/organizations.py` is **100%**; `branches.py`/`employees.py` are 94-96% (the few uncovered lines are the "authenticated but no org membership yet" branches on the collection routes — reachable in principle, low product value to test given `POST /orgs` is the very next call such a user would make). `app/services/employee_service.py` is 97%. **Aggregate across every Module 4 file: 98%** (610 statements, 10 missed), comfortably above the 90% target.

## Validation performed

- `bash scripts/validate_migrations_offline.sh` — 58 tables, 22 enums (including the new `nursery_status`), 41 RLS policies, 18 triggers, 291 seed rows, zero errors across the full 0001→0009 chain.
- `ruff check` — zero errors across every file this module touched or added (`app/api/routes/{organizations,branches,employees}.py`, `app/api/router.py`, `app/api/deps.py`'s Module 4 additions, all three service files, all three schema files, the domain-events package, the repository additions, and every new test file).
- `mypy` — zero new type errors. The full-codebase run shows 22 pre-existing errors (a `dict[int, ...]` vs `dict[int | str, ...]` mypy-invariance false positive already present in Module 2/3's `auth.py`/`audit.py`, plus a handful of unrelated Module 1/5-stub forward-reference and third-party-stub gaps) — none are in a file this module authored or modified; this module's own `_ERROR_RESPONSES` dicts are explicitly typed `dict[int | str, dict[str, Any]]` specifically to avoid adding to that count.
- `python3 -m pytest` — 263 tests passing (177 pre-existing + 86 new: 53 unit, 33 integration).
- Every route is protected: all twelve Module 4 endpoints require authentication (verified live — see below) and the correct permission code from `docs/ux/07-role-permission-matrix.md` (`org:read/write/delete`, `branch:read/write/delete`, `employees:read/write/delete`), verified both by direct unit assertion and by HTTP-level 403 tests for a role that lacks the permission.
- Tenant isolation verified: cross-tenant `GET` on both `/branches/{id}` and `/employees/{id}` returns 403 with `AuthorizationDenialReason.CROSS_TENANT_ORG`, asserted directly against `harness.denials.denials[-1].reason`, not just the status code.
- Audit logs generated: every service mutation writes an `AuditLog` row with a real before/after diff (or explicitly skips it for a genuine no-op update, so audit history isn't polluted with empty diffs) — unit-verified directly.
- Domain events generated: all ten required event types are published; `DomainEventPublisher`/`app/domain_events/events.py` at 100% coverage.
- OpenAPI documentation is live: booted the real app under `uvicorn` and fetched `/openapi.json` — all twelve endpoints appear with summaries and response models.
- Booted the real app under actual `uvicorn` against a genuinely unreachable database and Redis: `/healthz` stays up, `/readyz` reports 503, every Module 4 route correctly returns 401 for a missing or garbage bearer token without ever touching the unreachable database (JWT decoding fails before any repository call), and the server keeps serving subsequent requests throughout.

## What remains unverified

Same disclosed limitation as every prior module: no live PostgreSQL or Redis instance is reachable in this sandbox. `SqlAlchemyNurseryRepository`/`SqlAlchemyBranchRepository`/`SqlAlchemyEmployeeRepository`/`SqlAlchemyDomainEventRepository` (the real production implementations) have been validated for correct query/flush construction and exercised end-to-end through the app's HTTP layer against in-memory fakes, and the `get_db_session` commit/rollback fix has been verified against a real (if disposable, in-memory SQLite) database engine — but true multi-tenant row-level-security enforcement at query time, and the full `POST /orgs` → `provision_owner` transaction's atomicity under a real Postgres connection, remain unverified against real infrastructure. This should be exercised as soon as a database-and-Redis-attached environment is available, per the project's own "Module 9: Integration & Testing" phase.
