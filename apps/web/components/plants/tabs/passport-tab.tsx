"use client";

import * as React from "react";
import { BadgeCheck, Copy, ExternalLink, Plus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { usePlantPassportsQuery } from "@/lib/passport/queries";
import { useGeneratePassportMutation } from "@/lib/passport/mutations";
import { toast } from "@/lib/toast";
import type { PassportResponse } from "@/lib/api/passport";

/**
 * Every Passport version ever generated for this plant -- append-only,
 * per docs/ux/15-plant-passport-workflow.md's "each generation creates a
 * new immutable passport version rather than overwriting the previous
 * one." Reachable from the plant's Digital Twin per that same doc, which
 * is why this lives as a tab on `/plants/[id]` rather than a standalone
 * page -- see docs/frontend/15-plant-passport.md for the full reasoning.
 * `public_url` (this plant's tokenized, unauthenticated view) is what a
 * physical QR tag or a shared link ultimately opens -- see
 * `app/(passport)/passport/[token]/page.tsx` for that side.
 */
export function PassportTab({ plantId }: { plantId: string }) {
  const query = usePlantPassportsQuery(plantId);
  const [generateOpen, setGenerateOpen] = React.useState(false);

  if (query.isLoading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 2 }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-full" />
        ))}
      </div>
    );
  }
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;

  const passports = [...(query.data ?? [])].sort((a, b) => b.version - a.version);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-end">
        <PermissionGate permission="passport:generate">
          <Button type="button" size="sm" onClick={() => setGenerateOpen(true)}>
            <Plus className="size-4" aria-hidden="true" />
            Generate passport
          </Button>
        </PermissionGate>
      </div>

      {passports.length === 0 ? (
        <EmptyState
          icon={BadgeCheck}
          title="No passport generated yet"
          description="Generate a Plant Passport to give this plant a shareable, tokenized certificate -- species, provenance, and care history, no login required to view."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {passports.map((passport, index) => (
            <PassportRow key={passport.id} passport={passport} isLatest={index === 0} />
          ))}
        </ul>
      )}

      <GeneratePassportDialog plantId={plantId} open={generateOpen} onOpenChange={setGenerateOpen} />
    </div>
  );
}

function PassportRow({ passport, isLatest }: { passport: PassportResponse; isLatest: boolean }) {
  function copyLink() {
    void navigator.clipboard.writeText(passport.public_url).then(
      () => toast.success("Public link copied"),
      () => toast.error("Couldn't copy the link -- copy it manually instead."),
    );
  }

  return (
    <li className="flex flex-col gap-2 rounded-md border border-border p-3 text-body-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-foreground">Version {passport.version}</span>
        {isLatest && <Badge tone="success">Latest</Badge>}
        {passport.token_expires_at && new Date(passport.token_expires_at) < new Date() && <Badge tone="danger">Expired</Badge>}
      </div>
      <p className="text-caption text-muted-foreground">
        Generated {new Date(passport.generated_at).toLocaleString()}
        {passport.token_expires_at && ` · Expires ${new Date(passport.token_expires_at).toLocaleString()}`}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" size="sm" onClick={copyLink}>
          <Copy className="size-4" aria-hidden="true" />
          Copy public link
        </Button>
        <Button type="button" variant="outline" size="sm" asChild>
          <a href={passport.public_url} target="_blank" rel="noreferrer">
            <ExternalLink className="size-4" aria-hidden="true" />
            View public page
          </a>
        </Button>
      </div>
    </li>
  );
}

function GeneratePassportDialog({ plantId, open, onOpenChange }: { plantId: string; open: boolean; onOpenChange: (open: boolean) => void }) {
  const mutation = useGeneratePassportMutation(plantId);
  const [expiresAt, setExpiresAt] = React.useState("");

  // Render-body "adjusting state" sync (not an Effect) -- same
  // open/closed-transition pattern `ArchivePlantDialog.syncedOpen`
  // established: this field has no async data dependency (nothing to
  // race against arriving late), so gating purely on the open/closed
  // transition is correct here, unlike `create-return-dialog.tsx`'s
  // content-signature variant.
  const [syncedOpen, setSyncedOpen] = React.useState(false);
  if (open && !syncedOpen) {
    setSyncedOpen(true);
    setExpiresAt("");
  } else if (!open && syncedOpen) {
    setSyncedOpen(false);
  }

  function onSubmit() {
    mutation.mutate(
      { expires_at: expiresAt ? new Date(expiresAt).toISOString() : null, sale_id: null, sale_item_id: null },
      { onSuccess: () => onOpenChange(false) },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Generate passport</DialogTitle>
          <DialogDescription>
            Creates a new, immutable passport version with a fresh tokenized public link. Earlier versions stay retrievable here for audit purposes.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-1.5">
          <Label htmlFor="passport-expires-at">Link expires (optional)</Label>
          <Input id="passport-expires-at" type="datetime-local" value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} />
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button type="button" disabled={mutation.isPending} aria-busy={mutation.isPending} onClick={onSubmit}>
            {mutation.isPending && <Spinner className="text-current" />}
            Generate passport
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
