"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";

import { getMe, listSessions } from "@/lib/api/auth";
import { useSessionStore } from "@/store/session-store";

/**
 * Query key factory -- centralized so a mutation elsewhere (e.g. Module
 * 4's employee-profile update, once 7E exists) can invalidate
 * `authKeys.me()` without importing string literals.
 */
export const authKeys = {
  all: ["auth"] as const,
  me: () => [...authKeys.all, "me"] as const,
  sessions: () => [...authKeys.all, "sessions"] as const,
};

/**
 * `GET /auth/me` as server state, per docs/frontend/04-state-management.md's
 * split: TanStack Query owns the fetch/cache/refetch, `useSessionStore`
 * holds the synchronous mirror non-React code (lib/auth/permissions.ts,
 * the API client interceptor) needs. `providers/auth-provider.tsx`'s boot
 * sequence primes this query's cache directly via `queryClient.setQueryData`
 * so mounting this hook after boot doesn't trigger a redundant fetch.
 *
 * Only enabled once there's an access token to authenticate the request
 * with -- avoids an inevitable 401 on every cold boot before restoration
 * has had a chance to run.
 */
export function useMeQuery() {
  const hasToken = useSessionStore((state) => state.accessToken !== null);

  const query = useQuery({
    queryKey: authKeys.me(),
    queryFn: getMe,
    enabled: hasToken,
    staleTime: 60_000,
  });

  // React Query v5 removed useQuery's onSuccess callback -- this effect
  // is the replacement mechanism for keeping the Zustand mirror
  // (sessionStore.user, read by lib/auth/permissions.ts and anything
  // outside React) in sync whenever this query resolves with fresh data,
  // e.g. after lib/auth/mutations.ts's `useConfirmEmailVerificationMutation`
  // invalidates this key.
  useEffect(() => {
    if (query.data) {
      useSessionStore.getState().setUser(query.data);
    }
  }, [query.data]);

  return query;
}

/**
 * `GET /auth/sessions` -- the device/session list for the Account page.
 * See docs/frontend/06-authentication.md's Known Limitations: the
 * backend's `SessionResponse.is_current` is never actually populated by
 * the route (apps/api/app/api/routes/auth.py's `list_sessions` never
 * passes it), so every entry comes back `is_current: false` -- this UI
 * cannot highlight "this device" and doesn't pretend to.
 */
export function useSessionsQuery() {
  const isAuthenticated = useSessionStore((state) => state.status === "authenticated");

  return useQuery({
    queryKey: authKeys.sessions(),
    queryFn: listSessions,
    enabled: isAuthenticated,
    staleTime: 30_000,
  });
}
