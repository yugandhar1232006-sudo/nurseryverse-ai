"use client";

import * as React from "react";

import { usePermissions } from "@/lib/auth/use-permissions";

/**
 * Reusable permission-aware conditional rendering primitive -- the
 * building block "permission-aware navigation" is built from. UX only
 * (see docs/frontend/05-permission-aware-ui.md): hiding a control here
 * never substitutes for the backend's own authorization check, which
 * still applies regardless of what this renders.
 *
 * Accepts exactly one of `permission` / `anyOf` / `allOf` -- mirrors
 * `usePermissions()`'s three check functions (`can`/`canAny`/`canAll`)
 * one-to-one rather than inventing a fourth combinator here.
 */
export interface PermissionGateProps {
  permission?: string;
  anyOf?: readonly string[];
  allOf?: readonly string[];
  /** Rendered instead of `children` when the check fails (default: nothing). */
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

export function PermissionGate({ permission, anyOf, allOf, fallback = null, children }: PermissionGateProps) {
  const { can, canAny, canAll } = usePermissions();

  let allowed = false;
  if (permission) allowed = can(permission);
  else if (anyOf) allowed = canAny(anyOf);
  else if (allOf) allowed = canAll(allOf);

  return <>{allowed ? children : fallback}</>;
}
