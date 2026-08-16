"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Plus, UserRound } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { useCustomerContactsQuery } from "@/lib/customers/queries";
import { useAddCustomerContactMutation } from "@/lib/customers/mutations";
import { createCustomerContactSchema, type CreateCustomerContactFormValues } from "@/lib/validation/customers";

const DEFAULT_VALUES: CreateCustomerContactFormValues = { name: "", role: "", email: "", phone: "", is_primary: false };

/**
 * `GET/POST /customers/{id}/contacts` -- no delete/edit route exists
 * server-side (`customer_service.py` has `delete_contact` but no route
 * exposes it), so this tab is deliberately add-and-list only.
 */
export function ContactsTab({ customerId }: { customerId: string }) {
  const query = useCustomerContactsQuery(customerId);
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
            Add contact
          </Button>
        </PermissionGate>
      </div>

      {!query.data || query.data.length === 0 ? (
        <EmptyState icon={UserRound} title="No contacts yet" description="Add a point of contact for this customer." />
      ) : (
        <ul className="flex flex-col gap-2">
          {query.data.map((contact) => (
            <li key={contact.id} className="flex flex-col gap-1 rounded-md border border-border p-3 text-body-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-foreground">{contact.name}</span>
                {contact.is_primary && <Badge tone="info">Primary</Badge>}
                {contact.role && <span className="text-muted-foreground">{contact.role}</span>}
              </div>
              <div className="flex flex-wrap gap-x-4 text-muted-foreground">
                {contact.email && <span>{contact.email}</span>}
                {contact.phone && <span>{contact.phone}</span>}
              </div>
            </li>
          ))}
        </ul>
      )}

      <AddContactDialog customerId={customerId} open={addOpen} onOpenChange={setAddOpen} />
    </div>
  );
}

function AddContactDialog({ customerId, open, onOpenChange }: { customerId: string; open: boolean; onOpenChange: (open: boolean) => void }) {
  const mutation = useAddCustomerContactMutation(customerId);
  const form = useForm<CreateCustomerContactFormValues>({ resolver: zodResolver(createCustomerContactSchema), defaultValues: DEFAULT_VALUES });

  React.useEffect(() => {
    if (open) form.reset(DEFAULT_VALUES);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function onSubmit(values: CreateCustomerContactFormValues) {
    mutation.mutate(
      { name: values.name, role: values.role || null, email: values.email || null, phone: values.phone || null, is_primary: values.is_primary },
      { onSuccess: () => onOpenChange(false) },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Add contact</DialogTitle>
          <DialogDescription>Adds a point of contact for this customer.</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="role"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Role (optional)</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g. Procurement Manager" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid grid-cols-1 gap-4 tablet:grid-cols-2">
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Email (optional)</FormLabel>
                    <FormControl>
                      <Input type="email" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="phone"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Phone (optional)</FormLabel>
                    <FormControl>
                      <Input type="tel" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name="is_primary"
              render={({ field }) => (
                <FormItem>
                  <label className="flex items-center gap-2 text-body-sm text-foreground">
                    <Checkbox checked={field.value} onCheckedChange={(checked) => field.onChange(checked === true)} />
                    Primary contact
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
                Add contact
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
