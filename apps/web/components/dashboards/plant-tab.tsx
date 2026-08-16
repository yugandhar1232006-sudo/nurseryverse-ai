"use client";

import { Leaf } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { usePlantDashboardQuery } from "@/lib/dashboards/queries";
import { formatNumber } from "@/lib/utils";

/** Mirrors `PlantStatus` (apps/api/app/db/enums.py) exactly -- the real 5-value lifecycle status enum, not an invented set. */
const STATUS_TONE: Record<string, "success" | "warning" | "danger" | "info" | "neutral"> = {
  in_production: "info",
  ready_for_sale: "success",
  under_treatment: "warning",
  sold: "neutral",
  deceased: "danger",
};

function statusLabel(status: string): string {
  return status
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/** `GET /dashboards/plant` -- `by_status`/`by_species` counts, optionally filtered by the dashboard scope's branch. */
export function PlantTab({ branchId }: { branchId: string | null }) {
  const query = usePlantDashboardQuery(branchId, true);

  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  }

  const data = query.data;
  const statusEntries = data ? Object.entries(data.by_status) : [];
  const speciesRows = data ? (data.by_species as Array<{ species?: string; count?: number }>) : [];

  return (
    <div className="grid grid-cols-1 gap-4 laptop:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Plants by status</CardTitle>
        </CardHeader>
        <CardContent>
          {query.isLoading ? (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : statusEntries.length === 0 ? (
            <EmptyState icon={Leaf} title="No plants yet" description="Plant status breakdown appears here once plants are registered." />
          ) : (
            <ul className="flex flex-col gap-2">
              {statusEntries.map(([status, count]) => (
                <li key={status} className="flex items-center justify-between gap-2 text-body-sm">
                  <Badge tone={STATUS_TONE[status] ?? "neutral"}>{statusLabel(status)}</Badge>
                  <span className="tabular-nums font-medium text-foreground">{formatNumber(count)}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Top species</CardTitle>
        </CardHeader>
        <CardContent>
          {query.isLoading ? (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : speciesRows.length === 0 ? (
            <EmptyState icon={Leaf} title="No species data" description="A species breakdown appears once plants are linked to catalog species." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Species</TableHead>
                  <TableHead className="text-right">Plants</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {speciesRows.map((row, i) => (
                  <TableRow key={`${row.species}-${i}`}>
                    <TableCell className="font-medium text-foreground">{row.species ?? "Unknown"}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatNumber(row.count ?? 0)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
