import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { MobileNavSheet, MobileTabBar } from "@/components/layout/mobile-nav";
import { useSessionStore } from "@/store/session-store";
import { useUiStore } from "@/store/ui-store";
import { makeMe } from "@/test/fixtures/auth";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

function signInWith(permissions: string[]) {
  useSessionStore.setState({ status: "authenticated", user: makeMe({ permissions }) });
}

describe("MobileTabBar", () => {
  it("renders only the permission-permitted subset of the fixed 4-item mobile set", () => {
    signInWith(["plants:read"]);
    render(<MobileTabBar />);

    expect(screen.getByRole("link", { name: "Dashboard" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Plants" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Watering" })).not.toBeInTheDocument(); // no watering:read
    expect(screen.getByRole("button", { name: "Notifications" })).toBeInTheDocument(); // never gated
  });

  it("opens the shared notification center panel (not a second notification UI) when Alerts is tapped", async () => {
    const user = userEvent.setup();
    signInWith([]);
    render(<MobileTabBar />);

    expect(useUiStore.getState().notificationCenterOpen).toBe(false);
    await user.click(screen.getByRole("button", { name: "Notifications" }));
    expect(useUiStore.getState().notificationCenterOpen).toBe(true);
  });

  it("shows a loading skeleton while the session is still resolving", () => {
    useSessionStore.setState({ status: "resolving", user: null });
    render(<MobileTabBar />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});

describe("MobileNavSheet", () => {
  it("is closed by default and shows nothing", () => {
    signInWith([]);
    render(<MobileNavSheet />);
    expect(screen.queryByText("NurseryVerse AI")).not.toBeInTheDocument();
  });

  it("renders the full permitted nav tree once opened via useUiStore", () => {
    signInWith(["inventory:read", "reports:read"]);
    useUiStore.setState({ mobileNavOpen: true });
    render(<MobileNavSheet />);

    expect(screen.getByText("NurseryVerse AI")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Inventory" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Reports" })).toBeInTheDocument();
  });

  it("closes when a nav link is tapped", async () => {
    const user = userEvent.setup();
    signInWith(["inventory:read"]);
    useUiStore.setState({ mobileNavOpen: true });
    render(<MobileNavSheet />);

    await user.click(screen.getByRole("link", { name: "Inventory" }));
    expect(useUiStore.getState().mobileNavOpen).toBe(false);
  });
});
