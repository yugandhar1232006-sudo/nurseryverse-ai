import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it, vi } from "vitest";

import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/msw/server";
import ForgotPasswordPage from "@/app/(public)/forgot-password/page";

const BASE = "http://localhost:8000";

vi.mock("@/lib/toast", () => ({
  toast: { apiError: vi.fn(), success: vi.fn(), error: vi.fn(), info: vi.fn(), withUndo: vi.fn() },
}));

describe("ForgotPasswordPage", () => {
  it("shows the identical 'check your email' success message for any submitted email (anti-enumeration)", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ForgotPasswordPage />);

    await user.type(screen.getByLabelText("Email"), "someone@example.com");
    await user.click(screen.getByRole("button", { name: "Send reset link" }));

    expect(await screen.findByText("Reset link sent")).toBeInTheDocument();
    expect(
      screen.getByText(/If that email is registered, a password reset link has been sent\./),
    ).toBeInTheDocument();
  });

  it("shows a toast and stays on the form when the request itself fails (network/server error)", async () => {
    const { toast } = await import("@/lib/toast");
    server.use(http.post(`${BASE}/api/v1/auth/password/reset/request`, () => HttpResponse.error()));
    const user = userEvent.setup();
    renderWithProviders(<ForgotPasswordPage />);

    await user.type(screen.getByLabelText("Email"), "someone@example.com");
    await user.click(screen.getByRole("button", { name: "Send reset link" }));

    await vi.waitFor(() => expect(toast.apiError).toHaveBeenCalled());
    expect(screen.queryByText("Reset link sent")).not.toBeInTheDocument();
  });
});
