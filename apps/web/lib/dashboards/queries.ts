"use client";

import { useQuery } from "@tanstack/react-query";

import {
  getAIDashboard,
  getBranchDashboard,
  getBranchPerformance,
  getCustomerDashboard,
  getExecutiveDashboard,
  getFinancialDashboard,
  getInventoryDashboard,
  getKpiSummary,
  getNurseryDashboard,
  getPlantDashboard,
  getRevenueTrend,
  getSalesDashboard,
  type DateRangeQuery,
} from "@/lib/api/reports";

/**
 * Query key factory for every Module 12 dashboard/analytics read this
 * phase uses, mirroring lib/shell/queries.ts's `shellKeys` pattern.
 * Every dashboard query is namespaced by the currently-selected branch
 * id (or the literal "org" for the org-wide views) so switching branches
 * in the shell's `BranchSelector` (7C) naturally invalidates/refetches
 * the branch-scoped dashboards without any manual cache-busting code.
 */
export const dashboardKeys = {
  all: ["dashboards"] as const,
  executive: () => [...dashboardKeys.all, "executive"] as const,
  nursery: () => [...dashboardKeys.all, "nursery"] as const,
  branch: (branchId: string) => [...dashboardKeys.all, "branch", branchId] as const,
  plant: (branchId: string | null) => [...dashboardKeys.all, "plant", branchId ?? "org"] as const,
  inventory: (branchId: string | null) => [...dashboardKeys.all, "inventory", branchId ?? "org"] as const,
  sales: (branchId: string | null, range: DateRangeQuery) => [...dashboardKeys.all, "sales", branchId ?? "org", range] as const,
  customer: (branchId: string | null) => [...dashboardKeys.all, "customer", branchId ?? "org"] as const,
  ai: (branchId: string | null) => [...dashboardKeys.all, "ai", branchId ?? "org"] as const,
  financial: (branchId: string | null, range: DateRangeQuery) => [...dashboardKeys.all, "financial", branchId ?? "org", range] as const,
  kpiSummary: (branchId: string | null) => [...dashboardKeys.all, "kpi-summary", branchId ?? "org"] as const,
  revenueTrend: (branchId: string | null, range: DateRangeQuery) => [...dashboardKeys.all, "revenue-trend", branchId ?? "org", range] as const,
  branchPerformance: () => [...dashboardKeys.all, "branch-performance"] as const,
};

/**
 * Rollups refresh on a ~15-minute cycle server-side (per
 * docs/ux/18-analytics-workflow.md's "Why Pre-Aggregation" section) --
 * there is no point polling faster than that, so every dashboard query
 * below shares a 60s `staleTime` (frequent enough that switching tabs/
 * branches feels responsive, far below the point of hammering the
 * rollup views on every render) and relies on the header's Reload-style
 * refetch-on-window-focus (React Query's default) rather than its own
 * polling interval.
 */
const DASHBOARD_STALE_TIME = 60 * 1000;

export function useExecutiveDashboardQuery(enabled: boolean) {
  return useQuery({
    queryKey: dashboardKeys.executive(),
    queryFn: getExecutiveDashboard,
    enabled,
    staleTime: DASHBOARD_STALE_TIME,
  });
}

export function useNurseryDashboardQuery(enabled: boolean) {
  return useQuery({
    queryKey: dashboardKeys.nursery(),
    queryFn: getNurseryDashboard,
    enabled,
    staleTime: DASHBOARD_STALE_TIME,
  });
}

export function useBranchDashboardQuery(branchId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: dashboardKeys.branch(branchId ?? "none"),
    queryFn: () => getBranchDashboard(branchId as string),
    enabled: enabled && branchId !== null,
    staleTime: DASHBOARD_STALE_TIME,
  });
}

export function usePlantDashboardQuery(branchId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: dashboardKeys.plant(branchId),
    queryFn: () => getPlantDashboard(branchId),
    enabled,
    staleTime: DASHBOARD_STALE_TIME,
  });
}

export function useInventoryDashboardQuery(branchId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: dashboardKeys.inventory(branchId),
    queryFn: () => getInventoryDashboard(branchId),
    enabled,
    staleTime: DASHBOARD_STALE_TIME,
  });
}

export function useSalesDashboardQuery(branchId: string | null, range: DateRangeQuery, enabled: boolean) {
  return useQuery({
    queryKey: dashboardKeys.sales(branchId, range),
    queryFn: () => getSalesDashboard(branchId, range),
    enabled,
    staleTime: DASHBOARD_STALE_TIME,
  });
}

export function useCustomerDashboardQuery(branchId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: dashboardKeys.customer(branchId),
    queryFn: () => getCustomerDashboard(branchId),
    enabled,
    staleTime: DASHBOARD_STALE_TIME,
  });
}

export function useAIDashboardQuery(branchId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: dashboardKeys.ai(branchId),
    queryFn: () => getAIDashboard(branchId),
    enabled,
    staleTime: DASHBOARD_STALE_TIME,
  });
}

export function useFinancialDashboardQuery(branchId: string | null, range: DateRangeQuery, enabled: boolean) {
  return useQuery({
    queryKey: dashboardKeys.financial(branchId, range),
    queryFn: () => getFinancialDashboard(branchId, range),
    enabled,
    staleTime: DASHBOARD_STALE_TIME,
  });
}

export function useKpiSummaryQuery(branchId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: dashboardKeys.kpiSummary(branchId),
    queryFn: () => getKpiSummary(branchId),
    enabled,
    staleTime: DASHBOARD_STALE_TIME,
  });
}

export function useRevenueTrendQuery(branchId: string | null, range: DateRangeQuery, enabled: boolean) {
  return useQuery({
    queryKey: dashboardKeys.revenueTrend(branchId, range),
    queryFn: () => getRevenueTrend(branchId, range),
    enabled,
    staleTime: DASHBOARD_STALE_TIME,
  });
}

export function useBranchPerformanceQuery(enabled: boolean) {
  return useQuery({
    queryKey: dashboardKeys.branchPerformance(),
    queryFn: getBranchPerformance,
    enabled,
    staleTime: DASHBOARD_STALE_TIME,
  });
}
