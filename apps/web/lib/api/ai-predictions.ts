import { apiClient, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

/**
 * Thin typed wrappers for Module 10's AI Predictions surface
 * (`ai_predictions.py`) -- the six prediction modules (Disease Detection,
 * Growth, Survival, Water, Revenue Forecast) plus the Recommendation
 * Engine's list/refresh routes. Every route here requires authentication
 * and real `ai_predictions:read`/`ai_predictions:run` permission, unlike
 * 7K's public passport routes.
 *
 * Deliberately NOT wrapped here, because no such route exists server-side
 * (confirmed via direct `grep` against `schema.d.ts`, not assumed from
 * docs/ux/09-page-inventory.md's page descriptions, which reference some
 * of these as if they existed):
 *  - `GET /ai/predictions/growth-summary` (PG-31 cites this; the real
 *    backend only has per-plant `POST /plants/{id}/ai-predictions/growth`
 *    and the shared history route below, no org-wide growth summary).
 *  - `GET /ai/predictions/summary` (PG-07 Executive Dashboard cites
 *    this; 7D's dashboards module uses the real `GET /dashboards/ai`
 *    Module 12 route instead, which is a different, already-built
 *    surface -- see components/dashboards/ai-tab.tsx).
 *  - `POST /ai/recommendations/{id}/dismiss` (PG-33 cites this; no
 *    dismiss/act route exists in `ai_predictions.py` at all -- only
 *    list and refresh). See docs/frontend/16-ai-experience.md's Known
 *    Limitations for what this means for the Recommendation Feed UI.
 */

export type AIPredictionResponse = components["schemas"]["AIPredictionResponse"];
export type AIRecommendationResponse = components["schemas"]["AIRecommendationResponse"];

/**
 * `AIPredictionResponse.result` is `dict[str, Any]` on the backend (no
 * sub-schema), so the generated client type is opaque (`Record<string,
 * never>`) -- the same situation as `TwinSnapshot`/`PassportContent` in
 * 7H/7K. These two hand-written interfaces mirror the *real* shapes each
 * inference module actually returns (read directly from
 * `apps/api/app/ai/survival_prediction/inference.py`'s and
 * `.../revenue_forecast/inference.py`'s `predict()`/`postprocess()`
 * bodies, not guessed), cast via `result as unknown as SurvivalPrediction
 * Result` at each call site -- used by `/ai-center`'s Survival Risk and
 * Revenue Forecast panels to render real risk scores and a real forecast
 * chart instead of only the generic explanation text every prediction
 * type shares. The other three prediction types' result shapes are not
 * hand-written (out of scope -- see ai-predictions-tab.tsx's docstring).
 */
export interface SurvivalPredictionResult {
  risk_score: number;
  risk_level: "low" | "moderate" | "high" | "critical";
  factors: {
    latest_health_status: string | null;
    health_risk_contribution: number;
    disease_risk_contribution: number;
    environmental_variance_risk_contribution: number;
    watering_risk_contribution: number;
    days_since_last_watering: number | null;
    disease_report_count: number;
  };
  data_points_used: number;
}

export interface RevenueForecastResult {
  method: "seasonal_naive" | "insufficient_data";
  data_points_used: number;
  overall_mean_daily_revenue?: number;
  overall_stdev_daily_revenue?: number;
  forecast: Array<{ date: string; projected_revenue: number; lower_bound: number; upper_bound: number }>;
}
export type PageAIPredictionResponse = components["schemas"]["Page_AIPredictionResponse_"];
export type PageAIRecommendationResponse = components["schemas"]["Page_AIRecommendationResponse_"];
export type RunDiseaseDetectionRequest = components["schemas"]["RunDiseaseDetectionRequest"];
export type AIPredictionType = components["schemas"]["AIPredictionType"];
export type AIRecommendationStatus = components["schemas"]["AIRecommendationStatus"];

/** FR-8.1 -- always persists an `ai_predictions` row before returning, per FR-8.7 (enforced server-side, not by this wrapper). */
export async function runDiseaseDetection(body: RunDiseaseDetectionRequest): Promise<AIPredictionResponse> {
  return unwrap(() => apiClient.POST("/api/v1/ai/disease-detection/scan", { body }));
}

/** FR-8.8 -- every prediction ever generated for this plant, across all five prediction types, newest first. */
export async function listPlantAiPredictions(
  plantId: string,
  params: { page?: number; page_size?: number; prediction_type?: AIPredictionType } = {},
): Promise<PageAIPredictionResponse> {
  return unwrap(() =>
    apiClient.GET("/api/v1/plants/{plant_id}/ai-predictions", {
      params: { path: { plant_id: plantId }, query: params },
    }),
  );
}

/** FR-8.2 -- runs on-demand against this plant's real growth_timeline + species baseline; always persists first. */
export async function runGrowthPrediction(plantId: string): Promise<AIPredictionResponse> {
  return unwrap(() => apiClient.POST("/api/v1/plants/{plant_id}/ai-predictions/growth", { params: { path: { plant_id: plantId } } }));
}

/** FR-8.3 -- runs on-demand for this specific plant (distinct from the org/branch-wide survival-risk list below). */
export async function runSurvivalPrediction(plantId: string): Promise<AIPredictionResponse> {
  return unwrap(() => apiClient.POST("/api/v1/plants/{plant_id}/ai-predictions/survival", { params: { path: { plant_id: plantId } } }));
}

/** FR-8.4 -- runs on-demand from this plant's real species baseline + recent environmental/watering history. */
export async function runWaterRecommendation(plantId: string): Promise<AIPredictionResponse> {
  return unwrap(() => apiClient.POST("/api/v1/plants/{plant_id}/ai-predictions/water", { params: { path: { plant_id: plantId } } }));
}

/** FR-8.3 -- Survival Prediction history across the caller's org, optionally filtered to one branch (PG-31's ranked at-risk list). */
export async function listSurvivalRisk(params: {
  page?: number;
  page_size?: number;
  branch_id?: string;
}): Promise<PageAIPredictionResponse> {
  return unwrap(() => apiClient.GET("/api/v1/ai/predictions/survival-risk", { params: { query: params } }));
}

/** FR-8.5 -- runs on demand for the caller's org (optionally one branch); always persists first (PG-32). */
export async function runRevenueForecast(branchId: string | null): Promise<AIPredictionResponse> {
  return unwrap(() =>
    apiClient.POST("/api/v1/ai/predictions/revenue-forecast", { params: { query: branchId ? { branch_id: branchId } : {} } }),
  );
}

/** FR-8.5 -- Revenue Forecast history for the caller's org, optionally filtered to one branch, newest first. */
export async function listRevenueForecasts(params: {
  page?: number;
  page_size?: number;
  branch_id?: string;
}): Promise<PageAIPredictionResponse> {
  return unwrap(() => apiClient.GET("/api/v1/ai/predictions/revenue-forecast", { params: { query: params } }));
}

/** FR-8.6 -- lists persisted recommendations (PG-33's Recommendation Feed); no dismiss/act route exists server-side, see this file's docstring. */
export async function listRecommendations(params: {
  page?: number;
  page_size?: number;
  branch_id?: string;
  status_filter?: AIRecommendationStatus;
}): Promise<PageAIRecommendationResponse> {
  return unwrap(() => apiClient.GET("/api/v1/ai/recommendations", { params: { query: params } }));
}

/** On-demand refresh for one branch from its plants' latest Survival Predictions -- see ai_predictions.py's module docstring on why this endpoint exists at all. */
export async function refreshRecommendations(branchId: string): Promise<AIRecommendationResponse[]> {
  return unwrap(() => apiClient.POST("/api/v1/ai/recommendations/refresh", { params: { query: { branch_id: branchId } } }));
}
