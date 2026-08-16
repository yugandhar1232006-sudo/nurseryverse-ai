"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { MailPlus, MessageSquareWarning, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { FormActions } from "@/components/form/form-actions";
import { Input } from "@/components/ui/input";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useNotificationTemplatesQuery } from "@/lib/admin/queries";
import { useCreateTemplateMutation, useRetryDueNotificationsMutation, useSendSystemAlertMutation } from "@/lib/admin/mutations";
import {
  notificationTemplateSchema,
  systemAlertSchema,
  type NotificationTemplateFormValues,
  type SystemAlertFormValues,
} from "@/lib/validation/admin";
import { ALL_CATEGORIES, ALL_CHANNELS, CATEGORY_LABELS, CHANNEL_LABELS } from "@/lib/notifications/labels";
import type { NotificationCategory } from "@/lib/api/notifications";

function TemplatesTab() {
  const query = useNotificationTemplatesQuery();
  const createMutation = useCreateTemplateMutation();

  const form = useForm<NotificationTemplateFormValues>({
    resolver: zodResolver(notificationTemplateSchema),
    defaultValues: { category: "", channel: "in_app", format: "text", locale: "en", subject_template: "", body_template: "" },
  });
  const handleApiError = useApiFormErrors(form.setError);

  function onSubmit(values: NotificationTemplateFormValues) {
    createMutation.mutate(
      {
        category: values.category as NotificationCategory,
        channel: values.channel,
        format: values.format,
        locale: values.locale,
        version: 1,
        subject_template: values.subject_template || null,
        body_template: values.body_template,
        is_active: true,
      },
      {
        onSuccess: () => form.reset(),
        onError: handleApiError,
      },
    );
  }

  const templates = query.data ?? [];

  return (
    <div className="grid grid-cols-1 gap-4 desktop:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Existing templates</CardTitle>
        </CardHeader>
        <CardContent>
          {query.isLoading && (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
            </div>
          )}
          {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />}
          {query.data && templates.length === 0 && (
            <EmptyState icon={MailPlus} title="No templates yet" description="Create the first one using the form." />
          )}
          {query.data && templates.length > 0 && (
            <ul className="flex flex-col gap-2">
              {templates.map((t) => (
                <li key={t.id} className="rounded-md border border-border p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-body-sm font-medium text-foreground">{CATEGORY_LABELS[t.category] ?? t.category}</span>
                    <Badge tone="neutral" variant="tone">
                      {CHANNEL_LABELS[t.channel] ?? t.channel}
                    </Badge>
                    <Badge tone="neutral" variant="tone">
                      v{t.version}
                    </Badge>
                    <Badge tone="neutral" variant="tone">
                      {t.locale}
                    </Badge>
                    <Badge tone={t.is_active ? "success" : "neutral"} variant="tone">
                      {t.is_active ? "Active" : "Inactive"}
                    </Badge>
                    {t.nursery_id === null && (
                      <Badge tone="info" variant="tone">
                        Platform default
                      </Badge>
                    )}
                  </div>
                  {t.subject_template && <p className="mt-1 text-caption text-muted-foreground">{t.subject_template}</p>}
                  <p className="mt-1 whitespace-pre-wrap text-caption text-foreground">{t.body_template}</p>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>New template</CardTitle>
          <CardDescription>
            Creates a versioned org-scoped override for a (category, channel, locale) triple -- the platform default keeps working for
            every other locale/version.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
              <FormField
                control={form.control}
                name="category"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Category</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="w-full" aria-label="Category">
                          <SelectValue placeholder="Choose a category" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {ALL_CATEGORIES.map((category) => (
                          <SelectItem key={category} value={category}>
                            {CATEGORY_LABELS[category]}
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
                name="channel"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Channel</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="w-full" aria-label="Channel">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {ALL_CHANNELS.map((channel) => (
                          <SelectItem key={channel} value={channel}>
                            {CHANNEL_LABELS[channel]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="format"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Format</FormLabel>
                      <FormControl>
                        <Input {...field} placeholder="text" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="locale"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Locale</FormLabel>
                      <FormControl>
                        <Input {...field} placeholder="en" />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={form.control}
                name="subject_template"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Subject template (optional)</FormLabel>
                    <FormControl>
                      <Input {...field} placeholder="{{ plant_name }} needs watering" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="body_template"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Body template</FormLabel>
                    <FormControl>
                      <Textarea {...field} rows={4} placeholder="{{ plant_name }} in {{ location }} hasn't been watered in {{ days }} days." />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormActions primaryLabel="Create template" submitting={createMutation.isPending} />
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}

function BroadcastTab() {
  const alertMutation = useSendSystemAlertMutation();
  const retryMutation = useRetryDueNotificationsMutation();

  const form = useForm<SystemAlertFormValues>({
    resolver: zodResolver(systemAlertSchema),
    defaultValues: { title: "", message: "", severity: "info" },
  });
  const handleApiError = useApiFormErrors(form.setError);

  function onSubmit(values: SystemAlertFormValues) {
    alertMutation.mutate(values, { onSuccess: () => form.reset(), onError: handleApiError });
  }

  return (
    <div className="grid grid-cols-1 gap-4 desktop:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Send a system alert</CardTitle>
          <CardDescription>Broadcasts an in-app notification to every active employee in this organization -- a real send, not a preview.</CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
              <FormField
                control={form.control}
                name="title"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Title</FormLabel>
                    <FormControl>
                      <Input {...field} placeholder="Scheduled maintenance tonight" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="message"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Message</FormLabel>
                    <FormControl>
                      <Textarea {...field} rows={4} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="severity"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Severity</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="w-full" aria-label="Severity">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="info">Info</SelectItem>
                        <SelectItem value="warning">Warning</SelectItem>
                        <SelectItem value="critical">Critical</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormActions primaryLabel="Send alert" submitting={alertMutation.isPending} />
            </form>
          </Form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Retry due notifications</CardTitle>
          <CardDescription>
            Manually runs the same due-delivery retry sweep Module 14&apos;s Celery beat already runs on its own schedule -- a real
            operator override for when a delivery needs to go out now rather than at the next automatic pass.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button type="button" onClick={() => retryMutation.mutate()} disabled={retryMutation.isPending} aria-busy={retryMutation.isPending}>
            <RefreshCw className="size-4" aria-hidden="true" />
            Retry due notifications now
          </Button>
          {retryMutation.isSuccess && (
            <p className="mt-3 text-body-sm text-muted-foreground">Retried {retryMutation.data.retried_count} due notification(s).</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

/**
 * PG-?? Notification Administration -- the remaining three real
 * `/notifications/*` routes deferred from 7M (template authoring, org-
 * wide alert broadcast, delivery-retry sweep). All gated
 * `notifications:manage_preferences`, the same permission 7M's own
 * preferences routes use -- there is no separate "notifications admin"
 * permission in the real backend (see `lib/api/notifications.ts`).
 */
export function NotificationAdminPanel() {
  return (
    <PermissionGate
      permission="notifications:manage_preferences"
      fallback={
        <Card>
          <CardHeader>
            <CardTitle>Notifications</CardTitle>
            <CardDescription>Template authoring, system alerts, and the delivery-retry sweep require notification management access.</CardDescription>
          </CardHeader>
        </Card>
      }
    >
      <Card>
        <CardHeader>
          <CardTitle>Notifications</CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="templates">
            <TabsList>
              <TabsTrigger value="templates">
                <MailPlus className="size-4" aria-hidden="true" />
                Templates
              </TabsTrigger>
              <TabsTrigger value="broadcast">
                <MessageSquareWarning className="size-4" aria-hidden="true" />
                Broadcast &amp; Retry
              </TabsTrigger>
            </TabsList>
            <TabsContent value="templates">
              <TemplatesTab />
            </TabsContent>
            <TabsContent value="broadcast">
              <BroadcastTab />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </PermissionGate>
  );
}
