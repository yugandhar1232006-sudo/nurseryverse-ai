"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { HeartPulse, Bug, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { PermissionGate } from "@/components/auth/permission-gate";
import { RecordEntryList } from "@/components/plants/record-entry-list";
import { DiseaseReportCard } from "@/components/plants/disease-report-card";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useHealthQuery, useDiseaseReportsQuery } from "@/lib/plants/queries";
import { useRecordHealthMutation, useCreateDiseaseReportMutation } from "@/lib/plants/mutations";
import {
  recordHealthSchema,
  type RecordHealthFormValues,
  createDiseaseReportSchema,
  type CreateDiseaseReportFormValues,
} from "@/lib/validation/plants";
import type { HealthRecordResponse } from "@/lib/api/plant-records";

const HEALTH_DEFAULTS: RecordHealthFormValues = { status_label: "", health_score: "", notes: "" };
const DISEASE_DEFAULTS: CreateDiseaseReportFormValues = { condition_name: "", severity: "low" };

/**
 * Combines Health Records and Disease Reports/Treatments in one tab --
 * both are genuinely Module 6 / "Health & Disease" scope per
 * `disease_reports.py`'s own docstring ("also its disease history for
 * Health Records"), distinct from 7L's AI Disease *Detection* (running a
 * model on an image). `is_ai_observation`/`is_ai_sourced` are always
 * `false` for anything logged through this manual UI -- see each form's
 * submit handler.
 */
export function HealthTab({ plantId }: { plantId: string }) {
  const [page, setPage] = React.useState(1);
  const [healthFormOpen, setHealthFormOpen] = React.useState(false);
  const [diseaseFormOpen, setDiseaseFormOpen] = React.useState(false);

  const healthQuery = useHealthQuery(plantId, page);
  const diseaseQuery = useDiseaseReportsQuery(plantId);
  const recordHealthMutation = useRecordHealthMutation(plantId);
  const createDiseaseMutation = useCreateDiseaseReportMutation(plantId);

  const healthForm = useForm<RecordHealthFormValues>({ resolver: zodResolver(recordHealthSchema), defaultValues: HEALTH_DEFAULTS });
  const handleHealthApiError = useApiFormErrors(healthForm.setError);

  const diseaseForm = useForm<CreateDiseaseReportFormValues>({ resolver: zodResolver(createDiseaseReportSchema), defaultValues: DISEASE_DEFAULTS });
  const handleDiseaseApiError = useApiFormErrors(diseaseForm.setError);

  React.useEffect(() => {
    if (healthFormOpen) healthForm.reset(HEALTH_DEFAULTS);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [healthFormOpen]);
  React.useEffect(() => {
    if (diseaseFormOpen) diseaseForm.reset(DISEASE_DEFAULTS);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [diseaseFormOpen]);

  function onSubmitHealth(values: RecordHealthFormValues) {
    recordHealthMutation.mutate(
      {
        status_label: values.status_label,
        health_score: values.health_score === "" ? null : Number(values.health_score),
        notes: values.notes || null,
        is_ai_observation: false,
      },
      { onSuccess: () => setHealthFormOpen(false), onError: handleHealthApiError },
    );
  }

  function onSubmitDisease(values: CreateDiseaseReportFormValues) {
    createDiseaseMutation.mutate(
      { condition_name: values.condition_name, severity: values.severity, is_ai_sourced: false },
      { onSuccess: () => setDiseaseFormOpen(false), onError: handleDiseaseApiError },
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h2 className="text-body font-semibold text-foreground">Health observations</h2>
          <PermissionGate permission="health:write">
            <Button type="button" size="sm" onClick={() => setHealthFormOpen(true)}>
              <Plus className="size-4" aria-hidden="true" />
              Record observation
            </Button>
          </PermissionGate>
        </div>

        <RecordEntryList<HealthRecordResponse>
          icon={HeartPulse}
          emptyTitle="No health observations yet"
          emptyDescription="Record this plant's first health observation."
          items={healthQuery.data?.items ?? []}
          isLoading={healthQuery.isLoading}
          isError={healthQuery.isError}
          error={healthQuery.error}
          onRetry={() => healthQuery.refetch()}
          retrying={healthQuery.isFetching}
          page={page}
          totalPages={healthQuery.data?.meta.total_pages ?? 1}
          onPageChange={setPage}
          renderItem={(record) => (
            <div className="flex flex-col gap-1">
              <div className="flex flex-wrap items-center gap-x-4 text-body-sm">
                <span className="font-medium text-foreground">{record.status_label}</span>
                {record.health_score != null && <span>Score: {record.health_score}%</span>}
                {record.is_ai_observation && <span className="text-ai-accent-700">AI-observed</span>}
              </div>
              {record.notes && <p className="text-body-sm text-muted-foreground">{record.notes}</p>}
              <p className="text-caption text-muted-foreground">{new Date(record.recorded_at).toLocaleString()}</p>
            </div>
          )}
        />
      </div>

      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h2 className="text-body font-semibold text-foreground">Disease reports</h2>
          <PermissionGate permission="disease:write">
            <Button type="button" size="sm" onClick={() => setDiseaseFormOpen(true)}>
              <Plus className="size-4" aria-hidden="true" />
              Report issue
            </Button>
          </PermissionGate>
        </div>

        {diseaseQuery.isLoading && (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
        )}
        {diseaseQuery.isError && <ErrorState error={diseaseQuery.error} onRetry={() => diseaseQuery.refetch()} retrying={diseaseQuery.isFetching} />}
        {diseaseQuery.data?.length === 0 && (
          <EmptyState icon={Bug} title="No disease reports" description="This plant has no logged disease reports." />
        )}
        <div className="flex flex-col gap-2">
          {(diseaseQuery.data ?? []).map((report) => (
            <DiseaseReportCard key={report.id} plantId={plantId} report={report} />
          ))}
        </div>
      </div>

      <Dialog open={healthFormOpen} onOpenChange={setHealthFormOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Record health observation</DialogTitle>
            <DialogDescription>Creates a new, permanent health record entry.</DialogDescription>
          </DialogHeader>
          <Form {...healthForm}>
            <form onSubmit={healthForm.handleSubmit(onSubmitHealth)} className="flex flex-col gap-4" noValidate>
              <FormField
                control={healthForm.control}
                name="status_label"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Status label</FormLabel>
                    <FormControl>
                      <Input placeholder="healthy, stressed, wilting…" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={healthForm.control}
                name="health_score"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Health score (0–100, optional)</FormLabel>
                    <FormControl>
                      <Input inputMode="numeric" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={healthForm.control}
                name="notes"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Notes (optional)</FormLabel>
                    <FormControl>
                      <Textarea rows={3} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setHealthFormOpen(false)} disabled={recordHealthMutation.isPending}>
                  Cancel
                </Button>
                <Button type="submit" disabled={recordHealthMutation.isPending} aria-busy={recordHealthMutation.isPending}>
                  {recordHealthMutation.isPending && <Spinner className="text-current" />}
                  Save
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      <Dialog open={diseaseFormOpen} onOpenChange={setDiseaseFormOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Report a disease or condition</DialogTitle>
            <DialogDescription>Creates a draft report, pending confirmation.</DialogDescription>
          </DialogHeader>
          <Form {...diseaseForm}>
            <form onSubmit={diseaseForm.handleSubmit(onSubmitDisease)} className="flex flex-col gap-4" noValidate>
              <FormField
                control={diseaseForm.control}
                name="condition_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Condition name</FormLabel>
                    <FormControl>
                      <Input placeholder="root rot, powdery mildew…" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={diseaseForm.control}
                name="severity"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Severity</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="low">Low</SelectItem>
                        <SelectItem value="medium">Medium</SelectItem>
                        <SelectItem value="high">High</SelectItem>
                        <SelectItem value="critical">Critical</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setDiseaseFormOpen(false)} disabled={createDiseaseMutation.isPending}>
                  Cancel
                </Button>
                <Button type="submit" disabled={createDiseaseMutation.isPending} aria-busy={createDiseaseMutation.isPending}>
                  {createDiseaseMutation.isPending && <Spinner className="text-current" />}
                  Submit report
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
