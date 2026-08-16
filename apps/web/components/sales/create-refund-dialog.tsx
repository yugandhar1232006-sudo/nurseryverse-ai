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
import { Skeleton } from "@/components/ui/skeleton";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useBranchesQuery } from "@/lib/shell/queries";
import { useProcessRefundMutation } from "@/lib/sales/mutations";
import { processRefundSchema, type ProcessRefundFormValues } from "@/lib/validation/sales";

const DEFAULT_VALUES: ProcessRefundFormValues = {
  branch_id: "",
  amount: "",
  method: "cash",
  return_id: "",
  invoice_id: "",
  sale_id: "",
  reference: "",
};

/**
 * `POST /refunds` -- `return_id`/`invoice_id`/`sale_id` are all optional,
 * independent, loosely-linking fields (no FK-enforced "exactly one"
 * requirement server-side), so this general-purpose dialog exposes all
 * three as free-text id fields rather than assuming a caller always
 * arrives from one specific linked record. No real payment-gateway
 * integration exists -- a refund is created PENDING then immediately
 * flipped to COMPLETED synchronously, no webhook wait.
 */
export function CreateRefundDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const branchesQuery = useBranchesQuery();
  const mutation = useProcessRefundMutation();

  const form = useForm<ProcessRefundFormValues>({ resolver: zodResolver(processRefundSchema), defaultValues: DEFAULT_VALUES });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    if (open) form.reset(DEFAULT_VALUES);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function onSubmit(values: ProcessRefundFormValues) {
    mutation.mutate(
      {
        branch_id: values.branch_id,
        amount: Number(values.amount),
        method: values.method,
        return_id: values.return_id || null,
        invoice_id: values.invoice_id || null,
        sale_id: values.sale_id || null,
        reference: values.reference || null,
      },
      { onSuccess: () => onOpenChange(false), onError: handleApiError },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-md overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Process refund</DialogTitle>
          <DialogDescription>Refunds are recorded and completed immediately -- there is no external payment-gateway integration.</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <FormField
              control={form.control}
              name="branch_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Branch</FormLabel>
                  {branchesQuery.isLoading ? (
                    <Skeleton className="h-9 w-full" />
                  ) : (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select a branch" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {(branchesQuery.data ?? []).map((branch) => (
                          <SelectItem key={branch.id} value={branch.id}>
                            {branch.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid grid-cols-1 gap-4 tablet:grid-cols-2">
              <FormField
                control={form.control}
                name="amount"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Amount</FormLabel>
                    <FormControl>
                      <Input inputMode="decimal" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="method"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Method</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="cash">Cash</SelectItem>
                        <SelectItem value="upi">UPI</SelectItem>
                        <SelectItem value="card">Card</SelectItem>
                        <SelectItem value="bank_transfer">Bank transfer</SelectItem>
                        <SelectItem value="other">Other</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name="sale_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Sale ID (optional)</FormLabel>
                  <FormControl>
                    <Input placeholder="Paste a sale ID to link this refund" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="invoice_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Invoice ID (optional)</FormLabel>
                  <FormControl>
                    <Input placeholder="Paste an invoice ID to link this refund" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="return_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Return ID (optional)</FormLabel>
                  <FormControl>
                    <Input placeholder="Paste a return ID to link this refund" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="reference"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Reference (optional)</FormLabel>
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
                Process refund
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
