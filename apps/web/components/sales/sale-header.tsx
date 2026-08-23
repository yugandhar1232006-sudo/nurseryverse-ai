"use client";

import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CreateReturnDialog } from "@/components/sales/create-return-dialog";
import { useBranchesQuery } from "@/lib/shell/queries";
import { useSaleItemsQuery } from "@/lib/sales/queries";
import type { SaleResponse } from "@/lib/api/sales";

/** Completed Sale identity + items + "Request return" -- the entry point into 7J's Return workflow. */
export function SaleHeader({ sale }: { sale: SaleResponse }) {
  const branchesQuery = useBranchesQuery();
  const itemsQuery = useSaleItemsQuery(sale.id);
  const [returnOpen, setReturnOpen] = React.useState(false);

  const branchName = (branchesQuery.data ?? []).find((b) => b.id === sale.branch_id)?.name ?? "—";

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <h1 className="text-h2 font-semibold text-foreground">Sale</h1>
            <p className="text-body-sm text-muted-foreground">Branch: {branchName}</p>
          </div>
          <Badge tone={sale.status === "voided" ? "danger" : "success"} className="capitalize">
            {sale.status}
          </Badge>
        </div>

        <div className="flex flex-wrap gap-x-6 gap-y-1 text-body-sm text-muted-foreground">
          <span>
            Subtotal: <span className="text-foreground">₹{Number(sale.subtotal_amount).toFixed(2)}</span>
          </span>
          <span>
            Discount: <span className="text-foreground">₹{Number(sale.discount_amount).toFixed(2)}</span>
          </span>
          <span>
            Tax: <span className="text-foreground">₹{Number(sale.tax_amount).toFixed(2)}</span>
          </span>
          <span>
            Total: <span className="text-foreground">₹{Number(sale.total_amount).toFixed(2)}</span>
          </span>
          {sale.payment_method && <span>Payment method: {sale.payment_method}</span>}
          <span>{new Date(sale.created_at).toLocaleString()}</span>
        </div>

        {sale.status === "completed" && (
          <PermissionGate permission="sales:write">
            <div>
              <Button type="button" variant="outline" size="sm" onClick={() => setReturnOpen(true)}>
                Request return
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
                <TableHead className="text-right">Line total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(itemsQuery.data ?? []).map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="text-right">{item.quantity}</TableCell>
                  <TableCell className="text-right">₹{Number(item.unit_price).toFixed(2)}</TableCell>
                  <TableCell className="text-right font-medium text-foreground">₹{Number(item.line_total).toFixed(2)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      <CreateReturnDialog saleId={sale.id} customerId={sale.customer_id} open={returnOpen} onOpenChange={setReturnOpen} />
    </div>
  );
}
