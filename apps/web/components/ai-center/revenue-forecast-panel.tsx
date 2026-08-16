"use client";

import { format, parseISO } from "date-fns";
import { TrendingUp } from "lucide-react";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { useRevenueForecastsQuery } from "@/lib/ai-predictions/queries";
import { useRunRevenueForecastMutation } from "@/lib/ai-predictions/mutations";
import type { RevenueForecastResult } from "@/lib/api/ai-predictions";
import { formatCurrency } from "@/lib/utils";

/**
 * PG-32 Revenue Forecast -- `GET/POST /ai/predictions/revenue-forecast`.
 * The chart renders the real `forecast` array from the *most recent*
 * prediction's `result` (cast via `RevenueForecastResult`, see
 * lib/api/ai-predictions.ts's docstring on why this one hand-written
 * interface exists) -- a real 14-day projection with a real 95%
 * confidence band computed from actual historical daily-revenue standard
 * deviation, not a placeholder curve. "insufficient_data" (fewer than 7
 * days of real sales history) is rendered as an honest empty state, never
 * a fabricated flat line.
 */
export function RevenueForecastPanel({ branchId, currency }: { branchId: string | null; currency: string }) {
  const query = useRevenueForecastsQuery({ page: 1, page_size: 1, branch_id: branchId ?? undefined });
  const runMutation = useRunRevenueForecastMutation();

  if (query.isLoading) {
    return <Skeleton className="h-72 w-full" />;
  }

  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  }

  const latest = query.data?.items[0];
  const result = latest?.result as unknown as RevenueForecastResult | undefined;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <p className="text-body-sm text-muted-foreground">
          {latest ? `Generated ${new Date(latest.created_at).toLocaleString()}` : "No forecast generated yet."}
        </p>
        <PermissionGate permission="ai_predictions:run">
          <Button type="button" size="sm" disabled={runMutation.isPending} onClick={() => runMutation.mutate(branchId)}>
            {runMutation.isPending && <Spinner className="text-current" />}
            <TrendingUp className="size-4" aria-hidden="true" />
            Run forecast
          </Button>
        </PermissionGate>
      </div>

      {!latest && (
        <EmptyState icon={TrendingUp} title="No revenue forecast yet" description="Run a forecast above to project the next 14 days." />
      )}

      {latest && result?.method === "insufficient_data" && (
        <EmptyState
          icon={TrendingUp}
          title="Not enough sales history yet"
          description={latest.explanation ?? "At least 7 days of real sales history are needed for a seasonal forecast."}
        />
      )}

      {latest && result?.method === "seasonal_naive" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              14-day forecast <Badge tone="ai">Confidence: {latest.confidence ? `${(Number(latest.confidence) * 100).toFixed(0)}%` : "—"}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <p className="text-body-sm text-muted-foreground">{latest.explanation}</p>
            <ResponsiveContainer width="100%" height={256}>
              <ComposedChart
                data={result.forecast.map((p) => ({ ...p, label: safeFormatDate(p.date) }))}
                margin={{ top: 8, right: 8, left: 8, bottom: 0 }}
              >
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
                  formatter={(value, name) => [
                    formatCurrency(Number(value ?? 0), currency),
                    name === "upper_bound" ? "Upper bound" : name === "lower_bound" ? "Lower bound" : "Projected revenue",
                  ]}
                />
                <Area type="monotone" dataKey="upper_bound" stroke="none" fill="var(--color-primary)" fillOpacity={0.08} />
                <Area type="monotone" dataKey="lower_bound" stroke="none" fill="var(--color-card)" fillOpacity={1} />
                <Line type="monotone" dataKey="projected_revenue" stroke="var(--color-primary)" strokeWidth={2} dot={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function safeFormatDate(iso: string): string {
  try {
    return format(parseISO(iso), "MMM d");
  } catch {
    return iso;
  }
}
