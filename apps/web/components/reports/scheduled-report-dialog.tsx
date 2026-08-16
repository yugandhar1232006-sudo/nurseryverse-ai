"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useCreateScheduledReportMutation } from "@/lib/reports/mutations";
import { scheduledReportSchema, type ScheduledReportFormValues } from "@/lib/validation/reports";
import type { BranchResponse } from "@/lib/api/branches";
import type { ReportCatalogEntryResponse, ReportFormat, ReportScheduleFrequency, ReportType } from "@/lib/api/reports";

const FORMAT_LABELS: Record<ReportFormat, string> = { pdf: "PDF", excel: "Excel", csv: "CSV", json: "JSON" };
const FREQUENCY_LABELS: Record<ReportScheduleFrequency, string> = { daily: "Daily", weekly: "Weekly", monthly: "Monthly" };
const ORG_WIDE = "__org_wide__";

const DEFAULTS: ScheduledReportFormValues = {
  name: "",
  report_type: "",
  format: "pdf",
  branch_id: "",
  frequency: "weekly",
  next_run_at: "",
  date_from: "",
  date_to: "",
};

/** PG-52 "New scheduled report" -- `POST /reports/scheduled`, `reports:export`-gated. Same deliberately-narrowed filter set as `GenerateReportDialog` (date range only; see `lib/validation/reports.ts`'s docstring). */
export function ScheduledReportDialog({
  catalog,
  branches,
  open,
  onOpenChange,
}: {
  catalog: ReportCatalogEntryResponse[];
  branches: BranchResponse[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const mutation = useCreateScheduledReportMutation();
  const form = useForm<ScheduledReportFormValues>({ resolver: zodResolver(scheduledReportSchema), defaultValues: DEFAULTS });
  const handleApiError = useApiFormErrors(form.setError);

  const [synced, setSynced] = React.useState(false);
  if (open && !synced) {
    setSynced(true);
    form.reset(DEFAULTS);
  } else if (!open && synced) {
    setSynced(false);
  }

  function onSubmit(values: ScheduledReportFormValues) {
    mutation.mutate(
      {
        name: values.name,
        report_type: values.report_type as ReportType,
        format: values.format,
        branch_id: values.branch_id || undefined,
        frequency: values.frequency,
        next_run_at: new Date(values.next_run_at).toISOString(),
        filters:
          values.date_from || values.date_to
            ? { low_stock_only: false, date_from: values.date_from || undefined, date_to: values.date_to || undefined }
            : undefined,
      },
      { onSuccess: () => onOpenChange(false), onError: handleApiError },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>New scheduled report</DialogTitle>
          <DialogDescription>Automatically regenerates on the frequency you choose (PG-52).</DialogDescription>
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
                    <Input placeholder="Weekly sales summary" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="report_type"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Report type</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger className="w-full" aria-label="Report type">
                        <SelectValue placeholder="Choose a report type" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {catalog.map((entry) => (
                        <SelectItem key={entry.report_type} value={entry.report_type}>
                          {entry.title}
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
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="w-full" aria-label="Format">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {(Object.keys(FORMAT_LABELS) as ReportFormat[]).map((f) => (
                          <SelectItem key={f} value={f}>
                            {FORMAT_LABELS[f]}
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
                name="frequency"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Frequency</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="w-full" aria-label="Frequency">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {(Object.keys(FREQUENCY_LABELS) as ReportScheduleFrequency[]).map((f) => (
                          <SelectItem key={f} value={f}>
                            {FREQUENCY_LABELS[f]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name="branch_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Branch</FormLabel>
                  <Select value={field.value || ORG_WIDE} onValueChange={(v) => field.onChange(v === ORG_WIDE ? "" : v)}>
                    <FormControl>
                      <SelectTrigger className="w-full" aria-label="Branch">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value={ORG_WIDE}>Org-wide</SelectItem>
                      {branches.map((b) => (
                        <SelectItem key={b.id} value={b.id}>
                          {b.name}
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
              name="next_run_at"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>First run</FormLabel>
                  <FormControl>
                    <Input type="datetime-local" {...field} />
                  </FormControl>
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
                Create schedule
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
