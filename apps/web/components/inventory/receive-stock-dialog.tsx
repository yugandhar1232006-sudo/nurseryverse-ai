"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useInventoryLocationsQuery } from "@/lib/inventory/queries";
import { useReceiveStockMutation } from "@/lib/inventory/mutations";
import { receiveStockSchema, type ReceiveStockFormValues } from "@/lib/validation/inventory";

const NO_LOCATION = "__none__";
const DEFAULT_VALUES: ReceiveStockFormValues = { quantity: "", to_location_id: "", note: "" };

/** `POST /inventory/{id}/receive` (PG-50 purchase-order receipt or manual restock) -- always increments `quantity`, never decrements. */
export function ReceiveStockDialog({
  open,
  onOpenChange,
  lineId,
  branchId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  lineId: string;
  branchId: string;
}) {
  const locationsQuery = useInventoryLocationsQuery(branchId);
  const mutation = useReceiveStockMutation(lineId);

  const form = useForm<ReceiveStockFormValues>({ resolver: zodResolver(receiveStockSchema), defaultValues: DEFAULT_VALUES });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    if (open) form.reset(DEFAULT_VALUES);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function onSubmit(values: ReceiveStockFormValues) {
    mutation.mutate(
      {
        quantity: Number(values.quantity),
        to_location_id: values.to_location_id && values.to_location_id !== NO_LOCATION ? values.to_location_id : null,
        reference_purchase_order_id: null,
        note: values.note || null,
      },
      { onSuccess: () => onOpenChange(false), onError: handleApiError },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Receive stock</DialogTitle>
          <DialogDescription>Increases this line&apos;s on-hand quantity.</DialogDescription>
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
              name="to_location_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Location (optional)</FormLabel>
                  <Select value={field.value || NO_LOCATION} onValueChange={(v) => field.onChange(v === NO_LOCATION ? "" : v)}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Keep current location" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value={NO_LOCATION}>Keep current location</SelectItem>
                      {(locationsQuery.data ?? []).map((location) => (
                        <SelectItem key={location.id} value={location.id}>
                          {location.name}
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
                Receive stock
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
