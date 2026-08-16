"use client";

import * as React from "react";
import { History } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { usePlantTimelineQuery } from "@/lib/plants/queries";

/**
 * `PlantTimelineEntryResponse` has no `id` field (it's a projection over
 * several source event tables keyed by `source_id`, not a single-table
 * row) -- so this can't reuse `RecordEntryList<T extends {id: string}>`
 * and instead keys each row on `${event_type}-${source_id}`, which is
 * unique for one page of one plant's timeline in practice (the same
 * source record can't produce two entries of the same event_type).
 */
export function TimelineTab({ plantId }: { plantId: string }) {
  const [page, setPage] = React.useState(1);
  const query = usePlantTimelineQuery(plantId, page);

  if (query.isLoading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  }

  const items = query.data?.items ?? [];
  const meta = query.data?.meta;

  if (items.length === 0) {
    return <EmptyState icon={History} title="No timeline events yet" description="Every recorded event for this plant will appear here, newest first." />;
  }

  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-col gap-2">
        {items.map((entry) => (
          <li key={`${entry.event_type}-${entry.source_id}`} className="rounded-md border border-border p-3 text-body-sm">
            <span className="font-medium text-foreground">{entry.summary}</span>
            <p className="text-caption text-muted-foreground">{new Date(entry.occurred_at).toLocaleString()}</p>
          </li>
        ))}
      </ul>
      {meta && meta.total_pages > 1 && (
        <div className="flex items-center justify-between text-body-sm text-muted-foreground">
          <span>
            Page {meta.page} of {meta.total_pages}
          </span>
          <div className="flex gap-2">
            <Button type="button" variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </Button>
            <Button type="button" variant="outline" size="sm" disabled={page >= meta.total_pages} onClick={() => setPage((p) => p + 1)}>
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
