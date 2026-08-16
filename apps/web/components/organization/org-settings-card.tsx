"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/error-state";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { FormActions } from "@/components/form/form-actions";
import { PermissionGate } from "@/components/auth/permission-gate";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useOrgSettingsQuery } from "@/lib/shell/queries";
import { useUpdateOrganizationSettingsMutation } from "@/lib/organization/mutations";
import { orgSettingsSchema, type OrgSettingsFormValues } from "@/lib/validation/organization";
import type { OrgSettingsResponse } from "@/lib/api/organizations";

/**
 * Business Settings: currency, timezone, branding, and notification
 * sender identity/SMS toggle -- `GET/PATCH /orgs/{id}/settings`
 * (`OrgSettingsResponse`/`UpdateOrgSettingsRequest`). Every dashboard
 * (7D), sales, and inventory-valuation figure elsewhere in the app reads
 * `default_currency` from this same settings row via
 * `useOrgSettingsQuery` -- this is the one real place it's edited.
 */
export function OrgSettingsCard({ orgId }: { orgId: string }) {
  const query = useOrgSettingsQuery();

  if (query.isLoading) return <Skeleton className="h-72 w-full" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  if (!query.data) return null;

  return (
    <PermissionGate permission="org:write" fallback={<ReadOnlySettings settings={query.data} />}>
      <EditableSettings orgId={orgId} settings={query.data} />
    </PermissionGate>
  );
}

function ReadOnlySettings({ settings }: { settings: OrgSettingsResponse }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Business settings</CardTitle>
        <CardDescription>Read-only -- your role doesn&apos;t include org:write.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2 text-body-sm">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Currency</span>
          <span>{settings.default_currency}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Timezone</span>
          <span>{settings.default_timezone}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">SMS notifications</span>
          <span>{settings.sms_enabled ? "Enabled" : "Disabled"}</span>
        </div>
      </CardContent>
    </Card>
  );
}

function EditableSettings({ orgId, settings }: { orgId: string; settings: OrgSettingsResponse }) {
  const mutation = useUpdateOrganizationSettingsMutation(orgId);
  const form = useForm<OrgSettingsFormValues>({
    resolver: zodResolver(orgSettingsSchema),
    defaultValues: {
      currency: settings.default_currency,
      timezone: settings.default_timezone,
      branding_primary_color: settings.branding_primary_color ?? "",
      email_sender_identity: settings.email_sender_identity ?? "",
      sms_enabled: settings.sms_enabled,
    },
  });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    form.reset({
      currency: settings.default_currency,
      timezone: settings.default_timezone,
      branding_primary_color: settings.branding_primary_color ?? "",
      email_sender_identity: settings.email_sender_identity ?? "",
      sms_enabled: settings.sms_enabled,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings.id]);

  function onSubmit(values: OrgSettingsFormValues) {
    mutation.mutate(
      {
        currency: values.currency,
        timezone: values.timezone,
        branding_primary_color: values.branding_primary_color || null,
        email_sender_identity: values.email_sender_identity || null,
        sms_enabled: values.sms_enabled,
      },
      { onError: handleApiError },
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Business settings</CardTitle>
        <CardDescription>Currency, timezone, and branding used across dashboards, sales, and notifications.</CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <div className="grid grid-cols-1 gap-4 tablet:grid-cols-2">
              <FormField
                control={form.control}
                name="currency"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Currency (ISO 4217)</FormLabel>
                    <FormControl>
                      <Input placeholder="USD" maxLength={3} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="timezone"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Timezone (IANA)</FormLabel>
                    <FormControl>
                      <Input placeholder="America/Los_Angeles" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name="branding_primary_color"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Branding primary color</FormLabel>
                  <FormControl>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={/^#[0-9A-Fa-f]{6}$/.test(field.value ?? "") ? field.value : "#2E7D32"}
                        onChange={(e) => field.onChange(e.target.value)}
                        className="size-9 shrink-0 cursor-pointer rounded-sm border border-input"
                        aria-label="Pick branding primary color"
                      />
                      <Input placeholder="#2E7D32" {...field} />
                    </div>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="email_sender_identity"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email sender identity</FormLabel>
                  <FormControl>
                    <Input placeholder="Green Thumb Nursery <hello@greenthumb.test>" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="sms_enabled"
              render={({ field }) => (
                <FormItem className="flex flex-row items-center justify-between gap-4 rounded-md border border-border p-3">
                  <div>
                    <FormLabel>SMS notifications</FormLabel>
                    <p className="text-caption text-muted-foreground">Allow SMS delivery for notification categories that support it.</p>
                  </div>
                  <FormControl>
                    <Switch checked={field.value} onCheckedChange={field.onChange} aria-label="SMS notifications" />
                  </FormControl>
                </FormItem>
              )}
            />
            <FormActions primaryLabel="Save settings" submitting={mutation.isPending} />
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
