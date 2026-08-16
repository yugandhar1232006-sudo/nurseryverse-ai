"use client";

import * as React from "react";
import { CheckCircle2, RefreshCw, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { PermissionGate } from "@/components/auth/permission-gate";
import { useCurrentTwinQuery } from "@/lib/digital-twin/queries";
import { useVerifyTwinConsistencyMutation } from "@/lib/digital-twin/mutations";
import type { TwinSnapshot } from "@/lib/api/digital-twin";

const COUNT_LABELS: Record<keyof TwinSnapshot["counts"], string> = {
  growth: "Growth records",
  health: "Health observations",
  watering: "Watering events",
  fertilizer: "Fertilizer applications",
  environmental: "Environmental readings",
  disease_reports: "Disease reports",
  treatments: "Treatments",
  movements: "Branch/zone moves",
  images: "Images",
  inventory_movements: "Inventory movements",
  plant_sold: "Sales",
  plant_returned: "Returns",
  passports_generated: "Passports generated",
  qr_generated: "QR codes generated",
  ai_predictions: "AI predictions",
};

function formatDate(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleString() : "—";
}

/**
 * "Current Digital Twin" -- the read-optimized, event-driven projection
 * for this plant (`GET /plants/{id}/digital-twin`). Everything shown
 * here is a *summary derived from real events already recorded through
 * 7G's own forms* -- there is nothing editable on this page, matching
 * the backend's own structural guarantee that this module is entirely
 * `GET` routes (see lib/api/digital-twin.ts's docstring). `latest.*`
 * fields are quick-glance summaries only; the full historical record for
 * each is the corresponding 7G tab (Growth, Health, etc.), not this one.
 */
export function TwinOverview({ plantId }: { plantId: string }) {
  const twinQuery = useCurrentTwinQuery(plantId);
  const verifyMutation = useVerifyTwinConsistencyMutation(plantId);

  if (twinQuery.isLoading) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (twinQuery.isError) {
    return <ErrorState error={twinQuery.error} onRetry={() => twinQuery.refetch()} retrying={twinQuery.isFetching} />;
  }

  const twin = twinQuery.data;
  if (!twin) return null;

  // See lib/api/digital-twin.ts's `TwinSnapshot` docstring for why this
  // cast is necessary and honest: the backend's own schema declares
  // `snapshot: dict` with no sub-schema, so the generated client type is
  // opaque (`Record<string, never>`) -- this mirrors the same cast
  // pattern used for `AtRiskPlantResponse.result` in 7D.
  const snapshot = twin.snapshot as unknown as TwinSnapshot;

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-1 gap-4 tablet:grid-cols-2">
        <div className="flex flex-col gap-2 rounded-md border border-border p-4">
          <p className="text-caption text-muted-foreground">Lifecycle state</p>
          <Badge tone="info" className="w-fit">
            {snapshot.lifecycle_state}
          </Badge>
          <p className="text-caption text-muted-foreground">Operational status: {snapshot.operational_status}</p>
          {snapshot.growth_stage && <p className="text-caption text-muted-foreground">Growth stage: {snapshot.growth_stage}</p>}
        </div>
        <div className="flex flex-col gap-2 rounded-md border border-border p-4">
          <p className="text-caption text-muted-foreground">Ownership</p>
          <Badge tone={snapshot.ownership.owner_type === "customer" ? "warning" : "neutral"} className="w-fit">
            {snapshot.ownership.owner_type === "customer" ? "Owned by customer" : "Owned by nursery"}
          </Badge>
          {snapshot.ownership.since && <p className="text-caption text-muted-foreground">Since {formatDate(snapshot.ownership.since)}</p>}
        </div>
      </div>

      <div>
        <p className="mb-2 text-body-sm font-medium text-foreground">Activity counts (from real recorded events)</p>
        <div className="grid grid-cols-2 gap-2 tablet:grid-cols-4">
          {(Object.keys(snapshot.counts) as (keyof TwinSnapshot["counts"])[])
            .filter((key) => snapshot.counts[key] > 0)
            .map((key) => (
              <div key={key} className="rounded-md border border-border p-3">
                <p className="text-h3 font-semibold text-foreground">{snapshot.counts[key]}</p>
                <p className="text-caption text-muted-foreground">{COUNT_LABELS[key]}</p>
              </div>
            ))}
          {Object.values(snapshot.counts).every((v) => v === 0) && (
            <p className="text-body-sm text-muted-foreground">No recorded activity yet.</p>
          )}
        </div>
      </div>

      {snapshot.latest.ai_prediction && (
        <div className="rounded-md border border-ai-accent-200 bg-ai-accent-50 p-3">
          <div className="flex items-center gap-2">
            <Badge tone="ai">AI</Badge>
            <p className="text-body-sm font-medium text-foreground">Most recent AI prediction (summary only)</p>
          </div>
          <p className="mt-1 text-body-sm text-muted-foreground">
            {snapshot.latest.ai_prediction.prediction_type ?? "Prediction"} · confidence{" "}
            {snapshot.latest.ai_prediction.confidence != null ? `${(snapshot.latest.ai_prediction.confidence * 100).toFixed(0)}%` : "—"} ·{" "}
            {formatDate(snapshot.latest.ai_prediction.generated_at)}
          </p>
          <p className="text-caption text-muted-foreground">The full AI prediction history lives in the AI Experience module.</p>
        </div>
      )}

      <div className="rounded-md border border-border p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-body-sm font-medium text-foreground">Consistency verification</p>
            <p className="text-caption text-muted-foreground">
              Replays this plant&apos;s full event history from scratch and compares it against the stored projection above.
            </p>
          </div>
          <PermissionGate permission="plants:read">
            <Button type="button" variant="outline" size="sm" disabled={verifyMutation.isPending} onClick={() => verifyMutation.mutate()}>
              {verifyMutation.isPending ? <Spinner className="text-current" /> : <RefreshCw className="size-4" aria-hidden="true" />}
              Verify now
            </Button>
          </PermissionGate>
        </div>
        {verifyMutation.data && (
          <div className="mt-3 flex items-center gap-2 text-body-sm">
            {verifyMutation.data.consistent ? (
              <>
                <CheckCircle2 className="size-4 text-success-dark" aria-hidden="true" />
                <span>Consistent as of version {verifyMutation.data.current_version}.</span>
              </>
            ) : (
              <>
                <XCircle className="size-4 text-danger-dark" aria-hidden="true" />
                <span>
                  Replay diverged on: {verifyMutation.data.differing_keys.join(", ") || "(no keys reported)"}
                </span>
              </>
            )}
          </div>
        )}
        {verifyMutation.isError && <p className="mt-2 text-body-sm text-destructive">Verification failed to run. Try again.</p>}
      </div>

      <p className="text-caption text-muted-foreground">
        Projected from event {snapshot.identity.registered_at ? `at ${formatDate(twin.last_projected_at)}` : "—"} · current version{" "}
        {twin.current_version}
      </p>
    </div>
  );
}
