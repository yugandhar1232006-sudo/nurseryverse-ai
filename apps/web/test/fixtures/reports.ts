import type { ReportCatalogEntryResponse, ReportResponse, ScheduledReportResponse } from "@/lib/api/reports";

/** 7N -- fixtures for Report Catalog/Generate/History/Download + Scheduled Reports, mirrors test/fixtures/dashboards.ts's pattern. */

export function makeReportCatalogEntry(overrides: Partial<ReportCatalogEntryResponse> = {}): ReportCatalogEntryResponse {
  return {
    report_type: "sales",
    title: "Sales Report",
    description: "Revenue, orders, and payment activity for the selected period.",
    ...overrides,
  } as ReportCatalogEntryResponse;
}

export function makeReport(overrides: Partial<ReportResponse> = {}): ReportResponse {
  return {
    id: "77777777-7777-7777-7777-777777777701",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    branch_id: null,
    report_type: "sales",
    format: "pdf",
    status: "complete",
    filters: null,
    download_url: "/api/v1/reports/77777777-7777-7777-7777-777777777701/download",
    requested_by_user_id: "11111111-1111-1111-1111-111111111111",
    created_at: "2026-08-14T08:00:00Z",
    completed_at: "2026-08-14T08:00:05Z",
    ...overrides,
  } as ReportResponse;
}

export function makeReportPage(items: ReportResponse[] = [makeReport()]) {
  return { items, meta: { page: 1, page_size: 10, total_items: items.length, total_pages: 1 } };
}

export function makeScheduledReport(overrides: Partial<ScheduledReportResponse> = {}): ScheduledReportResponse {
  return {
    id: "88888888-8888-8888-8888-888888888701",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    branch_id: null,
    name: "Weekly sales summary",
    report_type: "sales",
    format: "pdf",
    filters: null,
    frequency: "weekly",
    is_active: true,
    created_by_user_id: "11111111-1111-1111-1111-111111111111",
    next_run_at: "2026-08-21T08:00:00Z",
    last_run_at: null,
    created_at: "2026-08-14T08:00:00Z",
    ...overrides,
  } as ScheduledReportResponse;
}

export function makeScheduledReportPage(items: ScheduledReportResponse[] = [makeScheduledReport()]) {
  return { items, meta: { page: 1, page_size: 10, total_items: items.length, total_pages: 1 } };
}
