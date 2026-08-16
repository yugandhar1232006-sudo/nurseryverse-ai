import { apiClient, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

/**
 * Thin typed wrappers for Module 12 (Reports & Analytics)'s
 * `/dashboards/*`, `/analytics/*`, `/reports/*` routes (see
 * apps/api/app/api/routes/reports.py's own module docstring). Every
 * route here requires `reports:read` (dashboards/analytics/catalog/
 * status/download/history) or `reports:export` (report generation,
 * every scheduled-report write) -- per docs/ux/07-role-permission-matrix.md,
 * only Owner/Org Admin (org-wide) and Branch Manager (their own branch)
 * hold `reports:read` at all; Horticulturist and Sales Staff hold
 * neither, by design (they have no reporting surface, not a bug to work
 * around client-side -- see components/dashboards/dashboard-page.tsx's
 * own docstring on how the Dashboard route degrades for those roles).
 *
 * `nursery_id`/`org_id` is never a parameter on any of these calls --
 * every route resolves it server-side from the caller's own tenant
 * context (see reports.py's docstring on why there is nothing for a
 * client to override). `branch_id` is the only scoping parameter a
 * client ever supplies, and only where the backend route itself accepts
 * one (executive/nursery/branch-performance dashboards and the report
 * catalog are always org-wide -- no `branch_id` parameter exists for
 * them at all).
 */

export type ExecutiveDashboardResponse = components["schemas"]["ExecutiveDashboardResponse"];
export type NurseryDashboardResponse = components["schemas"]["NurseryDashboardResponse"];
export type BranchSummaryResponse = components["schemas"]["BranchSummaryResponse"];
export type PlantDashboardResponse = components["schemas"]["PlantDashboardResponse"];
export type InventoryDashboardResponse = components["schemas"]["InventoryDashboardResponse"];
export type SalesDashboardResponse = components["schemas"]["SalesDashboardResponse"];
export type CustomerDashboardResponse = components["schemas"]["CustomerDashboardResponse"];
export type AIDashboardResponse = components["schemas"]["AIDashboardResponse"];
export type FinancialDashboardResponse = components["schemas"]["FinancialDashboardResponse"];
export type KpiSummaryResponse = components["schemas"]["KpiSummaryResponse"];
export type RevenueTrendPointResponse = components["schemas"]["RevenueTrendPointResponse"];
export type GrowthTrendPointResponse = components["schemas"]["GrowthTrendPointResponse"];
export type InventoryTrendPointResponse = components["schemas"]["InventoryTrendPointResponse"];
export type PlantHealthTrendPointResponse = components["schemas"]["PlantHealthTrendPointResponse"];
export type DiseaseTrendPointResponse = components["schemas"]["DiseaseTrendPointResponse"];
export type SalesForecastPointResponse = components["schemas"]["SalesForecastPointResponse"];
export type EmployeeProductivityPointResponse = components["schemas"]["EmployeeProductivityPointResponse"];
export type ReportCatalogEntryResponse = components["schemas"]["ReportCatalogEntryResponse"];
export type ReportResponse = components["schemas"]["ReportResponse"];
export type ScheduledReportResponse = components["schemas"]["ScheduledReportResponse"];
export type ReportCreateRequest = components["schemas"]["ReportCreateRequest"];
export type ScheduledReportCreateRequest = components["schemas"]["ScheduledReportCreateRequest"];
export type ScheduledReportUpdateRequest = components["schemas"]["ScheduledReportUpdateRequest"];
export type RunDueResponse = components["schemas"]["RunDueResponse"];
export type PageScheduledReportResponse = components["schemas"]["Page_ScheduledReportResponse_"];
export type PageReportResponse = components["schemas"]["Page_ReportResponse_"];
export type ReportType = components["schemas"]["ReportType"];
export type ReportFormat = components["schemas"]["ReportFormat"];
export type ReportStatus = components["schemas"]["ReportStatus"];
export type ReportScheduleFrequency = components["schemas"]["ReportScheduleFrequency"];

export interface DateRangeQuery {
  date_from?: string;
  date_to?: string;
}

// ----------------------------------------------------------------------
// Dashboards
// ----------------------------------------------------------------------

export async function getExecutiveDashboard(): Promise<ExecutiveDashboardResponse> {
  return unwrap(() => apiClient.GET("/api/v1/dashboards/executive"));
}

export async function getNurseryDashboard(): Promise<NurseryDashboardResponse> {
  return unwrap(() => apiClient.GET("/api/v1/dashboards/nursery"));
}

export async function getBranchDashboard(branchId: string): Promise<BranchSummaryResponse> {
  return unwrap(() => apiClient.GET("/api/v1/dashboards/branch/{branch_id}", { params: { path: { branch_id: branchId } } }));
}

export async function getPlantDashboard(branchId?: string | null): Promise<PlantDashboardResponse> {
  return unwrap(() => apiClient.GET("/api/v1/dashboards/plant", { params: { query: branchId ? { branch_id: branchId } : {} } }));
}

export async function getInventoryDashboard(branchId?: string | null): Promise<InventoryDashboardResponse> {
  return unwrap(() => apiClient.GET("/api/v1/dashboards/inventory", { params: { query: branchId ? { branch_id: branchId } : {} } }));
}

export async function getSalesDashboard(branchId?: string | null, range?: DateRangeQuery): Promise<SalesDashboardResponse> {
  return unwrap(() =>
    apiClient.GET("/api/v1/dashboards/sales", { params: { query: { ...(branchId ? { branch_id: branchId } : {}), ...range } } }),
  );
}

export async function getCustomerDashboard(branchId?: string | null): Promise<CustomerDashboardResponse> {
  return unwrap(() => apiClient.GET("/api/v1/dashboards/customer", { params: { query: branchId ? { branch_id: branchId } : {} } }));
}

export async function getAIDashboard(branchId?: string | null): Promise<AIDashboardResponse> {
  return unwrap(() => apiClient.GET("/api/v1/dashboards/ai", { params: { query: branchId ? { branch_id: branchId } : {} } }));
}

export async function getFinancialDashboard(branchId?: string | null, range?: DateRangeQuery): Promise<FinancialDashboardResponse> {
  return unwrap(() =>
    apiClient.GET("/api/v1/dashboards/financial", { params: { query: { ...(branchId ? { branch_id: branchId } : {}), ...range } } }),
  );
}

// ----------------------------------------------------------------------
// Analytics
// ----------------------------------------------------------------------

export async function getKpiSummary(branchId?: string | null): Promise<KpiSummaryResponse> {
  return unwrap(() => apiClient.GET("/api/v1/analytics/kpi-summary", { params: { query: branchId ? { branch_id: branchId } : {} } }));
}

export async function getRevenueTrend(branchId?: string | null, range?: DateRangeQuery): Promise<RevenueTrendPointResponse[]> {
  return unwrap(() =>
    apiClient.GET("/api/v1/analytics/revenue-trend", { params: { query: { ...(branchId ? { branch_id: branchId } : {}), ...range } } }),
  );
}

export async function getGrowthTrend(
  branchId?: string | null,
  speciesId?: string | null,
  range?: DateRangeQuery,
): Promise<GrowthTrendPointResponse[]> {
  return unwrap(() =>
    apiClient.GET("/api/v1/analytics/growth-trend", {
      params: { query: { ...(branchId ? { branch_id: branchId } : {}), ...(speciesId ? { species_id: speciesId } : {}), ...range } },
    }),
  );
}

export async function getInventoryTrend(branchId?: string | null, range?: DateRangeQuery): Promise<InventoryTrendPointResponse[]> {
  return unwrap(() =>
    apiClient.GET("/api/v1/analytics/inventory-trend", { params: { query: { ...(branchId ? { branch_id: branchId } : {}), ...range } } }),
  );
}

export async function getPlantHealthTrend(branchId?: string | null, range?: DateRangeQuery): Promise<PlantHealthTrendPointResponse[]> {
  return unwrap(() =>
    apiClient.GET("/api/v1/analytics/plant-health-trend", { params: { query: { ...(branchId ? { branch_id: branchId } : {}), ...range } } }),
  );
}

export async function getSalesForecast(branchId?: string | null): Promise<SalesForecastPointResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/analytics/sales-forecast", { params: { query: branchId ? { branch_id: branchId } : {} } }));
}

export async function getDiseaseTrend(branchId?: string | null, range?: DateRangeQuery): Promise<DiseaseTrendPointResponse[]> {
  return unwrap(() =>
    apiClient.GET("/api/v1/analytics/disease-trend", { params: { query: { ...(branchId ? { branch_id: branchId } : {}), ...range } } }),
  );
}

export async function getEmployeeProductivity(
  branchId?: string | null,
  range?: DateRangeQuery,
): Promise<EmployeeProductivityPointResponse[]> {
  return unwrap(() =>
    apiClient.GET("/api/v1/analytics/employee-productivity", {
      params: { query: { ...(branchId ? { branch_id: branchId } : {}), ...range } },
    }),
  );
}

export async function getBranchPerformance(): Promise<BranchSummaryResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/analytics/branch-performance"));
}

/** 7N -- same `CustomerDashboardResponse` shape as `/dashboards/customer` (confirmed via schema.d.ts); a distinct real route, not a duplicate client-side call of the dashboard one. */
export async function getCustomerAnalytics(branchId?: string | null): Promise<CustomerDashboardResponse> {
  return unwrap(() =>
    apiClient.GET("/api/v1/analytics/customer-analytics", { params: { query: branchId ? { branch_id: branchId } : {} } }),
  );
}

// ----------------------------------------------------------------------
// Report catalog / generation / history
// ----------------------------------------------------------------------

export async function getReportCatalog(): Promise<ReportCatalogEntryResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/reports/catalog"));
}

export async function createReport(body: ReportCreateRequest): Promise<ReportResponse> {
  return unwrap(() => apiClient.POST("/api/v1/reports", { body }));
}

export async function getReportStatus(reportId: string): Promise<ReportResponse> {
  return unwrap(() => apiClient.GET("/api/v1/reports/{report_id}", { params: { path: { report_id: reportId } } }));
}

export async function listReports(params: {
  page?: number;
  page_size?: number;
  report_type?: ReportType;
  branch_id?: string;
}): Promise<PageReportResponse> {
  return unwrap(() => apiClient.GET("/api/v1/reports", { params: { query: params } }));
}

export function reportDownloadUrl(reportId: string): string {
  return `/api/v1/reports/${reportId}/download`;
}

// ----------------------------------------------------------------------
// Scheduled reports
// ----------------------------------------------------------------------

export async function listScheduledReports(params: { page?: number; page_size?: number }): Promise<PageScheduledReportResponse> {
  return unwrap(() => apiClient.GET("/api/v1/reports/scheduled", { params: { query: params } }));
}

export async function getScheduledReport(id: string): Promise<ScheduledReportResponse> {
  return unwrap(() => apiClient.GET("/api/v1/reports/scheduled/{scheduled_id}", { params: { path: { scheduled_id: id } } }));
}

export async function createScheduledReport(body: ScheduledReportCreateRequest): Promise<ScheduledReportResponse> {
  return unwrap(() => apiClient.POST("/api/v1/reports/scheduled", { body }));
}

/**
 * 7N -- `POST /reports/scheduled/run-due`, registered in the real route
 * (`reports.py`) *before* the `{scheduled_id}` path param to avoid a
 * collision with the literal segment "run-due". Real Celery beat (Module
 * 14) already sweeps due scheduled reports on its own cadence; this is
 * the same real, `reports:export`-gated manual trigger an operator can
 * use to run the sweep immediately rather than waiting for the next beat
 * tick -- not a fabricated client-only action.
 */
export async function runDueScheduledReports(limit?: number): Promise<RunDueResponse> {
  return unwrap(() => apiClient.POST("/api/v1/reports/scheduled/run-due", { params: { query: limit ? { limit } : {} } }));
}

export async function updateScheduledReport(id: string, body: ScheduledReportUpdateRequest): Promise<ScheduledReportResponse> {
  return unwrap(() => apiClient.PATCH("/api/v1/reports/scheduled/{scheduled_id}", { params: { path: { scheduled_id: id } }, body }));
}

export async function pauseScheduledReport(id: string): Promise<ScheduledReportResponse> {
  return unwrap(() => apiClient.POST("/api/v1/reports/scheduled/{scheduled_id}/pause", { params: { path: { scheduled_id: id } } }));
}

export async function resumeScheduledReport(id: string): Promise<ScheduledReportResponse> {
  return unwrap(() => apiClient.POST("/api/v1/reports/scheduled/{scheduled_id}/resume", { params: { path: { scheduled_id: id } } }));
}

export async function deleteScheduledReport(id: string): Promise<void> {
  return unwrap(() => apiClient.DELETE("/api/v1/reports/scheduled/{scheduled_id}", { params: { path: { scheduled_id: id } } }));
}
