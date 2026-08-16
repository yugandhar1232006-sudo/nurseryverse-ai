"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useReserveStockMutation } from "@/lib/inventory/mutations";
import { reserveStockSchema, type ReserveStockFormValues } from "@/lib/validation/inventory";

const DEFAULT_VALUES: ReserveStockFormValues = { quantity: "", reference_type: "", note: "" };

/** `POST /inventory/{id}/reserve` -- holds quantity without decrementing `quantity`, only `reserved_quantity`; a real 409 if there isn't enough available (see `InsufficientStockError`'s docstring). */
export function ReserveStockDialog({ open, onOpenChange, lineId }: { open: boolean; onOpenChange: (open: boolean) => void; lineId: string }) {
  const mutation = useReserveStockMutation(lineId);
  const form = useForm<ReserveStockFormValues>({ resolver: zodResolver(reserveStockSchema), defaultValues: DEFAULT_VALUES });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    if (open) form.reset(DEFAULT_VALUES);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function onSubmit(values: ReserveStockFormValues) {
    mutation.mutate(
      {
        quantity: Number(values.quantity),
        reference_type: values.reference_type || null,
        reference_id: null,
        expires_at: null,
        note: values.note || null,
      },
      { onSuccess: () => onOpenChange(false), onError: handleApiError },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Reserve stock</DialogTitle>
          <DialogDescription>Holds quantity for a pending sale or order without removing it from the count.</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <FormField
              control={form.control}
              name="quantity"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Quantity</FormLabel>
                  <FormControl>
                    <Input inputMode="numeric" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="reference_type"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Reference type (optional)</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g. sales_order" {...field} />
                  </FormControl>
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
                Reserve stock
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
