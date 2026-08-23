"use client";

import { AlertTriangle, Boxes, IndianRupee, Package } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { KpiCard, KpiCardGrid } from "@/components/dashboards/kpi-card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useInventoryDashboardQuery } from "@/lib/dashboards/queries";
import { formatCurrency, formatNumber } from "@/lib/utils";

/** `GET /dashboards/inventory` -- on-hand units, valuation, and the real low-stock item list. */
export function InventoryTab({ branchId, currency }: { branchId: string | null; currency: string }) {
  const query = useInventoryDashboardQuery(branchId, true);

  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  }

  const data = query.data;

  return (
    <div className="flex flex-col gap-4">
      <KpiCardGrid>
        <KpiCard
          label="Line items"
          value={data ? formatNumber(data.total_line_items) : ""}
          icon={Package}
          loading={query.isLoading}
        />
        <KpiCard
          label="Units on hand"
          value={data ? formatNumber(data.total_units_on_hand) : ""}
          icon={Boxes}
          tone="info"
          loading={query.isLoading}
        />
        <KpiCard
          label="Inventory value"
          value={data ? formatCurrency(data.total_inventory_value, currency) : ""}
          icon={IndianRupee}
          tone="success"
          loading={query.isLoading}
        />
        <KpiCard
          label="Low stock items"
          value={data ? formatNumber(data.low_stock_count) : ""}
          icon={AlertTriangle}
          tone={data && data.low_stock_count > 0 ? "warning" : "neutral"}
          loading={query.isLoading}
        />
      </KpiCardGrid>

      <Card>
        <CardHeader>
          <CardTitle>Low stock items</CardTitle>
        </CardHeader>
        <CardContent>
          {query.isLoading ? (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : !data || data.low_stock_items.length === 0 ? (
            <EmptyState icon={Package} title="Nothing low on stock" description="Every inventory line is above its low-stock threshold right now." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Item</TableHead>
                  <TableHead className="text-right">Quantity</TableHead>
                  <TableHead className="text-right">Threshold</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.low_stock_items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="font-medium text-foreground">{item.name}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatNumber(item.quantity)}</TableCell>
                    <TableCell className="text-right tabular-nums text-muted-foreground">{formatNumber(item.low_stock_threshold)}</TableCell>
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
