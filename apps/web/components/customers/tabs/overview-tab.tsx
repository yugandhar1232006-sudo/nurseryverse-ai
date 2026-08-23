"use client";

import { IndianRupee, Repeat, ShoppingBag } from "lucide-react";

import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useCustomerAnalyticsQuery } from "@/lib/customers/queries";

/** `GET /customers/{id}/analytics` -- all derived/computed live, nothing persisted on Customer itself. */
export function OverviewTab({ customerId }: { customerId: string }) {
  const query = useCustomerAnalyticsQuery(customerId);

  if (query.isLoading) return <Skeleton className="h-24 w-full" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  const analytics = query.data;
  if (!analytics) return null;

  const cards = [
    { label: "Total orders", value: analytics.total_orders, icon: ShoppingBag },
    { label: "Total spent", value: `₹${analytics.total_spent.toFixed(2)}`, icon: IndianRupee },
    { label: "Average order value", value: `₹${analytics.average_order_value.toFixed(2)}`, icon: Repeat },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 tablet:grid-cols-3">
        {cards.map((card) => (
          <div key={card.label} className="rounded-md border border-border p-3">
            <p className="text-body-sm text-muted-foreground">{card.label}</p>
            <p className="text-h4 font-semibold text-foreground">{card.value}</p>
          </div>
        ))}
      </div>
      <p className="text-body-sm text-muted-foreground">
        Last purchase: {analytics.last_purchase_at ? new Date(analytics.last_purchase_at).toLocaleString() : "No purchases yet"}
      </p>
    </div>
  );
}
