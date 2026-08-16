import { describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import ReportsPage from "@/app/(app)/reports/page";
import { useSessionStore } from "@/store/session-store";
import { makeMe } from "@/test/fixtures/auth";
import { makeReport, makeReportCatalogEntry, makeReportPage, makeScheduledReport, makeScheduledReportPage } from "@/test/fixtures/reports";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/msw/server";

const BASE = "http://localhost:8000";

function signIn(permissions: string[]) {
  useSessionStore.setState({ status: "authenticated", user: makeMe({ permissions }), accessToken: "access-token-1" });
}

/**
 * 7N -- Report Catalog/Generate/History/Download + Scheduled Reports
 * CRUD, both real tabs of the `/reports` route. One combined file,
 * matching `sales.test.tsx`'s precedent of covering multiple real tabs
 * of one large page in a single describe block.
 */
describe("Reports & Scheduled Reports (7N)", () => {
  it("shows a permission-denied page without reports:read", async () => {
    signIn(["plants:read"]);
    renderWithProviders(<ReportsPage />);

    expect(await screen.findByText("You don't have access to this page")).toBeInTheDocument();
  });

  it("lists the real catalog and history, hiding Generate/export controls for a read-only role", async () => {
    signIn(["reports:read"]);
    server.use(
      http.get(`${BASE}/api/v1/reports/catalog`, () => HttpResponse.json([makeReportCatalogEntry({ title: "Sales Report" })])),
      http.get(`${BASE}/api/v1/reports`, () => HttpResponse.json(makeReportPage([makeReport({ status: "complete" })]))),
    );
    renderWithProviders(<ReportsPage />);

    expect(await screen.findAllByText("Sales Report")).toHaveLength(2); // catalog card + history row both label the same real report_type
    expect(screen.queryByRole("button", { name: "Generate report" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Generate" })).not.toBeInTheDocument();
  });

  it("shows a pending report without a download link, and a complete one with a real download link", async () => {
    signIn(["reports:read", "reports:export"]);
    server.use(
      http.get(`${BASE}/api/v1/reports`, () =>
        HttpResponse.json(
          makeReportPage([
            makeReport({ id: "report-pending", status: "processing", download_url: null }),
            makeReport({ id: "report-done", status: "complete", download_url: "/api/v1/reports/report-done/download" }),
          ]),
        ),
      ),
    );
    renderWithProviders(<ReportsPage />);

    await screen.findByText("Generating…");
    expect(screen.getByText("Complete")).toBeInTheDocument();
    const downloadLink = screen.getByRole("link", { name: /Download/ });
    expect(downloadLink).toHaveAttribute("href", "/api/v1/reports/report-done/download");
  });

  it("generates a real report through the dialog, sending the real report_type and format", async () => {
    const user = userEvent.setup();
    signIn(["reports:read", "reports:export"]);
    let submittedBody: { report_type?: string; format?: string } | null = null;
    server.use(
      http.get(`${BASE}/api/v1/reports/catalog`, () => HttpResponse.json([makeReportCatalogEntry({ report_type: "sales", title: "Sales Report" })])),
      http.get(`${BASE}/api/v1/reports`, () => HttpResponse.json(makeReportPage([]))),
      http.post(`${BASE}/api/v1/reports`, async ({ request }) => {
        submittedBody = (await request.json()) as typeof submittedBody;
        return HttpResponse.json(makeReport({ status: "pending" }), { status: 202 });
      }),
    );
    renderWithProviders(<ReportsPage />);

    await user.click(await screen.findByRole("button", { name: "Generate report" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("combobox", { name: "Report type" }));
    await user.click(await screen.findByRole("option", { name: "Sales Report" }));
    await user.click(within(dialog).getByRole("button", { name: "Generate" }));

    await waitFor(() => expect(submittedBody).not.toBeNull());
    expect(submittedBody).toMatchObject({ report_type: "sales", format: "pdf" });
  });

  it("lists real scheduled reports and pauses one through the real mutation", async () => {
    const user = userEvent.setup();
    signIn(["reports:read", "reports:export"]);
    let paused = false;
    server.use(
      http.get(`${BASE}/api/v1/reports/scheduled`, () =>
        HttpResponse.json(makeScheduledReportPage([makeScheduledReport({ id: "sched-1", name: "Weekly sales summary", is_active: true })])),
      ),
      http.post(`${BASE}/api/v1/reports/scheduled/:scheduledId/pause`, () => {
        paused = true;
        return HttpResponse.json(makeScheduledReport({ id: "sched-1", is_active: false }));
      }),
    );
    renderWithProviders(<ReportsPage />);

    await user.click(await screen.findByRole("tab", { name: "Scheduled" }));
    await user.click(await screen.findByRole("button", { name: "Pause" }));

    await waitFor(() => expect(paused).toBe(true));
  });

  it("creates a real scheduled report through the dialog", async () => {
    const user = userEvent.setup();
    signIn(["reports:read", "reports:export"]);
    let submittedBody: { name?: string; frequency?: string } | null = null;
    server.use(
      http.get(`${BASE}/api/v1/reports/catalog`, () => HttpResponse.json([makeReportCatalogEntry({ report_type: "sales", title: "Sales Report" })])),
      http.get(`${BASE}/api/v1/reports/scheduled`, () => HttpResponse.json(makeScheduledReportPage([]))),
      http.post(`${BASE}/api/v1/reports/scheduled`, async ({ request }) => {
        submittedBody = (await request.json()) as typeof submittedBody;
        return HttpResponse.json(makeScheduledReport(), { status: 201 });
      }),
    );
    renderWithProviders(<ReportsPage />);

    await user.click(await screen.findByRole("tab", { name: "Scheduled" }));
    await user.click(await screen.findByRole("button", { name: "New schedule" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Name"), "Monthly inventory");
    await user.click(within(dialog).getByRole("combobox", { name: "Report type" }));
    await user.click(await screen.findByRole("option", { name: "Sales Report" }));
    const futureLocal = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString().slice(0, 16);
    await user.type(within(dialog).getByLabelText("First run"), futureLocal);
    await user.click(within(dialog).getByRole("button", { name: "Create schedule" }));

    await waitFor(() => expect(submittedBody).not.toBeNull());
    expect(submittedBody).toMatchObject({ name: "Monthly inventory", frequency: "weekly" });
  });

  it("runs due scheduled reports now through the real mutation", async () => {
    const user = userEvent.setup();
    signIn(["reports:read", "reports:export"]);
    let ran = false;
    server.use(
      http.get(`${BASE}/api/v1/reports/scheduled`, () => HttpResponse.json(makeScheduledReportPage([]))),
      http.post(`${BASE}/api/v1/reports/scheduled/run-due`, () => {
        ran = true;
        return HttpResponse.json({ executed_count: 2, results: [] });
      }),
    );
    renderWithProviders(<ReportsPage />);

    await user.click(await screen.findByRole("tab", { name: "Scheduled" }));
    await user.click(await screen.findByRole("button", { name: "Run due reports now" }));

    await waitFor(() => expect(ran).toBe(true));
  });
});
