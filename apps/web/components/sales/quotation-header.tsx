"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useBranchesQuery } from "@/lib/shell/queries";
import { useQuotationItemsQuery } from "@/lib/sales/queries";
import { useChangeQuotationStatusMutation, useConvertQuotationMutation } from "@/lib/sales/mutations";
import type { QuotationResponse, QuotationStatus } from "@/lib/api/sales";

const STATUS_TONE: Record<QuotationStatus, "neutral" | "success" | "warning" | "danger" | "info"> = {
  draft: "neutral",
  sent: "info",
  accepted: "success",
  rejected: "danger",
  expired: "warning",
  converted: "success",
};

/**
 * Quotation identity + items + status actions. `DRAFT->{SENT,REJECTED,EXPIRED}`,
 * `SENT->{ACCEPTED,REJECTED,EXPIRED,DRAFT}` -- only the legal next statuses
 * for the current state are offered, an invalid transition is still a real
 * 409 the backend itself would reject, but the UI narrows the choices to
 * avoid inviting one. `ACCEPTED->CONVERTED` only happens through "Convert
 * to sales order", never through the status selector.
 */
export function QuotationHeader({ quotation }: { quotation: QuotationResponse }) {
  const router = useRouter();
  const branchesQuery = useBranchesQuery();
  const itemsQuery = useQuotationItemsQuery(quotation.id);
  const statusMutation = useChangeQuotationStatusMutation(quotation.id);
  const convertMutation = useConvertQuotationMutation(quotation.id);
  const [nextStatus, setNextStatus] = React.useState<QuotationStatus | "">("");

  const branchName = (branchesQuery.data ?? []).find((b) => b.id === quotation.branch_id)?.name ?? "—";

  const nextStatusOptions: QuotationStatus[] =
    quotation.status === "draft"
      ? ["sent", "rejected", "expired"]
      : quotation.status === "sent"
        ? ["accepted", "rejected", "expired", "draft"]
        : [];

  function applyStatusChange() {
    if (!nextStatus) return;
    statusMutation.mutate({ status: nextStatus }, { onSuccess: () => setNextStatus("") });
  }

  function convert() {
    convertMutation.mutate(undefined, {
      onSuccess: (order) => router.push(`/sales/orders/${order.id}`),
    });
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <h1 className="text-h2 font-semibold text-foreground">Quotation</h1>
            <p className="text-body-sm text-muted-foreground">Branch: {branchName}</p>
          </div>
          <Badge tone={STATUS_TONE[quotation.status]} className="capitalize">
            {quotation.status}
          </Badge>
        </div>

        <div className="flex flex-wrap gap-x-6 gap-y-1 text-body-sm text-muted-foreground">
          <span>
            Subtotal: <span className="text-foreground">₹{Number(quotation.subtotal_amount).toFixed(2)}</span>
          </span>
          <span>
            Discount: <span className="text-foreground">₹{Number(quotation.discount_amount).toFixed(2)}</span>
          </span>
          <span>
            Tax: <span className="text-foreground">₹{Number(quotation.tax_amount).toFixed(2)}</span>
          </span>
          <span>
            Total: <span className="text-foreground">₹{Number(quotation.total_amount).toFixed(2)}</span>
          </span>
          {quotation.valid_until && <span>Valid until: {new Date(quotation.valid_until).toLocaleDateString()}</span>}
        </div>
        {quotation.note && <p className="text-body-sm text-muted-foreground">Note: {quotation.note}</p>}

        <PermissionGate permission="sales:write">
          <div className="flex flex-wrap items-center gap-2">
            {nextStatusOptions.length > 0 && (
              <>
                <Select value={nextStatus} onValueChange={(v) => setNextStatus(v as QuotationStatus)}>
                  <SelectTrigger className="w-44" aria-label="Change status to">
                    <SelectValue placeholder="Change status to…" />
                  </SelectTrigger>
                  <SelectContent>
                    {nextStatusOptions.map((opt) => (
                      <SelectItem key={opt} value={opt} className="capitalize">
                        {opt}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button type="button" size="sm" disabled={!nextStatus || statusMutation.isPending} aria-busy={statusMutation.isPending} onClick={applyStatusChange}>
                  {statusMutation.isPending && <Spinner className="text-current" />}
                  Update status
                </Button>
              </>
            )}
            {quotation.status === "accepted" && (
              <Button type="button" variant="outline" size="sm" disabled={convertMutation.isPending} aria-busy={convertMutation.isPending} onClick={convert}>
                {convertMutation.isPending && <Spinner className="text-current" />}
                Convert to sales order
              </Button>
            )}
          </div>
        </PermissionGate>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="mb-3 text-h4 font-semibold text-foreground">Line items</h2>
        {itemsQuery.isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Description</TableHead>
                <TableHead className="text-right">Qty</TableHead>
                <TableHead className="text-right">Unit price</TableHead>
                <TableHead className="text-right">Discount</TableHead>
                <TableHead className="text-right">Line total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(itemsQuery.data ?? []).map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="text-foreground">{item.description ?? "—"}</TableCell>
                  <TableCell className="text-right">{item.quantity}</TableCell>
                  <TableCell className="text-right">₹{Number(item.unit_price).toFixed(2)}</TableCell>
                  <TableCell className="text-right">₹{Number(item.discount_amount).toFixed(2)}</TableCell>
                  <TableCell className="text-right font-medium text-foreground">₹{Number(item.line_total).toFixed(2)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
