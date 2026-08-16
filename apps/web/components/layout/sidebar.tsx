"use client";

import { ChevronsLeft, ChevronsRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { SidebarNavItem } from "@/components/layout/sidebar-nav-item";
import { useNavItems } from "@/lib/navigation/use-nav-items";
import { useSessionStore } from "@/store/session-store";
import { useUiStore } from "@/store/ui-store";
import { cn } from "@/lib/utils";

/**
 * Desktop/laptop persistent sidebar, per
 * docs/design/04-responsive-design-specifications.md's per-breakpoint
 * behavior ("Desktop/Laptop: persistent expanded icon+label" /
 * collapsible). Hidden entirely below the `tablet` breakpoint -- tablet
 * gets its own collapsible-drawer treatment and mobile gets the bottom
 * tab bar (`mobile-nav.tsx`), neither of which is this component.
 *
 * `aria-label="Primary"` + `<nav>` gives this a real landmark role
 * (Accessibility requirement: "semantic navigation landmarks") -- a
 * screen reader user can jump straight to it without linearly tabbing
 * through the header first.
 */
export function Sidebar() {
  const items = useNavItems();
  const collapsed = useUiStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);
  const isResolving = useSessionStore((state) => state.status === "resolving");

  return (
    <aside
      className={cn(
        "sticky top-0 hidden h-screen shrink-0 flex-col border-r border-border bg-card transition-[width] duration-fast tablet:flex",
        collapsed ? "w-16" : "w-60",
      )}
    >
      <nav aria-label="Primary" className="flex flex-1 flex-col gap-1 overflow-y-auto p-2">
        {isResolving ? (
          <div className="flex flex-col gap-2 p-1">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : (
          <ul className="flex flex-col gap-0.5">
            {items.map((item) => (
              <SidebarNavItem key={item.id} item={item} collapsed={collapsed} />
            ))}
          </ul>
        )}
      </nav>

      <div className="border-t border-border p-2">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className={cn("w-full", collapsed ? "justify-center px-0" : "justify-start")}
          onClick={toggleSidebar}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronsRight className="size-4" /> : <ChevronsLeft className="size-4" />}
          {!collapsed && "Collapse"}
        </Button>
      </div>
    </aside>
  );
}
