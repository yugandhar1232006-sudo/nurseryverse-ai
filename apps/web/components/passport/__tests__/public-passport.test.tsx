import { describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import PublicPassportPage from "@/app/(passport)/passport/[token]/page";
import { makePublicPassport, makeQrScanResponse } from "@/test/fixtures/passport";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/msw/server";

const BASE = "http://localhost:8000";

vi.mock("next/navigation", () => ({
  useParams: () => ({ token: "tok_abc123" }),
}));

/**
 * 7K's public, unauthenticated half -- `/passport/[token]`. Deliberately
 * does NOT sign in via `useSessionStore` anywhere in this file: the whole
 * point of this page is that it works with zero session state, and a
 * real signed-out visitor is exactly what these tests simulate.
 */
describe("PublicPassportPage (7K)", () => {
  it("renders the real certificate content with no authentication", async () => {
    server.use(
      http.get(`${BASE}/api/v1/public/passport/:token`, () => HttpResponse.json(makePublicPassport())),
      http.get(`${BASE}/api/v1/public/qr/:token`, () => HttpResponse.json(makeQrScanResponse())),
    );
    renderWithProviders(<PublicPassportPage />);

    expect(await screen.findByText("Bench 3 - Fig #1")).toBeInTheDocument();
    expect(screen.getByText(/NVA-PP-ABCD1234/)).toBeInTheDocument();
    expect(screen.getAllByText("Ficus lyrata").length).toBeGreaterThan(0);
  });

  it("shows the real live 'Current care status' section from the QR scan endpoint, separate from the frozen certificate", async () => {
    server.use(
      http.get(`${BASE}/api/v1/public/passport/:token`, () => HttpResponse.json(makePublicPassport())),
      http.get(`${BASE}/api/v1/public/qr/:token`, () => HttpResponse.json(makeQrScanResponse())),
    );
    renderWithProviders(<PublicPassportPage />);

    const heading = await screen.findByText("Current care status");
    expect(heading).toBeInTheDocument();
    const section = heading.closest("div")?.parentElement as HTMLElement;
    expect(within(section).getByText("Healthy")).toBeInTheDocument();
    expect(within(section).getByText(/10-10-10 fertilizer/)).toBeInTheDocument();
  });

  it("shows a real, unified not-found state for an invalid or expired token -- both public routes return the same generic 404", async () => {
    server.use(
      http.get(`${BASE}/api/v1/public/passport/:token`, () =>
        HttpResponse.json({ error: { code: "not_found", message: "Invalid or expired passport token." } }, { status: 404 }),
      ),
    );
    renderWithProviders(<PublicPassportPage />);

    expect(await screen.findByText(/invalid or has expired/i)).toBeInTheDocument();
  });

  it("still shows the certificate if only the live QR scan read fails, rather than hiding an otherwise-successful page", async () => {
    server.use(
      http.get(`${BASE}/api/v1/public/passport/:token`, () => HttpResponse.json(makePublicPassport())),
      http.get(`${BASE}/api/v1/public/qr/:token`, () =>
        HttpResponse.json({ error: { code: "internal_error", message: "Server error." } }, { status: 500 }),
      ),
    );
    renderWithProviders(<PublicPassportPage />);

    expect(await screen.findByText("Bench 3 - Fig #1")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("Current care status")).not.toBeInTheDocument());
  });
});
