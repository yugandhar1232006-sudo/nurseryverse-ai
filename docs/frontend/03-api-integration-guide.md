# API Integration Guide — Phase 7A (Foundation)

## Types come from the real backend, not hand-written

```
apps/api/scripts/export_openapi_schema.py   # dumps the live app.openapi() to JSON
apps/web/lib/api/generated/openapi.json     # the dump (committed — see below)
apps/web/lib/api/generated/schema.d.ts      # openapi-typescript output (committed, generated, not hand-edited)
```

Regenerate after any backend route/schema change:

```bash
cd apps/api && python3 scripts/export_openapi_schema.py   # writes into apps/web/lib/api/generated/openapi.json
cd apps/web && npm run generate:api-types                  # writes schema.d.ts
```

214 paths, 275 component schemas as of this writing. Both generated files are committed (not gitignored) so `npm install && npm run build` works standalone without the Python backend running — the alternative (regenerating in CI on every frontend build) would require standing up the backend as a CI step just to get types, which is unnecessary weight for something that only changes when a route actually changes.

Nobody hand-writes a TypeScript interface for a request/response body. If a type is wrong, the fix is regenerating from the real schema, not patching the generated file.

## The client

`lib/api/client.ts` wraps `openapi-fetch`'s `createClient<paths>()` (`apiClient`), so every call is typed end-to-end from the path string through the request body to the response shape — get an operation wrong and it's a compile error, not a runtime 404.

Two things `apiClient` alone doesn't do, layered on top:

- **Auth header injection** (`authRequestMiddleware`): attaches `Authorization: Bearer <token>` from `store/session-store.ts` and, only when a `nv_csrf_token` cookie is present (cookie-mode deployments), echoes it into `x-csrf-token`. Safe to run unconditionally in bearer-mode deployments (no cookie, no-op).
- **401 refresh-and-retry** (`unwrap()`, `withAuthRetry()`): every feature module calls through `unwrap(() => apiClient.GET(...))` rather than `apiClient` directly. On a 401, it attempts exactly one silent `POST /auth/refresh` (deduplicated across concurrent callers via a shared in-flight promise) and re-issues the original call once. A second 401 clears the session (`sessionStore.clearSession()`), which route guards react to in 7B/7C.

Retry is done by **re-invoking the typed call**, not by cloning/replaying the underlying `Request`. `openapi-fetch`'s response middleware can't safely retry a request with a consumed body stream (POST/PUT/PATCH), so `withAuthRetry` takes a thunk and lets `openapi-fetch` build a fresh request from the original typed arguments instead.

## Two backend auth deployment modes — the client supports both

`AUTH_USE_REFRESH_COOKIE` (`apps/api/app/core/config.py`) defaults to `false`. This matters for the frontend:

- **Bearer mode (default)**: `POST /auth/login`'s `TokenPairResponse` returns both `access_token` and `refresh_token` in the JSON body. The refresh token is held in memory only (`sessionStore`, never `localStorage` — XSS mitigation) and resent explicitly on `/auth/refresh`.
- **Cookie mode** (`AUTH_USE_REFRESH_COOKIE=true`): the backend sets an httpOnly `nv_refresh_token` cookie and a JS-readable `nv_csrf_token` cookie instead, and returns `refresh_token: ""` in the body. The browser attaches the refresh cookie automatically; the client only needs to echo the CSRF cookie into the `x-csrf-token` header (which `authRequestMiddleware` already does unconditionally).

`sessionStore.setSession()` normalizes an empty `refresh_token` string to `null`, and `refreshAccessToken()` in `client.ts` sends whatever's in the store (possibly `null`, which is fine — cookie mode doesn't need it) with `credentials: "include"` set on every request, so the same client code works against either deployment mode without a build-time flag. This is a deliberate design choice made during 7A after reading the actual (not assumed) backend implementation — an earlier planning-stage assumption that the refresh token was always cookie-based turned out not to match the real, already-approved Module 2 default, and the client was built against what the backend actually does rather than silently keeping the wrong assumption.

## Error handling

Every backend error response is one envelope (`apps/api/app/core/error_handlers.py`, `apps/api/app/core/responses.py`):

```json
{ "error": { "code": "string", "message": "string", "context": {} }, "request_id": "string | null" }
```

`lib/api/error.ts`'s `ApiError` normalizes this (and 422's `context.errors` — FastAPI's own `RequestValidationError.errors()` array of `{loc, msg, type}` — flattened into `fieldErrors: Record<field, string[]>`) into one shape. `unwrap()` throws `ApiError` for any non-2xx response; calling code (TanStack Query hooks, form submit handlers) only ever deals with the typed success value or a caught `ApiError` — never a raw `{data, error}` union.

| Status | UX pattern |
|---|---|
| 400 | Toast (`toast.apiError`) — malformed request, not user-fixable via a specific field. |
| 401 | Handled transparently by the refresh-retry; a second 401 signs the user out. |
| 403 | Section-level `ErrorState` or a disabled control with an explanation — never a silent no-op. |
| 404 | `ErrorState` (section) or a dedicated not-found UI for the resource. |
| 409 | Toast, usually with a "refresh and try again" framing (per the default message table). |
| 422 | Field-level, via `useApiFormErrors` → `form.setError`, not a toast. |
| 429 | Toast with the rate-limit message; caller decides whether to disable the trigger briefly. |
| 500/503 | `ErrorState`, with retry where the action is idempotent. |

`lib/toast.ts`'s `messageForStatus` fallback table backs all of these when the backend didn't supply its own `message`.

## Environment

`NEXT_PUBLIC_API_BASE_URL` (`.env.example`), read once through `lib/api/config.ts`. Defaults to `http://localhost:8000`, matching `docker-compose.yml`'s dev `api` service port.
