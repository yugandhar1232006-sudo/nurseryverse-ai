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
import { useCreateReportMutation } from "@/lib/reports/mutations";
import { generateReportSchema, type GenerateReportFormValues } from "@/lib/validation/reports";
import type { BranchResponse } from "@/lib/api/branches";
import type { ReportCatalogEntryResponse, ReportFormat, ReportType } from "@/lib/api/reports";

const FORMAT_LABELS: Record<ReportFormat, string> = { pdf: "PDF", excel: "Excel", csv: "CSV", json: "JSON" };
const ORG_WIDE = "__org_wide__";

/**
 * PG-51 "Generate report" -- `POST /reports` (real 202-Accepted async
 * generation; see docs/frontend/18-reports-analytics.md). Only exposes
 * report type, format, branch scope, and a date range -- see
 * `lib/validation/reports.ts`'s docstring for why the other seven real
 * `ReportFilters` fields (species/category/customer/status/etc., each
 * meaningful for only a subset of the 18 report types) are out of scope
 * for this pass.
 */
export function GenerateReportDialog({
  catalog,
  branches,
  defaultReportType,
  open,
  onOpenChange,
}: {
  catalog: ReportCatalogEntryResponse[];
  branches: BranchResponse[];
  defaultReportType?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const mutation = useCreateReportMutation();
  const form = useForm<GenerateReportFormValues>({
    resolver: zodResolver(generateReportSchema),
    defaultValues: { report_type: defaultReportType ?? "", format: "pdf", branch_id: "", date_from: "", date_to: "" },
  });
  const handleApiError = useApiFormErrors(form.setError);

  // Render-body "adjusting state" pattern (see ai-predictions-tab.tsx's
  // disease-scan dialog for the identical bare open/closed-transition use).
  const [synced, setSynced] = React.useState(false);
  if (open && !synced) {
    setSynced(true);
    form.reset({ report_type: defaultReportType ?? "", format: "pdf", branch_id: "", date_from: "", date_to: "" });
  } else if (!open && synced) {
    setSynced(false);
  }

  function onSubmit(values: GenerateReportFormValues) {
    mutation.mutate(
      {
        report_type: values.report_type as ReportType,
        format: values.format,
        branch_id: values.branch_id || undefined,
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
          <DialogTitle>Generate report</DialogTitle>
          <DialogDescription>
            Runs in the background -- track progress in Report History below (FR from PG-51).
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
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
            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="date_from"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Date from</FormLabel>
                    <FormControl>
                      <Input type="date" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="date_to"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Date to</FormLabel>
                    <FormControl>
                      <Input type="date" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={mutation.isPending}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending} aria-busy={mutation.isPending}>
                {mutation.isPending && <Spinner className="text-current" />}
                Generate
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
