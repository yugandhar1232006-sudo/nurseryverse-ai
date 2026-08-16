"use client";

import { Repeat, Users } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { KpiCard, KpiCardGrid } from "@/components/dashboards/kpi-card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useCustomerDashboardQuery } from "@/lib/dashboards/queries";
import { formatCurrency, formatNumber, formatPercent } from "@/lib/utils";

/** `GET /dashboards/customer` -- total/repeat customer counts and the real top-customers-by-lifetime-value list. */
export function CustomerTab({ branchId, currency }: { branchId: string | null; currency: string }) {
  const query = useCustomerDashboardQuery(branchId, true);

  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  }

  const data = query.data;

  return (
    <div className="flex flex-col gap-4">
      <KpiCardGrid className="tablet:grid-cols-3 laptop:grid-cols-3">
        <KpiCard label="Total customers" value={data ? formatNumber(data.total_customers) : ""} icon={Users} loading={query.isLoading} />
        <KpiCard
          label="Repeat customers"
          value={data ? formatNumber(data.repeat_customer_count) : ""}
          icon={Repeat}
          tone="info"
          loading={query.isLoading}
        />
        <KpiCard
          label="Repeat rate"
          value={data ? formatPercent(data.repeat_customer_rate) : ""}
          icon={Repeat}
          tone="success"
          loading={query.isLoading}
        />
      </KpiCardGrid>

      <Card>
        <CardHeader>
          <CardTitle>Top customers by lifetime value</CardTitle>
        </CardHeader>
        <CardContent>
          {query.isLoading ? (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : !data || data.top_customers.length === 0 ? (
            <EmptyState icon={Users} title="No customers yet" description="Top customers appear here once sales are recorded." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Customer</TableHead>
                  <TableHead className="text-right">Orders</TableHead>
                  <TableHead className="text-right">Total spent</TableHead>
                  <TableHead className="text-right">Last purchase</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.top_customers.map((c) => (
                  <TableRow key={c.customer_id}>
                    <TableCell className="font-medium text-foreground">{c.customer_name}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatNumber(c.total_orders)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatCurrency(c.total_spent, currency)}</TableCell>
                    <TableCell className="text-right text-muted-foreground">
                      {c.last_purchase_at ? new Date(c.last_purchase_at).toLocaleDateString() : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
