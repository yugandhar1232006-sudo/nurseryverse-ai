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
import { useMarkDamagedMutation } from "@/lib/inventory/mutations";
import { markDamagedSchema, type MarkDamagedFormValues } from "@/lib/validation/inventory";

const DEFAULT_VALUES: MarkDamagedFormValues = { quantity: "", note: "" };

/** `POST /inventory/{id}/damage` -- moves quantity into `damaged_quantity`; still on hand (`quantity` unchanged) but no longer sellable/available. */
export function MarkDamagedDialog({ open, onOpenChange, lineId }: { open: boolean; onOpenChange: (open: boolean) => void; lineId: string }) {
  const mutation = useMarkDamagedMutation(lineId);
  const form = useForm<MarkDamagedFormValues>({ resolver: zodResolver(markDamagedSchema), defaultValues: DEFAULT_VALUES });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    if (open) form.reset(DEFAULT_VALUES);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function onSubmit(values: MarkDamagedFormValues) {
    mutation.mutate({ quantity: Number(values.quantity), note: values.note || null }, { onSuccess: () => onOpenChange(false), onError: handleApiError });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Mark stock as damaged</DialogTitle>
          <DialogDescription>Removes quantity from sellable availability without disposing of it.</DialogDescription>
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
                Mark damaged
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
