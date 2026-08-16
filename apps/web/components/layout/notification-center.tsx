"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { formatDistanceToNowStrict } from "date-fns";
import { Bell, BellOff, CheckCheck, WifiOff } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import type { NotificationResponse } from "@/lib/api/notifications";
import { useMarkAllReadMutation, useMarkNotificationReadMutation } from "@/lib/notifications/mutations";
import { useNotificationsQuery, useUnreadCountQuery } from "@/lib/notifications/queries";
import { useNotificationSocket } from "@/lib/notifications/use-notification-socket";
import { useNotificationStore } from "@/store/notification-store";
import { useUiStore } from "@/store/ui-store";
import { cn } from "@/lib/utils";

/**
 * Category → label, matching the real `NotificationCategory` enum values
 * from the generated schema (Module 11). Kept as a display-only lookup --
 * unknown/future categories fall back to the raw value rather than a
 * hardcoded default, so a new backend category never silently disappears.
 */
function categoryLabel(category: string): string {
  return category
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function NotificationRow({
  notification,
  onOpen,
}: {
  notification: NotificationResponse;
  onOpen: (notification: NotificationResponse) => void;
}) {
  const isUnread = !notification.read_at;

  return (
    <li>
      <button
        type="button"
        onClick={() => onOpen(notification)}
        aria-label={`${notification.message}${isUnread ? " (unread)" : ""}`}
        className={cn(
          "flex w-full flex-col items-start gap-1 rounded-md px-3 py-2.5 text-left transition-colors duration-fast",
          "hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          isUnread && "bg-primary/5",
        )}
      >
        <div className="flex w-full items-start gap-2">
          {isUnread && <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" aria-hidden="true" />}
          <span className={cn("flex-1 text-body-sm", isUnread ? "font-medium text-foreground" : "text-muted-foreground")}>
            {notification.message}
          </span>
        </div>
        <div className="flex w-full items-center justify-between gap-2 pl-3.5 text-caption text-muted-foreground">
          <Badge variant="outline" className="text-caption">
            {categoryLabel(notification.category)}
          </Badge>
          <time dateTime={notification.created_at}>
            {formatDistanceToNowStrict(new Date(notification.created_at), { addSuffix: true })}
          </time>
        </div>
      </button>
    </li>
  );
}

/**
 * Bell trigger + slide-over panel. Consumes the real Module 11 REST +
 * WebSocket stack end to end:
 *  - `useNotificationSocket()` opens/maintains the live connection (this
 *    is the *only* place in the shell that hook is called, per its own
 *    docstring's "no second polling-based system" note).
 *  - Initial list/unread-count come from `useNotificationsQuery` /
 *    `useUnreadCountQuery`; live pushes land in `useNotificationStore`,
 *    which is what the panel actually renders once the first page has
 *    loaded (`setInitialPage` below seeds the store from that first
 *    query response so the store is always the single source of truth
 *    for what's on screen, never two competing lists).
 *  - Mark-read / mark-all-read call the real endpoints via
 *    `lib/notifications/mutations.ts`.
 *  - `deep_link` (when present) drives real client-side navigation on
 *    click -- never a placeholder `#` href.
 *
 * `open` is shared UI state (`useUiStore`'s `notificationCenterOpen`),
 * not a local `useState`, so `components/layout/mobile-nav.tsx`'s
 * "Alerts" bottom-tab button can open this exact panel instance instead
 * of building a second one.
 */
export function NotificationCenter() {
  const router = useRouter();
  const open = useUiStore((state) => state.notificationCenterOpen);
  const setOpen = useUiStore((state) => state.setNotificationCenterOpen);

  useNotificationSocket();

  const listQuery = useNotificationsQuery();
  const unreadCountQuery = useUnreadCountQuery();
  const markReadMutation = useMarkNotificationReadMutation();
  const markAllReadMutation = useMarkAllReadMutation();

  const notifications = useNotificationStore((state) => state.notifications);
  const storeUnreadCount = useNotificationStore((state) => state.unreadCount);
  const connectionStatus = useNotificationStore((state) => state.connectionStatus);
  const setInitialPage = useNotificationStore((state) => state.setInitialPage);

  // Seed the live store from the first successful page fetch. `hasSeeded`
  // (real state, read during render) is what the render below branches
  // on; `seededDataRef` (a ref, only ever read/written inside this
  // effect, never during render) just guards against re-seeding on every
  // background refetch once `staleTime` elapses, which would otherwise
  // stomp on notifications the socket has pushed in since the store was
  // last seeded.
  const [hasSeeded, setHasSeeded] = React.useState(false);
  const seededDataRef = React.useRef<unknown>(null);
  React.useEffect(() => {
    if (listQuery.data && listQuery.data !== seededDataRef.current) {
      seededDataRef.current = listQuery.data;
      setInitialPage(listQuery.data.items, unreadCountQuery.data?.unread_count ?? listQuery.data.items.filter((n) => !n.read_at).length);
      setHasSeeded(true);
    }
  }, [listQuery.data, unreadCountQuery.data, setInitialPage]);

  // Prefer the live socket-fed count once we have one; the REST value is
  // only the pre-hydration fallback (see useUnreadCountQuery's docstring).
  const unreadCount = hasSeeded ? storeUnreadCount : (unreadCountQuery.data?.unread_count ?? 0);

  function handleOpenNotification(notification: NotificationResponse) {
    if (!notification.read_at) {
      markReadMutation.mutate(notification.id);
    }
    setOpen(false);
    if (notification.deep_link) {
      router.push(notification.deep_link);
    }
  }

  const displayNotifications = hasSeeded ? notifications : (listQuery.data?.items ?? []);
  const hasUnread = unreadCount > 0;

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label={hasUnread ? `Notifications, ${unreadCount} unread` : "Notifications"}
          className="relative"
        >
          <Bell className="size-5" aria-hidden="true" />
          {hasUnread && (
            <span
              aria-hidden="true"
              className="absolute right-1 top-1 flex min-w-[1rem] items-center justify-center rounded-full bg-danger px-1 text-[10px] font-semibold leading-none text-danger-foreground"
            >
              {unreadCount > 99 ? "99+" : unreadCount}
            </span>
          )}
        </Button>
      </SheetTrigger>

      <SheetContent side="right" className="w-full max-w-sm p-0" aria-describedby={undefined}>
        <SheetHeader className="flex-row items-center justify-between space-y-0 border-b border-border">
          <SheetTitle>Notifications</SheetTitle>
          {connectionStatus !== "connected" && (
            <span className="flex items-center gap-1 text-caption text-muted-foreground" role="status">
              <WifiOff className="size-3.5" aria-hidden="true" />
              {connectionStatus === "connecting" ? "Reconnecting…" : "Offline"}
            </span>
          )}
        </SheetHeader>

        <div className="flex items-center justify-between px-4 py-2">
          <span className="text-body-sm text-muted-foreground">
            {hasUnread ? `${unreadCount} unread` : "You're all caught up"}
          </span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={!hasUnread || markAllReadMutation.isPending}
            onClick={() => markAllReadMutation.mutate()}
          >
            <CheckCheck className="size-4" />
            Mark all read
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto px-2 pb-4">
          {listQuery.isLoading ? (
            <div className="flex flex-col gap-2 px-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-14 w-full rounded-md" />
              ))}
            </div>
          ) : listQuery.isError ? (
            <ErrorState error={listQuery.error} onRetry={() => listQuery.refetch()} retrying={listQuery.isFetching} />
          ) : displayNotifications.length === 0 ? (
            <EmptyState
              icon={BellOff}
              title="No notifications yet"
              description="You'll see updates about your plants, orders, and account here."
            />
          ) : (
            <ul className="flex flex-col gap-0.5">
              {displayNotifications.map((notification) => (
                <NotificationRow key={notification.id} notification={notification} onOpen={handleOpenNotification} />
              ))}
            </ul>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
