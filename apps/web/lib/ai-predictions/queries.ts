"use client";

import { useQuery } from "@tanstack/react-query";

import * as aiApi from "@/lib/api/ai-predictions";

/** Query key factory for 7L's AI Predictions reads. */
export const aiPredictionKeys = {
  all: ["ai-predictions"] as const,
  plantList: (plantId: string, params: { page?: number; prediction_type?: string }) =>
    [...aiPredictionKeys.all, "plant-list", plantId, params] as const,
  survivalRisk: (params: { page?: number; page_size?: number; branch_id?: string }) =>
    [...aiPredictionKeys.all, "survival-risk", params] as const,
  revenueForecasts: (params: { page?: number; page_size?: number; branch_id?: string }) =>
    [...aiPredictionKeys.all, "revenue-forecasts", params] as const,
  recommendations: (params: { page?: number; page_size?: number; branch_id?: string; status_filter?: string }) =>
    [...aiPredictionKeys.all, "recommendations", params] as const,
};

/** FR-8.8 -- full prediction history for one plant (PG-26), across all five prediction types. */
export function usePlantAiPredictionsQuery(
  plantId: string | null,
  params: { page?: number; prediction_type?: aiApi.AIPredictionType } = {},
) {
  return useQuery({
    queryKey: aiPredictionKeys.plantList(plantId ?? "none", params),
    queryFn: () => aiApi.listPlantAiPredictions(plantId as string, params),
    enabled: plantId !== null,
  });
}

/** FR-8.3 -- org/branch-wide Survival Prediction history, newest first (PG-31). */
export function useSurvivalRiskQuery(params: { page?: number; page_size?: number; branch_id?: string }) {
  return useQuery({
    queryKey: aiPredictionKeys.survivalRisk(params),
    queryFn: () => aiApi.listSurvivalRisk(params),
  });
}

/** FR-8.5 -- org/branch-wide Revenue Forecast history, newest first (PG-32). */
export function useRevenueForecastsQuery(params: { page?: number; page_size?: number; branch_id?: string }) {
  return useQuery({
    queryKey: aiPredictionKeys.revenueForecasts(params),
    queryFn: () => aiApi.listRevenueForecasts(params),
  });
}

/** FR-8.6 -- persisted recommendations for the caller's org, optionally one branch/status (PG-33). */
export function useRecommendationsQuery(params: {
  page?: number;
  page_size?: number;
  branch_id?: string;
  status_filter?: aiApi.AIRecommendationStatus;
}) {
  return useQuery({
    queryKey: aiPredictionKeys.recommendations(params),
    queryFn: () => aiApi.listRecommendations(params),
  });
}
