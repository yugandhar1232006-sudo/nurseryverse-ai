"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import * as aiApi from "@/lib/api/ai-predictions";
import { aiPredictionKeys } from "@/lib/ai-predictions/queries";
import { toast } from "@/lib/toast";

/** FR-8.1 -- always persists an ai_predictions row first (FR-8.7), so a successful call always has a real result to show, never a client-side guess. */
export function useRunDiseaseDetectionMutation(plantId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (imageUrl: string) => aiApi.runDiseaseDetection({ plant_id: plantId, image_url: imageUrl }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: aiPredictionKeys.plantList(plantId, {}) });
      toast.success("Disease detection scan complete");
    },
    onError: (error) => toast.apiError(error),
  });
}

/** FR-8.2 -- on-demand growth prediction for one plant. */
export function useRunGrowthPredictionMutation(plantId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => aiApi.runGrowthPrediction(plantId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: aiPredictionKeys.plantList(plantId, {}) });
      toast.success("Growth prediction generated");
    },
    onError: (error) => toast.apiError(error),
  });
}

/** FR-8.3 -- on-demand survival prediction for one plant. */
export function useRunSurvivalPredictionMutation(plantId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => aiApi.runSurvivalPrediction(plantId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: aiPredictionKeys.plantList(plantId, {}) });
      toast.success("Survival prediction generated");
    },
    onError: (error) => toast.apiError(error),
  });
}

/** FR-8.4 -- on-demand water recommendation for one plant. */
export function useRunWaterRecommendationMutation(plantId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => aiApi.runWaterRecommendation(plantId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: aiPredictionKeys.plantList(plantId, {}) });
      toast.success("Water recommendation generated");
    },
    onError: (error) => toast.apiError(error),
  });
}

/** FR-8.5 -- on-demand revenue forecast for the caller's org, optionally scoped to one branch. */
export function useRunRevenueForecastMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (branchId: string | null) => aiApi.runRevenueForecast(branchId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: aiPredictionKeys.all });
      toast.success("Revenue forecast generated");
    },
    onError: (error) => toast.apiError(error),
  });
}

/** On-demand recommendation refresh for one branch, from its plants' latest Survival Predictions -- see ai_predictions.py's module docstring. */
export function useRefreshRecommendationsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (branchId: string) => aiApi.refreshRecommendations(branchId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: aiPredictionKeys.all });
      toast.success("Recommendations refreshed");
    },
    onError: (error) => toast.apiError(error),
  });
}
