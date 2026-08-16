"use client";

import Link from "next/link";
import { RefreshCw, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { useRecommendationsQuery } from "@/lib/ai-predictions/queries";
import { useRefreshRecommendationsMutation } from "@/lib/ai-predictions/mutations";
import type { AIRecommendationResponse } from "@/lib/api/ai-predictions";

const PRIORITY_TONE: Record<string, "success" | "warning" | "danger" | "info"> = {
  low: "info",
  medium: "warning",
  high: "danger",
  critical: "danger",
};

const STATUS_LABEL: Record<AIRecommendationResponse["status"], string> = {
  new: "New",
  dismissed: "Dismissed",
  acted_upon: "Acted upon",
};

/**
 * PG-33 Recommendation Feed -- `GET /ai/recommendations` + `POST
 * /ai/recommendations/refresh`. Real dismiss/act state (`status`) is
 * shown as a badge, but there is deliberately no dismiss/snooze *button*
 * here: no `POST /ai/recommendations/{id}/dismiss` (or any other write)
 * route exists in `ai_predictions.py` -- only list and refresh. Building
 * a dismiss control that silently did nothing, or called a route that
 * doesn't exist, would be exactly the "fake functionality" the kickoff
 * prohibits. See lib/api/ai-predictions.ts's docstring and
 * docs/frontend/16-ai-experience.md's Known Limitations.
 *
 * Refresh requires a specific branch (the real route's `branch_id` query
 * param is required, not optional) -- disabled with an explanatory state
 * when the page's scope selector is on "All branches."
 */
export function RecommendationsPanel({ branchId }: { branchId: string | null }) {
  const query = useRecommendationsQuery({ page: 1, page_size: 50, branch_id: branchId ?? undefined });
  const refreshMutation = useRefreshRecommendationsMutation();

  if (query.isLoading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-full" />
        ))}
      </div>
    );
  }

  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  }

  const recommendations = query.data?.items ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <p className="text-body-sm text-muted-foreground">
          {branchId ? "Prioritized, explained AI action suggestions for this branch." : "Select a specific branch to refresh recommendations."}
        </p>
        <PermissionGate permission="ai_predictions:run">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={!branchId || refreshMutation.isPending}
            onClick={() => branchId && refreshMutation.mutate(branchId)}
          >
            {refreshMutation.isPending ? <Spinner className="text-current" /> : <RefreshCw className="size-4" aria-hidden="true" />}
            Refresh recommendations
          </Button>
        </PermissionGate>
      </div>

      {recommendations.length === 0 ? (
        <EmptyState
          icon={Sparkles}
          title="No recommendations yet"
          description="Refresh above (with a specific branch selected) to generate recommendations from the latest survival predictions."
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {recommendations.map((rec) => (
            <li key={rec.id} className="flex flex-col gap-2 rounded-md border border-border p-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={PRIORITY_TONE[rec.priority] ?? "info"}>{rec.priority}</Badge>
                <Badge variant="outline">{STATUS_LABEL[rec.status]}</Badge>
                <span className="ml-auto text-caption text-muted-foreground">{new Date(rec.created_at).toLocaleDateString()}</span>
              </div>
              <p className="text-body-sm font-medium text-foreground">{rec.summary}</p>
              {rec.explanation && <p className="text-body-sm text-muted-foreground">{rec.explanation}</p>}
              {rec.deep_link && (
                <Link href={rec.deep_link} className="w-fit text-body-sm text-primary hover:underline">
                  View details
                </Link>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
