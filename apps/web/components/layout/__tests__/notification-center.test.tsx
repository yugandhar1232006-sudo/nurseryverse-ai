import { describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { NotificationCenter } from "@/components/layout/notification-center";
import { useSessionStore } from "@/store/session-store";
import { makeMe } from "@/test/fixtures/auth";
import { makeNotification, makeNotificationPage } from "@/test/fixtures/shell";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/msw/server";

const { mockPush } = vi.hoisted(() => ({ mockPush: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

const BASE = "http://localhost:8000";

function signIn() {
  useSessionStore.setState({ status: "authenticated", user: makeMe(), accessToken: "access-token-1" });
}

describe("NotificationCenter", () => {
  it("shows the unread badge count from the real unread-count endpoint", async () => {
    server.use(http.get(`${BASE}/api/v1/notifications/unread-count`, () => HttpResponse.json({ unread_count: 4 })));
    signIn();
    renderWithProviders(<NotificationCenter />);

    expect(await screen.findByText("4")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Notifications, 4 unread" })).toBeInTheDocument();
  });

  it("shows no badge when there are zero unread notifications", async () => {
    server.use(http.get(`${BASE}/api/v1/notifications/unread-count`, () => HttpResponse.json({ unread_count: 0 })));
    signIn();
    renderWithProviders(<NotificationCenter />);

    expect(await screen.findByRole("button", { name: "Notifications" })).toBeInTheDocument();
  });

  it("opens the panel and renders the real notification list", async () => {
    const user = userEvent.setup();
    const notification = makeNotification({ message: "Ficus batch #14 needs watering." });
    server.use(http.get(`${BASE}/api/v1/notifications`, () => HttpResponse.json(makeNotificationPage([notification]))));
    signIn();
    renderWithProviders(<NotificationCenter />);

    await user.click(await screen.findByRole("button", { name: /Notifications/ }));
    expect(await screen.findByText("Ficus batch #14 needs watering.")).toBeInTheDocument();
  });

  it("shows an honest empty state when there are genuinely no notifications", async () => {
    const user = userEvent.setup();
    server.use(
      http.get(`${BASE}/api/v1/notifications`, () => HttpResponse.json(makeNotificationPage([]))),
      http.get(`${BASE}/api/v1/notifications/unread-count`, () => HttpResponse.json({ unread_count: 0 })),
    );
    signIn();
    renderWithProviders(<NotificationCenter />);

    await user.click(await screen.findByRole("button", { name: "Notifications" }));
    expect(await screen.findByText("No notifications yet")).toBeInTheDocument();
  });

  it("shows an error state with retry when the list request fails", async () => {
    const user = userEvent.setup();
    server.use(http.get(`${BASE}/api/v1/notifications`, () => HttpResponse.json({ error: { code: "internal_error", message: "boom" } }, { status: 500 })));
    signIn();
    renderWithProviders(<NotificationCenter />);

    await user.click(await screen.findByRole("button", { name: /Notifications/ }));
    expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("marks a notification read and navigates to its real deep link on click", async () => {
    const user = userEvent.setup();
    const notification = makeNotification({ id: "n-click", message: "Low stock: potting soil", deep_link: "/inventory" });
    let markedReadId: string | null = null;
    server.use(
      http.get(`${BASE}/api/v1/notifications`, () => HttpResponse.json(makeNotificationPage([notification]))),
      http.patch(`${BASE}/api/v1/notifications/:id/read`, ({ params }) => {
        markedReadId = params.id as string;
        return HttpResponse.json({ ...notification, read_at: "2026-08-14T09:00:00Z" });
      }),
    );
    signIn();
    renderWithProviders(<NotificationCenter />);

    await user.click(await screen.findByRole("button", { name: /Notifications/ }));
    await user.click(await screen.findByText("Low stock: potting soil"));

    await waitFor(() => expect(markedReadId).toBe("n-click"));
    expect(mockPush).toHaveBeenCalledWith("/inventory");
  });

  it("marks all notifications read via the real bulk endpoint", async () => {
    const user = userEvent.setup();
    let markAllCalled = false;
    server.use(
      http.get(`${BASE}/api/v1/notifications/unread-count`, () => HttpResponse.json({ unread_count: 2 })),
      http.get(`${BASE}/api/v1/notifications`, () => HttpResponse.json(makeNotificationPage([makeNotification(), makeNotification({ id: "n-2" })]))),
      http.post(`${BASE}/api/v1/notifications/mark-all-read`, () => {
        markAllCalled = true;
        return HttpResponse.json({ marked_read_count: 2 });
      }),
    );
    signIn();
    renderWithProviders(<NotificationCenter />);

    await user.click(await screen.findByRole("button", { name: /Notifications/ }));
    await user.click(await screen.findByRole("button", { name: "Mark all read" }));

    await waitFor(() => expect(markAllCalled).toBe(true));
  });
});
