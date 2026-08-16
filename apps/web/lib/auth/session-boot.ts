import type { QueryClient } from "@tanstack/react-query";

import { getMe, refresh } from "@/lib/api/auth";
import { authKeys } from "@/lib/auth/queries";
import { sessionStore } from "@/store/session-store";

/**
 * Runs once when the app boots (`providers/auth-provider.tsx`), before
 * any protected content renders, to answer "is there already a valid
 * session?" without asking the user to log in again unnecessarily.
 *
 * The same code path serves both backend auth deployment modes without
 * needing to know which one is active:
 *
 * - **Cookie mode** (`AUTH_USE_REFRESH_COOKIE=true`): `sessionStore`'s
 *   `refreshToken` is `null` after a hard reload (nothing survives a
 *   reload in memory-only Zustand state, by design -- see
 *   store/session-store.ts's docstring). But the browser still holds the
 *   httpOnly `nv_refresh_token` cookie from the last visit and attaches
 *   it automatically (`credentials: "include"`, already set on every
 *   request by lib/api/client.ts). `refresh(null)` sends
 *   `{ refresh_token: null }` in the body -- the backend's
 *   `_resolve_refresh_token` (apps/api/app/api/routes/auth.py) falls
 *   through to the cookie in this mode, so this succeeds.
 * - **Bearer mode** (the actual current backend default -- see
 *   apps/api/app/core/config.py's `AUTH_USE_REFRESH_COOKIE: bool = False`):
 *   there is no cookie and no persisted token, so `refresh(null)` fails
 *   (400/422/401 depending on how the backend validates a missing
 *   token) exactly as it should. This is not an error to surface to the
 *   user -- it's the expected, secure consequence of never persisting a
 *   refresh token to survive a reload (per the Phase 7 kickoff's "never
 *   store sensitive credentials in unsafe browser storage" requirement).
 *   The practical implication, documented in docs/frontend/06-authentication.md:
 *   **a hard page reload in bearer mode always requires signing in
 *   again.** This is a deliberate security tradeoff, not a bug.
 */
export async function bootSession(queryClient: QueryClient): Promise<void> {
  try {
    const tokens = await refresh(sessionStore.getState().refreshToken);
    sessionStore.getState().setSession({
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
      expiresIn: tokens.expires_in,
    });

    const me = await getMe();
    sessionStore.getState().setUser(me);
    queryClient.setQueryData(authKeys.me(), me);
  } catch {
    // No valid session to restore (first visit, expired/absent refresh
    // token, bearer-mode reload -- see docstring above). Not an error;
    // just means the user starts out signed out.
    sessionStore.getState().clearSession();
  }
}
