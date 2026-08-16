"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import * as notificationsApi from "@/lib/api/notifications";
import { notificationKeys } from "@/lib/notifications/queries";
import { useNotificationStore } from "@/store/notification-store";
import { toast } from "@/lib/toast";

/**
 * Marks one notification read. Updates `useNotificationStore` (the
 * WebSocket-fed live list the notification center panel actually renders)
 * optimistically in `onSuccess` rather than waiting on a query
 * invalidation round-trip -- the backend's own WS hub also pushes an
 * `unread_count` frame on this same action (apps/api/app/api/routes/
 * notifications.py's websocket docstring), so this is belt-and-suspenders
 * for a socket that's momentarily disconnected, not the only path.
 */
export function useMarkNotificationReadMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => notificationsApi.markNotificationRead(id),
    onSuccess: (_data, id) => {
      useNotificationStore.getState().markRead(id);
      void queryClient.invalidateQueries({ queryKey: notificationKeys.unreadCount() });
    },
  });
}

export function useMarkAllReadMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => {
      useNotificationStore.getState().markAllRead();
      void queryClient.invalidateQueries({ queryKey: notificationKeys.unreadCount() });
    },
  });
}

/**
 * 7M -- saves the caller's PG-58 preference matrix. Verified directly
 * against `PreferenceRepository.upsert` (apps/api/app/repositories/
 * sqlalchemy_repositories.py): the real `PUT` route is a per-(category,
 * channel) UPSERT, never a bulk replace/delete -- any row omitted from the
 * request body is left completely untouched server-side. Because of that,
 * `NotificationPreferencesPanel` always sends one explicit row per visible
 * (category, channel) cell with its current checked state, including
 * unchecked ones (`enabled: false`), rather than omitting unchecked cells
 * -- omitting them would silently fail to persist a user's "off" choice
 * for a cell that already had a saved "on" row.
 */
export function useUpdatePreferencesMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: notificationsApi.NotificationPreferenceUpdateRequest[]) =>
      notificationsApi.updatePreferences(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: notificationKeys.preferences() });
      toast.success("Notification preferences saved");
    },
    onError: (error) => {
      toast.apiError(error);
    },
  });
}
