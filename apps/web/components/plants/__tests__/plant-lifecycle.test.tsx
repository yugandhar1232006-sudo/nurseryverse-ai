import { describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import PlantsPage from "@/app/(app)/plants/page";
import PlantDetailPage from "@/app/(app)/plants/[id]/page";
import { useSessionStore } from "@/store/session-store";
import { makeMe } from "@/test/fixtures/auth";
import { makeSpecies } from "@/test/fixtures/catalog";
import {
  makeDiseaseReport,
  makeGrowthRecord,
  makePlant,
  makePlantPage,
} from "@/test/fixtures/plants";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/msw/server";

const BASE = "http://localhost:8000";
const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  useParams: () => ({ id: makePlant().id }),
}));

function signIn(permissions: string[]) {
  useSessionStore.setState({ status: "authenticated", user: makeMe({ permissions }), accessToken: "access-token-1" });
}

/**
 * 7G Plant Lifecycle -- real MSW-mocked `apiClient` network responses,
 * same approach as 7D-7F's suites. Covers both `/plants` (the list) and
 * `/plants/[id]` (the Plant Profile's tabs), since they share one
 * permission model and one set of fixtures.
 */
describe("PlantsPage (7G)", () => {
  it("shows PermissionDenied for a role without plants:read", async () => {
    signIn([]);
    renderWithProviders(<PlantsPage />);

    expect(await screen.findByText("You don't have access to this page")).toBeInTheDocument();
    expect(screen.queryByText("Plants")).not.toBeInTheDocument();
  });

  it("lists real plants with status badges and supports the search filter re-fetching from the backend", async () => {
    const user = userEvent.setup();
    signIn(["plants:read"]);
    let lastSearch: string | null = null;
    server.use(
      http.get(`${BASE}/api/v1/plants`, ({ request }) => {
        lastSearch = new URL(request.url).searchParams.get("search");
        return HttpResponse.json(makePlantPage([makePlant({ common_label: "Bench 3 - Fig #1" })]));
      }),
    );
    renderWithProviders(<PlantsPage />);

    expect(await screen.findByText("Bench 3 - Fig #1")).toBeInTheDocument();
    expect(screen.getByText("In production")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Search plants"), "Fig");
    await waitFor(() => expect(lastSearch).toBe("Fig"), { timeout: 2000 });
  });

  it("registers a plant through the real form", async () => {
    const user = userEvent.setup();
    signIn(["plants:read", "plants:write"]);
    let registered: Record<string, unknown> | null = null;
    server.use(
      http.post(`${BASE}/api/v1/plants`, async ({ request }) => {
        registered = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(makePlant());
      }),
    );
    renderWithProviders(<PlantsPage />);

    await user.click(await screen.findByRole("button", { name: "Register plant" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("combobox", { name: "Branch" }));
    await user.click(await screen.findByRole("option", { name: "Main Branch" }));
    await user.click(within(dialog).getByRole("combobox", { name: "Species" }));
    await user.click(await screen.findByRole("option", { name: "Fiddle Leaf Fig" }));
    await user.click(within(dialog).getByRole("button", { name: "Register plant" }));

    await waitFor(() => expect(registered).not.toBeNull());
    expect(registered).toMatchObject({ species_id: makeSpecies().id });
  });

  it("shows a real empty state distinguishing 'no plants yet' from 'no matches'", async () => {
    signIn(["plants:read"]);
    server.use(http.get(`${BASE}/api/v1/plants`, () => HttpResponse.json(makePlantPage([]))));
    renderWithProviders(<PlantsPage />);

    expect(await screen.findByText("No plants yet")).toBeInTheDocument();
  });

  it("shows a real error state with retry when the plant list fails to load", async () => {
    signIn(["plants:read"]);
    server.use(
      http.get(`${BASE}/api/v1/plants`, () =>
        HttpResponse.json({ error: { code: "internal_error", message: "Server error." } }, { status: 500 }),
      ),
    );
    renderWithProviders(<PlantsPage />);

    expect(await screen.findByRole("button", { name: /try again/i })).toBeInTheDocument();
  });
});

describe("PlantDetailPage (7G)", () => {
  it("shows the plant's real identity, species, and status, and records a growth measurement", async () => {
    const user = userEvent.setup();
    signIn(["plants:read", "growth:read", "growth:write"]);
    server.use(http.get(`${BASE}/api/v1/species/:id`, () => HttpResponse.json(makeSpecies())));
    let recorded: Record<string, unknown> | null = null;
    server.use(
      http.post(`${BASE}/api/v1/plants/:plant_id/growth-timeline`, async ({ request }) => {
        recorded = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(makeGrowthRecord());
      }),
    );
    renderWithProviders(<PlantDetailPage />);

    // Scoped to the `<h1>` specifically -- the read-only Overview tab
    // (this signed-in user lacks `plants:write`) also renders the same
    // label text in a `<dd>`, so a plain `findByText` would match both.
    expect(await screen.findByRole("heading", { name: "Bench 3 - Fig #1" })).toBeInTheDocument();
    expect(await screen.findByText("Fiddle Leaf Fig")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Growth" }));
    await user.click(await screen.findByRole("button", { name: "Record measurement" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Height (cm)"), "50");
    await user.click(within(dialog).getByRole("button", { name: "Save measurement" }));

    await waitFor(() => expect(recorded).not.toBeNull());
    expect(recorded).toMatchObject({ height_cm: 50 });
  });

  it("confirms a draft disease report from the Health tab", async () => {
    const user = userEvent.setup();
    signIn(["plants:read", "health:read", "disease:approve"]);
    let confirmed = false;
    server.use(
      http.get(`${BASE}/api/v1/plants/:plant_id/disease-reports`, () => HttpResponse.json([makeDiseaseReport()])),
      http.post(`${BASE}/api/v1/disease-reports/:id/confirm`, () => {
        confirmed = true;
        return HttpResponse.json(makeDiseaseReport({ status: "confirmed" }));
      }),
    );
    renderWithProviders(<PlantDetailPage />);

    await user.click(await screen.findByRole("tab", { name: "Health" }));
    expect(await screen.findByText("Root rot")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirm" }));

    await waitFor(() => expect(confirmed).toBe(true));
  });

  it("moves a plant to a different branch through the real form", async () => {
    const user = userEvent.setup();
    signIn(["plants:read", "plants:transfer"]);
    let moved: Record<string, unknown> | null = null;
    server.use(
      http.post(`${BASE}/api/v1/plants/:id/move`, async ({ request }) => {
        moved = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(makePlant());
      }),
    );
    renderWithProviders(<PlantDetailPage />);

    await user.click(await screen.findByRole("button", { name: "Move" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Destination zone (optional)"), "Greenhouse C");
    await user.click(within(dialog).getByRole("button", { name: "Move plant" }));

    await waitFor(() => expect(moved).not.toBeNull());
    expect(moved).toMatchObject({ to_zone: "Greenhouse C" });
  });

  it("surfaces a 409 from an illegal status transition without silently closing the dialog", async () => {
    // `toast.apiError` (see lib/toast.ts) renders through the app's root
    // `<Toaster>` (app/layout.tsx), which `renderWithProviders` doesn't
    // mount for an isolated component test -- so this asserts the real,
    // in-tree observable behavior instead: `TransitionStatusDialog` only
    // closes on mutation success, so a 409 leaves it open rather than
    // silently discarding the error, which is what would happen if
    // `onError` were missing entirely.
    const user = userEvent.setup();
    signIn(["plants:read", "plants:write"]);
    let attempted = false;
    server.use(
      http.post(`${BASE}/api/v1/plants/:id/status`, () => {
        attempted = true;
        return HttpResponse.json({ error: { code: "invalid_transition", message: "Cannot move from sold to in_production." } }, { status: 409 });
      }),
    );
    renderWithProviders(<PlantDetailPage />);

    await user.click(await screen.findByRole("button", { name: "Change status" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Update status" }));

    await waitFor(() => expect(attempted).toBe(true));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("shows a real error state with retry when the plant fails to load", async () => {
    signIn(["plants:read"]);
    server.use(
      http.get(`${BASE}/api/v1/plants/:id`, () =>
        HttpResponse.json({ error: { code: "internal_error", message: "Server error." } }, { status: 500 }),
      ),
    );
    renderWithProviders(<PlantDetailPage />);

    expect(await screen.findByRole("button", { name: /try again/i })).toBeInTheDocument();
  });
});
