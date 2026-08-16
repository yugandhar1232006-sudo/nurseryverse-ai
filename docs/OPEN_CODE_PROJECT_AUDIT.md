# NurseryVerse AI — OpenCode Project Audit

**Audit date:** 2026-08-16
**Auditor:** opencode (read-only audit, no source files modified)
**Repo state:** `main` branch, **zero commits** — every file is untracked (`??` in `git status`). No `.git` history exists to diff against.

---

## 1. Current project status

NurseryVerse AI is a multi-tenant commercial nursery-management SaaS (FastAPI + PostgreSQL backend, Next.js frontend). The project was built in phases:

- **Phase 1–4 (Product, UX, Design, Architecture):** complete, fully documented (`docs/product/`, `docs/ux/`, `docs/design/`, `docs/architecture/01–13`).
- **Phase 5 (Database):** complete — 18 Alembic migrations, 81 SQLAlchemy tables.
- **Phase 6 (Backend):** complete and approved — 14 modules, 1,159 tests documented passing (see §5, §13 for re-verification caveats).
- **Phase 7 (Frontend):** in progress — sub-phases **7A–7N are implemented and documented**; **7O (Administration) is implemented in code but undocumented** (its doc `docs/frontend/19-administration.md` is referenced but missing); **7P (Testing) partial**; **7Q (Quality Gate: dockerize web, run e2e, frontend CI) not started**.

The frontend is a real, production-shaped implementation: openapi-fetch typed client against the real backend's 215-path OpenAPI schema, real auth flow, real WebSocket notifications, permission-gated routes, and no mock/static/fake data anywhere in production code. The backend has no fake AI responses (real deterministic statistical/heuristic baselines with documented version strings) and no TODO/FIXME/pass-stubs.

**The single most important finding:** the repo has never been committed to git, and the checked-in `apps/web/node_modules` was installed on **Linux ARM64** — it cannot run Vitest or a Turbopack build on this Mac. Both the last recorded `next build` and any `vitest` invocation fail with a missing `@rolldown/binding-darwin-arm64` native binding.

---

## 2. Completed phases

| Phase | Content | Status |
|---|---|---|
| 1 Product | BRD, SRS, personas, FR-1..20, NFRs, user stories (`docs/product/`) | Complete |
| 2 UX | 59-page sitemap/inventory, journeys, permission matrix, workflows (`docs/ux/`) | Complete |
| 3 Design | Design system, component library, all 59 screen specs, tokens, UI states (`docs/design/`) | Complete (README still says "pending approval" — stale) |
| 4 Architecture | 13 docs: high/low-level, backend/frontend/DB/AI/API/security/infra/devops (`docs/architecture/01–13`) | Complete |
| 5 Database | Migrations `0001`–`0006` (schema, seed, RLS, audit, views, triggers) + modules' migrations through `0018` | Complete |
| 6 Backend | Modules 1–14 (`apps/api`), 1,159 tests passing per Module-14 doc | **Complete & approved** |
| 7 Frontend | Sub-phases 7A–7N implemented + 7O admin implemented (undocumented) | **In progress** |

Phase 6 Module 14's own doc states "Phase 7 has not been built in this engagement" — that is a point-in-time statement from the end of Phase 6 and is now **stale**; Phase 7 work has since been done (frontend doc `01` L3 confirms Phase 6 approved).

---

## 3. Completed modules

### Backend — Phase 6 Modules 1–14 (all complete, each with its own architecture doc `docs/architecture/18–30`)
1. Core framework (undocumented — file numbering skips 15)
2. Authentication — JWT RS256 (15-min access), Argon2id, opaque rotating refresh tokens, lockout, email verification, invites (migration `0007`)
3. Authorization — 6 roles, atomic permission codes, `AuthorizationService.authorize()` choke point, denial logging (migration `0008`)
4. Organization — orgs/branches/employees/settings, domain-events outbox (migration `0009`)
5. Catalog — categories → species → varieties (no migration; fixed `Numeric`→`float`)
6. Plant Lifecycle — plant status state machine (migration `0010`)
7. Digital Twin Engine — event-sourced twin, timeline, versions, snapshots, consistency verification
8. Inventory — locations, stock lines, receive/transfer/reserve/adjust/damage/dispose/sell, movements, waste/valuation reports (migration `0012`)
9. Sales / CRM / Passport — quotations, sales orders, sales, invoices, payments, returns, refunds, customers, plant passport + public QR (migrations `0013`, `0014`)
10. AI Platform — 6 prediction modules + recommendation engine + Anthropic Claude assistant + Voyage/pgvector RAG + prediction logging (migration `0015`)
11. Notifications — in-app WebSocket hub + email/SMS/push providers, templates, preferences, retry/backoff + dead-letter (migration `0016`)
12. Reports & Analytics — 9 dashboards, 10 analytics endpoints, report generation (PDF/Excel/CSV), scheduled reports, materialized views (migration `0017`)
13. Administration — 40 routes: users, roles/permissions, feature flags, system config, audit & security events, AI admin, RAG status, retention (migration `0018`)
14. Production Readiness — Prometheus `/metrics`, Celery worker+beat, Docker images, Compose, Nginx, GitHub Actions CI/CD, backup/DR runbook, load test

### Frontend — Phase 7 sub-phases (implemented)
- 7A Foundation, 7B Auth, 7C App Shell, 7D Dashboards, 7E Organization, 7F Plant Catalog, 7G Plant Lifecycle, 7H Digital Twin, 7I Inventory, 7J Sales/CRM, 7K Passport, 7L AI Experience, 7M Notifications, 7N Reports/Analytics, **7O Administration (implemented, undocumented)**

---

## 4. Frontend completion status

Stack: Next.js 16.3 (App Router, Turbopack), React 19.2, TypeScript strict, Tailwind v4, Radix+shadcn-style primitives, TanStack Query v5, Zustand v5, RHF+Zod, openapi-fetch + openapi-typescript (215 paths / 276 schemas in the committed generated schema), Recharts, Framer Motion, sonner.

### Pages connected to real APIs (24 route files, all real)
`/` (9-tab dashboard), `/plants`, `/plants/[id]` (12 tabs incl. digital twin, passport, AI predictions, disease scan), `/plants/species`, `/inventory`, `/inventory/[id]`, `/customers`, `/customers/[id]`, `/sales` (6 tabs: quotations/orders/sales/returns/refunds/reports), `/sales/[id]`, `/sales/orders/[id]` (+invoice panel), `/sales/quotations/[id]`, `/sales/returns/[id]`, `/ai-center`, `/reports`, `/admin` (7O: users/roles/flags/audit/notifications/system tabs), `/account`, `/settings` (org/branches/employees/notifications tabs), `/passport/[token]` (public), and public auth pages: `/login`, `/forgot-password`, `/reset-password`, `/verify-email`.

Every page is permission-gated and backed by TanStack Query hooks calling the real backend through `lib/api/` (openapi-fetch). **No page renders mock/static/demo data.** MSW test handlers and fixtures live only under `test/` and `e2e/`.

### Placeholder pages
- **`/watering`** (`app/(app)/watering/page.tsx:17`) — the **only** genuine `ComingSoon` page. Backend has plant-scoped watering-log routes but no standalone task-list endpoint, so the placeholder is honest. Comment defers it to "Phase 7G" (already shipped — stale comment).
- `/settings` Employees tab shows `ComingSoon` only as a permission-denied fallback (not a stub).

### Pages from the 59-page inventory NOT built (PG codes from `docs/ux/09-page-inventory.md`)
| Page | Status |
|---|---|
| PG-01 Landing/Marketing | Not built (no route) |
| PG-02 Sign Up | **Not built — API client exists (`lib/api/auth.ts:60` `signup()`), no page; signup is only reachable via raw API** |
| PG-06 Accept Invite | Not built (backend `POST /auth/invite/accept` exists) |
| PG-09 Notification Center | Implemented as header overlay, not a standalone route |
| PG-10 AI Assistant | Implemented as persistent overlay panel (`components/assistant/assistant-panel.tsx`), not a standalone route |
| PG-21 Create Plant | Implemented as `RegisterPlantDialog` on `/plants` |
| PG-28 Disease Scan | Implemented inside the plant's AI Predictions tab |
| PG-29/30 Disease Reports list/detail | Not built — only `disease-report-card.tsx` on the plant detail tab; no `/disease-reports` page |
| PG-34/35 Watering tasks/log | ComingSoon (PG-34); PG-35 log-watering exists inside plant tabs |
| PG-39 POS/New Sale | Not built as a POS cart; create-sales-order-dialog exists in `/sales` |
| PG-44/45/46 Invoices | **No backend routes** — deliberately excluded from nav (`nav-config.ts:28-36`) |
| PG-47/48/49/50 Suppliers/Purchase Orders | **No backend routes** — deliberately excluded from nav |
| PG-54 Audit Log viewer | Implemented as Admin → Audit & Security tab |
| PG-56 Billing & Plan | Not built (no backend billing module) |
| PG-57 Roles & Permissions | Implemented as Admin → Roles & Permissions tab |
| PG-59 Integrations | Not built |

### Frontend infra gaps
- **No Docker image / compose `web` service** (`docker-compose.yml` services: postgres, redis, api, worker, beat, nginx only; nginx returns a deliberate 503 on `/`). 7Q work.
- **No frontend CI job** — `ci.yml` builds only api + worker images; no web build/lint/test job.
- **Last recorded `next build` FAILED** (`.next/trace-build`, 2026-08-16 09:04, `run-turbopack` failed) due to the platform binding issue (§9).
- No root `README.md`; `apps/web/README.md` is unmodified `create-next-app` boilerplate.

---

## 5. Backend completion status

**Complete across all 14 modules.** Evidence verified during this audit:

- **215 OpenAPI paths / 276 component schemas** (from committed `apps/web/lib/api/generated/openapi.json` — generated from the real app).
- **19 business routers + health** mounted in `app/api/router.py`: auth, audit, orgs, branches, employees, species/categories, plant-varieties, plants, plant-records, disease-reports, digital-twin, inventory, customers, sales, passport (+public), ai-predictions, ai-assistant, notifications, reports, admin.
- **26 service modules**, all layered (routes → services → repository interfaces → SQLAlchemy repos); import-linter enforces 4 boundary contracts.
- **81 SQLAlchemy tables** across 18 model files; **18 migrations** (`0001`–`0018`), 1:1 with documented modules.
- Auth: RS256 asymmetric JWT, Argon2id (OWASP params), opaque hashed refresh tokens, account lockout, per-endpoint authorization, tenant isolation via app middleware + PostgreSQL RLS (migration `0003`).
- **Zero** `TODO`/`FIXME`/`NotImplementedError`/bare-`pass` in `app/` (only legitimate `except WebSocketDisconnect: pass` drain in notifications).
- Celery worker + beat are real (`app/workers.py`): `retry_due_notifications`, `run_due_scheduled_reports`.

### Disclosed (documented, not hidden) backend gaps
- Disease detection returns typed `ModelUnavailableError` (503) until a trained artifact is deployed — real `preprocess`/`postprocess`, no fabricated "healthy" result.
- RAG knowledge-base retrieval returns `[]` — Voyage client real, but no ingestion pipeline yet.
- Email/SMS/push providers log-and-no-op without credentials (real SMTP client when configured).
- In-memory rate limiter/cache/notification hub; Redis upgrade paths wired.
- Module 11/12 route docstrings still claim "no scheduler exists" — stale after Module 14 added Celery.

---

## 6. Database status

- **18 Alembic migrations**, all immutable, sequentially numbered: `0001` initial schema (49 tables) → `0002` seeded metadata (roles/permissions/feature flags) → `0003` RLS policies → `0004` audit immutability → `0005` views + materialized views → `0006` `updated_at` triggers → `0007` auth security tables → `0008` authorization denials → `0009` organization → `0010` plant lifecycle → `0011` digital twin → `0012` inventory → `0013` sales/CRM/passport → `0014` public QR RLS carve-out → `0015` AI platform → `0016` notifications → `0017` reports/analytics → `0018` administration.
- **81 tables**, 22+ enums, ~40 RLS policies, 18 triggers, 291 seeded rows (per Module-3 doc).
- Postgres 16 + `pgvector/pgvector` image (migration 0001 needs the `vector` extension).
- Backend Module-14 doc reports migrations validated offline (`scripts/validate_migrations_offline.sh`) and schema resolved (`configure_mappers()` across all 81 tables). **No live Postgres exists in this environment** — an actual `alembic upgrade head` has only ever run in the CI design, never executed here.

---

## 7. AI status

**Real, not fake.** Every module records a versioned baseline string and computes real values from persisted data:

| Module | Implementation | Model version |
|---|---|---|
| Growth prediction | Least-squares linear fit over growth timeline, species-baseline fallback | `v1.0.0-linear-baseline` |
| Survival risk | Weighted composite scorer (0.45/0.25/0.15/0.15) over health/severity/trend | `v1.0.0-weighted-risk-baseline` |
| Water recommendation | Species baseline adjusted by soil-moisture/temp readings, clamped | `v1.0.0-rule-baseline` |
| Revenue forecast | Day-of-week seasonal-naive + 95% CI from historical stddev | `v1.0.0-seasonal-naive-baseline` |
| Recommendation engine | Feature-weighted scoring over persisted predictions | `v1.0.0-rule-baseline` |
| Disease detection | Real pipeline up to `ModelRegistry.get()`, then typed 503 (no artifact) | — |
| AI Assistant | Real Anthropic Claude tool-calling loop (`claude-sonnet-4-5-20250929`) with retry/backoff + cost tracking | — |
| RAG | Real Voyage embeddings + pgvector similarity; ingestion pipeline not built → returns `[]` | — |

`InferenceBase.run()` is a `final` template method that structurally enforces **persist-before-return** (FR-8.7). Heavy ML deps (`torch`, `prophet`, `xgboost`, `scikit-learn`) are pinned in `requirements/base.txt` but **never imported** — they are the declared target-framework stack for future trained models.

---

## 8. Remaining work

1. **7O documentation** — write `docs/frontend/19-administration.md` (6 code files reference it; it doesn't exist).
2. **7P — complete frontend test verification** — the 15 feature test files added after the recorded run (Aug 15–16) have no verified passing run.
3. **7Q — Quality Gate**:
   - Add `web` service + `web.Dockerfile` to `docker-compose.yml`/`docker-compose.prod.yml`; extend `nginx.conf` to proxy `/` (currently 503).
   - Add frontend jobs to `.github/workflows/ci.yml` (lint, typecheck, vitest, build, e2e).
   - Execute the full e2e suite (14 specs / 50 tests) against a real stack.
4. **Commit the repository to git** — zero commits exists today.
5. **Fix the platform build issue** — reinstall `node_modules` for darwin-arm64.
6. Optional product pages: Sign Up (PG-02), Accept Invite (PG-06), Landing (PG-01), Disease Reports list/detail (PG-29/30), POS (PG-39), Watering tasks (PG-34) — several require new backend endpoints first (invoices, suppliers, billing are backend-shaped gaps, not frontend).
7. Backend gaps disclosed by design: disease-detection model artifact, RAG ingestion pipeline, real provider credentials, standalone watering-tasks endpoint.

---

## 9. Critical blockers

| # | Blocker | Evidence |
|---|---|---|
| 1 | **Frontend node_modules is Linux-built.** `apps/web/node_modules/@rolldown/` contains only `binding-linux-arm64-gnu/musl`; this Mac needs `binding-darwin-arm64`. Vitest aborts: `Cannot find native binding... Cannot find module '@rolldown/binding-wasm32-wasi'`. Last `next build` failed at Turbopack compile (`.next/trace-build`, 2026-08-16). **Fix:** `rm -rf node_modules package-lock.json && npm i` on this machine. | `npx vitest run` fails; no `.next/BUILD_ID` |
| 2 | **Repo has zero git commits.** Everything untracked; no history, no rollback, `git diff`/`git log` are empty. CI has never run. | `git log` → "does not have any commits yet" |
| 3 | **No Python environment.** No `.venv`; system Python 3.14 lacks pytest/ruff/mypy. The documented 1,159-test backend suite cannot be re-run in this environment. | `python3 -c "import pytest"` → ModuleNotFoundError |
| 4 | **No live infrastructure.** No Docker/Postgres/Redis/nginx. All Docker/Compose/Nginx/CI artifacts are structurally validated only; the e2e suite and `alembic upgrade head` against a real DB have never run. | `docs/architecture/30-module14-production-readiness.md` "Disclosed limitations"; e2e specs self-document "not execution-verified" |
| 5 | **Frontend not deployable as-is.** No `web` Docker image, no compose `web` service, no frontend CI, nginx `/` returns 503. | `docker-compose.yml` / `.github/workflows/ci.yml` |

---

## 10. Bugs / issues found

1. **Missing doc `docs/frontend/19-administration.md`** — referenced by `apps/web/lib/navigation/nav-config.ts:144`, `components/admin/administration-content.tsx:19`, `components/admin/system-panel.tsx:200`, `components/admin/audit-security-panel.tsx:41`, `lib/api/admin.ts:51`, `e2e/administration.spec.ts:10`. File does not exist.
2. **Frontend suite partially unverified** — `apps/web/vitest.log` records a passing run of **22 files / 135 tests** (Aug 15, Linux sandbox). **37 test files exist today**; the 15 feature-test files (plants, inventory, sales, customers, digital-twin, reports, admin, ai-center, assistant, catalog, organization, passport, settings, etc.) have no recorded run.
3. **Documented-but-missing AI endpoints** — UX page inventory (PG-07/PG-31/PG-33) and `07-api-design.md` cite `GET /ai/predictions/summary`, `GET /ai/predictions/growth-summary`, `POST /ai/recommendations/{id}/dismiss`; none exist in the 215-path OpenAPI schema (frontend 7L doc explicitly notes this).
4. **Notification-preferences verb mismatch** — UX doc PG-58 and `07-api-design.md` specify `PATCH /notifications/preferences`; backend implemented `GET/PUT` (frontend uses `PUT`).
5. **Stale backend docstrings** — several Module 11/12 route docstrings say "no scheduler exists in this codebase," now false after Module 14's Celery worker/beat.
6. **Stale Module-14 statement** — "Phase 7 (Frontend) has not been built in this engagement" contradicts the shipped 7A–7O frontend.
7. **Stale READMEs** — `docs/architecture/README.md` (lists only docs 01–12, says "pending approval", omits 13–30); `docs/design/README.md` ("pending approval"); `apps/web/README.md` is create-next-app boilerplate.
8. **Watering page stale comment** — defers to "Phase 7G" which already shipped.
9. **Frontend bearer-mode session loss on hard reload** — documented deliberate tradeoff (`lib/auth/session-boot.ts:33-35`), but a real UX limitation; cookie mode is opt-in (`AUTH_USE_REFRESH_COOKIE`).
10. **Docs/architecture numbering gap** — no `15-*.md` (jump 14 → 16).
11. **`apps/web/.DS_Store` committed into the tree** (untracked) — minor cleanliness.
12. **Doc drift vs implementation** — Phase 4 docs say "Next.js 14+", "five system roles", `src/features/` layout, `/passport/public/{token}` paths; implementation is Next.js 16, six roles, top-level `app/components/lib`, `/public/passport/{token}`.

---

## 11. Technical debt

- **Documentation behind implementation** (7O undocumented; stale status READMEs; Module-14/11/12 docstrings).
- **Heavy unused ML deps** in `requirements/base.txt` (`torch==2.4.1`, `prophet==1.1.6`, `xgboost==2.1.1`, `scikit-learn==1.5.2`) never imported — future-framework placeholder inflating install time/image size.
- **`worker.Dockerfile` duplicates `api.Dockerfile` build stages** (documented deliberate tradeoff).
- **In-memory rate limiter / cache / notification hub** with Redis upgrade paths — must switch for multi-replica production.
- **No TLS in nginx** — TLS block commented out (no cert in repo); HSTS/CSP headers deferred to nginx and unset.
- **`cmdstan` install step in Dockerfiles unverified** (pinned `2.35.0`, never built).
- **No frontend containerization / frontend CI**.
- **`requirements/base.txt` reconstruction risk** — Module-14 doc "Defect 10" flags that the file was accidentally overwritten and reconstructed; recommends diffing against real history (impossible until git history exists).
- **No root README, no CONTRIBUTING, no AGENTS.md, no LICENSE.**

---

## 12. Security concerns

**Overall posture is strong** (defense-in-depth: permission → branch-scope → RLS; Argon2id; RS256 JWT; opaque hashed refresh tokens; account lockout; audit immutability at DB-grant level; CSRF token header; frontend stores tokens in memory only). Items to action before production:

1. **JWT key pair** (`JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY`) and **`PASSPORT_TOKEN_SECRET`** default to `""` — verify `app/core/keys.py` fail-fast behavior in production (documented: fail-fast in prod, ephemeral in dev). Must be set via secrets manager in deployment.
2. **`CORS_ALLOWED_ORIGINS`** defaults to `["http://localhost:3000"]` — must be production domains.
3. **TLS/HSTS/CSP not actually enabled** — nginx TLS block is commented out; security headers commented for later enablement.
4. **The one deliberate unauthenticated surface** — `GET /public/passport/{token}` and `GET /public/qr/{token}` (token-gated; RLS carve-out in migration `0014`). Ensure token entropy and the `PASSPORT_TOKEN_SECRET` in production.
5. **`pip-audit`/`bandit` in CI never executed** (zero commits); Module-14 ran bandit manually: 0 medium/high, 9 confirmed-false-positive lows.
6. **Deploy job is a placeholder** — no real hosting target; production DB credentials not wired anywhere.
7. **Backup/DR scripts never exercised** — first quarterly drill is the actual validation per `infra/backup/DR_RUNBOOK.md`.
8. **No secrets in repo** — verified; `.env.example` contains only dev-safe placeholders.
9. **`@rolldown`/`npm` optional-dependency mishap** suggests `package-lock.json` may pin wrong-platform packages — reinstall fresh and confirm the lockfile is platform-agnostic before committing.

---

## 13. Testing status

| Area | Status | Evidence |
|---|---|---|
| Backend unit + integration | **1,159 tests documented passing** (770 unit + 389 integration) at end of Module 14 | `docs/architecture/30-module14-production-readiness.md` |
| Backend re-run here | **Not possible** — no Python env (no pytest/ruff/mypy) | `python3 -c "import pytest"` fails |
| Frontend Vitest | **22 files / 135 tests passed** on record (Aug 15, Linux sandbox) | `apps/web/vitest.log` |
| Frontend Vitest here | **Fails to start** — rolldown native-binding mismatch (Linux-built node_modules on macOS) | `npx vitest run` → "Cannot find native binding" |
| Frontend unrecorded tests | 15 of 37 test files have no recorded passing run | file listing vs `vitest.log` |
| E2E (Playwright) | **14 spec files / 50 tests written, never executed** (no Chromium/Postgres; no `webServer` config — requires externally running app+backend) | `e2e/*.spec.ts` self-document "not execution-verified" |
| CI pipeline | Exists (`ci.yml`: lint → typecheck → import-boundaries → unit → integration → security → build/push → migration dry-run → deploy gate) but **never run** (zero commits) | `.github/workflows/ci.yml` |
| Frontend tooling status | `npx tsc --noEmit` → **0 errors**; `npm run lint` → **0 errors, 7 warnings** (6× react-hooks/incompatible-library on RHF `watch()`, 1× unused var in MSW test handler) | run during this audit |

---

## 14. Production-readiness status

**Backend (application-sense): production-ready.** Authenticated, authorized, tenant-isolated, audited, fully tested (1,159), lint/typecheck clean, import-boundaries enforced.

**Backend (infrastructure-sense): ready-by-design, unexercised.** Docker images, Compose, Nginx, CI/CD, metrics, Celery, backup/DR all exist and trace to the Phase-4 design, but **nothing has actually run** (no Docker/Postgres/Redis in this environment; CI never executed).

**Frontend: not yet production-ready.**
- Not containerized (no `web` image/compose service), nginx `/` returns 503.
- No frontend CI job.
- Production build not verified on this machine (last build failed on platform binding).
- E2E suite unexecuted; 15 test files unverified.
- Auth session lost on hard reload in the default bearer mode.

**Process-level:** repo never committed → no history, no CI runs, no rollback. This is the biggest production-readiness blocker.

**Overall: NOT deployable today.** Backend artifacts are buildable-in-principle; the frontend has no deployment path at all.

---

## 15. Exact recommended next task

> **Fix the platform build environment and establish git history, in this order:**
> 1. `git add -A && git commit` a first "initial import" snapshot (protects all 7A–7O work and gives the audit/diff a baseline; no secrets exist to leak — verified).
> 2. In `apps/web`: `rm -rf node_modules package-lock.json && npm i` on this Mac to obtain darwin-arm64 rolldown bindings.
> 3. Verify: `npx tsc --noEmit` (0 errors), `npm run lint` (0 errors), `npm run test` (run the full 37-file suite), `npm run build` (first successful local production build).
> 4. Only then proceed to 7Q: add the `web` service + `web.Dockerfile` to compose, extend nginx, add frontend jobs to `ci.yml`, and execute the 50-test e2e suite against a real Docker stack.

After the environment is green, the highest-value follow-ups are: (a) write the missing `docs/frontend/19-administration.md`, (b) close the three missing AI endpoints or explicitly document them out of scope, and (c) set up a Python 3.12 venv to re-run the backend's 1,159 tests and `ruff`/`mypy` as a second baseline.

---

## Appendix — Verified facts (with evidence)

- OpenAPI: 215 paths, 276 schemas — `apps/web/lib/api/generated/openapi.json`.
- Frontend tests: 37 `*.test.{ts,tsx}` files; `vitest.log` = 22 files / 135 passed.
- E2E: 14 specs, 50 `test()` calls.
- Backend: 70 test files (49 unit + 21 integration), `.pytest_cache`/`.ruff_cache`/`.mypy_cache` present.
- Migration count: 18 (`0001`–`0018`); model files: 18.
- Last build: `.next/trace-build` → `next-build` + `run-turbopack` `failed:true` (2026-08-16 09:04).
- ComingSoon usages (non-test): `app/(app)/watering/page.tsx` (real), `app/(app)/settings/page.tsx` (permission fallback); other hits are docstrings describing replaced placeholders.
- Missing files verified: no `packages/` directory; no `docs/frontend/19-administration.md`; no `docs/architecture/15-*.md`; no root README; no LICENSE.
