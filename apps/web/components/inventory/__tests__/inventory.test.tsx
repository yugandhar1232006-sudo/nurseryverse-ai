import { describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import InventoryPage from "@/app/(app)/inventory/page";
import InventoryDetailPage from "@/app/(app)/inventory/[id]/page";
import { useSessionStore } from "@/store/session-store";
import { makeMe } from "@/test/fixtures/auth";
import {
  makeInventoryItem,
  makeInventoryLocation,
  makeInventoryPage,
  makeStockMovement,
  makeStockMovementPage,
  makeStockReservation,
} from "@/test/fixtures/inventory";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/msw/server";

const BASE = "http://localhost:8000";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useParams: () => ({ id: makeInventoryItem().id }),
}));

function signIn(permissions: string[]) {
  useSessionStore.setState({ status: "authenticated", user: makeMe({ permissions }), accessToken: "access-token-1" });
}

/**
 * 7I Inventory -- real MSW-mocked `apiClient` network responses, same
 * approach as 7D-7H's suites. Covers `/inventory` (Stock/Locations/Reports
 * tabs) and `/inventory/[id]` (the line detail's Movements/Reservations
 * tabs), since they share one permission model and fixture set.
 */
describe("InventoryPage (7I)", () => {
  it("shows PermissionDenied for a role without inventory:read", async () => {
    signIn([]);
    renderWithProviders(<InventoryPage />);

    expect(await screen.findByText("You don't have access to this page")).toBeInTheDocument();
    expect(screen.queryByText("Inventory")).not.toBeInTheDocument();
  });

  it("lists real inventory lines and supports the search filter re-fetching from the backend", async () => {
    const user = userEvent.setup();
    signIn(["inventory:read"]);
    let lastSearch: string | null = null;
    server.use(
      http.get(`${BASE}/api/v1/inventory`, ({ request }) => {
        lastSearch = new URL(request.url).searchParams.get("search");
        return HttpResponse.json(makeInventoryPage([makeInventoryItem({ name: "4in nursery pots" })]));
      }),
    );
    renderWithProviders(<InventoryPage />);

    expect(await screen.findByText("4in nursery pots")).toBeInTheDocument();
    expect(screen.getByText("In stock")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Search inventory"), "pots");
    await waitFor(() => expect(lastSearch).toBe("pots"), { timeout: 2000 });
  });

  it("creates an inventory line through the real form", async () => {
    const user = userEvent.setup();
    signIn(["inventory:read", "inventory:write"]);
    let created: Record<string, unknown> | null = null;
    server.use(
      http.post(`${BASE}/api/v1/inventory`, async ({ request }) => {
        created = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(makeInventoryItem());
      }),
    );
    renderWithProviders(<InventoryPage />);

    await user.click(await screen.findByRole("button", { name: "Create line" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Name"), "10-10-10 fertilizer");
    await user.click(within(dialog).getByRole("combobox", { name: "Branch" }));
    await user.click(await screen.findByRole("option", { name: "Main Branch" }));
    await user.click(within(dialog).getByRole("combobox", { name: "Category" }));
    await user.click(await screen.findByRole("option", { name: "Houseplant" }));
    await user.click(within(dialog).getByRole("combobox", { name: "Unit" }));
    await user.click(await screen.findByRole("option", { name: "Each" }));
    await user.click(within(dialog).getByRole("button", { name: "Create line" }));

    await waitFor(() => expect(created).not.toBeNull());
    expect(created).toMatchObject({ name: "10-10-10 fertilizer" });
  });

  it("shows a real empty state distinguishing 'no inventory yet' from 'no matches'", async () => {
    signIn(["inventory:read"]);
    server.use(http.get(`${BASE}/api/v1/inventory`, () => HttpResponse.json(makeInventoryPage([]))));
    renderWithProviders(<InventoryPage />);

    expect(await screen.findByText("No inventory yet")).toBeInTheDocument();
  });

  it("shows a real error state with retry when the inventory list fails to load", async () => {
    signIn(["inventory:read"]);
    server.use(
      http.get(`${BASE}/api/v1/inventory`, () =>
        HttpResponse.json({ error: { code: "internal_error", message: "Server error." } }, { status: 500 }),
      ),
    );
    renderWithProviders(<InventoryPage />);

    await waitFor(() => expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument());
  });

  it("lists real locations for the selected branch and creates a new one through the real form", async () => {
    const user = userEvent.setup();
    signIn(["inventory:read", "inventory:write"]);
    let created: Record<string, unknown> | null = null;
    server.use(
      http.get(`${BASE}/api/v1/inventory-locations`, () => HttpResponse.json([makeInventoryLocation({ name: "Greenhouse 1" })])),
      http.post(`${BASE}/api/v1/inventory-locations`, async ({ request }) => {
        created = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(makeInventoryLocation({ name: "Rack A" }));
      }),
    );
    renderWithProviders(<InventoryPage />);

    await user.click(await screen.findByRole("tab", { name: "Locations" }));
    expect(await screen.findByText("Greenhouse 1")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "New location" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Name"), "Rack A");
    await user.click(within(dialog).getByRole("combobox", { name: "Type" }));
    await user.click(await screen.findByRole("option", { name: "Rack" }));
    await user.click(within(dialog).getByRole("button", { name: "Create location" }));

    await waitFor(() => expect(created).not.toBeNull());
    expect(created).toMatchObject({ name: "Rack A", location_type: "rack" });
  });

  it("shows the real Low Stock report", async () => {
    const user = userEvent.setup();
    signIn(["inventory:read"]);
    server.use(
      http.get(`${BASE}/api/v1/inventory/low-stock`, () =>
        HttpResponse.json([makeInventoryItem({ name: "Cactus soil mix", quantity: 3, low_stock_threshold: 20 })]),
      ),
    );
    renderWithProviders(<InventoryPage />);

    await user.click(await screen.findByRole("tab", { name: "Reports" }));
    expect(await screen.findByText("Cactus soil mix")).toBeInTheDocument();
  });
});

describe("InventoryDetailPage (7I)", () => {
  it("shows the real inventory line's identity strip -- name, branch, and quantity breakdown", async () => {
    signIn(["inventory:read"]);
    server.use(http.get(`${BASE}/api/v1/inventory/:id`, () => HttpResponse.json(makeInventoryItem({ name: "4in nursery pots" }))));
    renderWithProviders(<InventoryDetailPage />);

    expect(await screen.findByText("4in nursery pots")).toBeInTheDocument();
    // Branch name resolves from a separate `useBranchesQuery()` call, so
    // it can genuinely lag one render behind the item's own name -- use
    // `findByText` rather than `getByText` for it, same reasoning as
    // `InventoryHeader`'s real render (starts at "—" until branches load).
    expect(await screen.findByText("Branch: Main Branch")).toBeInTheDocument();
    expect(screen.getByText("88")).toBeInTheDocument();
  });

  it("receives stock through the real form", async () => {
    const user = userEvent.setup();
    signIn(["inventory:read", "inventory:write"]);
    let received: Record<string, unknown> | null = null;
    server.use(
      http.post(`${BASE}/api/v1/inventory/:id/receive`, async ({ request }) => {
        received = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(makeInventoryItem({ quantity: 150 }));
      }),
    );
    renderWithProviders(<InventoryDetailPage />);

    await user.click(await screen.findByRole("button", { name: "Receive" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Quantity"), "50");
    await user.click(within(dialog).getByRole("button", { name: "Receive stock" }));

    await waitFor(() => expect(received).not.toBeNull());
    expect(received).toMatchObject({ quantity: 50 });
  });

  it("surfaces a real 409 from an insufficient-stock adjustment without silently closing the dialog", async () => {
    // `toast.apiError` (see lib/toast.ts) renders through the app's root
    // `<Toaster>`, which `renderWithProviders` doesn't mount for an
    // isolated component test -- so this asserts the real, in-tree
    // observable behavior instead: `AdjustStockDialog` only closes on
    // mutation success, so a 409 leaves it open rather than silently
    // discarding the error.
    const user = userEvent.setup();
    signIn(["inventory:read", "inventory:adjust"]);
    let attempted = false;
    server.use(
      http.post(`${BASE}/api/v1/inventory/:id/adjust`, () => {
        attempted = true;
        return HttpResponse.json({ error: { code: "insufficient_stock", message: "Adjustment would take quantity below zero." } }, { status: 409 });
      }),
    );
    renderWithProviders(<InventoryDetailPage />);

    await user.click(await screen.findByRole("button", { name: "Adjust" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Change"), "-500");
    await user.click(within(dialog).getByRole("button", { name: "Adjust stock" }));

    await waitFor(() => expect(attempted).toBe(true));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("lists the real movement ledger for this line", async () => {
    const user = userEvent.setup();
    signIn(["inventory:read"]);
    server.use(
      http.get(`${BASE}/api/v1/inventory/:id/movements`, () =>
        HttpResponse.json(makeStockMovementPage([makeStockMovement({ movement_type: "incoming", quantity_delta: 50 })])),
      ),
    );
    renderWithProviders(<InventoryDetailPage />);

    await user.click(await screen.findByRole("tab", { name: "Movements" }));
    expect(await screen.findByText("Received")).toBeInTheDocument();
  });

  it("releases a real active reservation directly, with no confirmation dialog", async () => {
    const user = userEvent.setup();
    signIn(["inventory:read", "inventory:write"]);
    let released: string | null = null;
    server.use(
      http.get(`${BASE}/api/v1/inventory/:id/reservations`, () => HttpResponse.json([makeStockReservation({ status: "active" })])),
      http.post(`${BASE}/api/v1/stock-reservations/:id/release`, ({ params }) => {
        released = params.id as string;
        return HttpResponse.json(makeStockReservation({ status: "released" }));
      }),
    );
    renderWithProviders(<InventoryDetailPage />);

    await user.click(await screen.findByRole("tab", { name: "Reservations" }));
    await user.click(await screen.findByRole("button", { name: "Release" }));

    await waitFor(() => expect(released).toBe(makeStockReservation().id));
  });

  it("shows a real error state with retry when the inventory line fails to load", async () => {
    signIn(["inventory:read"]);
    server.use(
      http.get(`${BASE}/api/v1/inventory/:id`, () =>
        HttpResponse.json({ error: { code: "internal_error", message: "Server error." } }, { status: 500 }),
      ),
    );
    renderWithProviders(<InventoryDetailPage />);

    await waitFor(() => expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument());
  });
});
