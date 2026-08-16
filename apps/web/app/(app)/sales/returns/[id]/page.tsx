"use client";

import { useParams } from "next/navigation";

import { ErrorState } from "@/components/error-state";
import { PermissionDenied } from "@/components/layout/permission-denied";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { ReturnHeader } from "@/components/sales/return-header";
import { useReturnDetailQuery } from "@/lib/sales/queries";

/** `/sales/returns/[id]` -- the Return Detail page. */
export default function ReturnDetailPage() {
  const params = useParams<{ id: string }>();
  const returnId = params.id;

  const returnQuery = useReturnDetailQuery(returnId);

  return (
    <PermissionGate permission="sales:read" fallback={<PermissionDenied />}>
      <div className="flex flex-col gap-6">
        {returnQuery.isLoading && (
          <div className="flex flex-col gap-4">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        )}
        {returnQuery.isError && (
          <ErrorState variant="full-page" error={returnQuery.error} onRetry={() => returnQuery.refetch()} retrying={returnQuery.isFetching} />
        )}
        {returnQuery.data && <ReturnHeader ret={returnQuery.data} />}
      </div>
    </PermissionGate>
  );
}
