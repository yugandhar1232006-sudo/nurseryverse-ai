"use client";

import * as React from "react";
import { Download, FileText, Plus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/error-state";
import { PermissionGate } from "@/components/auth/permission-gate";
import { RecordEntryList } from "@/components/plants/record-entry-list";
import { Skeleton } from "@/components/ui/skeleton";
import { GenerateReportDialog } from "@/components/reports/generate-report-dialog";
import { useBranchesQuery } from "@/lib/shell/queries";
import { reportDownloadUrl, type ReportFormat, type ReportResponse, type ReportStatus } from "@/lib/api/reports";
import { useReportCatalogQuery, useReportHistoryQuery } from "@/lib/reports/queries";

const STATUS_TONE: Record<ReportStatus, "neutral" | "success" | "warning" | "danger" | "info"> = {
  pending: "neutral",
  processing: "info",
  complete: "success",
  failed: "danger",
};
const STATUS_LABEL: Record<ReportStatus, string> = {
  pending: "Pending",
  processing: "Generating…",
  complete: "Complete",
  failed: "Failed",
};
const FORMAT_LABELS: Record<ReportFormat, string> = { pdf: "PDF", excel: "Excel", csv: "CSV", json: "JSON" };

/**
 * PG-51 Report Catalog + Generate/Status/History/Download, all on one
 * screen. Report *type* titles come straight from the real
 * `GET /reports/catalog` response (never a hand-typed label map) so the
 * catalog grid and the history list's per-row type label always agree
 * with the backend's own real 18-value `ReportType` set, including if
 * that set ever changes.
 */
export function ReportHistoryPanel() {
  const [page, setPage] = React.useState(1);
  const [generateOpen, setGenerateOpen] = React.useState(false);
  const [presetType, setPresetType] = React.useState<string | undefined>(undefined);

  const catalogQuery = useReportCatalogQuery();
  const branchesQuery = useBranchesQuery();
  const historyQuery = useReportHistoryQuery({ page });

  const catalog = catalogQuery.data ?? [];
  const typeTitleByType = new Map(catalog.map((c) => [c.report_type, c.title]));
  const branchNameById = new Map((branchesQuery.data ?? []).map((b) => [b.id, b.name]));

  function openGenerate(reportType?: string) {
    setPresetType(reportType);
    setGenerateOpen(true);
  }

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle>Report Catalog</CardTitle>
          <PermissionGate permission="reports:export">
            <Button type="button" size="sm" onClick={() => openGenerate()}>
              <Plus className="size-4" aria-hidden="true" />
              Generate report
            </Button>
          </PermissionGate>
        </CardHeader>
        <CardContent>
          {catalogQuery.isLoading && (
            <div className="grid grid-cols-1 gap-3 tablet:grid-cols-2 desktop:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-24 w-full" />
              ))}
            </div>
          )}
          {catalogQuery.isError && (
            <ErrorState error={catalogQuery.error} onRetry={() => catalogQuery.refetch()} retrying={catalogQuery.isFetching} />
          )}
          {catalogQuery.data && (
            <div className="grid grid-cols-1 gap-3 tablet:grid-cols-2 desktop:grid-cols-3">
              {catalog.map((entry) => (
                <div key={entry.report_type} className="flex flex-col gap-2 rounded-md border border-border p-3">
                  <p className="text-body-sm font-medium text-foreground">{entry.title}</p>
                  <p className="text-caption text-muted-foreground">{entry.description}</p>
                  <PermissionGate permission="reports:export">
                    <Button type="button" variant="outline" size="sm" className="self-start" onClick={() => openGenerate(entry.report_type)}>
                      Generate
                    </Button>
                  </PermissionGate>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Report History</CardTitle>
        </CardHeader>
        <CardContent>
          <RecordEntryList<ReportResponse>
            icon={FileText}
            emptyTitle="No reports generated yet"
            emptyDescription="Generate a report above to see it here."
            items={historyQuery.data?.items ?? []}
            isLoading={historyQuery.isLoading}
            isError={historyQuery.isError}
            error={historyQuery.error}
            onRetry={() => historyQuery.refetch()}
            retrying={historyQuery.isFetching}
            page={page}
            totalPages={historyQuery.data?.meta.total_pages ?? 1}
            onPageChange={setPage}
            renderItem={(report) => (
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-col gap-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-body-sm font-medium text-foreground">
                      {typeTitleByType.get(report.report_type) ?? report.report_type}
                    </span>
                    <Badge tone={STATUS_TONE[report.status]} variant="tone">
                      {STATUS_LABEL[report.status]}
                    </Badge>
                    <span className="text-caption text-muted-foreground">{FORMAT_LABELS[report.format]}</span>
                    {report.branch_id && (
                      <span className="text-caption text-muted-foreground">{branchNameById.get(report.branch_id) ?? "Branch"}</span>
                    )}
                  </div>
                  <p className="text-caption text-muted-foreground">Requested {new Date(report.created_at).toLocaleString()}</p>
                </div>
                {report.status === "complete" && report.download_url && (
                  <Button asChild type="button" variant="outline" size="sm">
                    <a href={reportDownloadUrl(report.id)} target="_blank" rel="noreferrer">
                      <Download className="size-4" aria-hidden="true" />
                      Download
                    </a>
                  </Button>
                )}
              </div>
            )}
          />
        </CardContent>
      </Card>

      <GenerateReportDialog
        catalog={catalog}
        branches={branchesQuery.data ?? []}
        defaultReportType={presetType}
        open={generateOpen}
        onOpenChange={setGenerateOpen}
      />
    </div>
  );
}
