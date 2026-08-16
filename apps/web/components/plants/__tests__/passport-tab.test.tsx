import { describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import PlantDetailPage from "@/app/(app)/plants/[id]/page";
import { useSessionStore } from "@/store/session-store";
import { makeMe } from "@/test/fixtures/auth";
import { makePlant } from "@/test/fixtures/plants";
import { makePassport } from "@/test/fixtures/passport";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/msw/server";

const BASE = "http://localhost:8000";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useParams: () => ({ id: makePlant().id }),
}));

function signIn(permissions: string[]) {
  useSessionStore.setState({ status: "authenticated", user: makeMe({ permissions }), accessToken: "access-token-1" });
}

/**
 * 7K's internal, authenticated half -- the Passport tab on the existing
 * `/plants/[id]` page (see docs/frontend/15-plant-passport.md for why it
 * lives here rather than a standalone page). Separate file from
 * `plant-lifecycle.test.tsx` to avoid bloating that already-large suite.
 */
describe("PassportTab (7K)", () => {
  it("hides the Passport tab entirely for a role without passport:read", async () => {
    signIn(["plants:read"]);
    server.use(http.get(`${BASE}/api/v1/plants/:id`, () => HttpResponse.json(makePlant())));
    renderWithProviders(<PlantDetailPage />);

    await screen.findByRole("tab", { name: "Overview" });
    expect(screen.queryByRole("tab", { name: "Passport" })).not.toBeInTheDocument();
  });

  it("lists real passport versions and generates a new one through the real form", async () => {
    const user = userEvent.setup();
    signIn(["plants:read", "passport:read", "passport:generate"]);
    let created: Record<string, unknown> | null = null;
    server.use(
      http.get(`${BASE}/api/v1/plants/:id`, () => HttpResponse.json(makePlant())),
      http.get(`${BASE}/api/v1/plants/:plant_id/passports`, () => HttpResponse.json([makePassport({ version: 1 })])),
      http.post(`${BASE}/api/v1/plants/:plant_id/passports`, async ({ request }) => {
        created = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(makePassport({ version: 2 }));
      }),
    );
    renderWithProviders(<PlantDetailPage />);

    await user.click(await screen.findByRole("tab", { name: "Passport" }));
    expect(await screen.findByText("Version 1")).toBeInTheDocument();
    expect(screen.getByText("Latest")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Generate passport" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Generate passport" }));

    await waitFor(() => expect(created).not.toBeNull());
    expect(created).toMatchObject({ expires_at: null, sale_id: null, sale_item_id: null });
  });

  it("shows a real empty state when no passport has been generated yet", async () => {
    signIn(["plants:read", "passport:read"]);
    server.use(
      http.get(`${BASE}/api/v1/plants/:id`, () => HttpResponse.json(makePlant())),
      http.get(`${BASE}/api/v1/plants/:plant_id/passports`, () => HttpResponse.json([])),
    );
    renderWithProviders(<PlantDetailPage />);

    await userEvent.setup().click(await screen.findByRole("tab", { name: "Passport" }));
    expect(await screen.findByText("No passport generated yet")).toBeInTheDocument();
  });

  it("copies the real public link to the clipboard", async () => {
    const user = userEvent.setup();
    signIn(["plants:read", "passport:read"]);
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    server.use(
      http.get(`${BASE}/api/v1/plants/:id`, () => HttpResponse.json(makePlant())),
      http.get(`${BASE}/api/v1/plants/:plant_id/passports`, () =>
        HttpResponse.json([makePassport({ public_url: "http://localhost:3000/passport/tok_xyz" })]),
      ),
    );
    renderWithProviders(<PlantDetailPage />);

    await user.click(await screen.findByRole("tab", { name: "Passport" }));
    await user.click(await screen.findByRole("button", { name: "Copy public link" }));

    await waitFor(() => expect(writeText).toHaveBeenCalledWith("http://localhost:3000/passport/tok_xyz"));
  });
});
