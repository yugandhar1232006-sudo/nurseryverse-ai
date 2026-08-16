# Authentication — Phase 7B

There is exactly one authentication implementation in this app: the real `apps/api/app/api/routes/auth.py` routes, via the typed OpenAPI client (`03-api-integration-guide.md`). No mock/local auth path exists anywhere, including in tests (`Testing`, below).

## Architecture

```
store/session-store.ts        Zustand: in-memory session state (tokens, user, status)
lib/auth/session-marker.ts    non-sensitive cookie mirror, for proxy.ts only
lib/auth/session-boot.ts      app-boot restoration (silent refresh + /auth/me)
providers/auth-provider.tsx   runs session-boot once, never blocks rendering
lib/auth/use-session.ts       useSession() -- the read side
lib/auth/queries.ts           useMeQuery / useSessionsQuery (TanStack Query)
lib/auth/mutations.ts         useLoginMutation / useLogoutMutation / etc.
lib/auth/login-error.ts       classifies a failed login into a UI state
lib/auth/permissions.ts       pure permission-check functions (05-permission-aware-ui.md)
lib/api/auth.ts               typed wrappers for every /auth/* route
proxy.ts                      Next.js 16 edge proxy -- optimistic, non-authoritative redirect
app/(app)/layout.tsx           the actual, authoritative route guard
```

Split follows `04-state-management.md`: `sessionStore` is client/UI state (the synchronous mirror non-React code — the API client's 401 interceptor — needs), `useMeQuery`/`useSessionsQuery` are server state owned by TanStack Query. `useMeQuery`'s `useEffect` writes each fresh `/auth/me` result into `sessionStore` because React Query v5 removed `useQuery`'s `onSuccess` callback (still present on `useMutation`, which is why the mutations file doesn't need this pattern).

## Authentication flow

**Login** (`app/(public)/login/page.tsx` → `useLoginMutation`): `POST /auth/login` for a token pair, then `GET /auth/me` for the user/permissions snapshot — login alone doesn't return permissions, so both calls are required before the app can render anything permission-aware. `next` (post-login redirect target) is only followed if it starts with `/` and not `//` — an open-redirect guard, since the value comes from a URL query param an attacker could craft.

**Session restoration** (`lib/auth/session-boot.ts`, run once by `AuthProvider` on app boot): attempts `refresh(sessionStore.getState().refreshToken)` — which is `null` on a cold load — then `GET /auth/me` on success. This single code path is what makes restoration work identically in both backend deployment modes (see Token Lifecycle) without a frontend build-time flag: in cookie mode the browser auto-attaches the httpOnly refresh cookie regardless of the `null` body value; in bearer mode `refresh(null)` legitimately fails, and that failure is not an error — it's `sessionStore.clearSession()`, meaning "start out signed out." `AuthProvider` never blocks rendering `children` on this — public routes (Plant Passport, the login page itself) shouldn't wait on an auth check they don't need. A `useRef` guard prevents Strict Mode's dev-mode double-invoke from firing two concurrent restoration attempts.

**Logout / logout-all** (`useLogoutMutation` / `useLogoutAllMutation`): both clear local session state in `onSettled`, unconditionally — even if the backend call itself fails (offline, already-expired token). The user's intent ("log me out") is always honored locally; leaving stale "authenticated" UI up because the network request didn't land would be the wrong failure mode for a security-sensitive action.

**Change password / password-reset confirm**: the backend revokes every refresh token for the account on success — including the current session (`apps/api/app/services/auth_service.py`'s own docstring: "treated as this account may have been compromised"). Both mutations proactively call `clearSession()` on success and redirect to `/login`, rather than leaving the UI showing "signed in" until the next silent refresh fails and surprises the user.

**Email verification**: does **not** gate login. `auth_service.py`'s `login()` never checks `is_email_verified` — an unverified account logs in and uses the app normally. `MeResponse.is_email_verified` only drives `components/layout/email-verification-banner.tsx`, a soft, dismissable-by-navigating-away nudge in the protected layout.

## Token lifecycle

The backend has two deployment modes (`AUTH_USE_REFRESH_COOKIE`, `apps/api/app/core/config.py`, defaults to `false`), and the client supports both **transparently, with no frontend mode flag** — see `03-api-integration-guide.md`'s "Two backend auth deployment modes" for the underlying mechanism (`sessionStore` normalizing an empty `refresh_token` body string to `null`; `credentials: "include"` on every request).

- **Access token**: always in the JSON response body, held only in `sessionStore` (Zustand, in-memory) — never `localStorage`/`sessionStorage`. Attached to every request via `lib/api/client.ts`'s `authRequestMiddleware`.
- **Refresh token**: bearer mode returns it in the body too, held the same way (in-memory only). Cookie mode returns an empty string (normalized to `null`) and the real token lives in an httpOnly cookie the browser manages — this app's JS never sees it, by design.
- **Silent refresh + concurrent-401 dedup**: `lib/api/client.ts`'s `withAuthRetry()` — on a 401, attempts exactly one `POST /auth/refresh` and retries the original call once. A module-level `refreshInFlight` promise means a burst of simultaneous 401s (e.g., a page that fires several authenticated queries at once) triggers exactly one refresh, not one per request — each rotation invalidates the previous refresh token (replay-family revocation, backend-enforced), so multiple concurrent rotations would race and fail each other.
- **No infinite refresh loop**: a second 401 — either the refresh call itself failing, or the retried original call 401ing again post-refresh — calls `sessionStore.clearSession()` and returns the failure. There is no retry-of-a-retry anywhere in this path.
- **`unwrap()` vs `unwrapOnce()`**: `unwrap()` carries the refresh-and-retry behavior described above; `unwrapOnce()` has none of it. Three call sites need `unwrapOnce`, all for the same reason — none of them should trigger *another* refresh attempt off their own 401: `lib/api/auth.ts`'s `refresh()` itself (retrying a failed refresh by refreshing again is nonsensical), and `login()`/`signup()` (both unauthenticated endpoints — a 401 from either means wrong credentials, not "this access token needs refreshing," and routing them through `unwrap` was an actual defect caught by this phase's own test suite: see Testing, below).
- **Bearer-mode reload limitation**: because the refresh token is deliberately never persisted outside memory, a hard page reload in bearer mode cannot silently restore a session — there is nothing left to restore from. Only cookie-mode deployments get true reload-survival, via the httpOnly cookie the browser still holds. See Known Limitations.

## Route protection

Two layers, doing different jobs:

- **`proxy.ts`** (Next.js 16's edge middleware convention — renamed from `middleware.ts`/`export function middleware` to `proxy.ts`/`export function proxy` in Next 16; this app targets 16 from the start, so it uses the current convention) — a fast, optimistic server-side redirect. It cannot see `sessionStore`'s real in-memory state (edge middleware runs before any client JS), so it reads `lib/auth/session-marker.ts`'s `nv_has_session` cookie: a non-sensitive, non-httpOnly, JS-set marker carrying no token, set/cleared by `sessionStore.setUser()`/`clearSession()` alongside the real state changes. `PROTECTED_PREFIXES` is a deliberate allowlist (currently `["/account"]`) — under-protecting here is low-stakes (the client guard and the backend both still enforce it independently); over-protecting is not (accidentally gating a route that must stay public, like the Plant Passport in 7K, would be a real defect).
- **`app/(app)/layout.tsx`** — the actual, authoritative guard. Reads real `sessionStore` state via `useSession()`. `"resolving"` renders a loading skeleton (not a redirect — the session might still turn out to be valid); a settled `"unauthenticated"` redirects to `/login?next=<current-path>` and renders nothing, so protected content never flashes before the redirect fires. Every route nested under this layout is protected by virtue of being there — there's no separate per-page check to remember to add.

Neither layer is the real security boundary. That's the backend, on every request, independent of what either of these does — consistent with `05-permission-aware-ui.md`'s rule for permissions.

## Permission handling

Fully covered by `05-permission-aware-ui.md`; this phase's contribution is the first real consumer. `components/auth/permission-gate.tsx`'s `<PermissionGate>` wraps `usePermissions()`'s `can`/`canAny`/`canAll`, and `components/layout/app-header.tsx` uses it for the Admin badge (`anyOf={["roles:manage", "employees:write"]}`) — driven entirely by the real `permissions: string[]` on `GET /auth/me`'s response, never a hardcoded role name. As always: hiding a control is UX only, the backend re-authorizes every request regardless.

## Security considerations

- **No refresh tokens exposed unnecessarily**: bearer-mode refresh tokens live only in `sessionStore` (in-memory); never written to `localStorage`, `sessionStorage`, or any cookie by this app's own code. Cookie-mode tokens are httpOnly — this app's JS never has a value to expose in the first place.
- **`nv_has_session` marker carries no secret** — presence/absence only, read exclusively by `proxy.ts`, never sent to or trusted by the backend.
- **Concurrent 401s handled safely** — see Token Lifecycle's `refreshInFlight` dedup; without it, a burst of simultaneous requests after token expiry could each rotate the refresh token and invalidate each other.
- **Open-redirect prevention** on the login `next` param (see Authentication Flow).
- **Anti-enumeration UX preserved end-to-end**: the backend gives identical responses for "wrong password" / "unknown email" / "locked account" (a single `authentication_error`, distinguished only by message substring — see `classifyLoginError` below) and for password-reset requests regardless of whether the email is registered. The frontend doesn't add any signal the backend deliberately withholds; `app/(public)/forgot-password/page.tsx` shows the identical success message for every submission.
- **CSRF**: cookie-mode only, handled transparently by `authRequestMiddleware` echoing the `nv_csrf_token` cookie into the `x-csrf-token` header on every request (`03-api-integration-guide.md`).

## Testing

**Vitest + React Testing Library** (`apps/web/test/`): 56 tests across 10 files, run via `npm test`. `test/msw/` intercepts at the real network/fetch layer with MSW (`http`/`HttpResponse`/`setupServer`) rather than mocking `lib/api/auth.ts` or `apiClient` directly — the real `unwrap`/`withAuthRetry`/`ApiError`-parsing logic genuinely runs against these responses, per this phase's "do not mock the entire authentication system" instruction. Coverage: login (success, invalid credentials, account lockout, network failure, server error, loading state, open-redirect prevention), session restoration (valid/invalid/absent refresh token, network failure, partial failure), token refresh (silent refresh-and-retry, concurrent-401 dedup, refresh failure, retried-call-still-401), logout/logout-all (including "still clears locally when the backend call fails"), protected routes (resolving/unauthenticated/authenticated states, redirect-with-`next`), permission-based UI (single/`anyOf`/`allOf`/fail-closed), password reset (request + confirm, including the 422-expired-token state and the client-side mismatch check), email verification (auto-submit-on-mount, success, failure), and the pure `classifyLoginError` classifier.

**Playwright** (`apps/web/e2e/auth.spec.ts`, `apps/web/playwright.config.ts`), run via `npm run test:e2e`: the real authentication flow against a genuinely running backend, no MSW, no stubbing. Each test signs up a fresh, uniquely-emailed user directly against `POST /auth/signup` (there's no signup *page* yet — out of 7B's scope) rather than depending on pre-seeded fixture data. Covers: successful login, invalid credentials, protected-route redirect (with and without a prior login), logout, account lockout (six failed attempts, matching the real `AUTH_MAX_FAILED_LOGIN_ATTEMPTS=5` from `apps/api/app/core/config.py` — the request that *causes* the lock still returns the generic wrong-password message; only the next attempt after that surfaces "temporarily locked"), and the reset/verify pages' invalid-token states.

**This suite could not be execution-verified in this environment** — no `docker`/Postgres here, confirmed via `/readyz` (503) and a live login attempt (500, DNS resolution failure reaching the DB host), the same constraint already on record from the backend's own Module 14 work. `playwright.config.ts` and `e2e/auth.spec.ts` were written and reviewed against the real, already-implemented backend routes (read directly from `apps/api/app/services/auth_service.py` and `apps/api/app/core/config.py`), and `npx playwright test --list` confirms the config and spec parse and collect all 9 tests correctly — but they need a real `docker compose up` (Postgres + Redis + `api`) plus a running `apps/web` (`npm run dev` or build+start) to actually execute. `docker-compose.yml` does not yet include a `web` service for the Next.js app (a disclosed, pre-existing gap noted inline in that file from Module 14, deferred until Phase 7 built something to containerize) — wiring that up is cross-cutting infra work better suited to 7Q (Quality Gate) once more of the app exists, not a 7B blocker.

### Defects found and fixed during this phase's testing

- **`openapi-fetch`'s default `fetch: globalThis.fetch` is captured once, at `apiClient`'s module-load time** (`node_modules/openapi-fetch/src/index.js`) — harmless in production (nothing repatches `globalThis.fetch` after boot) but broke every MSW-backed test: MSW's `server.listen()` patches `globalThis.fetch` in a `beforeAll` hook, which runs *after* `lib/api/client.ts` has already imported and already captured the real, pre-patch fetch, so every request silently bypassed the mock and hit a nonexistent real backend. Fixed in `lib/api/client.ts` by passing `fetch: (input) => globalThis.fetch(input)` — a live lookup on every call instead of a one-time capture.
- **`usePermissions()`'s `state.user?.permissions ?? []` allocated a new array on every selector call** whenever there's no user. Zustand's `useSyncExternalStore`-based subscription compares successive selector results by reference; a fresh `[]` each call never equals the last one, so it looped — a genuine "Maximum update depth exceeded" crash, caught by `<PermissionGate>`'s own test suite, that would have hit any signed-out or still-resolving screen using permission checks. Fixed with a module-level stable `NO_PERMISSIONS` constant in `lib/auth/use-permissions.ts`.
- **`login()`/`signup()` routed through `unwrap()`** (full refresh-and-retry) instead of `unwrapOnce()`. Since both are unauthenticated endpoints, a 401 from either means "wrong credentials," never "token expired" — routing them through the retry path fired a pointless `/auth/refresh` call on every failed login/signup attempt and, as a side effect, called `clearSession()` off an action that was never authenticated to begin with. The user-visible error was always correct either way (the original 401 body is what's ultimately thrown), so this was a wasted round-trip and a confusing side effect rather than a user-facing bug — fixed by switching both to `unwrapOnce()`, matching `refresh()`'s existing precedent.
- **`app/(app)/layout.tsx`'s loading skeleton was missing `role="status"`** — present on this app's other loading indicators (e.g. `verify-email/page.tsx`) but omitted here, an a11y/consistency gap caught while writing the protected-route tests. Added.

All four are described here per the standing rule that defects get explained, fixed, and regression-tested, not silently patched.

## Known limitations

- **Bearer-mode hard reload always requires signing in again** (Token Lifecycle) — a deliberate security tradeoff (no refresh token ever persisted to survive a reload), not a bug, and the backend's actual default mode.
- **`GET /auth/sessions` never populates `is_current`** — `apps/api/app/api/routes/auth.py`'s `list_sessions` never sets it, so every entry always comes back `false`. Fixing this backend-side would need a session/family-id claim added to the JWT — too large a change to fold into this phase. `app/(app)/account/page.tsx`'s Sessions card does not pretend otherwise; it says so explicitly in the UI.
- **Account-lockout detection is a message-substring check** (`classifyLoginError`) — the backend deliberately returns an identical error *code* for wrong-password/unknown-email/locked-account (anti-enumeration), so "locked" vs. "invalid credentials" can only be distinguished by matching `/locked/i` against the message text. This is documented as fragile-by-design: if that backend copy ever changes, this needs updating alongside it.
- **`docker-compose.yml` has no `web` service yet** — see Testing's Playwright section. Deferred to 7Q.
- **No signup UI page** — out of 7B's explicit scope (login, reset, verify, account/session UI only); the Playwright fixture uses the API directly.

## What's built vs. what's next

7B ships everything above. 7C (Application Shell) replaces `app/(app)/layout.tsx`'s minimal header with the full nav (sidebar, breadcrumbs, notification bell, command palette) and is where `nv_has_session`-gated route coverage grows past `/account` as real feature routes land.
