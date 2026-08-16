"use client";

import { useQuery } from "@tanstack/react-query";

import {
  getReportCatalog,
  getReportStatus,
  getScheduledReport,
  listReports,
  listScheduledReports,
  type ReportType,
} from "@/lib/api/reports";
import { useSessionStore } from "@/store/session-store";

/**
 * 7N -- query-key factory for Report Catalog / Generate / Status /
 * History / Download and Scheduled Reports CRUD, mirroring
 * `lib/dashboards/queries.ts`'s `dashboardKeys` pattern (7D). Kept in a
 * separate file/key namespace from `dashboardKeys` even though both wrap
 * `lib/api/reports.ts` -- dashboards and analytics are always-fresh
 * rollup reads (60s staleTime), while report generation/scheduling is a
 * write-driven, poll-until-done workflow with entirely different caching
 * needs (see `useReportHistoryQuery`'s docstring).
 */
export const reportKeys = {
  all: ["reports"] as const,
  catalog: () => [...reportKeys.all, "catalog"] as const,
  history: (params: { page?: number; report_type?: ReportType; branch_id?: string }) =>
    [...reportKeys.all, "history", params] as const,
  status: (reportId: string) => [...reportKeys.all, "status", reportId] as const,
  scheduledList: (params: { page?: number }) => [...reportKeys.all, "scheduled", params] as const,
  scheduledDetail: (id: string) => [...reportKeys.all, "scheduled", "detail", id] as const,
};

/** PG-51's report catalog -- the 18 real `ReportType` values with title/description, `GET /reports/catalog`. Effectively static, so a long `staleTime` is safe. */
export function useReportCatalogQuery() {
  const enabled = useSessionStore((state) => state.status === "authenticated");
  return useQuery({ queryKey: reportKeys.catalog(), queryFn: getReportCatalog, enabled, staleTime: 10 * 60 * 1000 });
}

/**
 * The real generation history, `GET /reports` -- also the read this
 * screen polls while any report in the current page is `pending`/
 * `processing`, since `POST /reports` returns 202 with no
 * further-progress channel of its own (real backend uses `BackgroundTasks`,
 * not a webhook/SSE push -- see docs/frontend/18-reports-analytics.md).
 * `refetchInterval` is a function of the *last fetched data*, not a
 * fixed poll -- once every report on the page has settled into
 * `complete`/`failed`, polling stops on its own rather than running
 * forever.
 */
export function useReportHistoryQuery(params: { page?: number; report_type?: ReportType; branch_id?: string } = {}) {
  const enabled = useSessionStore((state) => state.status === "authenticated");
  return useQuery({
    queryKey: reportKeys.history(params),
    queryFn: () => listReports({ page: params.page ?? 1, page_size: 10, report_type: params.report_type, branch_id: params.branch_id }),
    enabled,
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      const stillRunning = items.some((r) => r.status === "pending" || r.status === "processing");
      return stillRunning ? 4_000 : false;
    },
  });
}

/** A single report's live status -- used by the "just submitted" inline banner so a freshly created report can be tracked by id without waiting for the next history-list refetch. */
export function useReportStatusQuery(reportId: string | null) {
  return useQuery({
    queryKey: reportKeys.status(reportId ?? "none"),
    queryFn: () => getReportStatus(reportId as string),
    enabled: reportId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "pending" || status === "processing" ? 3_000 : false;
    },
  });
}

export function useScheduledReportsQuery(params: { page?: number } = {}) {
  const enabled = useSessionStore((state) => state.status === "authenticated");
  return useQuery({
    queryKey: reportKeys.scheduledList(params),
    queryFn: () => listScheduledReports({ page: params.page ?? 1, page_size: 10 }),
    enabled,
  });
}

export function useScheduledReportQuery(id: string | null) {
  return useQuery({
    queryKey: reportKeys.scheduledDetail(id ?? "none"),
    queryFn: () => getScheduledReport(id as string),
    enabled: id !== null,
  });
}
