"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";

import { useBreadcrumbs, type Breadcrumb } from "@/lib/navigation/use-breadcrumbs";
import { cn } from "@/lib/utils";

export interface BreadcrumbsProps {
  /** See `useBreadcrumbs`'s docstring -- lets a detail page substitute a real resource name for a raw path segment. */
  dynamicLabels?: Record<string, string>;
  className?: string;
}

/**
 * Presentational breadcrumb trail, per docs/ux/04-navigation-architecture.md.
 * Not rendered at all for the Dashboard itself (a single "Dashboard" crumb
 * with nothing to navigate back to is noise, not navigation) -- every
 * other page gets the full trail back to Dashboard.
 *
 * Mobile-friendly behavior: on narrow viewports only the current page and
 * its immediate parent are shown (`hidden tablet:flex` on earlier crumbs),
 * matching the responsive design spec's instruction not to let a deep
 * trail wrap or overflow a small header.
 */
export function Breadcrumbs({ dynamicLabels, className }: BreadcrumbsProps) {
  const crumbs = useBreadcrumbs(dynamicLabels);

  if (crumbs.length <= 1) return null;

  return (
    <nav aria-label="Breadcrumb" className={cn("flex items-center", className)}>
      <ol className="flex items-center gap-1.5 text-body-sm text-muted-foreground">
        {crumbs.map((crumb: Breadcrumb, index) => {
          const isHiddenOnMobile = index < crumbs.length - 2;
          return (
            <li
              key={crumb.href}
              className={cn("flex items-center gap-1.5", isHiddenOnMobile && "hidden tablet:flex")}
            >
              {index > 0 && <ChevronRight className="size-3.5 shrink-0" aria-hidden="true" />}
              {crumb.isCurrent ? (
                <span aria-current="page" className="font-medium text-foreground">
                  {crumb.label}
                </span>
              ) : (
                <Link href={crumb.href} className="rounded-sm hover:text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                  {crumb.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
