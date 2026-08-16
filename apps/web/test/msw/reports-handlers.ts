import { http, HttpResponse } from "msw";

import { makeReport, makeReportCatalogEntry, makeReportPage, makeScheduledReport, makeScheduledReportPage } from "@/test/fixtures/reports";

const BASE = "http://localhost:8000";

/**
 * Default, happy-path handlers for 7N's Report Catalog/Generate/Status/
 * History/Download + Scheduled Reports CRUD routes -- separate file from
 * `dashboard-handlers.ts` even though both wrap `apps/api/app/api/routes/
 * reports.py`, matching that file's own `/dashboards/*` vs `/reports/*`
 * split (see docs/frontend/18-reports-analytics.md's Scope section).
 */
export const reportsHandlers = [
  http.get(`${BASE}/api/v1/reports/catalog`, () =>
    HttpResponse.json([
      makeReportCatalogEntry({ report_type: "sales", title: "Sales Report" }),
      makeReportCatalogEntry({ report_type: "inventory", title: "Inventory Report" }),
    ]),
  ),
  http.post(`${BASE}/api/v1/reports`, () => HttpResponse.json(makeReport({ status: "pending", download_url: null }), { status: 202 })),
  http.get(`${BASE}/api/v1/reports/:reportId`, () => HttpResponse.json(makeReport())),
  http.get(`${BASE}/api/v1/reports`, () => HttpResponse.json(makeReportPage())),

  http.get(`${BASE}/api/v1/reports/scheduled`, () => HttpResponse.json(makeScheduledReportPage())),
  http.post(`${BASE}/api/v1/reports/scheduled`, () => HttpResponse.json(makeScheduledReport(), { status: 201 })),
  http.post(`${BASE}/api/v1/reports/scheduled/run-due`, () => HttpResponse.json({ executed_count: 0, results: [] })),
  http.get(`${BASE}/api/v1/reports/scheduled/:scheduledId`, () => HttpResponse.json(makeScheduledReport())),
  http.patch(`${BASE}/api/v1/reports/scheduled/:scheduledId`, () => HttpResponse.json(makeScheduledReport())),
  http.post(`${BASE}/api/v1/reports/scheduled/:scheduledId/pause`, () => HttpResponse.json(makeScheduledReport({ is_active: false }))),
  http.post(`${BASE}/api/v1/reports/scheduled/:scheduledId/resume`, () => HttpResponse.json(makeScheduledReport({ is_active: true }))),
  http.delete(`${BASE}/api/v1/reports/scheduled/:scheduledId`, () => new HttpResponse(null, { status: 204 })),
];
