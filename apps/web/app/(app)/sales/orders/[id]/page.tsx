"use client";

import { useParams } from "next/navigation";

import { ErrorState } from "@/components/error-state";
import { PermissionDenied } from "@/components/layout/permission-denied";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { SalesOrderHeader } from "@/components/sales/sales-order-header";
import { InvoicePanel } from "@/components/sales/invoice-panel";
import { useSalesOrderDetailQuery } from "@/lib/sales/queries";

/**
 * `/sales/orders/[id]` -- the Sales Order Detail page. The generated
 * Invoice is only reachable from here (`SalesOrderResponse.invoice_id`),
 * not from the completed Sale's own detail page -- `SaleResponse` carries
 * no `invoice_id` field at all, so `/sales/[id]` intentionally does not
 * attempt to show invoice/payment info; this page does, once checkout has
 * populated `invoice_id`.
 */
export default function SalesOrderDetailPage() {
  const params = useParams<{ id: string }>();
  const orderId = params.id;

  const orderQuery = useSalesOrderDetailQuery(orderId);

  return (
    <PermissionGate permission="sales:read" fallback={<PermissionDenied />}>
      <div className="flex flex-col gap-6">
        {orderQuery.isLoading && (
          <div className="flex flex-col gap-4">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        )}
        {orderQuery.isError && (
          <ErrorState variant="full-page" error={orderQuery.error} onRetry={() => orderQuery.refetch()} retrying={orderQuery.isFetching} />
        )}
        {orderQuery.data && (
          <>
            <SalesOrderHeader order={orderQuery.data} />
            {orderQuery.data.invoice_id && (
              <PermissionGate permission="invoices:read">
                <InvoicePanel invoiceId={orderQuery.data.invoice_id} />
              </PermissionGate>
            )}
          </>
        )}
      </div>
    </PermissionGate>
  );
}
