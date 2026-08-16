import { HttpResponse, http } from "msw";
import { describe, expect, it, vi } from "vitest";

import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/msw/server";
import VerifyEmailPage from "@/app/(public)/verify-email/page";

const BASE = "http://localhost:8000";

const { searchParamsRef } = vi.hoisted(() => ({
  searchParamsRef: { current: new URLSearchParams("token=valid-verify-token") },
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParamsRef.current,
}));

describe("VerifyEmailPage", () => {
  it("shows an invalid-link state when there is no token in the URL", () => {
    searchParamsRef.current = new URLSearchParams();
    renderWithProviders(<VerifyEmailPage />);
    expect(screen.getByText("Invalid verification link")).toBeInTheDocument();
  });

  it("auto-submits on mount and shows success without requiring a button press", async () => {
    searchParamsRef.current = new URLSearchParams("token=valid-verify-token");
    renderWithProviders(<VerifyEmailPage />);

    expect(await screen.findByText("Email verified")).toBeInTheDocument();
  });

  it("shows a failure alert when the token is invalid or expired", async () => {
    searchParamsRef.current = new URLSearchParams("token=expired-token");
    server.use(
      http.post(`${BASE}/api/v1/auth/verify-email/confirm`, () =>
        HttpResponse.json(
          { error: { code: "validation_error", message: "This verification link has expired." } },
          { status: 422 },
        ),
      ),
    );
    renderWithProviders(<VerifyEmailPage />);

    expect(await screen.findByText("Verification failed")).toBeInTheDocument();
    expect(screen.getByText("This verification link has expired.")).toBeInTheDocument();
  });
});
