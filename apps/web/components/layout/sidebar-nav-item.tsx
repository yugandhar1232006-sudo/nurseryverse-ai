"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { isNavItemActive } from "@/lib/navigation/use-nav-items";
import type { VisibleNavItem } from "@/lib/navigation/use-nav-items";
import { cn } from "@/lib/utils";

interface SidebarNavItemProps {
  item: VisibleNavItem;
  collapsed: boolean;
  /** Closes the mobile drawer / notification-adjacent overlay on navigate, if supplied. */
  onNavigate?: () => void;
}

/**
 * A single nav destination, optionally with one level of nested children
 * (`lib/navigation/nav-config.ts`'s Plants -> Species Catalog example).
 * Nested children are only shown when the sidebar is expanded -- a
 * collapsed icon rail has no room to represent a sub-list, so the parent
 * link (its own real, working destination) is what a collapsed rail
 * offers instead. This is a deliberate, common icon-rail tradeoff, not a
 * lost feature: every child route is still reachable via the parent page
 * once the sidebar is expanded again, and the collapsed rail is desktop-
 * only chrome (mobile always gets the fully expanded drawer, see
 * mobile-nav.tsx).
 */
export function SidebarNavItem({ item, collapsed, onNavigate }: SidebarNavItemProps) {
  const pathname = usePathname();
  const active = isNavItemActive(pathname, item.href);
  const Icon = item.icon;

  const link = (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      // Explicit, not left to text-node computation: when `collapsed` is
      // true there's no visible label span at all (only the `aria-hidden`
      // icon below), and a hover/focus tooltip alone is not a reliable
      // accessible name for assistive tech (Radix's Tooltip wires up
      // `aria-describedby`, which contributes a *description*, not a
      // *name* -- WCAG 4.1.2 needs the latter). Setting this unconditionally
      // (not just when collapsed) also means the accessible name never
      // depends on the collapse/expand transition at all.
      aria-label={item.label}
      className={cn(
        "flex items-center gap-3 rounded-md px-3 py-2 text-body-sm font-medium outline-none transition-colors duration-fast",
        "focus-visible:ring-2 focus-visible:ring-ring",
        collapsed && "justify-center px-0",
        active
          ? "bg-accent text-accent-foreground"
          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
      )}
    >
      <Icon className="size-4 shrink-0" aria-hidden="true" />
      {!collapsed && <span className="truncate">{item.label}</span>}
    </Link>
  );

  return (
    <li>
      {collapsed ? (
        <Tooltip>
          <TooltipTrigger asChild>{link}</TooltipTrigger>
          <TooltipContent side="right">{item.label}</TooltipContent>
        </Tooltip>
      ) : (
        link
      )}

      {!collapsed && item.children && item.children.length > 0 && (
        <ul className="mt-1 flex flex-col gap-0.5 border-l border-border pl-4">
          {item.children.map((child) => (
            <SidebarNavItem key={child.id} item={child} collapsed={false} onNavigate={onNavigate} />
          ))}
        </ul>
      )}
    </li>
  );
}
