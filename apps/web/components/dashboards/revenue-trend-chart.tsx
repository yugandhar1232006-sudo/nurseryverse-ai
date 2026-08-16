"use client";

import { format, parseISO } from "date-fns";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Skeleton } from "@/components/ui/skeleton";
import type { RevenueTrendPointResponse } from "@/lib/api/reports";
import { formatCurrency } from "@/lib/utils";

/**
 * Renders `ExecutiveDashboardResponse.revenue_trend` -- real, already-
 * aggregated rollup points from `DashboardService.executive_dashboard`
 * (see docs/ux/18-analytics-workflow.md's "Report vs. Dashboard
 * Distinction": dashboards read pre-aggregated rollups, never raw sales
 * rows). `day` is typed `Any` on the backend schema (a raw SQL date
 * value serialized through Pydantic) -- normalized to an ISO string here
 * defensively since its exact serialized shape (date-only vs datetime)
 * isn't guaranteed by the OpenAPI contract.
 */
export function RevenueTrendChart({
  data,
  currency,
  loading,
}: {
  data: RevenueTrendPointResponse[] | undefined;
  currency: string;
  loading?: boolean;
}) {
  if (loading) {
    return <Skeleton className="h-64 w-full" />;
  }

  if (!data || data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-body-sm text-muted-foreground">
        No revenue data for this period yet.
      </div>
    );
  }

  const points = data.map((point) => {
    const raw = typeof point.day === "string" ? point.day : String(point.day);
    let label = raw;
    try {
      label = format(parseISO(raw), "MMM d");
    } catch {
      // Leave the raw value as-is if it isn't a parseable date string --
      // never crash a dashboard render over a chart axis label.
    }
    return { ...point, label };
  });

  return (
    <ResponsiveContainer width="100%" height={256}>
      <AreaChart data={points} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
        <defs>
          <linearGradient id="revenueTrendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="var(--color-primary)" stopOpacity={0.25} />
            <stop offset="95%" stopColor="var(--color-primary)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--color-border)" />
        <XAxis dataKey="label" tick={{ fontSize: 12 }} tickLine={false} axisLine={false} />
        <YAxis
          tick={{ fontSize: 12 }}
          tickLine={false}
          axisLine={false}
          width={64}
          tickFormatter={(value: number) => formatCurrency(value, currency)}
        />
        <Tooltip
          formatter={(value, name) =>
            name === "revenue" ? [formatCurrency(Number(value ?? 0), currency), "Revenue"] : [String(value ?? ""), "Sales"]
          }
          labelFormatter={(label) => label}
        />
        <Area type="monotone" dataKey="revenue" stroke="var(--color-primary)" strokeWidth={2} fill="url(#revenueTrendFill)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
