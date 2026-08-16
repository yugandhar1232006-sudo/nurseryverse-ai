"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Pin, StickyNote } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Form, FormControl, FormField, FormItem, FormMessage } from "@/components/ui/form";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { useCustomerNotesQuery } from "@/lib/customers/queries";
import { useAddCustomerNoteMutation } from "@/lib/customers/mutations";
import { createCustomerNoteSchema, type CreateCustomerNoteFormValues } from "@/lib/validation/customers";

const DEFAULT_VALUES: CreateCustomerNoteFormValues = { note: "", pinned: false };

/** `GET/POST /customers/{id}/notes` -- add-and-list only, paginated, pinned notes surfaced first via a client-side sort of the current page. */
export function NotesTab({ customerId }: { customerId: string }) {
  const [page, setPage] = React.useState(1);
  const query = useCustomerNotesQuery(customerId, page);
  const mutation = useAddCustomerNoteMutation(customerId);
  const form = useForm<CreateCustomerNoteFormValues>({ resolver: zodResolver(createCustomerNoteSchema), defaultValues: DEFAULT_VALUES });

  function onSubmit(values: CreateCustomerNoteFormValues) {
    mutation.mutate({ note: values.note, pinned: values.pinned }, { onSuccess: () => form.reset(DEFAULT_VALUES) });
  }

  if (query.isLoading) return <Skeleton className="h-32 w-full" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;

  const items = [...(query.data?.items ?? [])].sort((a, b) => Number(b.pinned) - Number(a.pinned));

  return (
    <div className="flex flex-col gap-4">
      <PermissionGate permission="customers:write">
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-2" noValidate>
            <FormField
              control={form.control}
              name="note"
              render={({ field }) => (
                <FormItem>
                  <FormControl>
                    <Textarea placeholder="Add a note about this customer…" aria-label="New note" rows={3} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="flex items-center justify-between">
              <FormField
                control={form.control}
                name="pinned"
                render={({ field }) => (
                  <FormItem>
                    <label className="flex items-center gap-2 text-body-sm text-foreground">
                      <Checkbox checked={field.value} onCheckedChange={(checked) => field.onChange(checked === true)} />
                      Pin this note
                    </label>
                  </FormItem>
                )}
              />
              <Button type="submit" size="sm" disabled={mutation.isPending} aria-busy={mutation.isPending}>
                {mutation.isPending && <Spinner className="text-current" />}
                Add note
              </Button>
            </div>
          </form>
        </Form>
      </PermissionGate>

      {items.length === 0 ? (
        <EmptyState icon={StickyNote} title="No notes yet" description="Add context or reminders about this customer." />
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((note) => (
            <li key={note.id} className="flex flex-col gap-1 rounded-md border border-border p-3 text-body-sm">
              <div className="flex items-center gap-2">
                {note.pinned && (
                  <Badge tone="warning" className="gap-1">
                    <Pin className="size-3" aria-hidden="true" />
                    Pinned
                  </Badge>
                )}
                <span className="text-caption text-muted-foreground">{new Date(note.created_at).toLocaleString()}</span>
              </div>
              <p className="whitespace-pre-wrap text-foreground">{note.note}</p>
            </li>
          ))}
        </ul>
      )}

      {query.data && query.data.meta.total_pages > 1 && (
        <div className="flex items-center justify-between text-body-sm text-muted-foreground">
          <span>
            Page {query.data.meta.page} of {query.data.meta.total_pages}
          </span>
          <div className="flex gap-2">
            <Button type="button" variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </Button>
            <Button type="button" variant="outline" size="sm" disabled={page >= query.data.meta.total_pages} onClick={() => setPage((p) => p + 1)}>
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
