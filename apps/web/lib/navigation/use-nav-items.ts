"use client";

import * as React from "react";

import { MOBILE_TAB_ITEMS, NAV_ITEMS, type MobileTabItem, type NavItem } from "@/lib/navigation/nav-config";
import { usePermissions } from "@/lib/auth/use-permissions";

export interface VisibleNavItem extends Omit<NavItem, "children"> {
  children?: VisibleNavItem[];
}

/**
 * Filters `NAV_ITEMS` down to what the current user is actually
 * permitted to see, per docs/frontend/07-application-shell.md's
 * "hidden, not disabled" rule (matching docs/ux/04-navigation-architecture.md:
 * "they never see a disabled/greyed item for a page they can't access --
 * absence, not disabled state"). A parent with a permission gate of its
 * own is dropped entirely if denied, *before* its children are even
 * considered (there's no scenario where a user can see "Plants" children
 * without `plants:read`, since every child route lives under `/plants`).
 * A parent with no gate (e.g. Dashboard, Settings) whose children *are*
 * all gated and all denied still renders, sans children, since the
 * parent's own destination is still valid on its own.
 *
 * This is UX-only filtering, same caveat as everywhere else in
 * lib/auth/permissions.ts: absence here never substitutes for the
 * backend's own authorization, which every route still enforces
 * independently.
 */
export function useNavItems(): VisibleNavItem[] {
  const { can, canAny } = usePermissions();

  const isVisible = React.useCallback(
    (item: NavItem): boolean => {
      if (item.permission) return can(item.permission);
      if (item.anyOf) return canAny(item.anyOf);
      return true;
    },
    [can, canAny],
  );

  return React.useMemo(() => {
    function filter(items: NavItem[]): VisibleNavItem[] {
      return items.filter(isVisible).map((item) => ({
        ...item,
        children: item.children ? filter(item.children) : undefined,
      }));
    }
    return filter(NAV_ITEMS);
  }, [isVisible]);
}

/**
 * Active-route detection: an item is "active" if the current pathname
 * equals its href exactly, or -- for anything other than the Dashboard's
 * `/` (which would otherwise match *everything*, since every path starts
 * with `/`) -- starts with its href as a path-segment prefix. `/plants`
 * matches `/plants/123` but `/plants-list` (hypothetically) would not,
 * since the check requires the next character to be `/` or end-of-string.
 */
export function isNavItemActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  if (pathname === href) return true;
  return pathname.startsWith(`${href}/`);
}

/** Same permission filtering as `useNavItems`, applied to the mobile bottom tab bar's separate, shorter list. */
export function useMobileTabItems(): MobileTabItem[] {
  const { can } = usePermissions();

  return React.useMemo(
    () => MOBILE_TAB_ITEMS.filter((item) => !item.permission || can(item.permission)),
    [can],
  );
}
