import { beforeEach, describe, expect, it, vi } from "vitest";

import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "@/test/utils";
import { useSessionStore } from "@/store/session-store";
import { makeMe } from "@/test/fixtures/auth";
import AppLayout from "@/app/(app)/layout";

const { mockReplace } = vi.hoisted(() => ({ mockReplace: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace, push: vi.fn() }),
  usePathname: () => "/account",
}));

describe("AppLayout (protected route guard)", () => {
  beforeEach(() => {
    mockReplace.mockClear();
  });

  it("shows a loading skeleton while session status is still resolving, and does not redirect", async () => {
    useSessionStore.setState({ status: "resolving" });
    renderWithProviders(
      <AppLayout>
        <div>Secret content</div>
      </AppLayout>,
    );

    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByText("Secret content")).not.toBeInTheDocument();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("redirects to /login with the current path preserved when unauthenticated, and renders nothing", async () => {
    useSessionStore.setState({ status: "unauthenticated", user: null });
    const { container } = renderWithProviders(
      <AppLayout>
        <div>Secret content</div>
      </AppLayout>,
    );

    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/login?next=%2Faccount"));
    expect(screen.queryByText("Secret content")).not.toBeInTheDocument();
    expect(container.firstChild).toBeNull();
  });

  it("renders the application shell and children once authenticated", async () => {
    useSessionStore.setState({ status: "authenticated", user: makeMe({ is_email_verified: true }) });
    renderWithProviders(
      <AppLayout>
        <div>Secret content</div>
      </AppLayout>,
    );

    expect(await screen.findByText("Secret content")).toBeInTheDocument();
    // The persistent header no longer has a static "NurseryVerse AI"
    // wordmark as of 7C's AppShell (org context is real API data, not a
    // hardcoded string) -- assert against shell chrome that renders
    // unconditionally instead: the skip link and the primary nav
    // landmark.
    expect(screen.getByText("Skip to main content")).toBeInTheDocument();
    expect(screen.getAllByRole("navigation", { name: "Primary" }).length).toBeGreaterThan(0);
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("shows the email-verification banner for an authenticated user with an unverified email", async () => {
    useSessionStore.setState({ status: "authenticated", user: makeMe({ is_email_verified: false }) });
    renderWithProviders(
      <AppLayout>
        <div>Secret content</div>
      </AppLayout>,
    );

    expect(
      await screen.findByText("Please verify your email address to secure your account."),
    ).toBeInTheDocument();
  });

  it("does not show the email-verification banner once the email is verified", async () => {
    useSessionStore.setState({ status: "authenticated", user: makeMe({ is_email_verified: true }) });
    renderWithProviders(
      <AppLayout>
        <div>Secret content</div>
      </AppLayout>,
    );

    await screen.findByText("Secret content");
    expect(
      screen.queryByText("Please verify your email address to secure your account."),
    ).not.toBeInTheDocument();
  });
});
