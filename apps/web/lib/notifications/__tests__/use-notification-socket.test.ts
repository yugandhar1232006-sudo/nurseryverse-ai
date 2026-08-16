import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";

import { useNotificationSocket } from "@/lib/notifications/use-notification-socket";
import { useNotificationStore } from "@/store/notification-store";
import { useSessionStore } from "@/store/session-store";
import { makeMe } from "@/test/fixtures/auth";
import { MockWebSocket } from "@/test/mock-websocket";

function signIn() {
  useSessionStore.setState({
    status: "authenticated",
    user: makeMe(),
    accessToken: "access-token-1",
  });
}

describe("useNotificationSocket", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("does not open a socket while unauthenticated, and reports disconnected", () => {
    useSessionStore.setState({ status: "unauthenticated", user: null, accessToken: null });
    renderHook(() => useNotificationSocket());

    expect(MockWebSocket.instances).toHaveLength(0);
    expect(useNotificationStore.getState().connectionStatus).toBe("disconnected");
  });

  it("opens a socket carrying the access token as a query param once authenticated", () => {
    signIn();
    renderHook(() => useNotificationSocket());

    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0].url).toContain("token=access-token-1");
  });

  it("flips connection status to connected on open", () => {
    signIn();
    renderHook(() => useNotificationSocket());

    MockWebSocket.instances[0].emitOpen();
    expect(useNotificationStore.getState().connectionStatus).toBe("connected");
  });

  it("merges a pushed notification frame into the store and increments unread count", () => {
    signIn();
    renderHook(() => useNotificationSocket());
    MockWebSocket.instances[0].emitOpen();

    MockWebSocket.instances[0].emitMessage({
      type: "notification",
      notification: {
        id: "n-1",
        category: "low_stock",
        message: "Potting soil is running low.",
        deep_link: "/inventory",
        created_at: "2026-08-14T10:00:00Z",
      },
      unread_count: 3,
    });

    const state = useNotificationStore.getState();
    expect(state.notifications).toHaveLength(1);
    expect(state.notifications[0].message).toBe("Potting soil is running low.");
    expect(state.notifications[0].read_at).toBeNull();
    // Real session values fill fields absent from the push frame, not blanks.
    expect(state.notifications[0].recipient_user_id).toBe(makeMe().id);
    expect(state.unreadCount).toBe(3);
  });

  it("applies a standalone unread_count frame", () => {
    signIn();
    renderHook(() => useNotificationSocket());
    MockWebSocket.instances[0].emitMessage({ type: "unread_count", unread_count: 7 });
    expect(useNotificationStore.getState().unreadCount).toBe(7);
  });

  it("ignores a malformed frame instead of crashing the handler", () => {
    signIn();
    renderHook(() => useNotificationSocket());
    expect(() => MockWebSocket.instances[0].onmessage?.({ data: "not json" })).not.toThrow();
  });

  it("reconnects with exponential backoff after an unexpected close", () => {
    signIn();
    renderHook(() => useNotificationSocket());
    expect(MockWebSocket.instances).toHaveLength(1);

    MockWebSocket.instances[0].emitClose();
    expect(useNotificationStore.getState().connectionStatus).toBe("disconnected");

    vi.advanceTimersByTime(1000);
    expect(MockWebSocket.instances).toHaveLength(2);
  });

  it("tears down the socket and cancels any pending reconnect on unmount", () => {
    signIn();
    const { unmount } = renderHook(() => useNotificationSocket());
    const socket = MockWebSocket.instances[0];

    unmount();
    expect(socket.closed).toBe(true);

    // A reconnect that was scheduled before unmount must not fire afterward.
    vi.advanceTimersByTime(30_000);
    expect(MockWebSocket.instances).toHaveLength(1);
  });
});
