import { describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { UserMenu } from "@/components/layout/user-menu";
import { useSessionStore } from "@/store/session-store";
import { makeMe } from "@/test/fixtures/auth";
import { renderWithProviders } from "@/test/utils";

const { mockReplace } = vi.hoisted(() => ({ mockReplace: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace, push: vi.fn() }),
}));

function signInWith(overrides: Parameters<typeof makeMe>[0] = {}) {
  useSessionStore.setState({ status: "authenticated", user: makeMe(overrides), accessToken: "t", refreshToken: "r" });
}

describe("UserMenu", () => {
  it("shows a loading skeleton before the session resolves", () => {
    useSessionStore.setState({ status: "resolving", user: null });
    renderWithProviders(<UserMenu />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("opens to reveal the real signed-in identity", async () => {
    const user = userEvent.setup();
    signInWith({ full_name: "Jane Grower", email: "jane@example.com" });
    renderWithProviders(<UserMenu />);

    await user.click(screen.getByRole("button", { name: /Account menu for Jane Grower/ }));
    expect(screen.getByText("Jane Grower")).toBeInTheDocument();
    expect(screen.getByText("jane@example.com")).toBeInTheDocument();
  });

  it("shows the Admin badge only for a permission-holding user (permission-aware UI, not a role string check)", async () => {
    const user = userEvent.setup();
    signInWith({ permissions: ["roles:manage"] });
    renderWithProviders(<UserMenu />);

    await user.click(screen.getByRole("button", { name: /Account menu/ }));
    expect(screen.getByText("Admin")).toBeInTheDocument();
  });

  it("hides the Admin badge for a user without an admin-shaped permission", async () => {
    const user = userEvent.setup();
    signInWith({ permissions: ["plants:read"] });
    renderWithProviders(<UserMenu />);

    await user.click(screen.getByRole("button", { name: /Account menu/ }));
    expect(screen.queryByText("Admin")).not.toBeInTheDocument();
  });

  it("logs out and redirects to /login on Sign out, clearing local session state regardless of backend outcome", async () => {
    const user = userEvent.setup();
    signInWith();
    renderWithProviders(<UserMenu />);

    await user.click(screen.getByRole("button", { name: /Account menu/ }));
    await user.click(screen.getByRole("menuitem", { name: /Sign out/ }));

    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/login"));
    expect(useSessionStore.getState().status).toBe("unauthenticated");
  });
});
