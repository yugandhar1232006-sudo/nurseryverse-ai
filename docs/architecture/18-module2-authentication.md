# Phase 6, Module 2 — Authentication

Real, running FastAPI code in `apps/api/app/`. This document explains the design decisions the module's requirements forced and records what was actually verified before calling it complete.

## Scope decision: staff-only RBAC

The module spec listed "Customer" among the RBAC roles to support. The already-approved architecture (Phases 1-4) treats customers as a CRM entity only — they never log in; they view a plant's info via the unauthenticated public Passport token (`passports.public_token`, Phase 5), specifically so they don't need an account. Confirmed with the user before building: this module implements auth/RBAC for the six existing staff roles (`platform_admin`, `owner`, `branch_manager`, `org_admin`, `horticulturist`, `sales_staff`) only. Customer accounts remain out of scope; the public Passport path is unchanged.

## Schema change: migration 0007

Phase 5's schema had no columns or tables for refresh-token storage/rotation, email verification, password reset, or account lockout — those are implementation-level needs that only became concrete while building the real login flow, the same way Attachments/Payments were discovered missing at Phase 5. Per this module's explicit rule, migrations 0001-0006 were never touched; everything new is `migrations/versions/0007_authentication_security.py`:

- `users` gained `is_email_verified`, `failed_login_attempts`, `locked_until` (all with `server_default`s, so the `ADD COLUMN` is safe even against a populated table).
- `refresh_tokens` — one row per issued refresh token, doubling as the session/device record (see "Sessions are refresh tokens" below).
- `email_verification_tokens`, `password_reset_tokens` — single-use, expiring, hashed-at-rest.
- `security_events` — a global, non-tenant-scoped auth/security log. `audit_logs` (Phase 5) requires a non-null `nursery_id`; a login attempt happens before any org context is known and may not resolve to a real user at all, so it structurally cannot go in `audit_logs`.
- `knowledge_base_chunks`'s RLS-exemption precedent (readiness review §5) extends here: none of these four new tables carry `nursery_id` or RLS policies — auth is user-scoped, not org-scoped, enforced by every service method filtering on `user_id` from the authenticated request.

Migration 0007 was generated the same mechanical way as 0001 (`scripts/generate_migration_0007.py`, reusing Alembic's own `render_op_text`/`CreateTableOp`/`AddColumnOp`), re-validated with the full offline chain (`scripts/validate_migrations_offline.sh`): 55 tables, 21 enums, all checks passing.

## Password hashing: Argon2id, not bcrypt

`app/core/security.py` uses `argon2-cffi` directly (OWASP's 2023-recommended parameters: `m=19456, t=2, p=1`), replacing the `passlib[bcrypt]` pin from Phase 5's requirements list — that pin predated this module's explicit Argon2id requirement and was never used. `needs_rehash()` lets a future parameter upgrade reach existing users transparently on their next successful login, without a forced mass reset.

## JWT: RS256, asymmetric

Access tokens are signed with a private key; anything that only verifies (a future worker, a resource server) only needs the public key. `app/core/keys.py` requires real, persistent `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY` PEM env vars in production (fails fast at startup if missing) but generates a real, process-cached ephemeral RSA-2048 keypair in dev/test — genuine RS256 signing, just not persisted across restarts, which is what lets a fresh `docker compose up` or `pytest` run work without anyone hand-generating keys first.

## Refresh tokens are opaque, and sessions *are* refresh tokens

Refresh/verification/reset tokens are random opaque strings (`secrets.token_urlsafe(32)`), not JWTs — a JWT can't be individually revoked without a server-side denylist anyway, so for anything needing revocation as a first-class operation, an opaque token whose SHA-256 hash is the only thing ever persisted is both simpler and gives the DB row itself as the natural revocation point. `refresh_tokens` deliberately doubles as the "session" concept the module's Session Management / Device Tracking requirements ask for — a session's lifetime, device info, and revocability *are* exactly a refresh token's lifetime, device info, and revocability in a JWT-based system; a parallel `sessions` table would just be two rows that must always be kept in sync.

## Replay attack prevention

Every refresh token carries a `family_id` (set once at login, preserved across every rotation in that chain) and, once rotated away, a `replaced_by_id` pointing at its successor. Presenting a token that already has `replaced_by_id` set is definitionally a replay — the entire family is revoked, not just the reused token, on the theory that whoever holds one token from a compromised chain may hold others. This is distinct from a plain logout-then-reuse (`revoked_at` set, `replaced_by_id` still null), which is just an expected "invalid token" rejection, not a security event. Verified in `tests/unit/test_auth_service.py::test_replaying_an_already_rotated_token_is_detected_and_revokes_the_family`.

## Account lockout / brute-force protection

Two independent layers: a per-IP rate limiter on `/auth/login` and `/auth/password/reset/request` (fixed-window, Redis-backed in production with a genuine per-process in-memory fallback if Redis is unreachable — see `app/core/rate_limit.py` and `app/main.py`'s `_try_upgrade_to_redis_rate_limiter`), and per-account lockout (`users.failed_login_attempts`/`locked_until`, configurable thresholds) that survives even if an attacker rotates IPs. A locked account gets a distinct, honest message ("temporarily locked") since by that point the attacker has already confirmed the account exists through repeated attempts; wrong-password and unknown-email both return the identical generic message, to prevent enumeration.

## RBAC: permissions from the database, not hardcoded

`app/services/permission_service.py` resolves a user's role and permissions entirely from Phase 5's existing tables (`role_assignments` → `roles` → `role_permissions` → `permissions`) — the seeded data migration 0002 mechanically parsed from `docs/ux/07-role-permission-matrix.md` is the only place a role-to-permission mapping exists. Changing what a role can do is a data change (a new migration seeding different `role_permissions` rows), never a code change. Resolved permissions are embedded directly in the access token's claims at issuance (login/refresh/invite-accept), so authorization checks (Module 3) don't need a second DB round-trip per request to know what a user can do.

## Cookies vs. bearer tokens, and CSRF

Default mode returns the refresh token in the JSON response body — appropriate for an SPA/mobile client that stores it itself, and immune to CSRF by construction (nothing about it is automatically attached by the browser). `Settings.AUTH_USE_REFRESH_COOKIE=true` switches to an httpOnly, Secure, SameSite cookie instead — which is exactly what makes it CSRF-exposed, so cookie mode also issues a non-httpOnly CSRF cookie and requires the matching value echoed in an `X-CSRF-Token` header on `/auth/refresh` and `/auth/logout` (the standard double-submit-cookie pattern).

## Email delivery

`app/services/email_sender.py`'s `SmtpEmailSender` is a real `smtplib` client, not a mock — it requires real SMTP credentials (`Settings.SMTP_*`) to actually deliver mail in a given deployment, the same way Cloudinary/Anthropic integrations elsewhere in this project require their own keys. No SMTP provider was ever selected in Phases 1-4, so nothing is configured to send to in this environment; when unconfigured, it logs the message content instead of silently discarding it (dev convenience) rather than raising and breaking the signup/reset flow. A full templated transactional-email system belongs to Module 12 (Notifications).

## API surface

15 endpoints under `/api/v1/auth`: `login`, `refresh`, `logout`, `logout-all`, `sessions` (list/revoke), `password/change`, `password/reset/request`, `password/reset/confirm`, `verify-email/request`, `verify-email/confirm`, `invite/accept`, `me`. `invite/accept` covers only the authentication half of onboarding (setting a password against an existing `invites` row) — provisioning the `Employee`/`RoleAssignment` rows that give the new user actual org access is Module 5's (User Management) responsibility.

## Validation performed

All from `apps/api/` unless noted:

- `bash scripts/validate_migrations_offline.sh` — 55 tables, 21 enums (including the new `security_event_type`), zero orphan FKs, zero circular dependencies, zero duplicate constraint names, full offline SQL generation clean.
- `python3 -m pytest` — 88 tests, all passing: 11 for `app/core/security.py` (hashing, JWT roundtrip/tamper/expiry/wrong-key rejection), 4 for the rate limiter, 8 for the exception hierarchy, 4 for config, 36 for `AuthService` (login/lockout/rotation/replay/logout/sessions/reset/verify/invite — one test per item in this module's own validation checklist), and 17 HTTP-level integration tests through the real FastAPI app with only the persistence layer swapped for in-memory fakes.
- Booted the real app under actual `uvicorn` (not the test client) and exercised it with `curl` against a genuinely unreachable database: `/healthz` stays up, `/readyz` reports 503 informatively, `/auth/login` returns a proper 500 error envelope (not a raw connection traceback or a crashed process), and the server keeps serving subsequent requests afterward.
- That live smoke test caught a real bug: 500 responses were coming back with `request_id: null`, because the generic exception handler runs in a middleware layer (`ServerErrorMiddleware`) positioned *outside* `RequestContextMiddleware`, after its `finally` had already reset the request-id contextvar. Fixed by also stashing the id on `request.state` (survives past the reset) and re-verified live — a regression test now covers it (`tests/integration/test_health.py::test_unhandled_exception_still_carries_request_id`).

## What remains unverified

Same disclosed limitation as every prior phase: no live PostgreSQL instance is reachable in this sandbox, so `SqlAlchemyUserRepository`/`SqlAlchemyRefreshTokenRepository`/etc. (the real production repository implementations) have been validated for correct SQLAlchemy query construction and exercised end-to-end through the app's HTTP layer against in-memory fakes, but never against a real database. This should be the first thing exercised once an environment with database access is available — ideally as part of the "Module 9: Integration & Testing" pass this project's own phase plan already schedules, but sooner if practical.
