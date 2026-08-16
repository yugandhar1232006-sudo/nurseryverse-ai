"use client";

import { useQuery } from "@tanstack/react-query";

import * as plantsApi from "@/lib/api/plants";
import * as recordsApi from "@/lib/api/plant-records";
import * as diseaseApi from "@/lib/api/disease-reports";
import { useSessionStore } from "@/store/session-store";

/** Query key factory for 7G's Plant Lifecycle reads. */
export const plantKeys = {
  all: ["plants"] as const,
  list: (params: plantsApi.ListPlantsParams) => [...plantKeys.all, "list", params] as const,
  detail: (id: string) => [...plantKeys.all, "detail", id] as const,
  images: (id: string) => [...plantKeys.all, "images", id] as const,
  timeline: (id: string, page: number) => [...plantKeys.all, "timeline", id, page] as const,
  movementHistory: (id: string) => [...plantKeys.all, "movement-history", id] as const,
  growth: (id: string, page: number) => [...plantKeys.all, "growth", id, page] as const,
  health: (id: string, page: number) => [...plantKeys.all, "health", id, page] as const,
  watering: (id: string, page: number) => [...plantKeys.all, "watering", id, page] as const,
  fertilizer: (id: string, page: number) => [...plantKeys.all, "fertilizer", id, page] as const,
  environmental: (id: string, page: number) => [...plantKeys.all, "environmental", id, page] as const,
  diseaseReports: (plantId: string) => [...plantKeys.all, "disease-reports", plantId] as const,
  treatments: (reportId: string) => [...plantKeys.all, "treatments", reportId] as const,
};

export function usePlantsListQuery(params: plantsApi.ListPlantsParams) {
  const orgId = useSessionStore((state) => state.user?.org_id ?? null);

  return useQuery({
    queryKey: plantKeys.list(params),
    queryFn: () => plantsApi.listPlants(params),
    enabled: orgId !== null,
    staleTime: 15 * 1000,
  });
}

export function usePlantDetailQuery(id: string | null) {
  return useQuery({
    queryKey: plantKeys.detail(id ?? "none"),
    queryFn: () => plantsApi.getPlant(id as string),
    enabled: id !== null,
    staleTime: 15 * 1000,
  });
}

export function usePlantImagesQuery(id: string | null) {
  return useQuery({
    queryKey: plantKeys.images(id ?? "none"),
    queryFn: () => plantsApi.listPlantImages(id as string),
    enabled: id !== null,
  });
}

export function usePlantTimelineQuery(id: string | null, page: number) {
  return useQuery({
    queryKey: plantKeys.timeline(id ?? "none", page),
    queryFn: () => plantsApi.getPlantTimeline(id as string, page),
    enabled: id !== null,
  });
}

export function useMovementHistoryQuery(id: string | null) {
  return useQuery({
    queryKey: plantKeys.movementHistory(id ?? "none"),
    queryFn: () => plantsApi.getMovementHistory(id as string),
    enabled: id !== null,
  });
}

export function useGrowthQuery(id: string | null, page: number) {
  return useQuery({
    queryKey: plantKeys.growth(id ?? "none", page),
    queryFn: () => recordsApi.listGrowth(id as string, page),
    enabled: id !== null,
  });
}

export function useHealthQuery(id: string | null, page: number) {
  return useQuery({
    queryKey: plantKeys.health(id ?? "none", page),
    queryFn: () => recordsApi.listHealth(id as string, page),
    enabled: id !== null,
  });
}

export function useWateringQuery(id: string | null, page: number) {
  return useQuery({
    queryKey: plantKeys.watering(id ?? "none", page),
    queryFn: () => recordsApi.listWatering(id as string, page),
    enabled: id !== null,
  });
}

export function useFertilizerQuery(id: string | null, page: number) {
  return useQuery({
    queryKey: plantKeys.fertilizer(id ?? "none", page),
    queryFn: () => recordsApi.listFertilizer(id as string, page),
    enabled: id !== null,
  });
}

export function useEnvironmentalQuery(id: string | null, page: number) {
  return useQuery({
    queryKey: plantKeys.environmental(id ?? "none", page),
    queryFn: () => recordsApi.listEnvironmental(id as string, page),
    enabled: id !== null,
  });
}

export function useDiseaseReportsQuery(plantId: string | null) {
  return useQuery({
    queryKey: plantKeys.diseaseReports(plantId ?? "none"),
    queryFn: () => diseaseApi.listDiseaseReportsForPlant(plantId as string),
    enabled: plantId !== null,
  });
}

/** On-demand only (e.g. expanding a report's treatment history) -- never fetched eagerly per report row. */
export function useTreatmentsQuery(reportId: string | null) {
  return useQuery({
    queryKey: plantKeys.treatments(reportId ?? "none"),
    queryFn: () => diseaseApi.listTreatments(reportId as string),
    enabled: reportId !== null,
  });
}
