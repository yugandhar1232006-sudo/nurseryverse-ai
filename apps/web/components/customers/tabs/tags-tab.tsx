"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Tag, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Form, FormControl, FormField, FormItem, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { useCustomerTagsQuery } from "@/lib/customers/queries";
import { useAddCustomerTagMutation, useRemoveCustomerTagMutation } from "@/lib/customers/mutations";
import { addCustomerTagSchema, type AddCustomerTagFormValues } from "@/lib/validation/customers";

const DEFAULT_VALUES: AddCustomerTagFormValues = { tag: "" };

/** `GET/POST/DELETE /customers/{id}/tags` -- the one CRM sub-resource with a real delete route. */
export function TagsTab({ customerId }: { customerId: string }) {
  const query = useCustomerTagsQuery(customerId);
  const addMutation = useAddCustomerTagMutation(customerId);
  const removeMutation = useRemoveCustomerTagMutation(customerId);
  const form = useForm<AddCustomerTagFormValues>({ resolver: zodResolver(addCustomerTagSchema), defaultValues: DEFAULT_VALUES });

  function onSubmit(values: AddCustomerTagFormValues) {
    addMutation.mutate(
      { tag: values.tag },
      {
        onSuccess: () => form.reset(DEFAULT_VALUES),
      },
    );
  }

  if (query.isLoading) return <Skeleton className="h-16 w-full" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;

  return (
    <div className="flex flex-col gap-4">
      <PermissionGate permission="customers:write">
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex items-start gap-2" noValidate>
            <FormField
              control={form.control}
              name="tag"
              render={({ field }) => (
                <FormItem className="flex-1">
                  <FormControl>
                    <Input placeholder="e.g. vip, seasonal" aria-label="New tag" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <Button type="submit" size="sm" disabled={addMutation.isPending} aria-busy={addMutation.isPending}>
              {addMutation.isPending && <Spinner className="text-current" />}
              Add tag
            </Button>
          </form>
        </Form>
      </PermissionGate>

      {!query.data || query.data.length === 0 ? (
        <EmptyState icon={Tag} title="No tags yet" description="Tag this customer to segment and filter later." />
      ) : (
        <div className="flex flex-wrap gap-2">
          {query.data.map((tagRow) => (
            <Badge key={tagRow.id} tone="neutral" className="gap-1">
              {tagRow.tag}
              <PermissionGate permission="customers:write">
                <button
                  type="button"
                  className="ml-1 rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring/30"
                  aria-label={`Remove tag ${tagRow.tag}`}
                  disabled={removeMutation.isPending}
                  onClick={() => removeMutation.mutate(tagRow.tag)}
                >
                  <X className="size-3" aria-hidden="true" />
                </button>
              </PermissionGate>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
