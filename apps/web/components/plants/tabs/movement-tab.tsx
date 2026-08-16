"use client";

import { ArrowLeftRight } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useBranchesQuery } from "@/lib/shell/queries";
import { useMovementHistoryQuery } from "@/lib/plants/queries";

/**
 * Read-only history of `POST /plants/{id}/move` calls (`PlantTransferResponse[]`,
 * unpaginated -- the backend returns the full history in one call, not a
 * `Page_*_` shape, unlike the other five record types). Newest first per
 * the backend's own ordering.
 */
export function MovementTab({ plantId }: { plantId: string }) {
  const branchesQuery = useBranchesQuery();
  const query = useMovementHistoryQuery(plantId);
  const branchNameById = new Map((branchesQuery.data ?? []).map((b) => [b.id, b.name]));

  if (query.isLoading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-14 w-full" />
        ))}
      </div>
    );
  }

  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  }

  if (!query.data || query.data.length === 0) {
    return <EmptyState icon={ArrowLeftRight} title="No movements yet" description="This plant has never been moved between branches or zones." />;
  }

  return (
    <ul className="flex flex-col gap-2">
      {query.data.map((transfer) => (
        <li key={transfer.id} className="rounded-md border border-border p-3 text-body-sm">
          <span className="font-medium text-foreground">
            {branchNameById.get(transfer.from_branch_id) ?? "—"} → {branchNameById.get(transfer.to_branch_id) ?? "—"}
          </span>
          {(transfer.from_zone || transfer.to_zone) && (
            <span className="text-muted-foreground">
              {" "}
              ({transfer.from_zone ?? "—"} → {transfer.to_zone ?? "—"})
            </span>
          )}
          {transfer.note && <p className="text-muted-foreground">{transfer.note}</p>}
          <p className="text-caption text-muted-foreground">{new Date(transfer.transferred_at).toLocaleString()}</p>
        </li>
      ))}
    </ul>
  );
}
