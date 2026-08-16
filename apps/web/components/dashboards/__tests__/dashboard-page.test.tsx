import { describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import DashboardPage from "@/app/(app)/page";
import { useSessionStore } from "@/store/session-store";
import { makeMe } from "@/test/fixtures/auth";
import { makeBranch } from "@/test/fixtures/shell";
import { makeExecutiveDashboard, makeNurseryDashboard } from "@/test/fixtures/dashboards";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/msw/server";

const BASE = "http://localhost:8000";

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>,
}));

function signInWithPermissions(permissions: string[]) {
  useSessionStore.setState({ status: "authenticated", user: makeMe({ permissions }), accessToken: "access-token-1" });
}

describe("DashboardPage (7D)", () => {
  it("shows the real no-reporting-access state for a role without reports:read, with links only to what they can access", async () => {
    signInWithPermissions(["plants:read"]);
    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("Reporting is not part of your role")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Plants/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Sales/ })).not.toBeInTheDocument();
  });

  it("shows a bare no-reporting-access state with no quick links for a role with no other permissions either", async () => {
    signInWithPermissions([]);
    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("Reporting is not part of your role")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("renders the Executive dashboard's real KPI figures and branch table for a user with reports:read", async () => {
    const exec = makeExecutiveDashboard({ revenue_today: 555, active_plant_count: 777 });
    server.use(http.get(`${BASE}/api/v1/dashboards/executive`, () => HttpResponse.json(exec)));
    signInWithPermissions(["reports:read"]);
    renderWithProviders(<DashboardPage />);

    expect(await screen.findByText("$555.00")).toBeInTheDocument();
    expect(screen.getByText("777")).toBeInTheDocument();
    expect(screen.getByText("Main Branch")).toBeInTheDocument();
  });

  it("switches to the Nursery tab and fetches/renders its own real dashboard data", async () => {
    const user = userEvent.setup();
    const nursery = makeNurseryDashboard({ total_plants: 999, branch_count: 4 });
    server.use(http.get(`${BASE}/api/v1/dashboards/nursery`, () => HttpResponse.json(nursery)));
    signInWithPermissions(["reports:read"]);
    renderWithProviders(<DashboardPage />);

    await user.click(await screen.findByRole("tab", { name: "Nursery" }));
    expect(await screen.findByText("999")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("shows an error state with retry when a dashboard request fails, and recovers on retry", async () => {
    const user = userEvent.setup();
    let attempt = 0;
    server.use(
      http.get(`${BASE}/api/v1/dashboards/executive`, () => {
        attempt += 1;
        if (attempt === 1) {
          return HttpResponse.json({ error: { code: "internal_error", message: "boom" } }, { status: 500 });
        }
        return HttpResponse.json(makeExecutiveDashboard());
      }),
    );
    signInWithPermissions(["reports:read"]);
    renderWithProviders(<DashboardPage />);

    const retryButton = await screen.findByRole("button", { name: "Try again" });
    await user.click(retryButton);

    await waitFor(() => expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument());
  });

  it("Branch tab prompts to pick a branch when scope is 'All branches', and loads real branch data once one is picked", async () => {
    const user = userEvent.setup();
    const branch = makeBranch({ id: "branch-9", name: "Riverside Branch" });
    server.use(
      http.get(`${BASE}/api/v1/branches`, () => HttpResponse.json([branch])),
      http.get(`${BASE}/api/v1/dashboards/branch/branch-9`, () =>
        HttpResponse.json({
          branch_id: "branch-9",
          nursery_id: "22222222-2222-2222-2222-222222222222",
          branch_name: "Riverside Branch",
          revenue_today: 12,
          revenue_mtd: 34,
          at_risk_plant_count: 0,
          low_stock_count: 0,
          pending_disease_reports: 0,
          last_refreshed_at: "2026-08-14T08:00:00Z",
        }),
      ),
    );
    signInWithPermissions(["reports:read"]);
    renderWithProviders(<DashboardPage />);

    await user.click(await screen.findByRole("tab", { name: "Branch" }));
    expect(await screen.findByText("Pick a branch")).toBeInTheDocument();

    const scopeSelect = screen.getByRole("combobox", { name: "Dashboard scope" });
    await user.click(scopeSelect);
    await user.click(await screen.findByRole("option", { name: "Riverside Branch" }));

    expect(await screen.findByText("$12.00")).toBeInTheDocument();
  });

  it("scopes Plant/Inventory/Sales/Customer/AI/Financial tab requests to the selected branch via ?branch_id=", async () => {
    const user = userEvent.setup();
    const branch = makeBranch({ id: "branch-9", name: "Riverside Branch" });
    let receivedBranchId: string | null = null;
    server.use(
      http.get(`${BASE}/api/v1/branches`, () => HttpResponse.json([branch])),
      http.get(`${BASE}/api/v1/dashboards/plant`, ({ request }) => {
        receivedBranchId = new URL(request.url).searchParams.get("branch_id");
        return HttpResponse.json({ by_status: {}, by_species: [] });
      }),
    );
    signInWithPermissions(["reports:read"]);
    renderWithProviders(<DashboardPage />);

    const scopeSelect = await screen.findByRole("combobox", { name: "Dashboard scope" });
    await user.click(scopeSelect);
    await user.click(await screen.findByRole("option", { name: "Riverside Branch" }));

    await user.click(await screen.findByRole("tab", { name: "Plants" }));
    await waitFor(() => expect(receivedBranchId).toBe("branch-9"));
  });

  it("shows an honest empty state for the AI tab when nothing has been flagged", async () => {
    const user = userEvent.setup();
    server.use(
      http.get(`${BASE}/api/v1/dashboards/ai`, () => HttpResponse.json({ at_risk_plants: [], prediction_accuracy: null })),
    );
    signInWithPermissions(["reports:read"]);
    renderWithProviders(<DashboardPage />);

    await user.click(await screen.findByRole("tab", { name: "AI" }));
    expect(await screen.findByText("No plants currently flagged")).toBeInTheDocument();
    expect(screen.getByText("Not enough data yet")).toBeInTheDocument();
  });

  it("labels AI confidence as a score, never as a probability or guarantee", async () => {
    const user = userEvent.setup();
    signInWithPermissions(["reports:read"]);
    renderWithProviders(<DashboardPage />);

    await user.click(await screen.findByRole("tab", { name: "AI" }));
    expect(await screen.findByText("Confidence score")).toBeInTheDocument();
    expect(screen.getByText(/AI-generated risk flags, not confirmed diagnoses/)).toBeInTheDocument();
  });

  it("renders the Financial tab's estimated figures with honest 'Estimated' labeling", async () => {
    const user = userEvent.setup();
    signInWithPermissions(["reports:read"]);
    renderWithProviders(<DashboardPage />);

    await user.click(await screen.findByRole("tab", { name: "Financial" }));
    expect(await screen.findByText("Estimated gross profit")).toBeInTheDocument();
    expect(screen.getByText("Estimated COGS")).toBeInTheDocument();
  });
});

describe("DashboardContent scope selector", () => {
  it("shows nothing when the org has zero branches yet, without crashing", async () => {
    server.use(http.get(`${BASE}/api/v1/branches`, () => HttpResponse.json([])));
    signInWithPermissions(["reports:read"]);
    renderWithProviders(<DashboardPage />);

    await waitFor(() => expect(screen.queryByRole("combobox", { name: "Dashboard scope" })).not.toBeInTheDocument());
    expect(await within(screen.getByRole("tabpanel")).findByText("Revenue trend")).toBeInTheDocument();
  });
});
