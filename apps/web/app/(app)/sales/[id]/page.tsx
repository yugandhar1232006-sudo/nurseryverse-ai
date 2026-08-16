"use client";

import { useParams } from "next/navigation";

import { ErrorState } from "@/components/error-state";
import { PermissionDenied } from "@/components/layout/permission-denied";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { SaleHeader } from "@/components/sales/sale-header";
import { useSaleDetailQuery } from "@/lib/sales/queries";

/** `/sales/[id]` -- the completed Sale detail page, reached from the Sales tab list, a customer's Purchase History, or after a Sales Order checkout. */
export default function SaleDetailPage() {
  const params = useParams<{ id: string }>();
  const saleId = params.id;

  const saleQuery = useSaleDetailQuery(saleId);

  return (
    <PermissionGate permission="sales:read" fallback={<PermissionDenied />}>
      <div className="flex flex-col gap-6">
        {saleQuery.isLoading && (
          <div className="flex flex-col gap-4">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        )}
        {saleQuery.isError && <ErrorState variant="full-page" error={saleQuery.error} onRetry={() => saleQuery.refetch()} retrying={saleQuery.isFetching} />}
        {saleQuery.data && <SaleHeader sale={saleQuery.data} />}
      </div>
    </PermissionGate>
  );
}
