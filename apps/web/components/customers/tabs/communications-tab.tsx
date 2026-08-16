"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { MessageSquare } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { useCustomerCommunicationsQuery } from "@/lib/customers/queries";
import { useLogCustomerCommunicationMutation } from "@/lib/customers/mutations";
import { logCommunicationSchema, type LogCommunicationFormValues } from "@/lib/validation/customers";

const DEFAULT_VALUES: LogCommunicationFormValues = { channel: "email", direction: "outbound", subject: "", notes: "" };

/** `GET/POST /customers/{id}/communications` -- add-and-list only, newest first (server-ordered), paginated. */
export function CommunicationsTab({ customerId }: { customerId: string }) {
  const [page, setPage] = React.useState(1);
  const query = useCustomerCommunicationsQuery(customerId, page);
  const mutation = useLogCustomerCommunicationMutation(customerId);
  const form = useForm<LogCommunicationFormValues>({ resolver: zodResolver(logCommunicationSchema), defaultValues: DEFAULT_VALUES });

  function onSubmit(values: LogCommunicationFormValues) {
    mutation.mutate(
      { channel: values.channel, direction: values.direction, subject: values.subject || null, notes: values.notes || null },
      { onSuccess: () => form.reset(DEFAULT_VALUES) },
    );
  }

  if (query.isLoading) return <Skeleton className="h-32 w-full" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  const items = query.data?.items ?? [];

  return (
    <div className="flex flex-col gap-4">
      <PermissionGate permission="customers:write">
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-3" noValidate>
            <div className="grid grid-cols-1 gap-3 tablet:grid-cols-2">
              <FormField
                control={form.control}
                name="channel"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Channel</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="email">Email</SelectItem>
                        <SelectItem value="phone">Phone</SelectItem>
                        <SelectItem value="sms">SMS</SelectItem>
                        <SelectItem value="in_person">In person</SelectItem>
                        <SelectItem value="other">Other</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="direction"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Direction</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="outbound">Outbound</SelectItem>
                        <SelectItem value="inbound">Inbound</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name="subject"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Subject (optional)</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="notes"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Notes (optional)</FormLabel>
                  <FormControl>
                    <Textarea rows={2} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="flex justify-end">
              <Button type="submit" size="sm" disabled={mutation.isPending} aria-busy={mutation.isPending}>
                {mutation.isPending && <Spinner className="text-current" />}
                Log communication
              </Button>
            </div>
          </form>
        </Form>
      </PermissionGate>

      {items.length === 0 ? (
        <EmptyState icon={MessageSquare} title="No communications logged yet" description="Log calls, emails, or in-person conversations with this customer." />
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((comm) => (
            <li key={comm.id} className="flex flex-col gap-1 rounded-md border border-border p-3 text-body-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="neutral" className="capitalize">
                  {comm.channel.replace("_", " ")}
                </Badge>
                <Badge tone={comm.direction === "inbound" ? "info" : "neutral"} className="capitalize">
                  {comm.direction}
                </Badge>
                <span className="text-caption text-muted-foreground">{new Date(comm.occurred_at).toLocaleString()}</span>
              </div>
              {comm.subject && <p className="font-medium text-foreground">{comm.subject}</p>}
              {comm.notes && <p className="text-muted-foreground">{comm.notes}</p>}
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
