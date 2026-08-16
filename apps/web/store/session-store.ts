import { create } from "zustand";

import type { components } from "@/lib/api/generated/schema";
import { clearSessionMarker, setSessionMarker } from "@/lib/auth/session-marker";

export type MeResponse = components["schemas"]["MeResponse"];

/**
 * Client/UI state only -- per the Phase 4 state-management split, server
 * data (the Me record's freshness, refetching, etc.) belongs to TanStack
 * Query, not here. What lives here is the auth *session* itself: the
 * tokens and the authenticated user snapshot needed to render immediately
 * and to authorize requests, kept in memory only (never localStorage --
 * XSS mitigation per the Phase 7 kickoff's security requirements).
 *
 * `refreshToken` is populated only when the backend is running in its
 * default bearer mode (`AUTH_USE_REFRESH_COOKIE=false`, see
 * apps/api/app/core/config.py and apps/api/app/api/routes/auth.py) --
 * the token then comes back in the JSON response body and must be
 * resent explicitly on `/auth/refresh`. In cookie mode the backend
 * returns an empty string here and instead sets an httpOnly
 * `nv_refresh_token` cookie the browser attaches automatically; the API
 * client (lib/api/client.ts) handles both cases transparently so this
 * store doesn't need to know which mode a given deployment is in.
 */
interface SessionState {
  user: MeResponse | null;
  accessToken: string | null;
  refreshToken: string | null;
  /** Epoch ms; used to proactively refresh slightly before actual expiry. */
  accessTokenExpiresAt: number | null;
  /**
   * `"resolving"` covers the app-boot silent-refresh window (before we
   * know whether an existing session is still valid) -- routes/UI should
   * treat it like a loading state, not "logged out".
   */
  status: "resolving" | "authenticated" | "unauthenticated";
}

interface SessionActions {
  setSession: (params: {
    accessToken: string;
    refreshToken: string;
    expiresIn: number;
    user?: MeResponse;
  }) => void;
  setUser: (user: MeResponse) => void;
  clearSession: () => void;
}

const initialState: SessionState = {
  user: null,
  accessToken: null,
  refreshToken: null,
  accessTokenExpiresAt: null,
  status: "resolving",
};

export const useSessionStore = create<SessionState & SessionActions>()((set) => ({
  ...initialState,

  setSession: ({ accessToken, refreshToken, expiresIn, user }) =>
    set((state) => ({
      accessToken,
      // Empty string means cookie mode (see docstring above) -- normalize to null.
      refreshToken: refreshToken || null,
      accessTokenExpiresAt: Date.now() + expiresIn * 1000,
      user: user ?? state.user,
      status: user ?? state.user ? "authenticated" : state.status,
    })),

  setUser: (user) => {
    // Flips to "authenticated" here (not in setSession) -- this is the
    // point the app actually knows who's signed in, not just that it
    // holds a token pair. See lib/auth/session-marker.ts for why this
    // also mirrors into a non-sensitive cookie for middleware.ts.
    setSessionMarker();
    set({ user, status: "authenticated" });
  },

  clearSession: () => {
    clearSessionMarker();
    set({ ...initialState, status: "unauthenticated" });
  },
}));

/**
 * Non-hook accessors for use outside React (the API client's 401
 * interceptor runs in a plain fetch wrapper, not a component).
 */
export const sessionStore = {
  getState: useSessionStore.getState,
  setState: useSessionStore.setState,
  subscribe: useSessionStore.subscribe,
};
