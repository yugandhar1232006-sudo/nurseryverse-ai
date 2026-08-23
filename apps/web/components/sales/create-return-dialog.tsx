"use client";

import * as React from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/lib/toast";
import { useSaleItemsQuery } from "@/lib/sales/queries";
import { useCreateReturnMutation } from "@/lib/sales/mutations";
import type { ReturnItemCondition } from "@/lib/api/sales";

interface RowState {
  included: boolean;
  quantity: string;
  restock: boolean;
  condition: ReturnItemCondition;
}

/**
 * Return line items are bounded to the completed Sale's own items (a
 * return can't invent a new line), so this dialog manages selection state
 * directly rather than a freely-repeatable `useFieldArray` -- each sale
 * item gets one checkbox row to include/exclude, not an add/remove list.
 */
export function CreateReturnDialog({
  saleId,
  customerId,
  open,
  onOpenChange,
}: {
  saleId: string;
  customerId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const itemsQuery = useSaleItemsQuery(saleId);
  const mutation = useCreateReturnMutation(saleId);
  const [reason, setReason] = React.useState("");
  const [rows, setRows] = React.useState<Record<string, RowState>>({});

  // Render-body "adjusting state" sync (not an Effect) -- same pattern
  // 7I's `locations-panel.tsx` uses, and for the same reason: gating
  // purely on "did `open` just flip true" would miss the case where
  // `itemsQuery.data` arrives *after* the dialog has already opened (a
  // real bug that pattern had before it was fixed there), so this also
  // re-syncs whenever the open dialog's item set changes shape.
  const itemsKey = open ? (itemsQuery.data ?? []).map((item) => item.id).join(",") : "";
  const [syncedKey, setSyncedKey] = React.useState<string | null>(null);
  if (open && itemsKey !== "" && syncedKey !== itemsKey) {
    setSyncedKey(itemsKey);
    setReason("");
    const initial: Record<string, RowState> = {};
    for (const item of itemsQuery.data ?? []) {
      initial[item.id] = { included: false, quantity: String(item.quantity), restock: true, condition: "resalable" };
    }
    setRows(initial);
  } else if (!open && syncedKey !== null) {
    setSyncedKey(null);
  }

  function updateRow(itemId: string, patch: Partial<RowState>) {
    setRows((prev) => ({ ...prev, [itemId]: { ...prev[itemId], ...patch } }));
  }

  function onSubmit() {
    if (!customerId) {
      toast.error("This sale has no linked customer, so a return can't be filed against it.");
      return;
    }
    const items = Object.entries(rows)
      .filter(([, row]) => row.included)
      .map(([saleItemId, row]) => ({
        sale_item_id: saleItemId,
        quantity: Number(row.quantity),
        restock: row.restock,
        condition: row.condition,
      }));
    if (items.length === 0) {
      toast.error("Select at least one line item to return.");
      return;
    }
    mutation.mutate({ customer_id: customerId, reason: reason || null, items }, { onSuccess: () => onOpenChange(false) });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Request return</DialogTitle>
          <DialogDescription>Select which line items are being returned, then submit for approval.</DialogDescription>
        </DialogHeader>

        {itemsQuery.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : (
          <div className="flex flex-col gap-3">
            {(itemsQuery.data ?? []).map((item) => {
              const row = rows[item.id];
              if (!row) return null;
              return (
                <div key={item.id} className="grid grid-cols-1 gap-2 rounded-md border border-border p-3 tablet:grid-cols-[auto_1fr_1fr_auto_1fr] tablet:items-center">
                  <Checkbox checked={row.included} onCheckedChange={(checked) => updateRow(item.id, { included: checked === true })} aria-label={`Include line ${item.id}`} />
                  <span className="text-body-sm text-foreground">
                    {item.quantity} × ₹{Number(item.unit_price).toFixed(2)}
                  </span>
                  <Input
                    inputMode="numeric"
                    aria-label="Return quantity"
                    value={row.quantity}
                    disabled={!row.included}
                    onChange={(e) => updateRow(item.id, { quantity: e.target.value })}
                  />
                  <label className="flex items-center gap-2 text-body-sm text-foreground">
                    <Checkbox checked={row.restock} disabled={!row.included} onCheckedChange={(checked) => updateRow(item.id, { restock: checked === true })} />
                    Restock
                  </label>
                  <Select value={row.condition} onValueChange={(v) => updateRow(item.id, { condition: v as ReturnItemCondition })}>
                    <SelectTrigger className="w-full" aria-label="Item condition" disabled={!row.included}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="resalable">Resalable</SelectItem>
                      <SelectItem value="damaged">Damaged</SelectItem>
                      <SelectItem value="disposed">Disposed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              );
            })}
          </div>
        )}

        <Textarea placeholder="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} rows={2} />

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button type="button" disabled={mutation.isPending} aria-busy={mutation.isPending} onClick={onSubmit}>
            {mutation.isPending && <Spinner className="text-current" />}
            Request return
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
