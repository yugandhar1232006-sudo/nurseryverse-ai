"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { ErrorState } from "@/components/error-state";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { FormActions } from "@/components/form/form-actions";
import { Input } from "@/components/ui/input";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useOrgSettingsQuery } from "@/lib/shell/queries";
import { usePreferencesQuery } from "@/lib/notifications/queries";
import { useUpdatePreferencesMutation } from "@/lib/notifications/mutations";
import {
  notificationPreferencesSchema,
  type NotificationPreferencesFormValues,
} from "@/lib/validation/notifications";
import type {
  NotificationCategory,
  NotificationChannel,
  NotificationFrequency,
  NotificationPreferenceUpdateRequest,
} from "@/lib/api/notifications";
import { ALL_CATEGORIES, CATEGORY_LABELS, CHANNEL_LABELS } from "@/lib/notifications/labels";

/**
 * Confirmed directly against `PreferenceService.resolve_channels`
 * (apps/api/app/notifications/preferences.py's `_DEFAULT_ENABLED`): a
 * (category, channel) pair with no saved row is NOT "off" -- in_app and
 * email default on, sms and push default off. The grid's initial
 * (unsaved) state mirrors this exactly rather than guessing/showing
 * everything unchecked, so what a user sees before ever touching this
 * panel matches what's actually happening today.
 */
const DEFAULT_ENABLED: Record<NotificationChannel, boolean> = {
  in_app: true,
  email: true,
  sms: false,
  push: false,
};

function cellKey(category: NotificationCategory, channel: NotificationChannel): string {
  return `${category}:${channel}`;
}

/** `time` fields round-trip as `HH:MM:SS`; the `<input type="time">` control only wants `HH:MM`. */
function toInputTime(value: string | null | undefined): string {
  if (!value) return "";
  return value.slice(0, 5);
}

/**
 * PG-58 Notification preferences -- replaces `app/(app)/settings/page.tsx`'s
 * `ComingSoon` placeholder in the "Notifications" tab. Gated on
 * `notifications:manage_preferences` (docs/ux/09-page-inventory.md's PG-58
 * entry), the one part of that entry independently confirmed correct --
 * unlike its route citation (`PATCH`, wrong; the real route is `PUT`, see
 * `lib/api/notifications.ts`'s `updatePreferences` docstring).
 *
 * **Scope decision, not an oversight**: the real schema allows a distinct
 * quiet-hours window and frequency per (category, channel) row, but a
 * 22-category x 4-channel grid of individual time pickers would be
 * unusable UX and isn't what any real nursery operator asked for in the
 * UX research. This panel applies one shared quiet-hours window and one
 * shared frequency to every row it saves. The shared controls are
 * pre-filled from the first saved row that has a non-null quiet-hours
 * value (if any) purely as a starting point -- if the caller already has
 * divergent per-row values from some other path, saving here normalizes
 * every row to the one shared value shown, which is disclosed in the
 * description text below, not hidden.
 *
 * The SMS column is shown only when `OrgSettingsResponse.sms_enabled` is
 * true (a real field, confirmed via `org-settings-card.tsx`), per PG-58's
 * stated FR-17.3 plan-gating rule -- `useOrgSettingsQuery()` is the same
 * query `OrgSettingsCard` already calls elsewhere on this same page, so
 * this doesn't add a second network round trip once that tab has loaded.
 */
export function NotificationPreferencesPanel() {
  const orgSettings = useOrgSettingsQuery();
  const prefsQuery = usePreferencesQuery();
  const mutation = useUpdatePreferencesMutation();

  const [grid, setGrid] = React.useState<Record<string, boolean>>({});
  const [initialized, setInitialized] = React.useState(false);

  const form = useForm<NotificationPreferencesFormValues>({
    resolver: zodResolver(notificationPreferencesSchema),
    defaultValues: { quiet_hours_start: "", quiet_hours_end: "", quiet_hours_timezone: "", frequency: "immediate" },
  });

  // Render-body "adjusting state" pattern (see ai-predictions-tab.tsx /
  // passport-tab.tsx precedent): seed the grid + shared quiet-hours form
  // from the real fetched rows exactly once, when data first arrives.
  if (!initialized && prefsQuery.data) {
    const seeded: Record<string, boolean> = {};
    for (const row of prefsQuery.data) {
      seeded[cellKey(row.category, row.channel)] = row.enabled;
    }
    setInitialized(true);
    setGrid(seeded);
    const withQuietHours = prefsQuery.data.find((row) => row.quiet_hours_start);
    if (withQuietHours) {
      form.reset({
        quiet_hours_start: toInputTime(withQuietHours.quiet_hours_start),
        quiet_hours_end: toInputTime(withQuietHours.quiet_hours_end),
        quiet_hours_timezone: withQuietHours.quiet_hours_timezone ?? "",
        frequency: withQuietHours.frequency,
      });
    }
  }

  if (prefsQuery.isLoading || orgSettings.isLoading) return <Skeleton className="h-96 w-full" />;
  if (prefsQuery.isError) return <ErrorState error={prefsQuery.error} onRetry={() => prefsQuery.refetch()} retrying={prefsQuery.isFetching} />;
  if (orgSettings.isError) return <ErrorState error={orgSettings.error} onRetry={() => orgSettings.refetch()} retrying={orgSettings.isFetching} />;

  const smsEnabled = orgSettings.data?.sms_enabled ?? false;
  const visibleChannels: NotificationChannel[] = smsEnabled
    ? ["in_app", "email", "sms", "push"]
    : ["in_app", "email", "push"];

  function isChecked(category: NotificationCategory, channel: NotificationChannel): boolean {
    const key = cellKey(category, channel);
    return key in grid ? grid[key] : DEFAULT_ENABLED[channel];
  }

  function toggle(category: NotificationCategory, channel: NotificationChannel, checked: boolean) {
    setGrid((prev) => ({ ...prev, [cellKey(category, channel)]: checked }));
  }

  function onSubmit(values: NotificationPreferencesFormValues) {
    const frequency: NotificationFrequency = values.frequency;
    const rows: NotificationPreferenceUpdateRequest[] = [];
    for (const category of ALL_CATEGORIES) {
      for (const channel of visibleChannels) {
        rows.push({
          category,
          channel,
          enabled: isChecked(category, channel),
          frequency,
          quiet_hours_start: values.quiet_hours_start ? `${values.quiet_hours_start}:00` : null,
          quiet_hours_end: values.quiet_hours_end ? `${values.quiet_hours_end}:00` : null,
          quiet_hours_timezone: values.quiet_hours_timezone || null,
        });
      }
    }
    mutation.mutate(rows);
  }

  return (
    <PermissionGate
      permission="notifications:manage_preferences"
      fallback={
        <Card>
          <CardHeader>
            <CardTitle>Notification preferences</CardTitle>
            <CardDescription>Your role doesn&apos;t include notifications:manage_preferences.</CardDescription>
          </CardHeader>
        </Card>
      }
    >
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
          <Card>
            <CardHeader>
              <CardTitle>Channels by category</CardTitle>
              <CardDescription>
                Choose how you&apos;re notified for each event type (FR-17.3).
                {!smsEnabled && " SMS is off for your organization, so the SMS column isn't shown."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Category</TableHead>
                    {visibleChannels.map((channel) => (
                      <TableHead key={channel} className="text-center">
                        {CHANNEL_LABELS[channel]}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {ALL_CATEGORIES.map((category) => (
                    <TableRow key={category}>
                      <TableCell className="whitespace-nowrap">{CATEGORY_LABELS[category]}</TableCell>
                      {visibleChannels.map((channel) => (
                        <TableCell key={channel} className="text-center">
                          <Checkbox
                            checked={isChecked(category, channel)}
                            onCheckedChange={(checked) => toggle(category, channel, checked === true)}
                            aria-label={`${CATEGORY_LABELS[category]} via ${CHANNEL_LABELS[channel]}`}
                          />
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Quiet hours &amp; frequency</CardTitle>
              <CardDescription>
                Applies to every category and channel above -- this frontend saves one shared window rather than a
                separate one per category, though the API supports per-row values.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-4 tablet:grid-cols-2">
              <FormField
                control={form.control}
                name="quiet_hours_start"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Quiet hours start</FormLabel>
                    <FormControl>
                      <Input type="time" className="w-32" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="quiet_hours_end"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Quiet hours end</FormLabel>
                    <FormControl>
                      <Input type="time" className="w-32" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="quiet_hours_timezone"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Quiet hours timezone (IANA)</FormLabel>
                    <FormControl>
                      <Input placeholder="America/Los_Angeles" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="frequency"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Delivery frequency</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="w-full" aria-label="Delivery frequency">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="immediate">Immediate</SelectItem>
                        <SelectItem value="daily_digest">Daily digest</SelectItem>
                        <SelectItem value="weekly_digest">Weekly digest</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </CardContent>
          </Card>

          <FormActions primaryLabel="Save preferences" submitting={mutation.isPending} />
        </form>
      </Form>
    </PermissionGate>
  );
}
