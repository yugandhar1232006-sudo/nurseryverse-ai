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
import { useArchiveInventoryLineMutation } from "@/lib/inventory/mutations";

/** `ArchiveInventoryRequest` has exactly one optional field -- a plain AlertDialog, same pattern as 7G's `ArchivePlantDialog`. */
export function ArchiveInventoryDialog({
  open,
  onOpenChange,
  lineId,
  lineName,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  lineId: string;
  lineName: string;
}) {
  const [reason, setReason] = React.useState("");
  const mutation = useArchiveInventoryLineMutation(lineId);

  // React's "adjusting state when a prop changes" pattern (not an Effect)
  // -- see docs/frontend/09-organization-management.md's defect writeup.
  const [syncedOpen, setSyncedOpen] = React.useState(open);
  if (open !== syncedOpen) {
    setSyncedOpen(open);
    if (open) setReason("");
  }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Archive {lineName}?</AlertDialogTitle>
          <AlertDialogDescription>
            Archived lines are removed from active lists but their full history is preserved. This action cannot be undone from here.
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
