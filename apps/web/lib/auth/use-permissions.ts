"use client";

import { useMemo } from "react";

import { hasAllPermissions, hasAnyPermission, hasPermission } from "@/lib/auth/permissions";
import { useSessionStore } from "@/store/session-store";

/**
 * Binds the pure permission functions in lib/auth/permissions.ts to the
 * current user's permissions from the session store, for ergonomic use
 * in components: `const { can } = usePermissions(); if (can("plants:write")) ...`.
 * Returns all-false/deny-by-default when there's no authenticated user
 * yet (resolving or unauthenticated), which is the correct fail-closed
 * default for a UX-only gate.
 */
// A stable, module-level fallback -- `state.user?.permissions ?? []` would
// allocate a brand-new array on *every* selector invocation whenever
// there's no user, and Zustand's `useSyncExternalStore`-based subscription
// compares successive selector results by reference to decide whether to
// re-render. A fresh `[]` each call never equals the previous one, so React
// treated every render as "the store changed," re-rendered, computed a new
// `[]` again, and looped -- surfacing as a real "Maximum update depth
// exceeded" crash (caught by this hook's own test suite) for any
// component using `usePermissions()`/`<PermissionGate>` while signed out
// or still resolving. Reusing one constant array fixes it: the reference
// is stable across calls, so the selector output only changes when the
// user's actual permissions do.
const NO_PERMISSIONS: readonly string[] = [];

export function usePermissions() {
  const permissions = useSessionStore((state) => state.user?.permissions ?? NO_PERMISSIONS);

  return useMemo(
    () => ({
      permissions,
      can: (required: string) => hasPermission(permissions, required),
      canAny: (required: readonly string[]) => hasAnyPermission(permissions, required),
      canAll: (required: readonly string[]) => hasAllPermissions(permissions, required),
    }),
    [permissions],
  );
}
