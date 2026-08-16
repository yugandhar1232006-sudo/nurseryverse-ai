"use client";

import { PackageCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { useLineReservationsQuery } from "@/lib/inventory/queries";
import { useReleaseReservationMutation, useFulfillReservationMutation } from "@/lib/inventory/mutations";
import type { StockReservationResponse } from "@/lib/api/inventory";

const STATUS_TONE: Record<StockReservationResponse["status"], "neutral" | "success" | "warning" | "danger" | "info"> = {
  active: "info",
  released: "neutral",
  fulfilled: "success",
  expired: "warning",
};

/**
 * `GET /inventory/{id}/reservations` -- unpaginated (`list[StockReservationResponse]`,
 * not a `Page_*_` shape), same pattern as 7G's `MovementTab`. Release
 * (`inventory:write`) and Fulfill (`inventory:adjust`, since it converts a
 * hold into a real departure of stock -- see `fulfill_reservation`'s route
 * summary) act directly with no confirmation dialog: releasing/fulfilling
 * an already-decided reservation is a low-risk, easily-visible action, the
 * same judgment call 7G's disease report "Confirm" button makes.
 */
export function ReservationsTab({ lineId }: { lineId: string }) {
  const query = useLineReservationsQuery(lineId);
  const releaseMutation = useReleaseReservationMutation(lineId);
  const fulfillMutation = useFulfillReservationMutation(lineId);

  if (query.isLoading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    );
  }

  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  }

  if (!query.data || query.data.length === 0) {
    return <EmptyState icon={PackageCheck} title="No reservations" description="Stock held for a pending sale or order will appear here." />;
  }

  return (
    <ul className="flex flex-col gap-2">
      {query.data.map((reservation) => (
        <li key={reservation.id} className="flex flex-col gap-2 rounded-md border border-border p-3 text-body-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium text-foreground">{reservation.quantity} units</span>
              <Badge tone={STATUS_TONE[reservation.status]}>{reservation.status}</Badge>
              {reservation.reference_type && <span className="text-muted-foreground">for {reservation.reference_type}</span>}
            </div>
            {reservation.status === "active" && (
              <div className="flex gap-2">
                <PermissionGate permission="inventory:write">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={releaseMutation.isPending}
                    onClick={() => releaseMutation.mutate(reservation.id)}
                  >
                    Release
                  </Button>
                </PermissionGate>
                <PermissionGate permission="inventory:adjust">
                  <Button
                    type="button"
                    size="sm"
                    disabled={fulfillMutation.isPending}
                    onClick={() => fulfillMutation.mutate({ reservationId: reservation.id, body: { reference_sale_id: null, plant_id: null } })}
                  >
                    Fulfill
                  </Button>
                </PermissionGate>
              </div>
            )}
          </div>
          {reservation.note && <p className="text-muted-foreground">{reservation.note}</p>}
          <p className="text-caption text-muted-foreground">Reserved {new Date(reservation.reserved_at).toLocaleString()}</p>
        </li>
      ))}
    </ul>
  );
}
