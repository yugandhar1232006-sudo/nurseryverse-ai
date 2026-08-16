"use client";

import { DollarSign, Receipt, TrendingDown, TrendingUp } from "lucide-react";

import { ErrorState } from "@/components/error-state";
import { KpiCard, KpiCardGrid } from "@/components/dashboards/kpi-card";
import type { DateRangeQuery } from "@/lib/api/reports";
import { useFinancialDashboardQuery } from "@/lib/dashboards/queries";
import { formatCurrency, formatNumber, formatPercent } from "@/lib/utils";

/**
 * `GET /dashboards/financial` -- `estimated_cogs`/`estimated_gross_profit`/
 * `estimated_gross_margin` are labeled "Estimated" here exactly as the
 * backend schema itself names them (see FinancialDashboardResponse) --
 * this is a real computed estimate from recorded cost/sale data, not a
 * full accounting close, and the UI should never imply otherwise.
 */
export function FinancialTab({ branchId, range, currency }: { branchId: string | null; range: DateRangeQuery; currency: string }) {
  const query = useFinancialDashboardQuery(branchId, range, true);

  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  }

  const data = query.data;

  return (
    <KpiCardGrid>
      <KpiCard label="Revenue" value={data ? formatCurrency(data.revenue, currency) : ""} icon={TrendingUp} tone="success" loading={query.isLoading} />
      <KpiCard
        label="Estimated COGS"
        value={data ? formatCurrency(data.estimated_cogs, currency) : ""}
        icon={TrendingDown}
        loading={query.isLoading}
      />
      <KpiCard
        label="Estimated gross profit"
        value={data ? formatCurrency(data.estimated_gross_profit, currency) : ""}
        icon={DollarSign}
        tone="success"
        loading={query.isLoading}
      />
      <KpiCard
        label="Estimated gross margin"
        value={data ? formatPercent(data.estimated_gross_margin) : ""}
        icon={DollarSign}
        tone="info"
        loading={query.isLoading}
      />
      <KpiCard
        label="Outstanding invoices"
        value={data ? formatNumber(data.outstanding_invoice_count) : ""}
        icon={Receipt}
        tone={data && data.outstanding_invoice_count > 0 ? "warning" : "neutral"}
        loading={query.isLoading}
      />
      <KpiCard
        label="Outstanding invoice total"
        value={data ? formatCurrency(data.outstanding_invoice_total, currency) : ""}
        icon={Receipt}
        tone={data && data.outstanding_invoice_total > 0 ? "warning" : "neutral"}
        loading={query.isLoading}
      />
    </KpiCardGrid>
  );
}
