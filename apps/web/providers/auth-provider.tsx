"use client";

import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";

import { bootSession } from "@/lib/auth/session-boot";

/**
 * Kicks off session restoration (lib/auth/session-boot.ts) exactly once
 * when the app mounts, then gets out of the way -- this does NOT block
 * rendering of `children`. Blocking here would delay public routes
 * (the Plant Passport, login page itself) on an auth check they don't
 * need. Protected routes/layouts (7C's `(app)` route group layout) are
 * what actually read `useSessionStore`'s `status` and show their own
 * loading/redirect behavior while it's `"resolving"`.
 *
 * The `hasRun` ref (rather than an empty-deps `useEffect` alone) guards
 * against React 18/19 Strict Mode's deliberate double-invoke of effects
 * in development -- without it, dev mode would fire two concurrent
 * `/auth/refresh` calls on every boot. Harmless correctness-wise (the
 * second would just fail against an already-rotated token in cookie
 * mode, or fail identically in bearer mode), but noisy and worth
 * avoiding cleanly.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const hasRun = React.useRef(false);

  React.useEffect(() => {
    if (hasRun.current) return;
    hasRun.current = true;
    void bootSession(queryClient);
  }, [queryClient]);

  return <>{children}</>;
}
