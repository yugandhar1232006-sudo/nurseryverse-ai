"use client";

import { useParams } from "next/navigation";

import { ErrorState } from "@/components/error-state";
import { PermissionDenied } from "@/components/layout/permission-denied";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { QuotationHeader } from "@/components/sales/quotation-header";
import { useQuotationDetailQuery } from "@/lib/sales/queries";

/** `/sales/quotations/[id]` -- the Quotation Detail page. Client-rendered throughout, same `useParams()` pattern as 7I's `/inventory/[id]`. */
export default function QuotationDetailPage() {
  const params = useParams<{ id: string }>();
  const quotationId = params.id;

  const quotationQuery = useQuotationDetailQuery(quotationId);

  return (
    <PermissionGate permission="sales:read" fallback={<PermissionDenied />}>
      <div className="flex flex-col gap-6">
        {quotationQuery.isLoading && (
          <div className="flex flex-col gap-4">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        )}
        {quotationQuery.isError && (
          <ErrorState variant="full-page" error={quotationQuery.error} onRetry={() => quotationQuery.refetch()} retrying={quotationQuery.isFetching} />
        )}
        {quotationQuery.data && <QuotationHeader quotation={quotationQuery.data} />}
      </div>
    </PermissionGate>
  );
}
