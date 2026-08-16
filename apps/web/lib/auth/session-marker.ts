/**
 * A non-sensitive, JS-only "am I logged in" marker cookie -- exists
 * solely so `middleware.ts` (which runs on the edge server, before any
 * client JS, and therefore cannot see `useSessionStore`'s in-memory
 * state) has *some* signal to make a fast redirect decision with.
 *
 * Why this is needed: in the backend's default bearer-token-auth mode
 * (see store/session-store.ts's docstring), there is no cookie of any
 * kind involved in the auth flow at all -- tokens live only in browser
 * JS memory. Middleware genuinely cannot distinguish "not authenticated"
 * from "authenticated via bearer tokens the server can't see" in that
 * mode. Without this marker, middleware would either have to (a) always
 * pass every request through unchecked (no server-side redirect ever,
 * even for the common case of an obviously-signed-out visitor hitting a
 * protected URL directly), or (b) redirect based on the *absence* of the
 * real `nv_refresh_token` cookie -- which would incorrectly redirect
 * every authenticated bearer-mode user, since that cookie only exists in
 * cookie-mode deployments.
 *
 * This marker carries no secret (just presence/absence, no token value),
 * is not `httpOnly` (it has to be settable from client JS, since that's
 * the only place that knows the real auth state), and is never read by
 * the backend or sent as authentication -- it is exclusively a same-
 * origin hint for this Next.js server's own middleware. The client-side
 * protected-layout guard (app/(app)/layout.tsx) remains the authoritative
 * check regardless of what this cookie says; middleware treats it as
 * optimistic, not a substitute for that guard or for the backend's own
 * authorization (which is the real security boundary, per the Phase 7
 * kickoff's "never trust the client").
 *
 * Deliberately a session cookie (no `max-age`), not persistent: it
 * should not outlive the browser tab any more than the in-memory tokens
 * it's mirroring would in bearer mode.
 */
const SESSION_MARKER_COOKIE = "nv_has_session";

export function setSessionMarker(): void {
  if (typeof document === "undefined") return;
  document.cookie = `${SESSION_MARKER_COOKIE}=1; path=/; samesite=lax`;
}

export function clearSessionMarker(): void {
  if (typeof document === "undefined") return;
  document.cookie = `${SESSION_MARKER_COOKIE}=; path=/; max-age=0; samesite=lax`;
}

export { SESSION_MARKER_COOKIE };
