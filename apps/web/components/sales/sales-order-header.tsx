"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useBranchesQuery } from "@/lib/shell/queries";
import { useSalesOrderItemsQuery } from "@/lib/sales/queries";
import { useCancelSalesOrderMutation, useCheckoutSalesOrderMutation, useConfirmSalesOrderMutation } from "@/lib/sales/mutations";
import type { SalesOrderResponse, SalesOrderStatus } from "@/lib/api/sales";

const STATUS_TONE: Record<SalesOrderStatus, "neutral" | "success" | "warning" | "danger" | "info"> = {
  draft: "neutral",
  confirmed: "info",
  processing: "warning",
  fulfilled: "success",
  cancelled: "danger",
};

/**
 * Sales Order identity + items + the real DRAFT->CONFIRMED->PROCESSING->FULFILLED
 * (or ->CANCELLED) lifecycle actions. A real `insufficient_stock` 409 is
 * possible on Confirm or Checkout -- surfaced via `toast.apiError` by the
 * underlying mutations, same discriminated-context `ConflictError` 7I's
 * dialogs already handle.
 */
export function SalesOrderHeader({ order }: { order: SalesOrderResponse }) {
  const router = useRouter();
  const branchesQuery = useBranchesQuery();
  const itemsQuery = useSalesOrderItemsQuery(order.id);
  const confirmMutation = useConfirmSalesOrderMutation(order.id);
  const cancelMutation = useCancelSalesOrderMutation(order.id);
  const checkoutMutation = useCheckoutSalesOrderMutation(order.id);
  const [cancelOpen, setCancelOpen] = React.useState(false);
  const [cancelReason, setCancelReason] = React.useState("");

  const branchName = (branchesQuery.data ?? []).find((b) => b.id === order.branch_id)?.name ?? "—";
  const isTerminal = order.order_status === "fulfilled" || order.order_status === "cancelled";

  function checkout() {
    checkoutMutation.mutate(undefined, {
      onSuccess: (updated) => {
        if (updated.sale_id) router.push(`/sales/${updated.sale_id}`);
      },
    });
  }

  function confirmCancel() {
    cancelMutation.mutate({ reason: cancelReason || null }, { onSuccess: () => setCancelOpen(false) });
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <h1 className="text-h2 font-semibold text-foreground">Sales Order</h1>
            <p className="text-body-sm text-muted-foreground">Branch: {branchName}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge tone={STATUS_TONE[order.order_status]} className="capitalize">
              {order.order_status}
            </Badge>
            <Badge tone="neutral" className="capitalize">
              {order.payment_status.replace("_", " ")}
            </Badge>
          </div>
        </div>

        <div className="flex flex-wrap gap-x-6 gap-y-1 text-body-sm text-muted-foreground">
          <span>
            Total: <span className="text-foreground">${Number(order.total_amount).toFixed(2)}</span>
          </span>
          {order.confirmed_at && <span>Confirmed: {new Date(order.confirmed_at).toLocaleString()}</span>}
          {order.fulfilled_at && <span>Fulfilled: {new Date(order.fulfilled_at).toLocaleString()}</span>}
          {order.cancelled_at && <span>Cancelled: {new Date(order.cancelled_at).toLocaleString()}</span>}
        </div>
        {order.cancel_reason && <p className="text-body-sm text-muted-foreground">Cancel reason: {order.cancel_reason}</p>}

        {!isTerminal && (
          <PermissionGate permission="sales:write">
            <div className="flex flex-wrap gap-2">
              {order.order_status === "draft" && (
                <Button type="button" size="sm" disabled={confirmMutation.isPending} aria-busy={confirmMutation.isPending} onClick={() => confirmMutation.mutate()}>
                  {confirmMutation.isPending && <Spinner className="text-current" />}
                  Confirm
                </Button>
              )}
              {!order.sale_id && (
                <Button type="button" size="sm" disabled={checkoutMutation.isPending} aria-busy={checkoutMutation.isPending} onClick={checkout}>
                  {checkoutMutation.isPending && <Spinner className="text-current" />}
                  Checkout
                </Button>
              )}
              <Button type="button" variant="outline" size="sm" className="text-destructive hover:text-destructive" onClick={() => setCancelOpen(true)}>
                Cancel order
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
                <TableHead className="text-right">Unit price</TableHead>
                <TableHead className="text-right">Tax</TableHead>
                <TableHead className="text-right">Line total</TableHead>
                <TableHead>Reserved</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(itemsQuery.data ?? []).map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="text-right">{item.quantity}</TableCell>
                  <TableCell className="text-right">${Number(item.unit_price).toFixed(2)}</TableCell>
                  <TableCell className="text-right">${Number(item.tax_amount).toFixed(2)}</TableCell>
                  <TableCell className="text-right font-medium text-foreground">${Number(item.line_total).toFixed(2)}</TableCell>
                  <TableCell className="text-muted-foreground">{item.reservation_id ? "Yes" : "No"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      <Dialog open={cancelOpen} onOpenChange={setCancelOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Cancel order</DialogTitle>
            <DialogDescription>Releases any reserved stock. This cannot be undone.</DialogDescription>
          </DialogHeader>
          <Textarea placeholder="Reason (optional)" value={cancelReason} onChange={(e) => setCancelReason(e.target.value)} rows={3} />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setCancelOpen(false)} disabled={cancelMutation.isPending}>
              Keep order
            </Button>
            <Button type="button" variant="outline" className="text-destructive hover:text-destructive" disabled={cancelMutation.isPending} aria-busy={cancelMutation.isPending} onClick={confirmCancel}>
              {cancelMutation.isPending && <Spinner className="text-current" />}
              Cancel order
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
