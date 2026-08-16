"use client";

import * as React from "react";
import { Radio } from "lucide-react";

import { RecordEntryList } from "@/components/plants/record-entry-list";
import { useEventHistoryQuery } from "@/lib/digital-twin/queries";
import type { DomainEventResponse } from "@/lib/api/digital-twin";

/**
 * "Event history" -- the raw `domain_events` rows for this plant,
 * including full payloads. This is the actual source of truth the twin
 * is projected from; shown here for transparency/debugging, not as a
 * primary user-facing view (payloads are raw JSON, not humanized).
 */
export function EventHistoryPanel({ plantId }: { plantId: string }) {
  const [page, setPage] = React.useState(1);
  const query = useEventHistoryQuery(plantId, page);

  return (
    <RecordEntryList<DomainEventResponse>
      icon={Radio}
      emptyTitle="No events recorded yet"
      emptyDescription="Every real domain event for this plant will appear here."
      items={query.data?.items ?? []}
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      onRetry={() => query.refetch()}
      retrying={query.isFetching}
      page={page}
      totalPages={query.data?.meta.total_pages ?? 1}
      onPageChange={setPage}
      renderItem={(event) => (
        <details className="flex flex-col gap-1">
          <summary className="cursor-pointer text-body-sm">
            <span className="font-medium text-foreground">{event.event_type}</span>{" "}
            <span className="text-caption text-muted-foreground">
              seq {event.sequence} · {new Date(event.occurred_at).toLocaleString()}
            </span>
          </summary>
          <pre className="mt-2 max-h-48 overflow-auto rounded-sm bg-muted p-2 text-caption text-muted-foreground">
            {JSON.stringify(event.payload, null, 2)}
          </pre>
        </details>
      )}
    />
  );
}
