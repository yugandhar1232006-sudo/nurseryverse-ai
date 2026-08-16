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
import { useSellStockMutation } from "@/lib/inventory/mutations";
import { sellStockSchema, type SellStockFormValues } from "@/lib/validation/inventory";

const DEFAULT_VALUES: SellStockFormValues = { quantity: "" };

/**
 * `POST /inventory/{id}/sell` -- a direct decrement for a sale with no
 * prior reservation (e.g. a walk-in cash sale rung up straight from
 * stock). `reference_sale_id`/`plant_id` are left unset here: this
 * standalone dialog has no Sales Order context to link back to -- 7J's
 * checkout flow calls the same real backend route with a real
 * `reference_sale_id` once that module exists.
 */
export function SellStockDialog({ open, onOpenChange, lineId }: { open: boolean; onOpenChange: (open: boolean) => void; lineId: string }) {
  const mutation = useSellStockMutation(lineId);
  const form = useForm<SellStockFormValues>({ resolver: zodResolver(sellStockSchema), defaultValues: DEFAULT_VALUES });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    if (open) form.reset(DEFAULT_VALUES);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function onSubmit(values: SellStockFormValues) {
    mutation.mutate(
      { quantity: Number(values.quantity), reference_sale_id: null, plant_id: null },
      { onSuccess: () => onOpenChange(false), onError: handleApiError },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Sell stock</DialogTitle>
          <DialogDescription>Directly decrements quantity for a sale with no prior reservation.</DialogDescription>
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
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={mutation.isPending}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending} aria-busy={mutation.isPending}>
                {mutation.isPending && <Spinner className="text-current" />}
                Sell stock
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
