import { describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { GlobalSearch } from "@/components/layout/global-search";
import { useSessionStore } from "@/store/session-store";
import { useUiStore } from "@/store/ui-store";
import { makeMe } from "@/test/fixtures/auth";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/msw/server";

const { mockPush } = vi.hoisted(() => ({ mockPush: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

const BASE = "http://localhost:8000";

function signInWith(permissions: string[]) {
  useSessionStore.setState({ status: "authenticated", user: makeMe({ permissions }), accessToken: "access-token-1" });
}

describe("GlobalSearch", () => {
  it("renders nothing when closed", () => {
    signInWith(["plants:read"]);
    renderWithProviders(<GlobalSearch />);
    expect(screen.queryByPlaceholderText(/Search plants/)).not.toBeInTheDocument();
  });

  it("prompts for at least 2 characters before searching", async () => {
    const user = userEvent.setup();
    signInWith(["plants:read"]);
    renderWithProviders(<GlobalSearch />);
    useUiStore.setState({ commandPaletteOpen: true });

    const input = await screen.findByPlaceholderText(/Search plants/);
    await user.type(input, "a");
    expect(screen.getByText("Type at least 2 characters to search.")).toBeInTheDocument();
  });

  it("shows a permission-scoped empty state when the user has no searchable permissions at all", async () => {
    signInWith([]);
    renderWithProviders(<GlobalSearch />);
    useUiStore.setState({ commandPaletteOpen: true });

    expect(await screen.findByText("Nothing to search yet")).toBeInTheDocument();
  });

  it("returns real results from the real plants search endpoint and never fabricates them", async () => {
    const user = userEvent.setup();
    server.use(
      http.get(`${BASE}/api/v1/plants`, ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get("search")).toBe("fic");
        return HttpResponse.json({
          items: [
            { id: "p-1", nursery_id: "n", branch_id: "b", species_id: "s", variety_id: null, common_label: "Ficus Lyrata #12", zone: "A1", status: "healthy", qr_code_token: "t", price: null, planted_at: "2026-01-01T00:00:00Z", sold_at: null, deceased_at: null, deceased_reason: null, batch_number: "B-12", supplier_id: null, purchase_price: null, purchase_date: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
          ],
          meta: { page: 1, page_size: 5, total_items: 1, total_pages: 1 },
        });
      }),
    );
    signInWith(["plants:read"]);
    renderWithProviders(<GlobalSearch />);
    useUiStore.setState({ commandPaletteOpen: true });

    const input = await screen.findByPlaceholderText(/Search plants/);
    await user.type(input, "fic");

    expect(await screen.findByText("Ficus Lyrata #12")).toBeInTheDocument();
  });

  it("only fans out to endpoints the user actually has permission for", async () => {
    const user = userEvent.setup();
    let customersRequested = false;
    server.use(
      http.get(`${BASE}/api/v1/customers`, () => {
        customersRequested = true;
        return HttpResponse.json({ items: [], meta: { page: 1, page_size: 5, total_items: 0, total_pages: 0 } });
      }),
    );
    signInWith(["plants:read"]); // no customers:read
    renderWithProviders(<GlobalSearch />);
    useUiStore.setState({ commandPaletteOpen: true });

    const input = await screen.findByPlaceholderText(/Search plants/);
    await user.type(input, "abc");
    await waitFor(() => expect(screen.queryByText("Type at least 2 characters to search.")).not.toBeInTheDocument());
    expect(customersRequested).toBe(false);
  });

  it("navigates keyboard-only via ArrowDown + Enter to a result's real parent list route", async () => {
    const user = userEvent.setup();
    server.use(
      http.get(`${BASE}/api/v1/species`, () =>
        HttpResponse.json({
          items: [
            { id: "sp-1", nursery_id: "n", category_id: "c", common_name: "Snake Plant", botanical_name: "Dracaena trifasciata", light_requirement: null, water_baseline_ml_per_week: null, soil_type: null, temperature_min_celsius: null, temperature_max_celsius: null, growth_curve_baseline: null, disease_susceptibility: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
          ],
          meta: { page: 1, page_size: 5, total_items: 1, total_pages: 1 },
        }),
      ),
    );
    signInWith(["species:read"]);
    renderWithProviders(<GlobalSearch />);
    useUiStore.setState({ commandPaletteOpen: true });

    const input = await screen.findByPlaceholderText(/Search plants/);
    await user.type(input, "snake");
    await screen.findByText("Snake Plant");

    await user.keyboard("{ArrowDown}{Enter}");
    expect(mockPush).toHaveBeenCalledWith("/plants/species");
  });

  it("closes and resets the query when reopened", async () => {
    const user = userEvent.setup();
    signInWith(["plants:read"]);
    renderWithProviders(<GlobalSearch />);
    useUiStore.setState({ commandPaletteOpen: true });

    const input = await screen.findByPlaceholderText(/Search plants/);
    await user.type(input, "xyz");
    useUiStore.setState({ commandPaletteOpen: false });
    await waitFor(() => expect(screen.queryByPlaceholderText(/Search plants/)).not.toBeInTheDocument());

    useUiStore.setState({ commandPaletteOpen: true });
    const reopenedInput = await screen.findByPlaceholderText(/Search plants/);
    expect(reopenedInput).toHaveValue("");
    void user;
  });
});
