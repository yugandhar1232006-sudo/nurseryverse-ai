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
import { useBranchesQuery } from "@/lib/shell/queries";
import { useInventoryLocationsQuery } from "@/lib/inventory/queries";
import { useTransferStockMutation } from "@/lib/inventory/mutations";
import { transferStockSchema, type TransferStockFormValues } from "@/lib/validation/inventory";

const SAME_BRANCH = "__same__";
const NO_LOCATION = "__none__";
const DEFAULT_VALUES: TransferStockFormValues = { quantity: "", to_location_id: "", to_branch_id: "", note: "" };

/**
 * `POST /inventory/{id}/transfer` -- either a same-branch location move or
 * a cross-branch transfer. A cross-branch transfer needs `inventory:write`
 * on the destination branch too (see lib/api/inventory.ts's docstring); a
 * 403 surfaces as a toast, and the dialog stays open so the caller can
 * pick a different destination.
 */
export function TransferStockDialog({
  open,
  onOpenChange,
  lineId,
  currentBranchId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  lineId: string;
  currentBranchId: string;
}) {
  const branchesQuery = useBranchesQuery();
  const mutation = useTransferStockMutation(lineId);

  const form = useForm<TransferStockFormValues>({ resolver: zodResolver(transferStockSchema), defaultValues: DEFAULT_VALUES });
  const handleApiError = useApiFormErrors(form.setError);
  const toBranchId = form.watch("to_branch_id");

  const locationsQuery = useInventoryLocationsQuery(toBranchId || currentBranchId);

  React.useEffect(() => {
    if (open) form.reset(DEFAULT_VALUES);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function onSubmit(values: TransferStockFormValues) {
    mutation.mutate(
      {
        quantity: Number(values.quantity),
        to_location_id: values.to_location_id && values.to_location_id !== NO_LOCATION ? values.to_location_id : null,
        to_branch_id: values.to_branch_id && values.to_branch_id !== SAME_BRANCH ? values.to_branch_id : null,
        note: values.note || null,
      },
      { onSuccess: () => onOpenChange(false), onError: handleApiError },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Transfer stock</DialogTitle>
          <DialogDescription>Move quantity to a different location and/or branch.</DialogDescription>
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
              name="to_branch_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Destination branch (optional)</FormLabel>
                  <Select
                    value={field.value || SAME_BRANCH}
                    onValueChange={(v) => {
                      field.onChange(v === SAME_BRANCH ? "" : v);
                      form.setValue("to_location_id", "");
                    }}
                  >
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Keep current branch" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value={SAME_BRANCH}>Keep current branch</SelectItem>
                      {(branchesQuery.data ?? [])
                        .filter((b) => b.id !== currentBranchId)
                        .map((branch) => (
                          <SelectItem key={branch.id} value={branch.id}>
                            {branch.name}
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
              name="to_location_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Destination location (optional)</FormLabel>
                  <Select value={field.value || NO_LOCATION} onValueChange={(v) => field.onChange(v === NO_LOCATION ? "" : v)}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="No specific location" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value={NO_LOCATION}>No specific location</SelectItem>
                      {(locationsQuery.data ?? []).map((location) => (
                        <SelectItem key={location.id} value={location.id}>
                          {location.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormDescription>Specify a destination branch, a location, or both.</FormDescription>
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
                Transfer stock
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
