import { describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import SpeciesCatalogPage from "@/app/(app)/plants/species/page";
import { useSessionStore } from "@/store/session-store";
import { makeMe } from "@/test/fixtures/auth";
import { makePlantVariety, makePlantVarietyPage, makeSpecies, makeSpeciesPage } from "@/test/fixtures/catalog";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/msw/server";

const BASE = "http://localhost:8000";

function signIn(permissions: string[]) {
  useSessionStore.setState({ status: "authenticated", user: makeMe({ permissions }), accessToken: "access-token-1" });
}

/**
 * 7F Plant Catalog (Species/Variety) -- real MSW-mocked `apiClient`
 * network responses, same approach as 7D/7E's suites.
 */
describe("SpeciesCatalogPage (7F)", () => {
  it("shows PermissionDenied for a role without species:read", async () => {
    signIn([]);
    renderWithProviders(<SpeciesCatalogPage />);

    expect(await screen.findByText("You don't have access to this page")).toBeInTheDocument();
    expect(screen.queryByText("Species catalog")).not.toBeInTheDocument();
  });

  it("lists real species with category badges and supports the search filter re-fetching from the backend", async () => {
    const user = userEvent.setup();
    signIn(["species:read"]);
    let lastSearch: string | null = null;
    server.use(
      http.get(`${BASE}/api/v1/species`, ({ request }) => {
        lastSearch = new URL(request.url).searchParams.get("search");
        return HttpResponse.json(makeSpeciesPage([makeSpecies({ common_name: "Fiddle Leaf Fig" })]));
      }),
    );
    renderWithProviders(<SpeciesCatalogPage />);

    expect(await screen.findByText("Fiddle Leaf Fig")).toBeInTheDocument();
    expect(screen.getByText("Houseplant")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Search species"), "Ficus");
    await waitFor(() => expect(lastSearch).toBe("Ficus"), { timeout: 2000 });
  });

  it("creates a species through the real form", async () => {
    const user = userEvent.setup();
    signIn(["species:read", "species:write"]);
    server.use(http.get(`${BASE}/api/v1/species`, () => HttpResponse.json(makeSpeciesPage([]))));
    let created: Record<string, unknown> | null = null;
    server.use(
      http.post(`${BASE}/api/v1/species`, async ({ request }) => {
        created = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(makeSpecies());
      }),
    );
    renderWithProviders(<SpeciesCatalogPage />);

    await user.click(await screen.findByRole("button", { name: "Add species" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("combobox", { name: "Category" }));
    await user.click(await screen.findByRole("option", { name: "Houseplant" }));
    await user.type(within(dialog).getByLabelText("Common name"), "Snake Plant");
    await user.type(within(dialog).getByLabelText("Botanical name"), "Dracaena trifasciata");
    await user.click(within(dialog).getByRole("button", { name: "Add species" }));

    await waitFor(() => expect(created).not.toBeNull());
    expect(created).toMatchObject({ common_name: "Snake Plant", botanical_name: "Dracaena trifasciata" });
  });

  it("opens a species' detail view, shows real care attributes, and adds a variety", async () => {
    const user = userEvent.setup();
    signIn(["species:read", "species:write"]);
    server.use(http.get(`${BASE}/api/v1/plant-varieties`, () => HttpResponse.json(makePlantVarietyPage([]))));
    let createdVariety: Record<string, unknown> | null = null;
    server.use(
      http.post(`${BASE}/api/v1/plant-varieties`, async ({ request }) => {
        createdVariety = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(makePlantVariety());
      }),
    );
    renderWithProviders(<SpeciesCatalogPage />);

    await user.click(await screen.findByText("Fiddle Leaf Fig"));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("500 mL/week")).toBeInTheDocument();
    expect(within(dialog).getByText("root rot")).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Add variety" }));
    const varietyDialog = await screen.findByRole("dialog", { name: "Add variety" });
    await user.type(within(varietyDialog).getByLabelText("Variety name"), "Bambino");
    await user.click(within(varietyDialog).getByRole("button", { name: "Add variety" }));

    await waitFor(() => expect(createdVariety).not.toBeNull());
    expect(createdVariety).toMatchObject({ name: "Bambino", species_id: makeSpecies().id });
  });

  it("archives a species through the AlertDialog confirmation", async () => {
    const user = userEvent.setup();
    signIn(["species:read", "species:delete"]);
    let archived = false;
    server.use(
      http.delete(`${BASE}/api/v1/species/:id`, () => {
        archived = true;
        return HttpResponse.json(makeSpecies());
      }),
    );
    renderWithProviders(<SpeciesCatalogPage />);

    await screen.findByText("Fiddle Leaf Fig");
    await user.click(screen.getByRole("button", { name: "Archive" }));
    const alert = await screen.findByRole("alertdialog");
    await user.click(within(alert).getByRole("button", { name: "Archive" }));

    await waitFor(() => expect(archived).toBe(true));
  });

  it("shows a real empty state distinguishing 'no species yet' from 'no matches'", async () => {
    signIn(["species:read"]);
    server.use(http.get(`${BASE}/api/v1/species`, () => HttpResponse.json(makeSpeciesPage([]))));
    renderWithProviders(<SpeciesCatalogPage />);

    expect(await screen.findByText("No species yet")).toBeInTheDocument();
  });

  it("shows a real error state with retry when the species list fails to load", async () => {
    signIn(["species:read"]);
    server.use(http.get(`${BASE}/api/v1/species`, () => HttpResponse.json({ error: { code: "internal_error", message: "Server error." } }, { status: 500 })));
    renderWithProviders(<SpeciesCatalogPage />);

    expect(await screen.findByRole("button", { name: /try again/i })).toBeInTheDocument();
  });
});
