"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { SidebarNavItem } from "@/components/layout/sidebar-nav-item";
import { isNavItemActive, useMobileTabItems, useNavItems } from "@/lib/navigation/use-nav-items";
import { useSessionStore } from "@/store/session-store";
import { useUiStore } from "@/store/ui-store";
import { cn } from "@/lib/utils";

/**
 * Mobile's persistent bottom tab bar, per
 * docs/design/04-responsive-design-specifications.md's "Mobile: replaced
 * entirely by BottomTabBar" (the `Sidebar` component itself is `hidden`
 * below the `tablet` breakpoint -- this is genuinely the *only* primary
 * navigation surface on a phone-sized viewport, not an addition on top of
 * a hidden sidebar). Renders `useMobileTabItems()` -- the UX doc's fixed
 * 4-item field-workflow set, already permission-filtered.
 *
 * The "Alerts" tab is not a route -- it opens the exact same
 * `NotificationCenter` panel the header bell does, via `useUiStore`'s
 * shared `notificationCenterOpen` flag (see that store's docstring for
 * why this isn't a second notification UI).
 */
export function MobileTabBar() {
  const pathname = usePathname();
  const items = useMobileTabItems();
  const isResolving = useSessionStore((state) => state.status === "resolving");
  const setNotificationCenterOpen = useUiStore((state) => state.setNotificationCenterOpen);

  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-sticky flex h-16 items-stretch border-t border-border bg-card tablet:hidden"
    >
      {isResolving ? (
        <div className="flex w-full items-center justify-around px-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="size-8 rounded-md" />
          ))}
        </div>
      ) : (
        items.map((item) => {
          const Icon = item.icon;
          const active = item.href ? isNavItemActive(pathname, item.href) : false;

          const content = (
            <>
              <Icon className="size-5" aria-hidden="true" />
              <span className="text-caption">{item.label}</span>
            </>
          );

          const className = cn(
            "flex flex-1 flex-col items-center justify-center gap-0.5 text-caption outline-none transition-colors duration-fast",
            "focus-visible:bg-accent",
            active ? "text-primary" : "text-muted-foreground",
          );

          if (item.isNotifications) {
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setNotificationCenterOpen(true)}
                aria-label="Notifications"
                className={className}
              >
                {content}
              </button>
            );
          }

          return (
            <Link key={item.id} href={item.href as string} aria-current={active ? "page" : undefined} className={className}>
              {content}
            </Link>
          );
        })
      )}
    </nav>
  );
}

/**
 * The "More" drawer -- full `useNavItems()` tree (everything the sidebar
 * shows on larger screens), opened from `TopNav`'s hamburger button via
 * `useUiStore`'s `mobileNavOpen`. This is where a mobile user reaches
 * anything not in the bottom bar's 4-item set (Sales, Customers, Reports,
 * Settings, AI Center, etc.) -- reuses `SidebarNavItem` directly rather
 * than a second nav-rendering implementation, with `collapsed={false}`
 * (a drawer always has room for full labels) and `onNavigate` wired to
 * close the sheet on tap.
 */
export function MobileNavSheet() {
  const open = useUiStore((state) => state.mobileNavOpen);
  const setOpen = useUiStore((state) => state.setMobileNavOpen);
  const items = useNavItems();

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetContent side="left" className="w-72 p-0" aria-describedby={undefined}>
        <SheetHeader className="border-b border-border">
          <SheetTitle>NurseryVerse AI</SheetTitle>
        </SheetHeader>
        {/*
          Labeled distinctly from `MobileTabBar`'s "Primary" landmark --
          both can be in the DOM at once while this sheet is open, and
          ARIA authoring practice calls for unique names when more than
          one `nav` landmark is present simultaneously.
        */}
        <nav aria-label="More navigation" className="flex-1 overflow-y-auto p-2">
          <ul className="flex flex-col gap-0.5">
            {items.map((item) => (
              <SidebarNavItem key={item.id} item={item} collapsed={false} onNavigate={() => setOpen(false)} />
            ))}
          </ul>
        </nav>
      </SheetContent>
    </Sheet>
  );
}
