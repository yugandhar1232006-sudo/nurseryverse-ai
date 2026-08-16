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
import { LineItemsFieldArray } from "@/components/sales/line-items-field-array";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useBranchesQuery } from "@/lib/shell/queries";
import { useCustomerListQuery } from "@/lib/customers/queries";
import { useCreateSalesOrderMutation } from "@/lib/sales/mutations";
import { createSalesOrderSchema, type CreateSalesOrderFormValues } from "@/lib/validation/sales";

const DEFAULT_VALUES: CreateSalesOrderFormValues = { branch_id: "", customer_id: "", items: [], tax_rate: "", header_discount: "" };

/**
 * A "walk-up" Sales Order -- created directly, not necessarily from a
 * Quotation (the other creation path is `QuotationHeader`'s "Convert to
 * sales order" action). Both paths land on the same `SalesOrderResponse`.
 */
export function CreateSalesOrderDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const branchesQuery = useBranchesQuery();
  const mutation = useCreateSalesOrderMutation();

  const form = useForm<CreateSalesOrderFormValues>({ resolver: zodResolver(createSalesOrderSchema), defaultValues: DEFAULT_VALUES });
  const handleApiError = useApiFormErrors(form.setError);
  const branchId = form.watch("branch_id");
  const customersQuery = useCustomerListQuery({ branch_id: branchId || undefined, page: 1, page_size: 100 });

  React.useEffect(() => {
    if (open) form.reset(DEFAULT_VALUES);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function onSubmit(values: CreateSalesOrderFormValues) {
    mutation.mutate(
      {
        branch_id: values.branch_id,
        customer_id: values.customer_id,
        items: values.items.map((item) => ({
          inventory_id: item.inventory_id,
          description: item.description || null,
          quantity: Number(item.quantity),
          unit_price: Number(item.unit_price),
          discount_amount: item.discount_amount === "" ? 0 : Number(item.discount_amount),
        })),
        tax_rate: values.tax_rate === "" ? 0 : Number(values.tax_rate),
        header_discount: values.header_discount === "" ? 0 : Number(values.header_discount),
        idempotency_key: null,
      },
      { onSuccess: () => onOpenChange(false), onError: handleApiError },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>New sales order</DialogTitle>
          <DialogDescription>Creates a sales order directly -- confirm it to reserve stock, then check it out to complete the sale.</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <div className="grid grid-cols-1 gap-4 tablet:grid-cols-2">
              <FormField
                control={form.control}
                name="branch_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Branch</FormLabel>
                    {branchesQuery.isLoading ? (
                      <Skeleton className="h-9 w-full" />
                    ) : (
                      <Select
                        value={field.value}
                        onValueChange={(value) => {
                          field.onChange(value);
                          form.setValue("customer_id", "");
                          form.setValue("items", []);
                        }}
                      >
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
              <FormField
                control={form.control}
                name="customer_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Customer</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange} disabled={!branchId}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder={branchId ? "Select a customer" : "Select a branch first"} />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {(customersQuery.data?.items ?? []).map((customer) => (
                          <SelectItem key={customer.id} value={customer.id}>
                            {customer.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <LineItemsFieldArray control={form.control} branchId={branchId} name="items" />

            <div className="grid grid-cols-1 gap-4 tablet:grid-cols-2">
              <FormField
                control={form.control}
                name="tax_rate"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Tax rate (optional)</FormLabel>
                    <FormControl>
                      <Input inputMode="decimal" placeholder="e.g. 0.08" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="header_discount"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Header discount (optional)</FormLabel>
                    <FormControl>
                      <Input inputMode="decimal" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={mutation.isPending}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending} aria-busy={mutation.isPending}>
                {mutation.isPending && <Spinner className="text-current" />}
                Create sales order
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
