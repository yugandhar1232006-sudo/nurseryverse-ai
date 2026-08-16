"use client";

import * as React from "react";
import { CalendarClock, Pause, Play, Plus, RefreshCw, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PermissionGate } from "@/components/auth/permission-gate";
import { RecordEntryList } from "@/components/plants/record-entry-list";
import { Spinner } from "@/components/ui/spinner";
import { ScheduledReportDialog } from "@/components/reports/scheduled-report-dialog";
import { useBranchesQuery } from "@/lib/shell/queries";
import { useReportCatalogQuery, useScheduledReportsQuery } from "@/lib/reports/queries";
import {
  useDeleteScheduledReportMutation,
  usePauseScheduledReportMutation,
  useResumeScheduledReportMutation,
  useRunDueScheduledReportsMutation,
} from "@/lib/reports/mutations";
import type { ReportScheduleFrequency, ScheduledReportResponse } from "@/lib/api/reports";

const FREQUENCY_LABELS: Record<ReportScheduleFrequency, string> = { daily: "Daily", weekly: "Weekly", monthly: "Monthly" };

/**
 * PG-52 Scheduled Reports CRUD -- list, create, pause/resume, delete, and
 * a real "Run due reports now" trigger (`POST /reports/scheduled/run-due`,
 * see `runDueScheduledReports`'s docstring for why this manual action
 * exists alongside the automatic Celery beat sweep). All writes gated on
 * `reports:export`; the list itself only needs `reports:read`.
 */
export function ScheduledReportsPanel() {
  const [page, setPage] = React.useState(1);
  const [createOpen, setCreateOpen] = React.useState(false);

  const catalogQuery = useReportCatalogQuery();
  const branchesQuery = useBranchesQuery();
  const query = useScheduledReportsQuery({ page });
  const pauseMutation = usePauseScheduledReportMutation();
  const resumeMutation = useResumeScheduledReportMutation();
  const deleteMutation = useDeleteScheduledReportMutation();
  const runDueMutation = useRunDueScheduledReportsMutation();

  const catalog = catalogQuery.data ?? [];
  const typeTitleByType = new Map(catalog.map((c) => [c.report_type, c.title]));
  const branchNameById = new Map((branchesQuery.data ?? []).map((b) => [b.id, b.name]));

  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-2 space-y-0">
        <CardTitle>Scheduled Reports</CardTitle>
        <PermissionGate permission="reports:export">
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={runDueMutation.isPending}
              onClick={() => runDueMutation.mutate(undefined)}
            >
              {runDueMutation.isPending ? <Spinner className="text-current" /> : <RefreshCw className="size-4" aria-hidden="true" />}
              Run due reports now
            </Button>
            <Button type="button" size="sm" onClick={() => setCreateOpen(true)}>
              <Plus className="size-4" aria-hidden="true" />
              New schedule
            </Button>
          </div>
        </PermissionGate>
      </CardHeader>
      <CardContent>
        <RecordEntryList<ScheduledReportResponse>
          icon={CalendarClock}
          emptyTitle="No scheduled reports yet"
          emptyDescription="Create a schedule above to have a report generated automatically."
          items={query.data?.items ?? []}
          isLoading={query.isLoading}
          isError={query.isError}
          error={query.error}
          onRetry={() => query.refetch()}
          retrying={query.isFetching}
          page={page}
          totalPages={query.data?.meta.total_pages ?? 1}
          onPageChange={setPage}
          renderItem={(scheduled) => (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-col gap-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-body-sm font-medium text-foreground">{scheduled.name}</span>
                  <Badge tone={scheduled.is_active ? "success" : "neutral"} variant="tone">
                    {scheduled.is_active ? "Active" : "Paused"}
                  </Badge>
                  <span className="text-caption text-muted-foreground">
                    {typeTitleByType.get(scheduled.report_type) ?? scheduled.report_type}
                  </span>
                  <span className="text-caption text-muted-foreground">{FREQUENCY_LABELS[scheduled.frequency]}</span>
                  {scheduled.branch_id && (
                    <span className="text-caption text-muted-foreground">{branchNameById.get(scheduled.branch_id) ?? "Branch"}</span>
                  )}
                </div>
                <p className="text-caption text-muted-foreground">
                  Next run {new Date(scheduled.next_run_at).toLocaleString()}
                  {scheduled.last_run_at && ` · Last run ${new Date(scheduled.last_run_at).toLocaleString()}`}
                </p>
              </div>
              <PermissionGate permission="reports:export">
                <div className="flex items-center gap-2">
                  {scheduled.is_active ? (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={pauseMutation.isPending}
                      onClick={() => pauseMutation.mutate(scheduled.id)}
                    >
                      <Pause className="size-4" aria-hidden="true" />
                      Pause
                    </Button>
                  ) : (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={resumeMutation.isPending}
                      onClick={() => resumeMutation.mutate(scheduled.id)}
                    >
                      <Play className="size-4" aria-hidden="true" />
                      Resume
                    </Button>
                  )}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={deleteMutation.isPending}
                    onClick={() => deleteMutation.mutate(scheduled.id)}
                    aria-label={`Delete ${scheduled.name}`}
                  >
                    <Trash2 className="size-4" aria-hidden="true" />
                  </Button>
                </div>
              </PermissionGate>
            </div>
          )}
        />
      </CardContent>

      <ScheduledReportDialog catalog={catalog} branches={branchesQuery.data ?? []} open={createOpen} onOpenChange={setCreateOpen} />
    </Card>
  );
}
