"use client";

import * as React from "react";
import { ArrowLeftRight, Archive, QrCode } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PermissionGate } from "@/components/auth/permission-gate";
import { PlantStatusBadge } from "@/components/plants/plant-status-badge";
import { MovePlantDialog } from "@/components/plants/move-plant-dialog";
import { TransitionStatusDialog } from "@/components/plants/transition-status-dialog";
import { ArchivePlantDialog } from "@/components/plants/archive-plant-dialog";
import { useBranchesQuery } from "@/lib/shell/queries";
import { useSpeciesDetailQuery } from "@/lib/catalog/queries";
import type { PlantResponse } from "@/lib/api/plants";

/**
 * Plant Profile identity strip. `age_days` is `PlantResponse`'s own
 * computed field, always derived from `planted_at` server-side (see
 * lib/api/plants.ts's docstring) -- displayed as-is, never recomputed
 * here from `planted_at` client-side.
 */
export function PlantHeader({ plant }: { plant: PlantResponse }) {
  const branchesQuery = useBranchesQuery();
  const speciesQuery = useSpeciesDetailQuery(plant.species_id);

  const [moveOpen, setMoveOpen] = React.useState(false);
  const [statusOpen, setStatusOpen] = React.useState(false);
  const [archiveOpen, setArchiveOpen] = React.useState(false);

  const branchName = (branchesQuery.data ?? []).find((b) => b.id === plant.branch_id)?.name ?? "—";
  const label = plant.common_label ?? speciesQuery.data?.common_name ?? "Unlabeled plant";
  const isArchived = plant.archived_at !== null;

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-h2 font-semibold text-foreground">{label}</h1>
          <p className="text-body-sm text-muted-foreground">
            {speciesQuery.data?.common_name ?? "—"}
            {speciesQuery.data?.botanical_name && <span className="italic"> ({speciesQuery.data.botanical_name})</span>}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <PlantStatusBadge status={plant.status} />
          {isArchived && <Badge tone="neutral">Archived</Badge>}
        </div>
      </div>

      <div className="flex flex-wrap gap-x-6 gap-y-1 text-body-sm text-muted-foreground">
        <span>
          Branch: <span className="text-foreground">{branchName}</span>
        </span>
        <span>
          Zone: <span className="text-foreground">{plant.zone ?? "—"}</span>
        </span>
        <span>
          Batch: <span className="text-foreground">{plant.batch_number ?? "—"}</span>
        </span>
        <span>
          Age: <span className="text-foreground">{plant.age_days} days</span>
        </span>
        <span className="flex items-center gap-1">
          <QrCode className="size-3.5" aria-hidden="true" />
          <span className="text-foreground">{plant.qr_code_token}</span>
        </span>
      </div>

      {!isArchived && (
        <div className="flex flex-wrap gap-2">
          <PermissionGate permission="plants:transfer">
            <Button type="button" variant="outline" size="sm" onClick={() => setMoveOpen(true)}>
              <ArrowLeftRight className="size-4" aria-hidden="true" />
              Move
            </Button>
          </PermissionGate>
          <PermissionGate permission="plants:write">
            <Button type="button" variant="outline" size="sm" onClick={() => setStatusOpen(true)}>
              Change status
            </Button>
          </PermissionGate>
          <PermissionGate permission="plants:write">
            <Button type="button" variant="outline" size="sm" className="text-destructive hover:text-destructive" onClick={() => setArchiveOpen(true)}>
              <Archive className="size-4" aria-hidden="true" />
              Archive
            </Button>
          </PermissionGate>
        </div>
      )}

      <MovePlantDialog open={moveOpen} onOpenChange={setMoveOpen} plantId={plant.id} currentBranchId={plant.branch_id} />
      <TransitionStatusDialog open={statusOpen} onOpenChange={setStatusOpen} plantId={plant.id} currentStatus={plant.status} />
      <ArchivePlantDialog open={archiveOpen} onOpenChange={setArchiveOpen} plantId={plant.id} plantLabel={label} />
    </div>
  );
}
