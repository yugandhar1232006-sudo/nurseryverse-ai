"use client";

import { useQuery } from "@tanstack/react-query";

import { getUnreadCount, listNotifications, listPreferences } from "@/lib/api/notifications";
import { useSessionStore } from "@/store/session-store";

export const notificationKeys = {
  all: ["notifications"] as const,
  list: () => [...notificationKeys.all, "list"] as const,
  unreadCount: () => [...notificationKeys.all, "unread-count"] as const,
  preferences: () => [...notificationKeys.all, "preferences"] as const,
};

/**
 * The first page of the caller's notification history, newest first --
 * backs the notification center panel's list. Enabled only once
 * authenticated (mirrors `lib/auth/queries.ts`'s `useMeQuery` pattern of
 * gating on real session state rather than firing on mount regardless).
 */
export function useNotificationsQuery() {
  const isAuthenticated = useSessionStore((state) => state.status === "authenticated");

  return useQuery({
    queryKey: notificationKeys.list(),
    queryFn: () => listNotifications({ pageSize: 20 }),
    enabled: isAuthenticated,
    staleTime: 15_000,
  });
}

/**
 * The unread badge count. This is a real, independent REST fallback/
 * initial value -- the WebSocket hub (`use-notification-socket.ts`) pushes
 * live updates into `useNotificationStore` directly once connected, but a
 * fresh page load needs a starting number before any socket frame has
 * arrived, and a dropped/reconnecting socket shouldn't leave the badge
 * stuck stale forever (`refetchInterval` provides a slow-polling safety
 * net independent of socket health).
 */
export function useUnreadCountQuery() {
  const isAuthenticated = useSessionStore((state) => state.status === "authenticated");

  return useQuery({
    queryKey: notificationKeys.unreadCount(),
    queryFn: getUnreadCount,
    enabled: isAuthenticated,
    staleTime: 15_000,
    refetchInterval: 60_000,
  });
}

/** 7M -- PG-58's real, saved preference rows. Categories/channels with no saved row yet are handled by the panel's own default, not fabricated here. */
export function usePreferencesQuery() {
  const isAuthenticated = useSessionStore((state) => state.status === "authenticated");

  return useQuery({
    queryKey: notificationKeys.preferences(),
    queryFn: listPreferences,
    enabled: isAuthenticated,
  });
}
