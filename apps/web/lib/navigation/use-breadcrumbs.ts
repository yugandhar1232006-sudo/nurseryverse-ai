"use client";

import * as React from "react";
import { usePathname } from "next/navigation";

import { flattenNavItems } from "@/lib/navigation/nav-config";

export interface Breadcrumb {
  label: string;
  href: string;
  /** The current page -- rendered as text, not a link. */
  isCurrent: boolean;
}

function titleCase(segment: string): string {
  return segment
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/**
 * Route-based breadcrumb generation, per
 * docs/ux/04-navigation-architecture.md's "Breadcrumbs" section: used on
 * pages nested more than one level deep, resolving each path segment to a
 * label from `NAV_ITEMS` where one exists (e.g. `/plants/species` ->
 * "Plants / Species Catalog") and falling back to a title-cased version of
 * the raw segment otherwise (so an unmapped or dynamic segment never
 * renders as a blank crumb).
 *
 * `dynamicLabels` lets a detail page override a specific segment with a
 * real resource name once it's loaded (e.g. a plant's actual identifier
 * instead of its UUID) -- keyed by the exact path segment being replaced.
 * No page in 7C uses this yet (no detail routes exist), but the mechanism
 * is here for 7G/7H's Plant Digital Twin breadcrumbs
 * ("Plants / Ficus Lyrata #FLY-0142 / Health History") to plug into
 * without every future page reinventing path-parsing.
 */
export function useBreadcrumbs(dynamicLabels: Record<string, string> = {}): Breadcrumb[] {
  const pathname = usePathname();

  return React.useMemo(() => {
    const flatNav = flattenNavItems();
    const segments = pathname.split("/").filter(Boolean);

    if (segments.length === 0) {
      return [{ label: "Dashboard", href: "/", isCurrent: true }];
    }

    const crumbs: Breadcrumb[] = [{ label: "Dashboard", href: "/", isCurrent: false }];
    let accumulatedPath = "";

    segments.forEach((segment, index) => {
      accumulatedPath += `/${segment}`;
      const isLast = index === segments.length - 1;
      const navMatch = flatNav.find((item) => item.href === accumulatedPath);
      const label = dynamicLabels[segment] ?? navMatch?.label ?? titleCase(segment);
      crumbs.push({ label, href: accumulatedPath, isCurrent: isLast });
    });

    return crumbs;
  }, [pathname, dynamicLabels]);
}
