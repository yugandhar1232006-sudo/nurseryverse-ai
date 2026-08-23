"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useInventorySummaryQuery } from "@/lib/inventory/queries";

/**
 * `GET /inventory/summary` -- real, backend-computed aggregate counts
 * (not derived client-side from the paginated list, which would only see
 * one page's worth of rows). `total_valuation` uses `unit_cost * quantity`
 * server-side; see `InventoryService.inventory_summary`'s own docstring.
 */
export function InventorySummaryCards({ branchId }: { branchId: string }) {
  const query = useInventorySummaryQuery(branchId);

  if (query.isLoading) {
    return (
      <div className="grid grid-cols-2 gap-4 tablet:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
    );
  }

  const summary = query.data;
  if (!summary) return null;

  const cards = [
    { label: "Lines", value: summary.line_count },
    { label: "Available", value: summary.total_available_quantity },
    { label: "Low stock", value: summary.low_stock_count },
    { label: "Valuation", value: `₹${summary.total_valuation.toFixed(2)}` },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 tablet:grid-cols-4">
      {cards.map((card) => (
        <Card key={card.label}>
          <CardHeader className="pb-2">
            <CardTitle className="text-body-sm font-medium text-muted-foreground">{card.label}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-h3 font-semibold text-foreground">{card.value}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
