"use client";

import * as React from "react";
import { History } from "lucide-react";

import { RecordEntryList } from "@/components/plants/record-entry-list";
import { useLineMovementsQuery } from "@/lib/inventory/queries";
import type { StockMovementResponse } from "@/lib/api/inventory";

const MOVEMENT_LABELS: Record<StockMovementResponse["movement_type"], string> = {
  incoming: "Received",
  outgoing: "Removed",
  transfer: "Transferred",
  adjustment: "Adjusted",
  waste: "Disposed",
  damage: "Marked damaged",
  reservation: "Reserved",
  release: "Reservation released",
  sale: "Sold",
  archive: "Archived",
};

/**
 * `GET /inventory/{id}/movements` -- the immutable ledger every real
 * mutation on this line writes exactly one row to (see
 * `InventoryService`'s module docstring: `_apply_change()` is the sole
 * write path). Reuses 7G's `RecordEntryList` scaffold since
 * `StockMovementResponse` has a real `id`, same as the five plant record
 * types.
 */
export function MovementsTab({ lineId }: { lineId: string }) {
  const [page, setPage] = React.useState(1);
  const query = useLineMovementsQuery(lineId, page);

  return (
    <RecordEntryList<StockMovementResponse>
      icon={History}
      emptyTitle="No movements yet"
      emptyDescription="Every receive, transfer, reserve, adjust, damage, dispose, sale, or archive action on this line appears here."
      items={query.data?.items ?? []}
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      onRetry={() => query.refetch()}
      retrying={query.isFetching}
      page={page}
      totalPages={query.data?.meta.total_pages ?? 1}
      onPageChange={setPage}
      renderItem={(movement) => (
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2 text-body-sm">
            <span className="font-medium text-foreground">{MOVEMENT_LABELS[movement.movement_type]}</span>
            <span className={movement.quantity_delta >= 0 ? "text-success-dark" : "text-danger-dark"}>
              {movement.quantity_delta >= 0 ? "+" : ""}
              {movement.quantity_delta}
            </span>
            <span className="text-muted-foreground">→ {movement.quantity_after} on hand</span>
          </div>
          {movement.reason && <p className="text-caption text-muted-foreground">Reason: {movement.reason}</p>}
          {movement.note && <p className="text-body-sm text-muted-foreground">{movement.note}</p>}
          <p className="text-caption text-muted-foreground">{new Date(movement.created_at).toLocaleString()}</p>
        </div>
      )}
    />
  );
}
