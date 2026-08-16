"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { ChevronDown, ChevronUp } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/spinner";
import { Skeleton } from "@/components/ui/skeleton";
import { PermissionGate } from "@/components/auth/permission-gate";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useTreatmentsQuery } from "@/lib/plants/queries";
import {
  useConfirmDiseaseReportMutation,
  useDismissDiseaseReportMutation,
  useApplyTreatmentMutation,
} from "@/lib/plants/mutations";
import { dismissDiseaseReportSchema, applyTreatmentSchema, type DismissDiseaseReportFormValues, type ApplyTreatmentFormValues } from "@/lib/validation/plants";
import type { DiseaseReportResponse } from "@/lib/api/disease-reports";

const SEVERITY_TONE: Record<DiseaseReportResponse["severity"], "neutral" | "success" | "warning" | "danger" | "info"> = {
  low: "info",
  medium: "warning",
  high: "danger",
  critical: "danger",
};

const STATUS_LABEL: Record<DiseaseReportResponse["status"], string> = {
  draft: "Draft",
  confirmed: "Confirmed",
  dismissed: "Dismissed",
  treated: "Treated",
  resolved: "Resolved",
};

/**
 * One `DiseaseReportResponse` plus the actions available at its current
 * `DiseaseReportStatus` (draft -> confirmed/dismissed -> treated ->
 * resolved). `disease:approve` (confirm/dismiss a draft) is a narrower
 * permission than `disease:write` (log a report, apply a treatment) --
 * see lib/api/disease-reports.ts's docstring. Confirming an above-
 * threshold report auto-transitions the plant to `Under Treatment`
 * server-side; this card does not attempt to reflect that itself, it
 * just re-fetches the plant on success (see the mutation's own
 * `invalidatePlant` call).
 */
export function DiseaseReportCard({ plantId, report }: { plantId: string; report: DiseaseReportResponse }) {
  const [expanded, setExpanded] = React.useState(false);
  const [dismissOpen, setDismissOpen] = React.useState(false);
  const [treatOpen, setTreatOpen] = React.useState(false);
  const [confirming, setConfirming] = React.useState(false);

  const treatmentsQuery = useTreatmentsQuery(expanded ? report.id : null);
  const confirmMutation = useConfirmDiseaseReportMutation(plantId);
  const dismissMutation = useDismissDiseaseReportMutation(plantId);
  const treatMutation = useApplyTreatmentMutation(plantId);

  const dismissForm = useForm<DismissDiseaseReportFormValues>({
    resolver: zodResolver(dismissDiseaseReportSchema),
    defaultValues: { dismissed_reason: "" },
  });
  const handleDismissApiError = useApiFormErrors(dismissForm.setError);

  const treatForm = useForm<ApplyTreatmentFormValues>({
    resolver: zodResolver(applyTreatmentSchema),
    defaultValues: { description: "", outcome: "ongoing" },
  });
  const handleTreatApiError = useApiFormErrors(treatForm.setError);

  return (
    <div className="flex flex-col gap-2 rounded-md border border-border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="font-medium text-foreground">{report.condition_name}</span>
          <Badge tone={SEVERITY_TONE[report.severity]}>{report.severity}</Badge>
          <Badge variant="outline">{STATUS_LABEL[report.status]}</Badge>
          {report.is_ai_sourced && <Badge tone="ai">AI-sourced</Badge>}
        </div>
        <Button type="button" variant="ghost" size="sm" onClick={() => setExpanded((e) => !e)}>
          {expanded ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
          Treatments
        </Button>
      </div>

      {report.is_ai_sourced && report.ai_confidence != null && (
        <p className="text-caption text-muted-foreground">AI confidence at time of report: {(report.ai_confidence * 100).toFixed(0)}%</p>
      )}
      {report.dismissed_reason && <p className="text-body-sm text-muted-foreground">Dismissed: {report.dismissed_reason}</p>}

      {report.status === "draft" && (
        <div className="flex gap-2">
          <PermissionGate permission="disease:approve">
            <Button type="button" size="sm" variant="outline" disabled={confirmMutation.isPending} onClick={() => { setConfirming(true); confirmMutation.mutate(report.id, { onSettled: () => setConfirming(false) }); }}>
              {confirming && <Spinner className="text-current" />}
              Confirm
            </Button>
            <Button type="button" size="sm" variant="outline" className="text-destructive hover:text-destructive" onClick={() => setDismissOpen(true)}>
              Dismiss
            </Button>
          </PermissionGate>
        </div>
      )}

      {(report.status === "confirmed" || report.status === "treated") && (
        <PermissionGate permission="disease:write">
          <div>
            <Button type="button" size="sm" variant="outline" onClick={() => setTreatOpen(true)}>
              Apply treatment
            </Button>
          </div>
        </PermissionGate>
      )}

      {expanded && (
        <div className="flex flex-col gap-2 border-t border-border pt-2">
          {treatmentsQuery.isLoading && <Skeleton className="h-10 w-full" />}
          {treatmentsQuery.isError && <p className="text-body-sm text-destructive">Couldn&apos;t load treatments.</p>}
          {treatmentsQuery.data?.length === 0 && <p className="text-body-sm text-muted-foreground">No treatments applied yet.</p>}
          {(treatmentsQuery.data ?? []).map((t) => (
            <div key={t.id} className="text-body-sm">
              <span className="font-medium text-foreground">{t.outcome}</span> — {t.description}
              <span className="block text-caption text-muted-foreground">{new Date(t.applied_at).toLocaleString()}</span>
            </div>
          ))}
        </div>
      )}

      <AlertDialog open={dismissOpen} onOpenChange={setDismissOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Dismiss this report?</AlertDialogTitle>
            <AlertDialogDescription>A reason is required so the record stays auditable.</AlertDialogDescription>
          </AlertDialogHeader>
          <Form {...dismissForm}>
            <form
              id="dismiss-disease-form"
              onSubmit={dismissForm.handleSubmit((values) =>
                dismissMutation.mutate(
                  { reportId: report.id, reason: values.dismissed_reason },
                  { onSuccess: () => setDismissOpen(false), onError: handleDismissApiError },
                ),
              )}
            >
              <FormField
                control={dismissForm.control}
                name="dismissed_reason"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Reason</FormLabel>
                    <FormControl>
                      <Textarea rows={3} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </form>
          </Form>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={dismissMutation.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction type="submit" form="dismiss-disease-form" disabled={dismissMutation.isPending}>
              Dismiss report
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog open={treatOpen} onOpenChange={setTreatOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Apply treatment</DialogTitle>
            <DialogDescription>Creates a new, permanent treatment entry for this disease report.</DialogDescription>
          </DialogHeader>
          <Form {...treatForm}>
            <form
              onSubmit={treatForm.handleSubmit((values) =>
                treatMutation.mutate(
                  { reportId: report.id, body: { description: values.description, outcome: values.outcome } },
                  { onSuccess: () => setTreatOpen(false), onError: handleTreatApiError },
                ),
              )}
              className="flex flex-col gap-4"
              noValidate
            >
              <FormField
                control={treatForm.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description</FormLabel>
                    <FormControl>
                      <Textarea rows={3} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={treatForm.control}
                name="outcome"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Outcome</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="ongoing">Ongoing</SelectItem>
                        <SelectItem value="recovered">Recovered</SelectItem>
                        <SelectItem value="plant_lost">Plant lost</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setTreatOpen(false)} disabled={treatMutation.isPending}>
                  Cancel
                </Button>
                <Button type="submit" disabled={treatMutation.isPending} aria-busy={treatMutation.isPending}>
                  {treatMutation.isPending && <Spinner className="text-current" />}
                  Save treatment
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
