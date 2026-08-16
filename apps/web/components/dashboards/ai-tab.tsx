"use client";

import { Sparkles, Target } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { KpiCard, KpiCardGrid } from "@/components/dashboards/kpi-card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAIDashboardQuery } from "@/lib/dashboards/queries";
import { formatNumber, formatPercent } from "@/lib/utils";

/**
 * `GET /dashboards/ai` -- real, previously-generated `AIPrediction` rows
 * (see AtRiskPlantResponse's own docstring on the backend: this never
 * runs a model inline, only reads what a prior prediction job already
 * persisted) plus a real correct/scored ratio. Per the 7L/7H kickoff's
 * AI-honesty rules (which apply to every AI-adjacent surface, not only
 * the dedicated AI Center): a raw model `confidence` score is labeled
 * "Confidence score," never "probability" or "accuracy" -- it's the
 * model's own self-reported score, not a calibrated statistical
 * guarantee. "Accuracy" below is a real, computed ratio
 * (correct_prediction_count / scored_prediction_count) over predictions
 * that have actually been scored against a real outcome -- not the same
 * thing as the model's per-prediction confidence.
 */
export function AITab({ branchId }: { branchId: string | null }) {
  const query = useAIDashboardQuery(branchId, true);

  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  }

  const data = query.data;
  const accuracy = data?.prediction_accuracy;
  const accuracyRatio =
    accuracy && accuracy.scored_prediction_count > 0 ? accuracy.correct_prediction_count / accuracy.scored_prediction_count : null;

  return (
    <div className="flex flex-col gap-4">
      <KpiCardGrid className="tablet:grid-cols-2 laptop:grid-cols-3">
        <KpiCard
          label="At-risk plants flagged"
          value={data ? formatNumber(data.at_risk_plants.length) : ""}
          icon={Sparkles}
          tone="warning"
          loading={query.isLoading}
        />
        <KpiCard
          label="Scored predictions"
          value={accuracy ? formatNumber(accuracy.scored_prediction_count) : "0"}
          icon={Target}
          loading={query.isLoading}
        />
        <KpiCard
          label="Prediction accuracy"
          value={accuracyRatio !== null ? formatPercent(accuracyRatio) : "Not enough data yet"}
          icon={Target}
          tone="info"
          hint={accuracy ? `${formatNumber(accuracy.correct_prediction_count)} of ${formatNumber(accuracy.scored_prediction_count)} scored predictions were correct` : undefined}
          loading={query.isLoading}
        />
      </KpiCardGrid>

      <Card>
        <CardHeader>
          <CardTitle>Plants flagged at risk by AI</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-3 text-caption text-muted-foreground">
            AI-generated risk flags, not confirmed diagnoses. Review each plant&apos;s full record before acting.
          </p>
          {query.isLoading ? (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : !data || data.at_risk_plants.length === 0 ? (
            <EmptyState icon={Sparkles} title="No plants currently flagged" description="AI has not flagged any plants as at-risk in this scope." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Plant</TableHead>
                  <TableHead>Confidence score</TableHead>
                  <TableHead className="text-right">Flagged</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.at_risk_plants.map((p) => (
                  <TableRow key={p.plant_id}>
                    <TableCell className="font-medium text-foreground">{p.common_label ?? p.plant_id}</TableCell>
                    <TableCell>
                      {p.confidence !== null && p.confidence !== undefined ? (
                        <Badge tone="ai">{formatPercent(p.confidence)}</Badge>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right text-muted-foreground">{new Date(p.created_at).toLocaleDateString()}</TableCell>
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
