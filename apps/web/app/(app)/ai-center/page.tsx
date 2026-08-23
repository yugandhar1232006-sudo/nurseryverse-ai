"use client";

import * as React from "react";

import { PermissionDenied } from "@/components/layout/permission-denied";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ALL_BRANCHES, DashboardScopeSelect } from "@/components/dashboards/dashboard-scope-select";
import { SurvivalRiskPanel } from "@/components/ai-center/survival-risk-panel";
import { RevenueForecastPanel } from "@/components/ai-center/revenue-forecast-panel";
import { RecommendationsPanel } from "@/components/ai-center/recommendations-panel";
import { useBranchesQuery, useOrgSettingsQuery } from "@/lib/shell/queries";

/**
 * `/ai-center` -- 7C reserved this route (`nav-config.ts`'s `ai-center`
 * entry, `ai_predictions:read`-gated) with a `ComingSoon` placeholder
 * explicitly deferring to "Phase 7L". This is that phase's real
 * implementation: PG-31 Survival Risk, PG-32 Revenue Forecast, PG-33
 * Recommendation Feed as tabs of one destination -- the same "one real
 * sidebar entry, multiple tabs" pattern 7D's Dashboard uses (see
 * dashboard-content.tsx's docstring), for the identical reason: there is
 * exactly one `ai-center` entry in `NAV_ITEMS`, not three.
 *
 * Distinct from 7D's Dashboard "AI" tab (`components/dashboards/ai-tab.tsx`,
 * `GET /dashboards/ai`): that one is a read-only KPI summary (at-risk
 * count, prediction accuracy ratio) drawing on Module 12's pre-aggregated
 * dashboard rollup. This page is the actual AI *workspace* -- the
 * Module 10 raw prediction/recommendation history, with real on-demand
 * "run" actions (`ai_predictions:run`) this phase adds for the first
 * time anywhere in the frontend. Neither duplicates the other's data
 * source or its permission-gated actions.
 *
 * The branch scope selector reuses `components/dashboards/dashboard-
 * scope-select.tsx`'s `DashboardScopeSelect`/`ALL_BRANCHES` directly
 * (a read-only import, not a modification to 7D's completed files) --
 * that component's own implementation is generic (branches + an "all"
 * sentinel), and every route wrapped here (`survival-risk`,
 * `revenue-forecast`, `recommendations`) accepts the identical optional
 * `branch_id` query parameter shape, so building a second, functionally
 * identical selector would be pure duplication.
 */
export default function AiCenterPage() {
  const branchesQuery = useBranchesQuery();
  const orgSettingsQuery = useOrgSettingsQuery();
  const [scope, setScope] = React.useState<string>(ALL_BRANCHES);

  const branches = branchesQuery.data ?? [];
  const currency = orgSettingsQuery.data?.default_currency ?? "INR";
  const scopeBranchId = scope === ALL_BRANCHES ? null : scope;

  return (
    <PermissionGate permission="ai_predictions:read" fallback={<PermissionDenied />}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-3 tablet:flex-row tablet:items-center tablet:justify-between">
          <h1 className="text-h2 font-semibold text-foreground">AI Center</h1>
          <DashboardScopeSelect branches={branches} value={scope} onChange={setScope} loading={branchesQuery.isLoading} />
        </div>

        <Tabs defaultValue="survival-risk">
          <TabsList className="flex-wrap">
            <TabsTrigger value="survival-risk">Survival Risk</TabsTrigger>
            <TabsTrigger value="revenue-forecast">Revenue Forecast</TabsTrigger>
            <TabsTrigger value="recommendations">Recommendations</TabsTrigger>
          </TabsList>

          <TabsContent value="survival-risk">
            <SurvivalRiskPanel branchId={scopeBranchId} />
          </TabsContent>
          <TabsContent value="revenue-forecast">
            <RevenueForecastPanel branchId={scopeBranchId} currency={currency} />
          </TabsContent>
          <TabsContent value="recommendations">
            <RecommendationsPanel branchId={scopeBranchId} />
          </TabsContent>
        </Tabs>
      </div>
    </PermissionGate>
  );
}
