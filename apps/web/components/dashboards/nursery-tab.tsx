"use client";

import { Building2, Leaf, Package, ShieldAlert, Users } from "lucide-react";

import { ErrorState } from "@/components/error-state";
import { KpiCard, KpiCardGrid } from "@/components/dashboards/kpi-card";
import { useNurseryDashboardQuery } from "@/lib/dashboards/queries";
import { formatNumber } from "@/lib/utils";

/** `GET /dashboards/nursery` -- always org-wide, per lib/api/reports.ts. */
export function NurseryTab() {
  const query = useNurseryDashboardQuery(true);

  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  }

  const data = query.data;

  return (
    <KpiCardGrid>
      <KpiCard label="Total plants" value={data ? formatNumber(data.total_plants) : ""} icon={Leaf} tone="info" loading={query.isLoading} />
      <KpiCard
        label="Active plants"
        value={data ? formatNumber(data.active_plant_count) : ""}
        icon={Leaf}
        tone="success"
        loading={query.isLoading}
      />
      <KpiCard label="Branches" value={data ? formatNumber(data.branch_count) : ""} icon={Building2} loading={query.isLoading} />
      <KpiCard label="Employees" value={data ? formatNumber(data.employee_count) : ""} icon={Users} loading={query.isLoading} />
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
