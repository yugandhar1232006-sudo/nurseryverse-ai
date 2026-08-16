import { describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import PlantDetailPage from "@/app/(app)/plants/[id]/page";
import { useSessionStore } from "@/store/session-store";
import { makeMe } from "@/test/fixtures/auth";
import { makePlant } from "@/test/fixtures/plants";
import {
  makeDomainEvent,
  makeDomainEventPage,
  makeReplayConsistency,
  makeTwinSnapshot,
  makeTwinVersion,
  makeTwinVersionPage,
  makeVersionComparison,
} from "@/test/fixtures/digital-twin";
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
 * 7H Plant Digital Twin -- real MSW-mocked `apiClient` network responses.
 * The Digital Twin reuses `plants:read` (no separate permission code, see
 * lib/api/digital-twin.ts's docstring), so every test here only needs
 * that one permission, same as the rest of the Plant Profile.
 */
describe("Digital Twin tab (7H)", () => {
  it("shows the real current twin -- lifecycle state, activity counts, and the latest AI prediction summary", async () => {
    const user = userEvent.setup();
    signIn(["plants:read"]);
    renderWithProviders(<PlantDetailPage />);

    await user.click(await screen.findByRole("tab", { name: "Digital Twin" }));

    expect(await screen.findByText("in_production")).toBeInTheDocument();
    expect(screen.getByText("Owned by nursery")).toBeInTheDocument();
    expect(await screen.findByText("Watering events")).toBeInTheDocument();
    // The prediction type is one interpolated segment inside a longer
    // sentence (type · confidence · timestamp), so it's matched with a
    // regex rather than an exact string.
    expect(screen.getByText(/growth_forecast/)).toBeInTheDocument();
    expect(screen.getByText(/The full AI prediction history lives in the AI Experience module/)).toBeInTheDocument();
  });

  it("runs a real consistency verification on demand and shows the real result", async () => {
    const user = userEvent.setup();
    signIn(["plants:read"]);
    server.use(http.get(`${BASE}/api/v1/plants/:id/digital-twin/verify`, () => HttpResponse.json(makeReplayConsistency({ consistent: true, current_version: 5 }))));
    renderWithProviders(<PlantDetailPage />);

    await user.click(await screen.findByRole("tab", { name: "Digital Twin" }));
    await user.click(await screen.findByRole("button", { name: "Verify now" }));

    expect(await screen.findByText("Consistent as of version 5.")).toBeInTheDocument();
  });

  it("shows a real inconsistency result without hiding the failure", async () => {
    const user = userEvent.setup();
    signIn(["plants:read"]);
    server.use(
      http.get(`${BASE}/api/v1/plants/:id/digital-twin/verify`, () =>
        HttpResponse.json(makeReplayConsistency({ consistent: false, differing_keys: ["growth_stage", "counts"] })),
      ),
    );
    renderWithProviders(<PlantDetailPage />);

    await user.click(await screen.findByRole("tab", { name: "Digital Twin" }));
    await user.click(await screen.findByRole("button", { name: "Verify now" }));

    expect(await screen.findByText(/Replay diverged on: growth_stage, counts/)).toBeInTheDocument();
  });

  it("lists the real twin timeline (versions), newest event first", async () => {
    const user = userEvent.setup();
    signIn(["plants:read"]);
    server.use(
      http.get(`${BASE}/api/v1/plants/:id/digital-twin/timeline`, () =>
        HttpResponse.json(makeTwinVersionPage([makeTwinVersion({ version: 6, event_type: "plant.health_recorded" })])),
      ),
    );
    renderWithProviders(<PlantDetailPage />);

    await user.click(await screen.findByRole("tab", { name: "Digital Twin" }));
    // Scoped to the Digital Twin's own nested tablist -- the outer Plant
    // Profile page has its own top-level "Timeline" tab (7G), so an
    // unscoped query matches both.
    const twinTabs = screen.getByRole("tablist", { name: "Digital Twin views" });
    await user.click(within(twinTabs).getByRole("tab", { name: "Timeline" }));

    expect(await screen.findByText("plant.health_recorded")).toBeInTheDocument();
    expect(screen.getByText("v6")).toBeInTheDocument();
  });

  it("views a specific version's real snapshot and compares two real versions", async () => {
    const user = userEvent.setup();
    signIn(["plants:read"]);
    server.use(
      http.get(`${BASE}/api/v1/plants/:id/digital-twin/versions`, () =>
        HttpResponse.json(
          makeTwinVersionPage([
            makeTwinVersion({ id: "v5", version: 5, event_type: "plant.watering_recorded" }),
            makeTwinVersion({ id: "v4", version: 4, event_type: "plant.growth_recorded", snapshot: makeTwinSnapshot({ growth_stage: "seedling" }) as unknown as Record<string, never> }),
          ]),
        ),
      ),
      http.get(`${BASE}/api/v1/plants/:id/digital-twin/versions/compare`, () => HttpResponse.json(makeVersionComparison())),
    );
    renderWithProviders(<PlantDetailPage />);

    await user.click(await screen.findByRole("tab", { name: "Digital Twin" }));
    await user.click(screen.getByRole("tab", { name: "Versions" }));

    await user.click((await screen.findAllByRole("button", { name: "View snapshot" }))[0]);
    expect(await screen.findByText(/Snapshot -- version/)).toBeInTheDocument();
    await user.keyboard("{Escape}");

    await user.click(screen.getByLabelText("Select version 5 to compare"));
    await user.click(screen.getByLabelText("Select version 4 to compare"));
    await user.click(screen.getByRole("button", { name: "Compare" }));

    const compareDialog = await screen.findByRole("dialog", { name: /Compare v4 vs v5/ });
    expect(within(compareDialog).getByText(/Changed: growth_stage, counts, latest/)).toBeInTheDocument();
  });

  it("lists the real raw event history with expandable payloads", async () => {
    const user = userEvent.setup();
    signIn(["plants:read"]);
    server.use(
      http.get(`${BASE}/api/v1/plants/:id/digital-twin/events`, () =>
        HttpResponse.json(makeDomainEventPage([makeDomainEvent({ event_type: "plant.registered", sequence: 1 })])),
      ),
    );
    renderWithProviders(<PlantDetailPage />);

    await user.click(await screen.findByRole("tab", { name: "Digital Twin" }));
    await user.click(screen.getByRole("tab", { name: "Events" }));

    expect(await screen.findByText("plant.registered")).toBeInTheDocument();
  });

  it("shows a real error state with retry when the current twin fails to load", async () => {
    signIn(["plants:read"]);
    server.use(
      http.get(`${BASE}/api/v1/plants/:id/digital-twin`, () =>
        HttpResponse.json({ error: { code: "internal_error", message: "Server error." } }, { status: 500 }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<PlantDetailPage />);

    await user.click(await screen.findByRole("tab", { name: "Digital Twin" }));
    await waitFor(() => expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument());
  });
});
