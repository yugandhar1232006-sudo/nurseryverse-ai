"use client";

import * as React from "react";

import { API_BASE_URL } from "@/lib/api/config";
import { useNotificationStore, type NotificationResponse } from "@/store/notification-store";
import { useSessionStore } from "@/store/session-store";

/**
 * Wires the real Module 11 WebSocket hub (`GET /api/v1/notifications/ws`,
 * apps/api/app/api/routes/notifications.py) into `useNotificationStore` --
 * per the 7C kickoff, this is the *only* notification transport; there is
 * no second polling-based system layered on top for live updates (the
 * unread-count query's `refetchInterval` in lib/notifications/queries.ts
 * is a slow safety net for a disconnected socket, not a replacement).
 *
 * Auth: browsers cannot set an `Authorization` header on a WebSocket
 * handshake, so the access token goes as a `?token=` query parameter --
 * this is the backend's actual, already-implemented contract (see that
 * route's own docstring), not a workaround invented here.
 *
 * Frame shapes, read directly from
 * apps/api/app/notifications/notification_handler.py (not guessed):
 *   {"type": "notification", "notification": {id, category, message,
 *     deep_link, created_at}, "unread_count": number}
 *   {"type": "unread_count", "unread_count": number}
 * A pushed "notification" frame never includes `read_at` (a just-created
 * notification is definitionally unread), so it's synthesized as `null`
 * here to match `NotificationResponse`'s shape.
 *
 * Reconnection: exponential backoff (1s, 2s, 4s, ... capped at 30s) on an
 * unexpected close, using a ref (not state) for the retry counter and
 * timer handle so reconnect scheduling doesn't itself trigger re-renders.
 * The effect re-runs (tearing down and reopening cleanly) whenever the
 * access token changes -- e.g. after a silent refresh rotates it -- so a
 * long-lived tab never ends up holding a socket authenticated with an
 * access token that's already been superseded.
 */
export function useNotificationSocket(): void {
  const accessToken = useSessionStore((state) => state.accessToken);
  const isAuthenticated = useSessionStore((state) => state.status === "authenticated");

  React.useEffect(() => {
    if (!isAuthenticated || !accessToken) {
      useNotificationStore.getState().setConnectionStatus("disconnected");
      return;
    }

    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;
    let stopped = false;

    const wsBaseUrl = API_BASE_URL.replace(/^http/, "ws");

    function connect() {
      if (stopped) return;
      useNotificationStore.getState().setConnectionStatus("connecting");
      socket = new WebSocket(`${wsBaseUrl}/api/v1/notifications/ws?token=${encodeURIComponent(accessToken as string)}`);

      socket.onopen = () => {
        attempt = 0;
        useNotificationStore.getState().setConnectionStatus("connected");
      };

      socket.onmessage = (event) => {
        let frame: { type?: string; notification?: unknown; unread_count?: number };
        try {
          frame = JSON.parse(event.data);
        } catch {
          return; // Malformed frame -- ignore rather than crash the socket handler.
        }

        if (frame.type === "notification" && frame.notification) {
          const raw = frame.notification as Omit<NotificationResponse, "read_at" | "nursery_id" | "recipient_user_id">;
          const { user } = useSessionStore.getState();
          useNotificationStore.getState().addNotification({
            ...raw,
            read_at: null,
            // Not present on the pushed frame, but both are knowable and
            // real without guessing: `push_to_user` (hub.py) only ever
            // targets the current user, and every notification this org
            // pushes is scoped to the org the current user belongs to --
            // filling these from the real session snapshot rather than
            // leaving them blank/fake.
            nursery_id: user?.org_id ?? "",
            recipient_user_id: user?.id ?? "",
          } as NotificationResponse);
          if (typeof frame.unread_count === "number") {
            useNotificationStore.getState().setUnreadCount(frame.unread_count);
          }
        } else if (frame.type === "unread_count" && typeof frame.unread_count === "number") {
          useNotificationStore.getState().setUnreadCount(frame.unread_count);
        }
      };

      socket.onclose = () => {
        useNotificationStore.getState().setConnectionStatus("disconnected");
        if (stopped) return;
        const delay = Math.min(30_000, 1000 * 2 ** attempt);
        attempt += 1;
        reconnectTimer = setTimeout(connect, delay);
      };

      socket.onerror = () => {
        // `onclose` always fires after `onerror` for a WebSocket -- the
        // reconnect scheduling above is sufficient; nothing extra to do
        // here beyond not letting an uncaught error escape the handler.
      };
    }

    connect();

    return () => {
      stopped = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [accessToken, isAuthenticated]);
}
