"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Receipt } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useCustomerPurchaseHistoryQuery } from "@/lib/customers/queries";

/** `GET /customers/{id}/purchase-history` -- paginated `SaleResponse` list, clicking a row navigates to the shared `/sales/[id]` detail page. */
export function PurchaseHistoryTab({ customerId }: { customerId: string }) {
  const router = useRouter();
  const [page, setPage] = React.useState(1);
  const query = useCustomerPurchaseHistoryQuery(customerId, page);

  if (query.isLoading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  const items = query.data?.items ?? [];
  if (items.length === 0) {
    return <EmptyState icon={Receipt} title="No purchases yet" description="Completed sales for this customer will appear here." />;
  }

  return (
    <div className="flex flex-col gap-4">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Date</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Total</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((sale) => (
            <TableRow key={sale.id} className="cursor-pointer" onClick={() => router.push(`/sales/${sale.id}`)}>
              <TableCell className="text-foreground">{new Date(sale.created_at).toLocaleDateString()}</TableCell>
              <TableCell>
                <Badge tone={sale.status === "voided" ? "danger" : "success"} className="capitalize">
                  {sale.status}
                </Badge>
              </TableCell>
              <TableCell className="text-right font-medium text-foreground">${Number(sale.total_amount).toFixed(2)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {query.data && query.data.meta.total_pages > 1 && (
        <div className="flex items-center justify-between text-body-sm text-muted-foreground">
          <span>
            Page {query.data.meta.page} of {query.data.meta.total_pages}
          </span>
          <div className="flex gap-2">
            <Button type="button" variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </Button>
            <Button type="button" variant="outline" size="sm" disabled={page >= query.data.meta.total_pages} onClick={() => setPage((p) => p + 1)}>
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
