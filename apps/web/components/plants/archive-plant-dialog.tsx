"use client";

import * as React from "react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Textarea } from "@/components/ui/textarea";
import { useArchivePlantMutation } from "@/lib/plants/mutations";

/**
 * Archiving a plant is not the same as marking it `deceased` -- it's a
 * soft-delete of the record itself (`archived_at`/`archived_reason` on
 * `PlantResponse`), independent of lifecycle status. Kept as a plain
 * AlertDialog with a free-text reason rather than a full RHF form since
 * `ArchivePlantRequest` has exactly one optional field.
 */
export function ArchivePlantDialog({
  open,
  onOpenChange,
  plantId,
  plantLabel,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  plantId: string;
  plantLabel: string;
}) {
  const [reason, setReason] = React.useState("");
  const mutation = useArchivePlantMutation(plantId);

  // React's "adjusting state when a prop changes" pattern (not an
  // Effect) -- see docs/frontend/09-organization-management.md's
  // defect writeup for why an Effect-based setState here would trip
  // the `react-hooks/set-state-in-effect` rule.
  const [syncedOpen, setSyncedOpen] = React.useState(open);
  if (open !== syncedOpen) {
    setSyncedOpen(open);
    if (open) setReason("");
  }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Archive {plantLabel}?</AlertDialogTitle>
          <AlertDialogDescription>
            Archived plants are removed from active lists but their full history is preserved. This action cannot be undone from here.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <Textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Reason (optional)"
          rows={3}
          aria-label="Archive reason"
        />
        <AlertDialogFooter>
          <AlertDialogCancel disabled={mutation.isPending}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            disabled={mutation.isPending}
            onClick={() => mutation.mutate({ reason: reason || null }, { onSuccess: () => onOpenChange(false) })}
          >
            Archive
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
