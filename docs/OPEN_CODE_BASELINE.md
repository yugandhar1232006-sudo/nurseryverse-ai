# NurseryVerse AI — OpenCode Baseline

Reference point for all future frontend/backend work on this machine. Everything below was verified locally on 2026-08-16.

## Environment

| Item | Value |
|---|---|
| Machine | macOS (darwin-arm64) |
| Node | v26.5.0 |
| Package manager | npm 11.17.0 (lockfile: `apps/web/package-lock.json`, `lockfileVersion` 3) |
| Python | 3.14.6 (system) — no `.venv`, no pytest/ruff/mypy installed |
| Git | branch `main`, commits: `dd431aa` (baseline), `5c6fe0d` (test env fix) |

## Git baseline

- `dd431aa` — `chore: initial NurseryVerse AI baseline` (754 files; root `.gitignore` added; `.env.example` files committed by design; no secrets/build artifacts).
- `5c6fe0d` — `fix(test): restore jsdom localStorage for vitest on Node 26` (`test/setup-localstorage.ts` + `vitest.config.ts`). Required because Node 26 defines a shadowing `localStorage` global and vitest 4's `populateGlobal` drops jsdom's Storage, breaking zustand `persist` in every test.

## Frontend verification (all pass on this machine)

| Check | Command | Result |
|---|---|---|
| Typecheck | `npx tsc --noEmit` | 0 errors |
| Lint | `npm run lint` | 0 errors, 7 warnings (6 `react-hooks/incompatible-library` on `form.watch`, 1 unused var in `test/msw/inventory-handlers.ts`) |
| Unit/component tests | `npx vitest run` | 37 files / 242 tests passed |
| Production build | `npm run build` | success (Turbopack, Next.js 16.3.0) |

Test run is a **full 37-file / 242-test pass** — strictly better than the last recorded Linux run (`vitest.log`, Aug 15: 22 files / 135 tests). This resolves the audit's 7P "partial" status: every frontend test file now has a verified passing run.

## Backend status

- **Not runnable locally**: no Python venv, no pytest/ruff/mypy, no Postgres/Redis. The documented 1,159-test backend suite has not been executed in this environment.
- **OpenAPI surface**: 215 paths / 276 schemas in the committed `apps/web/lib/api/generated/openapi.json`.

## Known unavailable infrastructure

- No Docker / Postgres / Redis / nginx running.
- `docker-compose.yml` / `.docker-compose.prod.yml` have **no `web` service**; nginx proxies `/api/*` and `/ws/*` only, so a request to `/` 502s.
- `.github/workflows/ci.yml` is backend-only (lint/typecheck/import-boundaries/unit/integration/security); **no frontend jobs**, never run.
- 14 Playwright e2e specs / 50 `test()` calls exist but were never executed; `playwright.config.ts` deliberately has no `webServer`.

## Known API / frontend mismatches (from the audit, re-verified)

1. **Missing AI endpoints** (documented in UX/API docs but absent from OpenAPI): `GET /api/v1/ai/predictions/summary`, `GET /api/v1/ai/predictions/growth-summary`, `POST /api/v1/ai/recommendations/{id}/dismiss` (all 0 occurrences).
2. **Notification-preferences verb**: backend implements `GET`/`PUT /api/v1/notifications/preferences`; UX doc PG-58 and `07-api-design.md` specify `PATCH`; frontend correctly uses `PUT`.
3. **Watering**: backend only has plant-scoped `GET`/`POST /api/v1/plants/{plant_id}/watering-logs`; no standalone watering-task-list endpoint (hence `/watering` is honestly a ComingSoon page).
4. **Invoices**: only read/payment endpoints exist (`GET /api/v1/invoices/{id}`, `GET {id}/items`, `GET {id}/payments`, `POST {id}/payments`) — no list/create/update; frontend has an invoice panel inside `/sales/orders/[id]`, no standalone invoices pages.
5. **Suppliers / Purchase Orders**: zero routes in OpenAPI; frontend deliberately excludes them from nav.
6. **Billing**: no backend module, no page.

## Remaining frontend work (verified, NOT implemented)

| Item | Status |
|---|---|
| 7O documentation | Missing — `docs/frontend/19-administration.md` referenced by 6 code files, file does not exist (docs/frontend ends at 10) |
| 7Q Quality Gate | Not started — `web` Docker service/image, nginx `/` proxy, frontend CI jobs, e2e execution |
| PG-01 Landing | Not built |
| PG-02 Sign Up | Not built — API client `lib/api/auth.ts:60` and backend `POST /api/v1/auth/signup` exist |
| PG-06 Accept Invite | Not built — backend `POST /api/v1/auth/invite/accept` exists |
| PG-29/30 Disease Reports list/detail | Not built |
| PG-39 POS / New Sale cart | Not built (create-sales-order dialog exists) |
| PG-34 Watering tasks | ComingSoon placeholder only (`app/(app)/watering/page.tsx:17`) |
| PG-44/45/46 Invoices pages | Blocked on backend (see mismatches) |
| PG-47/48/49/50 Suppliers/PO | Blocked on backend (no routes) |
| PG-56 Billing & Plan | Blocked on backend (no module) |
| PG-59 Integrations | Not built |
| 3 documented AI endpoints | Blocked on backend (see mismatches) |
