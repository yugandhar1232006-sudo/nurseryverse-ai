"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useDisposeStockMutation } from "@/lib/inventory/mutations";
import { disposeStockSchema, type DisposeStockFormValues } from "@/lib/validation/inventory";

const DEFAULT_VALUES: DisposeStockFormValues = { quantity: "", from_damaged: false, note: "" };

/** `POST /inventory/{id}/dispose` -- Waste, a permanent removal (`disposed_quantity` increments, `quantity` decrements). `from_damaged` draws the disposed quantity out of already-damaged stock rather than fresh on-hand stock. */
export function DisposeStockDialog({ open, onOpenChange, lineId }: { open: boolean; onOpenChange: (open: boolean) => void; lineId: string }) {
  const mutation = useDisposeStockMutation(lineId);
  const form = useForm<DisposeStockFormValues>({ resolver: zodResolver(disposeStockSchema), defaultValues: DEFAULT_VALUES });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    if (open) form.reset(DEFAULT_VALUES);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function onSubmit(values: DisposeStockFormValues) {
    mutation.mutate(
      { quantity: Number(values.quantity), from_damaged: values.from_damaged, plant_id: null, note: values.note || null },
      { onSuccess: () => onOpenChange(false), onError: handleApiError },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Dispose stock</DialogTitle>
          <DialogDescription>Permanently removes quantity as waste. This cannot be undone.</DialogDescription>
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
              name="from_damaged"
              render={({ field }) => (
                <label className="flex items-center gap-2 text-body-sm text-foreground">
                  <Checkbox checked={field.value} onCheckedChange={(checked) => field.onChange(checked === true)} />
                  Dispose from already-damaged stock
                </label>
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
              <Button type="submit" variant="destructive" disabled={mutation.isPending} aria-busy={mutation.isPending}>
                {mutation.isPending && <Spinner className="text-current" />}
                Dispose stock
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
