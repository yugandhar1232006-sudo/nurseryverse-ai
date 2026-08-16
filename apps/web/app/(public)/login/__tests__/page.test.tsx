import { HttpResponse, http } from "msw";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/msw/server";
import { VALID_EMAIL, VALID_PASSWORD } from "@/test/msw/handlers";
import LoginPage from "@/app/(public)/login/page";

const BASE = "http://localhost:8000";

const { mockReplace, searchParamsRef } = vi.hoisted(() => ({
  mockReplace: vi.fn(),
  searchParamsRef: { current: new URLSearchParams() },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace, push: vi.fn() }),
  useSearchParams: () => searchParamsRef.current,
  usePathname: () => "/login",
}));

async function fillAndSubmit(email: string, password: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Email"), email);
  await user.type(screen.getByLabelText("Password"), password);
  await user.click(screen.getByRole("button", { name: "Sign in" }));
}

describe("LoginPage", () => {
  beforeEach(() => {
    mockReplace.mockClear();
    searchParamsRef.current = new URLSearchParams();
  });

  it("renders the sign-in form", () => {
    renderWithProviders(<LoginPage />);
    expect(
      screen.getByText("Enter your credentials to access your NurseryVerse AI account."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });

  it("shows client-side validation errors for an empty submission without calling the API", async () => {
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />);

    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Email is required.")).toBeInTheDocument();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("successful login redirects to / by default", async () => {
    renderWithProviders(<LoginPage />);

    await fillAndSubmit(VALID_EMAIL, VALID_PASSWORD);

    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/"));
  });

  it("successful login redirects to a same-origin ?next= destination", async () => {
    searchParamsRef.current = new URLSearchParams("next=/account");
    renderWithProviders(<LoginPage />);

    await fillAndSubmit(VALID_EMAIL, VALID_PASSWORD);

    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/account"));
  });

  it("ignores a protocol-relative ?next= as an open-redirect attempt and falls back to /", async () => {
    searchParamsRef.current = new URLSearchParams("next=//evil.example.com");
    renderWithProviders(<LoginPage />);

    await fillAndSubmit(VALID_EMAIL, VALID_PASSWORD);

    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/"));
  });

  it("shows an invalid-credentials alert on wrong password and does not redirect", async () => {
    renderWithProviders(<LoginPage />);

    await fillAndSubmit(VALID_EMAIL, "wrong-password-here");

    expect(await screen.findByText("Sign-in failed")).toBeInTheDocument();
    expect(screen.getByText("Incorrect email or password.")).toBeInTheDocument();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("shows an account-locked alert when the backend's lockout message is returned", async () => {
    server.use(
      http.post(`${BASE}/api/v1/auth/login`, () =>
        HttpResponse.json(
          {
            error: {
              code: "authentication_error",
              message: "Account is temporarily locked due to too many failed login attempts.",
            },
          },
          { status: 401 },
        ),
      ),
    );
    renderWithProviders(<LoginPage />);

    await fillAndSubmit(VALID_EMAIL, VALID_PASSWORD);

    expect(await screen.findByText("Account temporarily locked")).toBeInTheDocument();
  });

  it("shows a network-failure alert when the request can't reach the server", async () => {
    server.use(http.post(`${BASE}/api/v1/auth/login`, () => HttpResponse.error()));
    renderWithProviders(<LoginPage />);

    await fillAndSubmit(VALID_EMAIL, VALID_PASSWORD);

    expect(await screen.findByText("Can't reach the server")).toBeInTheDocument();
  });

  it("shows a server-unavailable alert on a 5xx response", async () => {
    server.use(
      http.post(`${BASE}/api/v1/auth/login`, () =>
        HttpResponse.json({ error: { code: "unknown_error", message: "Down for maintenance." } }, { status: 503 }),
      ),
    );
    renderWithProviders(<LoginPage />);

    await fillAndSubmit(VALID_EMAIL, VALID_PASSWORD);

    expect(await screen.findByText("Service unavailable")).toBeInTheDocument();
  });

  it("disables the submit button while the request is pending", async () => {
    server.use(
      http.post(`${BASE}/api/v1/auth/login`, async () => {
        await new Promise((resolve) => setTimeout(resolve, 50));
        return HttpResponse.json({
          access_token: "access-token-1",
          refresh_token: "refresh-token-1",
          token_type: "bearer",
          expires_in: 900,
        });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />);
    await user.type(screen.getByLabelText("Email"), VALID_EMAIL);
    await user.type(screen.getByLabelText("Password"), VALID_PASSWORD);

    await user.click(screen.getByRole("button", { name: "Sign in" }));

    // While pending the button also contains a Spinner (role="status",
    // aria-label="Loading"), which changes the button's computed
    // accessible name to include that label -- match with a substring
    // regex rather than the exact idle-state name.
    expect(screen.getByRole("button", { name: /sign in/i })).toBeDisabled();
    await waitFor(() => expect(mockReplace).toHaveBeenCalled());
  });
});
