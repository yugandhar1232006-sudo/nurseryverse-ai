"use client";

import { useParams } from "next/navigation";

import { ErrorState } from "@/components/error-state";
import { PermissionDenied } from "@/components/layout/permission-denied";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { InventoryHeader } from "@/components/inventory/inventory-header";
import { MovementsTab } from "@/components/inventory/tabs/movements-tab";
import { ReservationsTab } from "@/components/inventory/tabs/reservations-tab";
import { useInventoryDetailQuery } from "@/lib/inventory/queries";

/**
 * The Inventory Line Detail page -- `/inventory/[id]`, the 7I counterpart
 * to 7G's `/plants/[id]` Plant Profile. Uses `useParams()` for the same
 * reason that page does: this whole page is client-rendered (TanStack
 * Query + permission-aware hooks throughout), so Next 16's Server
 * Component `params`-as-Promise would add an async boundary with no
 * benefit here.
 */
export default function InventoryDetailPage() {
  const params = useParams<{ id: string }>();
  const lineId = params.id;

  const lineQuery = useInventoryDetailQuery(lineId);

  return (
    <PermissionGate permission="inventory:read" fallback={<PermissionDenied />}>
      <div className="flex flex-col gap-6">
        {lineQuery.isLoading && (
          <div className="flex flex-col gap-4">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
        )}
        {lineQuery.isError && (
          <ErrorState variant="full-page" error={lineQuery.error} onRetry={() => lineQuery.refetch()} retrying={lineQuery.isFetching} />
        )}
        {lineQuery.data && (
          <>
            <InventoryHeader item={lineQuery.data} />

            <Tabs defaultValue="movements">
              <TabsList>
                <TabsTrigger value="movements">Movements</TabsTrigger>
                <TabsTrigger value="reservations">Reservations</TabsTrigger>
              </TabsList>
              <TabsContent value="movements">
                <MovementsTab lineId={lineId} />
              </TabsContent>
              <TabsContent value="reservations">
                <ReservationsTab lineId={lineId} />
              </TabsContent>
            </Tabs>
          </>
        )}
      </div>
    </PermissionGate>
  );
}
