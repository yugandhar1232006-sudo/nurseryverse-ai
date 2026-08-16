"use client";

import Link from "next/link";
import { AlertTriangle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useSurvivalRiskQuery } from "@/lib/ai-predictions/queries";
import type { SurvivalPredictionResult } from "@/lib/api/ai-predictions";

const RISK_TONE: Record<SurvivalPredictionResult["risk_level"], "success" | "warning" | "danger"> = {
  low: "success",
  moderate: "warning",
  high: "danger",
  critical: "danger",
};

/**
 * PG-31 AI Predictions Dashboard's "ranked at-risk plant list with
 * contributing factors" -- `GET /ai/predictions/survival-risk`, the raw
 * Module 10 history, sorted newest-first per the route's own docstring
 * (not literally risk-sorted server-side; ranking by risk_score happens
 * here, client-side, since the backend contract is "newest N," not "top N
 * by risk").
 *
 * The raw `AIPredictionResponse` carries only `plant_id` (a uuid), not a
 * plant label or species name -- unlike 7D's `GET /dashboards/ai`
 * (`AtRiskPlantResponse`, which bundles `common_label`). This is a real
 * gap in Module 10's own response shape, not a frontend oversight: no
 * batch "resolve these plant ids to labels" route exists. Each row links
 * to `/plants/{id}` (a real, working destination) using the id itself as
 * the visible text -- honest given what the API actually returns, rather
 * than fabricating a label. See docs/frontend/16-ai-experience.md's Known
 * Limitations.
 */
export function SurvivalRiskPanel({ branchId }: { branchId: string | null }) {
  const query = useSurvivalRiskQuery({ page: 1, page_size: 50, branch_id: branchId ?? undefined });

  if (query.isLoading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  }

  const rows = (query.data?.items ?? [])
    .map((prediction) => ({ prediction, result: prediction.result as unknown as SurvivalPredictionResult }))
    .sort((a, b) => (b.result?.risk_score ?? 0) - (a.result?.risk_score ?? 0));

  if (rows.length === 0) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="No survival predictions yet"
        description="Run a survival prediction from a plant's AI Predictions tab, or check back after a scheduled model pass."
      />
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Plant</TableHead>
          <TableHead>Risk level</TableHead>
          <TableHead>Risk score</TableHead>
          <TableHead>Contributing factors</TableHead>
          <TableHead className="text-right">Generated</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map(({ prediction, result }) => (
          <TableRow key={prediction.id}>
            <TableCell className="font-medium text-foreground">
              {prediction.plant_id ? (
                <Link href={`/plants/${prediction.plant_id}`} className="text-primary hover:underline">
                  {prediction.plant_id}
                </Link>
              ) : (
                "—"
              )}
            </TableCell>
            <TableCell>
              {result?.risk_level ? <Badge tone={RISK_TONE[result.risk_level]}>{result.risk_level}</Badge> : <span>—</span>}
            </TableCell>
            <TableCell>{result?.risk_score != null ? `${result.risk_score}/100` : "—"}</TableCell>
            <TableCell className="text-body-sm text-muted-foreground">{prediction.explanation ?? "—"}</TableCell>
            <TableCell className="text-right text-muted-foreground">{new Date(prediction.created_at).toLocaleDateString()}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
