import { create } from "zustand";

import type { components } from "@/lib/api/generated/schema";

export type NotificationResponse = components["schemas"]["NotificationResponse"];

/**
 * Holds the live, real-time notification feed pushed over the backend's
 * WebSocket hub (apps/api/app/api/routes/notifications.py's
 * `/api/v1/notifications/ws`, Module 11). This is client state, not
 * server-fetched state, for a deliberate reason: the initial page of
 * notifications *is* fetched via TanStack Query (GET /notifications,
 * paginated, cacheable, refetchable) but the WebSocket then pushes
 * incremental updates that need to merge into that list and update
 * `unreadCount` immediately without waiting on a query invalidation
 * round-trip -- exactly the kind of "state React Query wasn't designed
 * for" the Phase 4 state-management doc's split calls out.
 *
 * The actual `WebSocket` connection lifecycle (open/reconnect/backoff)
 * is built in Phase 7M against this store -- this file only defines the
 * shape and the pure state-transition actions so 7M has a stable target
 * to wire against instead of inventing the shape ad hoc.
 *
 * Auth note: per the real, already-implemented Module 11 route (not the
 * short-lived-ticket design floated in earlier planning), the WebSocket
 * handshake authenticates via `?token=<access_token>` as a query
 * parameter -- browsers cannot set an `Authorization` header on a
 * WebSocket upgrade request. 7M's connection hook must source that
 * token from `useSessionStore.getState().accessToken` at connect time
 * and reconnect with a fresh one after a token refresh.
 */
interface NotificationState {
  notifications: NotificationResponse[];
  unreadCount: number;
  connectionStatus: "disconnected" | "connecting" | "connected";
}

interface NotificationActions {
  setInitialPage: (notifications: NotificationResponse[], unreadCount: number) => void;
  addNotification: (notification: NotificationResponse) => void;
  markRead: (id: string) => void;
  markAllRead: () => void;
  setUnreadCount: (count: number) => void;
  setConnectionStatus: (status: NotificationState["connectionStatus"]) => void;
  reset: () => void;
}

const initialState: NotificationState = {
  notifications: [],
  unreadCount: 0,
  connectionStatus: "disconnected",
};

export const useNotificationStore = create<NotificationState & NotificationActions>()((set) => ({
  ...initialState,

  setInitialPage: (notifications, unreadCount) => set({ notifications, unreadCount }),

  addNotification: (notification) =>
    set((state) => ({
      notifications: [notification, ...state.notifications],
      unreadCount: notification.read_at ? state.unreadCount : state.unreadCount + 1,
    })),

  markRead: (id) =>
    set((state) => {
      const target = state.notifications.find((n) => n.id === id);
      const wasUnread = Boolean(target) && !target?.read_at;
      return {
        notifications: state.notifications.map((n) =>
          n.id === id && !n.read_at ? { ...n, read_at: new Date().toISOString() } : n,
        ),
        unreadCount: wasUnread ? Math.max(0, state.unreadCount - 1) : state.unreadCount,
      };
    }),

  markAllRead: () =>
    set((state) => ({
      notifications: state.notifications.map((n) => (n.read_at ? n : { ...n, read_at: new Date().toISOString() })),
      unreadCount: 0,
    })),

  setUnreadCount: (count) => set({ unreadCount: count }),
  setConnectionStatus: (status) => set({ connectionStatus: status }),
  reset: () => set(initialState),
}));
