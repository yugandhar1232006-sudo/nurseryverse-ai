"use client";

import { Receipt, ShoppingCart, TrendingUp } from "lucide-react";

import { ErrorState } from "@/components/error-state";
import { KpiCard, KpiCardGrid } from "@/components/dashboards/kpi-card";
import type { DateRangeQuery } from "@/lib/api/reports";
import { useSalesDashboardQuery } from "@/lib/dashboards/queries";
import { formatCurrency, formatNumber } from "@/lib/utils";

/** `GET /dashboards/sales` -- transaction count/total/average for the dashboard's scope + date range. */
export function SalesTab({ branchId, range, currency }: { branchId: string | null; range: DateRangeQuery; currency: string }) {
  const query = useSalesDashboardQuery(branchId, range, true);

  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  }

  const data = query.data;

  return (
    <KpiCardGrid className="tablet:grid-cols-3 laptop:grid-cols-3">
      <KpiCard
        label="Transactions"
        value={data ? formatNumber(data.transaction_count) : ""}
        icon={ShoppingCart}
        loading={query.isLoading}
      />
      <KpiCard
        label="Total sales"
        value={data ? formatCurrency(data.total_sales, currency) : ""}
        icon={TrendingUp}
        tone="success"
        loading={query.isLoading}
      />
      <KpiCard
        label="Average sale value"
        value={data ? formatCurrency(data.average_sale_value, currency) : ""}
        icon={Receipt}
        loading={query.isLoading}
      />
    </KpiCardGrid>
  );
}
