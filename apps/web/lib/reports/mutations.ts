"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import * as reportsApi from "@/lib/api/reports";
import { reportKeys } from "@/lib/reports/queries";
import { toast } from "@/lib/toast";

/** `POST /reports` -- real 202-Accepted async generation (see `useReportHistoryQuery`'s docstring). Invalidates the history list so the new `pending` row appears immediately and its own polling takes over. */
export function useCreateReportMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: reportsApi.ReportCreateRequest) => reportsApi.createReport(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: reportKeys.all });
      toast.success("Report generation started");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useCreateScheduledReportMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: reportsApi.ScheduledReportCreateRequest) => reportsApi.createScheduledReport(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: reportKeys.all });
      toast.success("Scheduled report created");
    },
  });
}

export function useUpdateScheduledReportMutation(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: reportsApi.ScheduledReportUpdateRequest) => reportsApi.updateScheduledReport(id, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: reportKeys.all });
      toast.success("Scheduled report updated");
    },
  });
}

export function usePauseScheduledReportMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => reportsApi.pauseScheduledReport(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: reportKeys.all });
      toast.success("Scheduled report paused");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useResumeScheduledReportMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => reportsApi.resumeScheduledReport(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: reportKeys.all });
      toast.success("Scheduled report resumed");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useDeleteScheduledReportMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => reportsApi.deleteScheduledReport(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: reportKeys.all });
      toast.success("Scheduled report deleted");
    },
    onError: (error) => toast.apiError(error),
  });
}

/** `POST /reports/scheduled/run-due` -- see `runDueScheduledReports`'s docstring for why this real manual trigger exists alongside the automatic Celery beat sweep. */
export function useRunDueScheduledReportsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (limit?: number) => reportsApi.runDueScheduledReports(limit),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: reportKeys.all });
      toast.success(`Ran ${data.executed_count} due report(s)`);
    },
    onError: (error) => toast.apiError(error),
  });
}
