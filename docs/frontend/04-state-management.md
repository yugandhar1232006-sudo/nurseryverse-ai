# State Management — Phase 7A (Foundation)

## The split (non-negotiable, per Phase 4)

**TanStack Query owns everything that came from the backend.** Any data fetched via `apiClient`/`unwrap()` — plant records, org settings, dashboards, AI predictions — is server state: cached, refetched, invalidated by query key, never duplicated into a Zustand store. `providers/query-provider.tsx` configures the shared `QueryClient`: 30s stale time, no refetch-on-window-focus (avoids surprising refetches during data entry), and a `retry` function that never retries 400/401/403/404/409/422 (retrying won't change those outcomes — 401 is handled separately by the API client's own refresh-retry, not TanStack Query's retry).

**Zustand owns client/UI state that has no backend representation**, or that needs to be read/written outside of React (e.g. the API client's interceptor). Three stores exist after 7A:

### `store/session-store.ts`
The auth session: `user` (the real `MeResponse` from `GET /auth/me`), `accessToken`, `refreshToken`, `accessTokenExpiresAt`, `status` (`resolving | authenticated | unauthenticated`). In-memory only — never persisted to `localStorage`, per the Phase 7 kickoff's explicit XSS-mitigation requirement. Exposes both the React hook (`useSessionStore`) and a plain `sessionStore.getState()/setState()` accessor for `lib/api/client.ts`'s interceptor, which runs outside any component.

`status: "resolving"` exists specifically for the app-boot silent-refresh window (7B will wire this) — before that resolves, the app doesn't yet know if there's a valid session, and that's a different state from "definitely logged out," which route guards need to distinguish (a resolving app shouldn't flash a login redirect before the silent refresh has had a chance to succeed).

### `store/ui-store.ts`
Layout chrome only: sidebar collapsed, mobile nav open, command palette open. `sidebarCollapsed` is persisted to `localStorage` via Zustand's `persist` middleware (`partialize`d to just that one field) — this is a layout preference, not sensitive data, a different category from the session store's tokens.

### `store/notification-store.ts`
The live notification feed pushed over Module 11's WebSocket hub (`/api/v1/notifications/ws`). Holds `notifications`, `unreadCount`, `connectionStatus`. This is client state rather than TanStack Query state on purpose: the initial page *is* fetched via Query (`GET /notifications`, paginated, cacheable), but the WebSocket then pushes incremental updates that need to merge into that list and update the unread count immediately, without waiting on a query-invalidation round trip — the kind of state React Query's request/response model isn't built for. The actual WebSocket connection lifecycle is 7M's work; this store only defines the shape (matching the real `NotificationResponse` schema) and pure state-transition actions so 7M has a stable target.

One documented deviation from earlier planning: the WebSocket authenticates via `?token=<access_token>` as a query parameter (per the real, already-implemented `apps/api/app/api/routes/notifications.py`), not the short-lived-ticket design floated earlier — browsers can't set an `Authorization` header on a WebSocket upgrade request, and the backend's actual, approved Module 11 implementation uses the query-param approach. 7M's connection hook sources the token from `sessionStore.getState().accessToken` at connect time.

## What's deliberately not a store

Form state is React Hook Form's, not Zustand's (see `docs/frontend/02-component-architecture.md`'s form composition section). Anything fetchable from the backend stays in TanStack Query even if it feels like it "belongs" to the UI (e.g. a list's current filter *values* might be local `useState`/URL search params, but the *filtered results* are always a Query, never copied into a store).
