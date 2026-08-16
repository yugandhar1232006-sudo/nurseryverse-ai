# Backend Architecture

FastAPI, Python 3.12, async throughout. This document is what Phase 6 (Backend implementation) builds against directly.

## 1. FastAPI Structure / Folder Organization

```
apps/api/
├── app/
│   ├── main.py                     # FastAPI app factory, mounts routers/middleware
│   ├── api/
│   │   └── v1/
│   │       ├── router.py           # aggregates all v1 routers under /api/v1
│   │       └── endpoints/          # one module per feature (auth.py, plants.py, ...)
│   ├── core/
│   │   ├── config.py               # pydantic-settings, env-driven, fail-fast on missing required vars
│   │   ├── security.py             # JWT issue/verify, password hashing
│   │   ├── logging.py              # structlog configuration
│   │   └── exceptions.py           # domain exception hierarchy + handlers
│   ├── domain/                     # framework-free entities, value objects, domain exceptions
│   ├── models/                     # SQLAlchemy 2.0 ORM models (one file per aggregate)
│   ├── schemas/                    # Pydantic v2 request/response DTOs (one file per feature)
│   ├── repositories/               # data access, one per aggregate root
│   ├── services/                   # business logic / use cases, one package per module (per LLD)
│   ├── ai/                         # AI modules (full detail in 06-ai-architecture.md)
│   ├── workers/                    # Celery app + task modules
│   ├── websockets/                 # connection manager, channel handlers
│   ├── reports/                    # PDF/Excel/CSV generators
│   ├── integrations/               # external service adapters (cloudinary, claude, email, sms)
│   ├── middleware/                 # auth, tenant-scoping, logging, rate limiting
│   └── db/                         # session factory, base model, RLS helpers
├── migrations/                     # Alembic (Phase 5)
└── tests/
```

## 2. Feature Modules & Import Boundaries

Each module in `02-low-level-design.md` maps to: `api/v1/endpoints/<module>.py` (controller), `schemas/<module>.py` (DTOs), `services/<module>/` (use cases), `repositories/<module>_repository.py` (data access), and contributes entities to `models/`. **Enforced import direction:** `api → services → repositories → models`; `domain/` is importable only by `services/`; no layer imports "upward." This is enforced in CI via an import-linter rule (`10-devops.md`'s CI pipeline), not just convention — a PR that violates the boundary fails the build.

## 3. Repository Pattern

Every aggregate root (Plant, Sale, Invoice, etc.) has exactly one repository class owning all SQL/ORM query logic for that aggregate. Repositories expose intention-revealing methods (`get_active_plants_by_branch()`, not a generic `find()` that leaks query-building to the caller). Repositories return domain/ORM entities, never raw rows or dicts — the service layer never constructs a query itself. This is what makes the service layer unit-testable against a fake repository without a database.

## 4. Service Layer

Services orchestrate one or more repositories inside a single transaction boundary per use case (e.g., `SalesService.create_sale()` owns the transaction spanning `sales`, `sale_items`, and the `InventoryService`/`PlantService` calls it makes). Services are the only layer allowed to call other services (a repository never calls another repository directly, and endpoints never call repositories directly) — this keeps cross-module coordination (like Sales calling Inventory) explicit and testable rather than implicit at the data layer.

## 5. Dependency Injection

FastAPI's `Depends()` graph wires the full chain: DB session → repository instances → service instances → endpoint parameter. Every repository/service is defined behind a Python `Protocol` interface so tests inject fakes/mocks without touching the database (supports NFR-8.3's coverage requirements without every test paying a real-DB cost). Cross-cutting dependencies (`current_user`, `require_permission("plants:write")`, `tenant_context`) are themselves DI-resolved, composed into endpoint signatures declaratively.

## 6. Authentication

JWT (RS256), access token (15 min) + refresh token (14 day, rotating, hashed at rest, revocable via a Redis-backed denylist keyed by token ID). `core/security.py` owns issuance/verification; `middleware/auth.py` resolves the bearer token on every request into a `RequestUser` context object (id, org_id, branch_ids, role, permissions) attached to `request.state`, consumed by every downstream dependency. Full detail in `08-security-architecture.md`.

## 7. Authorization

`require_permission("<module>:<action>")` is a FastAPI dependency factory — every mutating and most read endpoints declare it explicitly in their route signature (not inferred). Branch-scoped (`B`) permissions additionally check `resource.branch_id in request.state.user.branch_ids` at the service layer before any write, in addition to the PostgreSQL RLS policy that would reject the query even if the application check were somehow bypassed (defense in depth, per NFR-4.3). Permission codes and role mappings exactly mirror `docs/ux/07-role-permission-matrix.md` — that document is the source of truth; this is its enforcement mechanism.

## 8. Middleware Stack (execution order)

1. **Request ID + structured logging** — assigns a correlation ID, logs request start/end with timing.
2. **CORS** — restricts to the configured frontend origin(s) only.
3. **Rate limiting** — Redis token-bucket, stricter buckets for `/auth/*` and `/ai/*` endpoints.
4. **Authentication** — resolves JWT → `RequestUser`, or passes through for the small set of unauthenticated routes (`/auth/*`, `/passport/public/*`, `/healthz`).
5. **Tenant scoping** — sets PostgreSQL session variables (`app.current_org_id`, `app.current_branch_ids`) for the request's DB connection, activating RLS policies for every query that follows.
6. **Exception handling** (outermost, wraps the rest) — catches domain exceptions and maps them to the standard error envelope.

## 9. Background Jobs

Celery (Redis broker + result backend), four named queues: `ai` (inference jobs — isolated so a burst of AI work doesn't starve notification delivery), `reports` (PDF/Excel/CSV generation), `notifications` (email/SMS/push dispatch), `maintenance` (scheduled digest jobs, invoice overdue scan, watering schedule recalculation, DB housekeeping). Celery Beat drives all scheduled (non-event-triggered) jobs — nightly revenue forecast, invoice overdue scan, notification-escalation checks. Workers share the same `app/services/` and `app/repositories/` code as the API process (imported, not duplicated) — a Celery task is a thin wrapper calling the same service method a request handler would call.

## 10. WebSockets

A single `/ws/{channel}` endpoint family (`dashboard`, `notifications`, `inventory`, `ai`), authenticated via a short-lived ticket issued by `POST /ws/ticket` (avoids putting a long-lived JWT in a query string). `websockets/connection_manager.py` tracks active connections per org/branch/channel in-process, with Redis pub/sub as the fan-out mechanism across multiple API worker processes (a notification published by any worker reaches all connected clients regardless of which worker holds their socket).

## 11. API Versioning

URL-path versioning (`/api/v1/...`), per `07-api-design.md`. A v2 would be introduced as an entirely new router mounted alongside v1 (not a breaking in-place change), with v1 maintained on a documented deprecation timeline — no versioning scheme more elaborate than this is warranted at current scale.

## 12. Logging

`structlog`, JSON output to stdout (container-log-driver-friendly, per NFR-10.1), every log line carries the request correlation ID and, where applicable, `org_id`/`user_id`. Log levels: `DEBUG` (local dev only), `INFO` (request lifecycle, business events), `WARNING` (handled exceptions, degraded-mode operation), `ERROR` (unhandled exceptions, also forwarded to Sentry). Sensitive fields (passwords, tokens, full JWT) are never logged — a redaction filter is applied at the logging boundary, not left to individual call sites to remember.

## 13. Configuration

`core/config.py` (pydantic-settings) is the single source of runtime configuration, populated from environment variables (`.env.example` is the canonical list of required/optional vars). Settings validate at process startup — a missing required var fails the container immediately rather than failing on the first request that happens to need it (fail-fast, supports NFR-3.4/health-check reliability). No configuration value is hardcoded in business logic anywhere in `app/services/` or `app/domain/`.

## 14. Exception Handling

A typed domain exception hierarchy (`core/exceptions.py`): `DomainError` (base) → `ValidationError`, `NotFoundError`, `AuthenticationError`, `AuthorizationError`, `ConflictError` (e.g., `InvalidStatusTransitionError`, `InsufficientStockError`), `PlanLimitExceededError`, `ExternalServiceError` (Cloudinary/Claude/email failures). A single global exception handler maps each type to its HTTP status and the standard error envelope (`{code, message, details, request_id}` — per `07-api-design.md` §3); unhandled exceptions fall through to a generic 500 with no internal detail leaked to the client (NFR-6.2), full detail logged server-side and sent to Sentry.
