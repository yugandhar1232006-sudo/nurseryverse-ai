"use client";

import { AlertTriangle, Building2, Package, ShieldAlert, TrendingUp } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { KpiCard, KpiCardGrid } from "@/components/dashboards/kpi-card";
import { useBranchDashboardQuery } from "@/lib/dashboards/queries";
import { formatCurrency, formatNumber } from "@/lib/utils";

/**
 * PG-08 Branch Dashboard, backed by `GET /dashboards/branch/{branch_id}`
 * -- the one dashboard route that requires a specific branch, never
 * "all branches" (see reports.py: it 404s without a real branch id).
 * When the dashboard scope selector is set to "All branches," this tab
 * shows a real prompt to pick one rather than silently falling back to
 * some arbitrary branch.
 */
export function BranchTab({ branchId, currency }: { branchId: string | null; currency: string }) {
  const query = useBranchDashboardQuery(branchId, branchId !== null);

  if (branchId === null) {
    return (
      <EmptyState
        icon={Building2}
        title="Pick a branch"
        description="Select a specific branch from the scope dropdown above to see its dashboard."
      />
    );
  }

  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  }

  const data = query.data;

  return (
    <KpiCardGrid>
      <KpiCard
        label="Revenue today"
        value={data ? formatCurrency(data.revenue_today, currency) : ""}
        icon={TrendingUp}
        tone="success"
        loading={query.isLoading}
      />
      <KpiCard
        label="Revenue MTD"
        value={data ? formatCurrency(data.revenue_mtd, currency) : ""}
        icon={TrendingUp}
        tone="success"
        loading={query.isLoading}
      />
      <KpiCard
        label="At-risk plants"
        value={data ? formatNumber(data.at_risk_plant_count) : ""}
        icon={AlertTriangle}
        tone={data && data.at_risk_plant_count > 0 ? "warning" : "neutral"}
        loading={query.isLoading}
      />
      <KpiCard
        label="Low stock items"
        value={data ? formatNumber(data.low_stock_count) : ""}
        icon={Package}
        tone={data && data.low_stock_count > 0 ? "warning" : "neutral"}
        loading={query.isLoading}
      />
      <KpiCard
        label="Pending disease reports"
        value={data ? formatNumber(data.pending_disease_reports) : ""}
        icon={ShieldAlert}
        tone={data && data.pending_disease_reports > 0 ? "danger" : "neutral"}
        loading={query.isLoading}
      />
    </KpiCardGrid>
  );
}
