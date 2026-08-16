"use client";

import * as React from "react";
import { Layers } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { RecordEntryList } from "@/components/plants/record-entry-list";
import { Skeleton } from "@/components/ui/skeleton";
import { useVersionHistoryQuery, useVersionCompareQuery } from "@/lib/digital-twin/queries";
import type { DigitalTwinVersionResponse } from "@/lib/api/digital-twin";

/**
 * "Version history" -- every immutable version of this plant's Digital
 * Twin, each viewable as a full snapshot, plus a real "version
 * comparison" (`GET .../versions/compare`) between any two selected
 * versions. Selection is capped at exactly two -- the backend endpoint
 * itself only accepts `version_a`/`version_b`, not an arbitrary set.
 */
export function VersionHistoryPanel({ plantId }: { plantId: string }) {
  const [page, setPage] = React.useState(1);
  const [selected, setSelected] = React.useState<number[]>([]);
  const [viewingVersion, setViewingVersion] = React.useState<DigitalTwinVersionResponse | null>(null);
  const [compareOpen, setCompareOpen] = React.useState(false);

  const query = useVersionHistoryQuery(plantId, page);
  const [versionA, versionB] = selected;
  const compareQuery = useVersionCompareQuery(plantId, compareOpen ? (versionA ?? null) : null, compareOpen ? (versionB ?? null) : null);

  function toggleSelect(version: number) {
    setSelected((prev) => {
      if (prev.includes(version)) return prev.filter((v) => v !== version);
      if (prev.length >= 2) return [prev[1], version];
      return [...prev, version];
    });
  }

  return (
    <div className="flex flex-col gap-4">
      {selected.length === 2 && (
        <div className="flex items-center justify-between rounded-md border border-border p-3">
          <p className="text-body-sm">
            Comparing v{Math.min(versionA, versionB)} and v{Math.max(versionA, versionB)}
          </p>
          <Button type="button" size="sm" onClick={() => setCompareOpen(true)}>
            Compare
          </Button>
        </div>
      )}

      <RecordEntryList<DigitalTwinVersionResponse>
        icon={Layers}
        emptyTitle="No versions yet"
        emptyDescription="Every immutable version of this plant's Digital Twin will appear here."
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
          <div className="flex items-center justify-between gap-2">
            <label className="flex items-center gap-2 text-body-sm">
              <Checkbox checked={selected.includes(v.version)} onCheckedChange={() => toggleSelect(v.version)} aria-label={`Select version ${v.version} to compare`} />
              <span className="font-medium text-foreground">v{v.version}</span>
              <span className="text-muted-foreground">{v.event_type}</span>
              <span className="text-caption text-muted-foreground">{new Date(v.occurred_at).toLocaleString()}</span>
            </label>
            <Button type="button" variant="ghost" size="sm" onClick={() => setViewingVersion(v)}>
              View snapshot
            </Button>
          </div>
        )}
      />

      <Dialog open={viewingVersion !== null} onOpenChange={(open) => !open && setViewingVersion(null)}>
        <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Snapshot -- version {viewingVersion?.version}</DialogTitle>
            <DialogDescription>Full projected state right after {viewingVersion?.event_type}.</DialogDescription>
          </DialogHeader>
          <pre className="max-h-[60vh] overflow-auto rounded-sm bg-muted p-3 text-caption text-muted-foreground">
            {viewingVersion ? JSON.stringify(viewingVersion.snapshot, null, 2) : ""}
          </pre>
        </DialogContent>
      </Dialog>

      <Dialog open={compareOpen} onOpenChange={setCompareOpen}>
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              Compare v{compareQuery.data?.version_a ?? versionA} vs v{compareQuery.data?.version_b ?? versionB}
            </DialogTitle>
            <DialogDescription>Top-level fields that differ between the two versions.</DialogDescription>
          </DialogHeader>
          {compareQuery.isLoading && <Skeleton className="h-40 w-full" />}
          {compareQuery.isError && <p className="text-body-sm text-destructive">Couldn&apos;t load this comparison.</p>}
          {compareQuery.data && (
            <div className="flex flex-col gap-3">
              {compareQuery.data.changed_keys.length === 0 ? (
                <p className="text-body-sm text-muted-foreground">These two versions have identical top-level fields.</p>
              ) : (
                <p className="text-body-sm text-foreground">Changed: {compareQuery.data.changed_keys.join(", ")}</p>
              )}
              <div className="grid grid-cols-1 gap-3 tablet:grid-cols-2">
                <div>
                  <p className="mb-1 text-caption font-medium text-muted-foreground">Version {compareQuery.data.version_a}</p>
                  <pre className="max-h-64 overflow-auto rounded-sm bg-muted p-2 text-caption text-muted-foreground">
                    {JSON.stringify(compareQuery.data.snapshot_a, null, 2)}
                  </pre>
                </div>
                <div>
                  <p className="mb-1 text-caption font-medium text-muted-foreground">Version {compareQuery.data.version_b}</p>
                  <pre className="max-h-64 overflow-auto rounded-sm bg-muted p-2 text-caption text-muted-foreground">
                    {JSON.stringify(compareQuery.data.snapshot_b, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
