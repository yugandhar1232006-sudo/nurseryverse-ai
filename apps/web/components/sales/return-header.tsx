"use client";

import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useBranchesQuery } from "@/lib/shell/queries";
import { useReturnItemsQuery } from "@/lib/sales/queries";
import { useApproveReturnMutation, useCompleteReturnMutation, useRejectReturnMutation } from "@/lib/sales/mutations";
import type { ReturnResponse, ReturnStatus } from "@/lib/api/sales";

const STATUS_TONE: Record<ReturnStatus, "neutral" | "success" | "warning" | "danger" | "info"> = {
  requested: "warning",
  approved: "info",
  rejected: "danger",
  completed: "success",
};

/**
 * Return identity + items + the real `REQUESTED->{APPROVED,REJECTED}`,
 * `APPROVED->COMPLETED` lifecycle. Completing a return is `sales:void`-gated
 * (heavier than `sales:write`, used for approve/reject) since it's the
 * inventory-restocking, irreversible step -- see `sales.py`'s route
 * declarations.
 */
export function ReturnHeader({ ret }: { ret: ReturnResponse }) {
  const branchesQuery = useBranchesQuery();
  const itemsQuery = useReturnItemsQuery(ret.id);
  const approveMutation = useApproveReturnMutation(ret.id);
  const rejectMutation = useRejectReturnMutation(ret.id);
  const completeMutation = useCompleteReturnMutation(ret.id);
  const [rejectOpen, setRejectOpen] = React.useState(false);
  const [rejectReason, setRejectReason] = React.useState("");

  const branchName = (branchesQuery.data ?? []).find((b) => b.id === ret.branch_id)?.name ?? "—";

  function confirmReject() {
    rejectMutation.mutate({ reason: rejectReason || null }, { onSuccess: () => setRejectOpen(false) });
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <h1 className="text-h2 font-semibold text-foreground">Return</h1>
            <p className="text-body-sm text-muted-foreground">Branch: {branchName}</p>
          </div>
          <Badge tone={STATUS_TONE[ret.status]} className="capitalize">
            {ret.status}
          </Badge>
        </div>
        {ret.reason && <p className="text-body-sm text-muted-foreground">Reason: {ret.reason}</p>}
        <p className="text-caption text-muted-foreground">Requested {new Date(ret.created_at).toLocaleString()}</p>

        {ret.status === "requested" && (
          <PermissionGate permission="sales:write">
            <div className="flex flex-wrap gap-2">
              <Button type="button" size="sm" disabled={approveMutation.isPending} aria-busy={approveMutation.isPending} onClick={() => approveMutation.mutate()}>
                {approveMutation.isPending && <Spinner className="text-current" />}
                Approve
              </Button>
              <Button type="button" variant="outline" size="sm" className="text-destructive hover:text-destructive" onClick={() => setRejectOpen(true)}>
                Reject
              </Button>
            </div>
          </PermissionGate>
        )}
        {ret.status === "approved" && (
          <PermissionGate permission="sales:void">
            <div>
              <Button type="button" size="sm" disabled={completeMutation.isPending} aria-busy={completeMutation.isPending} onClick={() => completeMutation.mutate()}>
                {completeMutation.isPending && <Spinner className="text-current" />}
                Complete return
              </Button>
            </div>
          </PermissionGate>
        )}
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="mb-3 text-h4 font-semibold text-foreground">Line items</h2>
        {itemsQuery.isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-right">Qty</TableHead>
                <TableHead>Restock</TableHead>
                <TableHead>Condition</TableHead>
                <TableHead className="text-right">Refund amount</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(itemsQuery.data ?? []).map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="text-right">{item.quantity}</TableCell>
                  <TableCell className="text-muted-foreground">{item.restock ? "Yes" : "No"}</TableCell>
                  <TableCell className="capitalize text-muted-foreground">{item.condition}</TableCell>
                  <TableCell className="text-right font-medium text-foreground">₹{Number(item.line_refund_amount).toFixed(2)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Reject return</DialogTitle>
            <DialogDescription>Rejecting a return is final for this request.</DialogDescription>
          </DialogHeader>
          <Textarea placeholder="Reason (optional)" value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} rows={3} />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setRejectOpen(false)} disabled={rejectMutation.isPending}>
              Keep pending
            </Button>
            <Button
              type="button"
              variant="outline"
              className="text-destructive hover:text-destructive"
              disabled={rejectMutation.isPending}
              aria-busy={rejectMutation.isPending}
              onClick={confirmReject}
            >
              {rejectMutation.isPending && <Spinner className="text-current" />}
              Reject return
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
