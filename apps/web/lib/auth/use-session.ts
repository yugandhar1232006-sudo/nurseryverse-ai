"use client";

import { useSessionStore } from "@/store/session-store";

/**
 * The ergonomic read side of the auth session -- components should use
 * this instead of reaching into `useSessionStore` field-by-field.
 * `isResolving` is the app-boot restoration window (see
 * lib/auth/session-boot.ts); route guards and any UI that cares about
 * "are we sure yet" should check it explicitly rather than treating
 * `!isAuthenticated` as "definitely signed out" (it might just not know
 * yet).
 */
export function useSession() {
  const user = useSessionStore((state) => state.user);
  const status = useSessionStore((state) => state.status);

  return {
    user,
    status,
    isResolving: status === "resolving",
    isAuthenticated: status === "authenticated",
  };
}
