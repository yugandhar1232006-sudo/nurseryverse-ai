"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Bug, Droplets, HeartPulse, Sparkles, TrendingUp } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { PermissionGate } from "@/components/auth/permission-gate";
import { RecordEntryList } from "@/components/plants/record-entry-list";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { usePlantAiPredictionsQuery } from "@/lib/ai-predictions/queries";
import {
  useRunDiseaseDetectionMutation,
  useRunGrowthPredictionMutation,
  useRunSurvivalPredictionMutation,
  useRunWaterRecommendationMutation,
} from "@/lib/ai-predictions/mutations";
import { runDiseaseDetectionSchema, type RunDiseaseDetectionFormValues } from "@/lib/validation/ai";
import type { AIPredictionResponse, AIPredictionType } from "@/lib/api/ai-predictions";

const TYPE_LABELS: Record<AIPredictionType, string> = {
  disease_detection: "Disease detection",
  growth_prediction: "Growth prediction",
  survival_prediction: "Survival prediction",
  water_recommendation: "Water recommendation",
  revenue_forecast: "Revenue forecast",
};

const ALL_TYPES = "__all__";
const DISEASE_DEFAULTS: RunDiseaseDetectionFormValues = { image_url: "" };

function formatConfidence(confidence: string | null): string {
  if (confidence === null) return "—";
  const n = Number(confidence);
  return Number.isFinite(n) ? `${(n * 100).toFixed(0)}%` : "—";
}

/**
 * PG-26 AI Predictions (tab) + PG-28 AI Disease Detection Scan, both on
 * the existing `/plants/[id]` page -- an additive tab, matching how 7K's
 * Passport tab was added (see that phase's docs on why "genuinely
 * required" additions to a completed-but-not-frozen page are allowed).
 * `TwinOverview` (7H) explicitly defers here: "The full AI prediction
 * history lives in the AI Experience module" -- this is that module's
 * per-plant half; the org-wide half is `/ai-center`.
 *
 * All five on-demand triggers below (growth/survival/water/disease scan)
 * share the exact same real permission, `ai_predictions:run` -- verified
 * directly against `ai_predictions.py`'s route bodies, not assumed from
 * docs/ux/09-page-inventory.md's PG-28 entry, which claims disease scan
 * additionally requires `disease:write` (the real route's
 * `run_disease_detection` only ever checks `ai_predictions:run`, a single
 * permission, via `_authorize_plant`). Documented as a real doc/code
 * discrepancy in docs/frontend/16-ai-experience.md, not silently
 * "corrected" by gating on both.
 *
 * `AIPredictionResponse.result` is an opaque `dict[str, Any]` whose shape
 * differs per prediction type (five different result shapes) -- unlike
 * 7H/7K's single-shape `TwinSnapshot`/`PassportContent` casts, hand-
 * writing five separate result interfaces for a read-only history list
 * was judged out of scope for this phase; `confidence`/`explanation`/
 * `model_version` (the three fields every module always populates per
 * the AI Prediction Logging Contract, docs/ux/12-ai-workflow-diagrams.md)
 * are shown instead. See Known Limitations.
 */
export function AiPredictionsTab({ plantId }: { plantId: string }) {
  const [page, setPage] = React.useState(1);
  const [typeFilter, setTypeFilter] = React.useState<string>(ALL_TYPES);
  const [scanOpen, setScanOpen] = React.useState(false);

  const query = usePlantAiPredictionsQuery(plantId, {
    page,
    prediction_type: typeFilter === ALL_TYPES ? undefined : (typeFilter as AIPredictionType),
  });

  const growthMutation = useRunGrowthPredictionMutation(plantId);
  const survivalMutation = useRunSurvivalPredictionMutation(plantId);
  const waterMutation = useRunWaterRecommendationMutation(plantId);
  const scanMutation = useRunDiseaseDetectionMutation(plantId);

  const scanForm = useForm<RunDiseaseDetectionFormValues>({
    resolver: zodResolver(runDiseaseDetectionSchema),
    defaultValues: DISEASE_DEFAULTS,
  });
  const handleScanApiError = useApiFormErrors(scanForm.setError);

  // Render-body "adjusting state" pattern (bare open/closed-transition
  // variant -- see passport-tab.tsx's identical use for why this variant,
  // not the content-signature one, is correct for a simple field reset
  // with no async data dependency).
  const [syncedScanOpen, setSyncedScanOpen] = React.useState(false);
  if (scanOpen && !syncedScanOpen) {
    setSyncedScanOpen(true);
    scanForm.reset(DISEASE_DEFAULTS);
  } else if (!scanOpen && syncedScanOpen) {
    setSyncedScanOpen(false);
  }

  function onSubmitScan(values: RunDiseaseDetectionFormValues) {
    scanMutation.mutate(values.image_url, { onSuccess: () => setScanOpen(false), onError: handleScanApiError });
  }

  const anyRunPending = growthMutation.isPending || survivalMutation.isPending || waterMutation.isPending;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 tablet:flex-row tablet:items-center tablet:justify-between">
        <p className="text-body-sm text-muted-foreground">
          Every AI prediction ever generated for this plant, across all prediction types (FR-8.8).
        </p>
        <Select
          value={typeFilter}
          onValueChange={(v) => {
            setTypeFilter(v);
            setPage(1);
          }}
        >
          <SelectTrigger size="sm" aria-label="Filter by prediction type" className="w-full tablet:w-56">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_TYPES}>All prediction types</SelectItem>
            {(Object.keys(TYPE_LABELS) as AIPredictionType[]).map((t) => (
              <SelectItem key={t} value={t}>
                {TYPE_LABELS[t]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <PermissionGate permission="ai_predictions:run">
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-ai-accent-200 bg-ai-accent-50 p-3">
          <Badge tone="ai">AI</Badge>
          <Button type="button" variant="outline" size="sm" disabled={anyRunPending} onClick={() => growthMutation.mutate()}>
            {growthMutation.isPending ? <Spinner className="text-current" /> : <TrendingUp className="size-4" aria-hidden="true" />}
            Run growth prediction
          </Button>
          <Button type="button" variant="outline" size="sm" disabled={anyRunPending} onClick={() => survivalMutation.mutate()}>
            {survivalMutation.isPending ? <Spinner className="text-current" /> : <HeartPulse className="size-4" aria-hidden="true" />}
            Run survival prediction
          </Button>
          <Button type="button" variant="outline" size="sm" disabled={anyRunPending} onClick={() => waterMutation.mutate()}>
            {waterMutation.isPending ? <Spinner className="text-current" /> : <Droplets className="size-4" aria-hidden="true" />}
            Run water recommendation
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={() => setScanOpen(true)}>
            <Bug className="size-4" aria-hidden="true" />
            Scan for disease
          </Button>
        </div>
      </PermissionGate>

      <RecordEntryList<AIPredictionResponse>
        icon={Sparkles}
        emptyTitle="No AI predictions yet"
        emptyDescription="Run a prediction above, or check back after a scheduled model pass."
        items={query.data?.items ?? []}
        isLoading={query.isLoading}
        isError={query.isError}
        error={query.error}
        onRetry={() => query.refetch()}
        retrying={query.isFetching}
        page={page}
        totalPages={query.data?.meta.total_pages ?? 1}
        onPageChange={setPage}
        renderItem={(prediction) => (
          <div className="flex flex-col gap-1">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="ai">{TYPE_LABELS[prediction.prediction_type]}</Badge>
              <span className="text-body-sm text-muted-foreground">Confidence score: {formatConfidence(prediction.confidence)}</span>
              <span className="text-caption text-muted-foreground">Model {prediction.model_version}</span>
            </div>
            {prediction.explanation && <p className="text-body-sm text-foreground">{prediction.explanation}</p>}
            <p className="text-caption text-muted-foreground">{new Date(prediction.created_at).toLocaleString()}</p>
          </div>
        )}
      />

      <Dialog open={scanOpen} onOpenChange={setScanOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Scan for disease</DialogTitle>
            <DialogDescription>
              Runs AI Disease Detection against an already-hosted plant photo. A result is always persisted, even a low-confidence one
              (FR-8.7) -- there is no binary upload here, matching this backend&apos;s real URL-registration contract (see 7G&apos;s
              Images tab).
            </DialogDescription>
          </DialogHeader>
          <Form {...scanForm}>
            <form onSubmit={scanForm.handleSubmit(onSubmitScan)} className="flex flex-col gap-4" noValidate>
              <FormField
                control={scanForm.control}
                name="image_url"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Photo URL</FormLabel>
                    <FormControl>
                      <Input placeholder="https://…" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setScanOpen(false)} disabled={scanMutation.isPending}>
                  Cancel
                </Button>
                <Button type="submit" disabled={scanMutation.isPending} aria-busy={scanMutation.isPending}>
                  {scanMutation.isPending && <Spinner className="text-current" />}
                  Run scan
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
