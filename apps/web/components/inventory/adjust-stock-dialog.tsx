"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage, FormDescription } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useAdjustStockMutation } from "@/lib/inventory/mutations";
import { adjustStockSchema, type AdjustStockFormValues } from "@/lib/validation/inventory";
import type { InventoryAdjustmentReason } from "@/lib/api/inventory";

const DEFAULT_VALUES: AdjustStockFormValues = { quantity_delta: "", reason: "correction", note: "" };

const REASON_OPTIONS: { value: InventoryAdjustmentReason; label: string }[] = [
  { value: "correction", label: "Count correction" },
  { value: "internal_use", label: "Internal use" },
  { value: "damage", label: "Damage" },
  { value: "purchase_order_receipt", label: "Purchase order receipt" },
  { value: "sale", label: "Sale" },
  { value: "return", label: "Return" },
  { value: "other", label: "Other" },
];

/** `POST /inventory/{id}/adjust` -- `inventory:adjust`-gated (correcting the count, not a normal operational flow). Signed delta; a negative delta below zero comes back as a real 409. */
export function AdjustStockDialog({ open, onOpenChange, lineId }: { open: boolean; onOpenChange: (open: boolean) => void; lineId: string }) {
  const mutation = useAdjustStockMutation(lineId);
  const form = useForm<AdjustStockFormValues>({ resolver: zodResolver(adjustStockSchema), defaultValues: DEFAULT_VALUES });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    if (open) form.reset(DEFAULT_VALUES);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function onSubmit(values: AdjustStockFormValues) {
    mutation.mutate(
      { quantity_delta: Number(values.quantity_delta), reason: values.reason, note: values.note || null },
      { onSuccess: () => onOpenChange(false), onError: handleApiError },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Adjust stock</DialogTitle>
          <DialogDescription>Manually correct the quantity (stocktake, count error, etc.) -- requires a reason.</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <FormField
              control={form.control}
              name="quantity_delta"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Change</FormLabel>
                  <FormControl>
                    <Input inputMode="numeric" placeholder="e.g. 5 or -3" {...field} />
                  </FormControl>
                  <FormDescription>Positive adds stock, negative removes it.</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="reason"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Reason</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {REASON_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="note"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Note (optional)</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={mutation.isPending}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending} aria-busy={mutation.isPending}>
                {mutation.isPending && <Spinner className="text-current" />}
                Adjust stock
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
