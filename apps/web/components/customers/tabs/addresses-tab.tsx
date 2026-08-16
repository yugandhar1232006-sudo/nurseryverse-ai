"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { MapPin, Plus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { useCustomerAddressesQuery } from "@/lib/customers/queries";
import { useAddCustomerAddressMutation } from "@/lib/customers/mutations";
import { createCustomerAddressSchema, type CreateCustomerAddressFormValues } from "@/lib/validation/customers";

const DEFAULT_VALUES: CreateCustomerAddressFormValues = {
  address_type: "other",
  line1: "",
  line2: "",
  city: "",
  state: "",
  postal_code: "",
  country: "",
  is_default: false,
};

/** `GET/POST /customers/{id}/addresses` -- add-and-list only, same server-side constraint as `ContactsTab`. */
export function AddressesTab({ customerId }: { customerId: string }) {
  const query = useCustomerAddressesQuery(customerId);
  const [addOpen, setAddOpen] = React.useState(false);

  if (query.isLoading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 2 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    );
  }
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <PermissionGate permission="customers:write">
          <Button type="button" size="sm" onClick={() => setAddOpen(true)}>
            <Plus className="size-4" aria-hidden="true" />
            Add address
          </Button>
        </PermissionGate>
      </div>

      {!query.data || query.data.length === 0 ? (
        <EmptyState icon={MapPin} title="No addresses yet" description="Add a billing or shipping address for this customer." />
      ) : (
        <ul className="flex flex-col gap-2">
          {query.data.map((address) => (
            <li key={address.id} className="flex flex-col gap-1 rounded-md border border-border p-3 text-body-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="neutral" className="capitalize">
                  {address.address_type}
                </Badge>
                {address.is_default && <Badge tone="info">Default</Badge>}
              </div>
              <p className="text-foreground">
                {address.line1}
                {address.line2 ? `, ${address.line2}` : ""}
              </p>
              <p className="text-muted-foreground">
                {[address.city, address.state, address.postal_code, address.country].filter(Boolean).join(", ") || "—"}
              </p>
            </li>
          ))}
        </ul>
      )}

      <AddAddressDialog customerId={customerId} open={addOpen} onOpenChange={setAddOpen} />
    </div>
  );
}

function AddAddressDialog({ customerId, open, onOpenChange }: { customerId: string; open: boolean; onOpenChange: (open: boolean) => void }) {
  const mutation = useAddCustomerAddressMutation(customerId);
  const form = useForm<CreateCustomerAddressFormValues>({ resolver: zodResolver(createCustomerAddressSchema), defaultValues: DEFAULT_VALUES });

  React.useEffect(() => {
    if (open) form.reset(DEFAULT_VALUES);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function onSubmit(values: CreateCustomerAddressFormValues) {
    mutation.mutate(
      {
        address_type: values.address_type,
        line1: values.line1,
        line2: values.line2 || null,
        city: values.city || null,
        state: values.state || null,
        postal_code: values.postal_code || null,
        country: values.country || null,
        is_default: values.is_default,
      },
      { onSuccess: () => onOpenChange(false) },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-md overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Add address</DialogTitle>
          <DialogDescription>Adds a billing or shipping address for this customer.</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <FormField
              control={form.control}
              name="address_type"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Type</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="billing">Billing</SelectItem>
                      <SelectItem value="shipping">Shipping</SelectItem>
                      <SelectItem value="other">Other</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="line1"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Address line 1</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="line2"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Address line 2 (optional)</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid grid-cols-1 gap-4 tablet:grid-cols-2">
              <FormField
                control={form.control}
                name="city"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>City (optional)</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="state"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>State (optional)</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <div className="grid grid-cols-1 gap-4 tablet:grid-cols-2">
              <FormField
                control={form.control}
                name="postal_code"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Postal code (optional)</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="country"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Country (optional)</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name="is_default"
              render={({ field }) => (
                <FormItem>
                  <label className="flex items-center gap-2 text-body-sm text-foreground">
                    <Checkbox checked={field.value} onCheckedChange={(checked) => field.onChange(checked === true)} />
                    Default address
                  </label>
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
                Add address
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
