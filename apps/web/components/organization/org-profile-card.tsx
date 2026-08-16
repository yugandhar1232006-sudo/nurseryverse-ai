"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/error-state";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { FormActions } from "@/components/form/form-actions";
import { PermissionGate } from "@/components/auth/permission-gate";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useOrganizationQuery } from "@/lib/shell/queries";
import { useUpdateOrganizationMutation } from "@/lib/organization/mutations";
import { orgProfileSchema, type OrgProfileFormValues } from "@/lib/validation/organization";
import type { NurseryResponse } from "@/lib/api/organizations";

export function OrgProfileCard({ orgId }: { orgId: string }) {
  const query = useOrganizationQuery();

  if (query.isLoading) return <Skeleton className="h-64 w-full" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  if (!query.data) return null;

  return (
    <PermissionGate permission="org:write" fallback={<ReadOnlyProfile org={query.data} />}>
      <EditableProfile orgId={orgId} org={query.data} />
    </PermissionGate>
  );
}

function ReadOnlyProfile({ org }: { org: NurseryResponse }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Organization profile</CardTitle>
        <CardDescription>Read-only -- your role doesn&apos;t include org:write.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2 text-body-sm">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Name</span>
          <span>{org.name}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Contact email</span>
          <span>{org.contact_email}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Contact phone</span>
          <span>{org.contact_phone ?? "—"}</span>
        </div>
      </CardContent>
    </Card>
  );
}

function EditableProfile({ orgId, org }: { orgId: string; org: NurseryResponse }) {
  const mutation = useUpdateOrganizationMutation(orgId);
  const form = useForm<OrgProfileFormValues>({
    resolver: zodResolver(orgProfileSchema),
    defaultValues: {
      name: org.name,
      contact_email: org.contact_email,
      contact_phone: org.contact_phone ?? "",
      logo_url: org.logo_url ?? "",
    },
  });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    form.reset({
      name: org.name,
      contact_email: org.contact_email,
      contact_phone: org.contact_phone ?? "",
      logo_url: org.logo_url ?? "",
    });
    // Only re-sync when the server row itself changes -- not on every
    // render, which would clobber in-progress edits.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [org.id, org.updated_at]);

  function onSubmit(values: OrgProfileFormValues) {
    mutation.mutate(
      {
        name: values.name,
        contact_email: values.contact_email,
        contact_phone: values.contact_phone || null,
        logo_url: values.logo_url || null,
      },
      { onError: handleApiError },
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Organization profile</CardTitle>
        <CardDescription>Name, contact details, and logo shown throughout NurseryVerse.</CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Organization name</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="contact_email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Contact email</FormLabel>
                  <FormControl>
                    <Input type="email" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="contact_phone"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Contact phone</FormLabel>
                  <FormControl>
                    <Input type="tel" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="logo_url"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Logo URL</FormLabel>
                  <FormControl>
                    <Input type="url" placeholder="https://…" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormActions primaryLabel="Save profile" submitting={mutation.isPending} />
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
