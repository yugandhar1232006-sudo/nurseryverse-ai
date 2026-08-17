# 7L — AI Center

## Route Structure

```
app/(app)/ai-center/page.tsx          ai_predictions:read — AI Center hub (3 tabs)
app/(app)/plants/[id]/page.tsx        plants:read + ai_predictions:read — "AI Predictions" tab
```

`/ai-center` is a single nav entry with 3 tabs: Survival Risk, Revenue Forecast,
Recommendations. The nav item is visible to any role with `ai_predictions:read`.

Per-plant AI predictions live as a tab within `/plants/[id]` (Module 7G's detail page). The
`AiPredictionsTab` component provides per-plant prediction history and run buttons, distinct
from the org-wide AI Center view.

## Architecture

```
lib/api/ai.ts                       Typed wrappers for Module 10 /ai/* routes
lib/ai/queries.ts                   aiPredictionKeys factory + per-endpoint query hooks
lib/ai/mutations.ts                 Mutation hooks for run-prediction and disease-detection
lib/validation/ai.ts                Zod schemas for disease detection + assistant messages

components/ai-center/
  ai-center-content.tsx             Tabbed orchestrator: 3 tabs
  survival-risk-panel.tsx           Org-wide table sorted by risk_score descending
  revenue-forecast-panel.tsx        Recharts chart with confidence bands
  recommendations-panel.tsx         Cards with priority/status badges

components/plants/
  ai-predictions-tab.tsx            Per-plant prediction history + 4 run buttons
  run-prediction-buttons.tsx        Reusable buttons: growth, survival, water, disease detection
```

## Components

`SurvivalRiskPanel` renders a `DataTable` of all plants ranked by `risk_score` descending.
Each row shows plant name, species, risk score, risk factors, and last-updated timestamp.
Client-side sorting is available on all columns. The panel fetches from
`GET /ai/predictions/survival-risk` with optional branch scope.

`RevenueForecastPanel` renders a Recharts `AreaChart` with the forecast line and shaded
confidence bands. Data points include `forecast_month`, `predicted_revenue`, `lower_bound`,
`upper_bound`. The chart is responsive. Scope selector (reuse from 7D dashboards) filters by
branch.

`RecommendationsPanel` renders a card grid. Each card shows recommendation type, description,
priority badge (critical/high/medium/low), status badge (pending/accepted/rejected/dismissed),
and action buttons (accept/reject/dismiss). Data comes from `GET /ai/recommendations`.

`AiPredictionsTab` (per-plant) shows a history table of past predictions for that plant and
4 action buttons: Run Growth Prediction, Run Survival Prediction, Run Water Prediction, Run
Disease Detection. Each button triggers a POST mutation and invalidates the relevant query.

## API Endpoints

```
POST   /ai/disease-detection/scan              Run disease detection on an image
GET    /plants/{id}/predictions                Per-plant prediction history
POST   /plants/{id}/predictions                Trigger a specific prediction for a plant
GET    /plants/{id}/predictions/growth         Growth prediction
GET    /plants/{id}/predictions/survival       Survival prediction
GET    /plants/{id}/predictions/water          Water prediction
POST   /plants/{id}/predictions/growth         Run growth prediction
POST   /plants/{id}/predictions/survival       Run survival prediction
POST   /plants/{id}/predictions/water          Run water prediction
GET    /ai/predictions/survival-risk           Org-wide survival risk rankings
POST   /ai/predictions/survival-risk           Run org-wide survival risk analysis
GET    /ai/predictions/revenue-forecast        Org-wide revenue forecast
POST   /ai/predictions/revenue-forecast        Refresh revenue forecast
GET    /ai/recommendations                     Org-wide recommendations list
POST   /ai/recommendations                     Refresh/regenerate recommendations
```

## Query Keys & Mutations

```
aiPredictionKeys.all                               ['ai-predictions']
aiPredictionKeys.plantPredictions(plantId)         ['ai-predictions', 'plant', plantId]
aiPredictionKeys.plantGrowth(plantId)              ['ai-predictions', 'plant', plantId, 'growth']
aiPredictionKeys.plantSurvival(plantId)            ['ai-predictions', 'plant', plantId, 'survival']
aiPredictionKeys.plantWater(plantId)               ['ai-predictions', 'plant', plantId, 'water']
aiPredictionKeys.survivalRisk(scope?)              ['ai-predictions', 'survival-risk', scope]
aiPredictionKeys.revenueForecast(scope?)           ['ai-predictions', 'revenue-forecast', scope]
aiPredictionKeys.recommendations(scope?)           ['ai-predictions', 'recommendations', scope]
```

Key invalidation pattern: `useRunSurvivalPredictionMutation` invalidates both
`aiPredictionKeys.plantSurvival(plantId)` (per-plant detail) and
`aiPredictionKeys.survivalRisk({})` (org-wide summary), since a single plant's survival
analysis can change its position in the org-wide risk ranking. Other mutations invalidate
only their direct query key.

All run-prediction mutations also invalidate the plant-level `plantKeys.detail(plantId)` to
refresh the plant's summary if any prediction-derived fields appear there.

## Validation

```
runDiseaseDetectionSchema    image_url (required, URL format)
sendAssistantMessageSchema   content (required, max 4000 chars)
```

The `sendAssistantMessageSchema` exists for an AI assistant chat interface (planned future
scope) but is included here for schema completeness. The disease detection schema is the only
one actively used by current UI components.

## Permission Gates

```
ai_predictions:read    /ai-center page visibility + "AI Predictions" tab on plant detail
                       Survival Risk, Revenue Forecast, Recommendations tab content
ai_predictions:run     All "Run" buttons (per-plant prediction buttons, forecast refresh,
                       recommendations refresh, disease detection scan)
```

`ai_predictions:read` is the minimum to see the AI Center page and its tabs.
`ai_predictions:run` gates every action that triggers a new prediction or analysis. A user
with `read` but not `run` sees historical results but cannot trigger new ones.

The `/ai-center` nav entry in `nav-config.ts` is gated on `ai_predictions:read`. The plant
detail "AI Predictions" tab is additionally gated on `plants:read` (the parent route's own
permission).

## Patterns

- **Hand-written result interfaces.** The backend OpenAPI schema emits prediction results as
  opaque `dict[str, Any]` -- no typed fields. The frontend defines its own interfaces
  (`SurvivalRiskResult`, `RevenueForecastResult`, etc.) based on the actual response shape.
  Only 2 of 5 prediction types (survival risk, revenue forecast) are fully hand-typed; the
  remaining 3 (growth, water, disease detection) use looser typing since their UI surfaces
  are simpler.
- **Client-side sorting.** Survival risk table sorting is done in the browser, not via API
  parameters. The dataset is small enough (hundreds of plants, not millions) that client-side
  sort is practical and avoids backend pagination complexity.
- **Scope selector reuse.** Revenue Forecast and Recommendations panels reuse
  `DashboardScopeSelect` from 7D for branch filtering, maintaining consistency with the
  dashboard experience rather than building a separate branch picker.
- **Only 2 of 5 prediction types hand-typed.** Growth, water, and disease detection results
  are rendered with generic fallbacks (display raw fields) because their schemas are simpler
  and less stable across backend iterations. Survival risk and revenue forecast have
  dedicated chart/table components that require stable types.

## Known Limitations

- Prediction result types are partially hand-written against an opaque backend schema. If the
  backend changes response shapes, the frontend types may silently mismatch until a runtime
  error surfaces. No schema-level contract enforcement exists for the 3 loosely-typed
  prediction types.
- Revenue forecast chart has no date-range picker -- it shows whatever the backend returns as
  the default forecast window. A date-range control would require backend support for
  custom forecast periods.
- Disease detection requires a pre-existing image URL. There is no upload flow -- the user
  must provide a URL to an image already hosted somewhere. This matches the same URL-only
  pattern from 7G's plant images.
- The AI assistant chat interface (`sendAssistantMessageSchema`) has no UI yet. The schema is
  defined for forward compatibility but no component consumes it.
- Recommendations have accept/reject/dismiss actions but no "details" drill-down. The card
  shows a summary; full recommendation details would require additional backend endpoints.

## Test Coverage

- **Playwright** (`e2e/ai-center.spec.ts`, 3 tests): run a survival prediction from the plant
  detail page and see results; navigate to AI Center hub and verify tabs render; send an
  assistant message (schema-level test, no full chat UI). All use real org + plant creation.
  Written and collected; **not execution-verified** in this sandbox.
- **Vitest/RTL** (`components/ai-center/__tests__/`, 12 tests across 3 test files):
  - `survival-risk.test.tsx`: table rendering sorted by risk score, empty state, permission
    gating on run button, client-side column sorting
  - `revenue-forecast.test.tsx`: chart rendering with mock data, loading skeleton, scope
    selector filtering, confidence band labels
  - `recommendations.test.tsx`: card rendering with priority/status badges, accept/reject
    actions invalidating query, empty state for no recommendations, permission gating on
    action buttons
- **Full regression**: all prior suites plus the new 12 tests pass. `npx tsc --noEmit` clean.
  `npx eslint .` clean.
