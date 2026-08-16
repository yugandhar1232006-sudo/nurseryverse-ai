"use client";

import * as React from "react";
import { History } from "lucide-react";

import { RecordEntryList } from "@/components/plants/record-entry-list";
import { useTwinTimelineQuery } from "@/lib/digital-twin/queries";
import type { DigitalTwinVersionResponse } from "@/lib/api/digital-twin";

/**
 * "Timeline" -- one entry per event that updated this plant's Digital
 * Twin, newest first. Distinct from 7G's own `TimelineTab`: that one
 * reads `PlantTimelineEntryResponse` (a human-readable event summary
 * with no snapshot attached); this one reads
 * `DigitalTwinVersionResponse` (the actual projected snapshot at that
 * point, usable for "what did the twin look like right after this
 * event"). Both are real, both matter, and they read from genuinely
 * different backend tables.
 */
export function TwinTimelinePanel({ plantId }: { plantId: string }) {
  const [page, setPage] = React.useState(1);
  const query = useTwinTimelineQuery(plantId, page);

  return (
    <RecordEntryList<DigitalTwinVersionResponse>
      icon={History}
      emptyTitle="No twin events yet"
      emptyDescription="Every event that updates this plant's Digital Twin will appear here."
      items={query.data?.items ?? []}
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      onRetry={() => query.refetch()}
      retrying={query.isFetching}
      page={page}
      totalPages={query.data?.meta.total_pages ?? 1}
      onPageChange={setPage}
      renderItem={(v) => (
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2 text-body-sm">
            <span className="font-medium text-foreground">v{v.version}</span>
            <span className="text-muted-foreground">{v.event_type}</span>
          </div>
          <p className="text-caption text-muted-foreground">{new Date(v.occurred_at).toLocaleString()}</p>
        </div>
      )}
    />
  );
}
