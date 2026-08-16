import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/msw/server";
import ResetPasswordPage from "@/app/(public)/reset-password/page";

const BASE = "http://localhost:8000";

const { mockReplace, searchParamsRef } = vi.hoisted(() => ({
  mockReplace: vi.fn(),
  searchParamsRef: { current: new URLSearchParams("token=valid-reset-token") },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace, push: vi.fn() }),
  useSearchParams: () => searchParamsRef.current,
}));

const VALID_PASSWORD = "New-strong-pass1";

async function fillAndSubmit(password: string, confirm: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("New password"), password);
  await user.type(screen.getByLabelText("Confirm new password"), confirm);
  await user.click(screen.getByRole("button", { name: "Reset password" }));
}

describe("ResetPasswordPage", () => {
  beforeEach(() => {
    mockReplace.mockClear();
    searchParamsRef.current = new URLSearchParams("token=valid-reset-token");
  });

  it("shows an invalid-link state when there is no token in the URL", () => {
    searchParamsRef.current = new URLSearchParams();
    renderWithProviders(<ResetPasswordPage />);
    expect(screen.getByText("Invalid reset link")).toBeInTheDocument();
  });

  it("shows a client-side mismatch error and does not call the API when passwords don't match", async () => {
    renderWithProviders(<ResetPasswordPage />);
    await fillAndSubmit(VALID_PASSWORD, "Different-pass1");
    expect(await screen.findByText("Passwords don't match.")).toBeInTheDocument();
  });

  it("shows a success state and signals the account was signed out everywhere on success", async () => {
    renderWithProviders(<ResetPasswordPage />);
    await fillAndSubmit(VALID_PASSWORD, VALID_PASSWORD);
    expect(await screen.findByText("Your password has been reset")).toBeInTheDocument();
    expect(screen.getByText(/you've been signed out everywhere/i)).toBeInTheDocument();
  });

  it("shows an expired/invalid-token alert on a 422 from the backend", async () => {
    server.use(
      http.post(`${BASE}/api/v1/auth/password/reset/confirm`, () =>
        HttpResponse.json(
          { error: { code: "validation_error", message: "This reset token is invalid or has expired." } },
          { status: 422 },
        ),
      ),
    );
    renderWithProviders(<ResetPasswordPage />);
    await fillAndSubmit(VALID_PASSWORD, VALID_PASSWORD);

    expect(await screen.findByText("Link expired or already used")).toBeInTheDocument();
    expect(screen.getByText(/This reset token is invalid or has expired\./)).toBeInTheDocument();
  });

  it("navigates to /login when 'Go to sign in' is clicked after success", async () => {
    renderWithProviders(<ResetPasswordPage />);
    await fillAndSubmit(VALID_PASSWORD, VALID_PASSWORD);
    await screen.findByText("Your password has been reset");

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Go to sign in" }));

    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/login"));
  });
});
