"use client";

import { AlertTriangle, Leaf, ShieldAlert, TrendingUp } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/error-state";
import { KpiCard, KpiCardGrid } from "@/components/dashboards/kpi-card";
import { RevenueTrendChart } from "@/components/dashboards/revenue-trend-chart";
import { BranchPerformanceTable } from "@/components/dashboards/branch-performance-table";
import { useExecutiveDashboardQuery } from "@/lib/dashboards/queries";
import { formatCurrency, formatNumber } from "@/lib/utils";

/**
 * PG-07 Org Dashboard, backed 1:1 by `GET /dashboards/executive` --
 * always org-wide (no `branch_id` parameter exists on this route; see
 * lib/api/reports.ts's own docstring), so it ignores the dashboard scope
 * selector entirely. `last_refreshed_at` is surfaced verbatim rather
 * than implied as "live," per the 18-analytics-workflow.md rollup
 * cadence -- an honest "as of" timestamp, not a fabricated real-time
 * claim.
 */
export function ExecutiveTab({ currency }: { currency: string }) {
  const query = useExecutiveDashboardQuery(true);

  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  }

  const data = query.data;

  return (
    <div className="flex flex-col gap-4">
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
          label="Active plants"
          value={data ? formatNumber(data.active_plant_count) : ""}
          icon={Leaf}
          tone="info"
          loading={query.isLoading}
        />
        <KpiCard
          label="At-risk plants"
          value={data ? formatNumber(data.at_risk_plant_count) : ""}
          icon={AlertTriangle}
          tone={data && data.at_risk_plant_count > 0 ? "warning" : "neutral"}
          loading={query.isLoading}
        />
      </KpiCardGrid>

      <KpiCardGrid className="tablet:grid-cols-2 laptop:grid-cols-2">
        <KpiCard
          label="Open disease reports"
          value={data ? formatNumber(data.open_disease_reports) : ""}
          icon={ShieldAlert}
          tone={data && data.open_disease_reports > 0 ? "danger" : "neutral"}
          loading={query.isLoading}
        />
      </KpiCardGrid>

      <Card>
        <CardHeader>
          <CardTitle>Revenue trend</CardTitle>
        </CardHeader>
        <CardContent>
          <RevenueTrendChart data={data?.revenue_trend} currency={currency} loading={query.isLoading} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Branches</CardTitle>
        </CardHeader>
        <CardContent>
          <BranchPerformanceTable branches={data?.branches} currency={currency} loading={query.isLoading} />
        </CardContent>
      </Card>

      {data?.last_refreshed_at && (
        <p className="text-caption text-muted-foreground">
          Figures reflect the last scheduled rollup, as of {new Date(data.last_refreshed_at).toLocaleString()}.
        </p>
      )}
    </div>
  );
}
