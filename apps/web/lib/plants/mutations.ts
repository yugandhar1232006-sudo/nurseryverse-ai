"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import * as plantsApi from "@/lib/api/plants";
import * as recordsApi from "@/lib/api/plant-records";
import * as diseaseApi from "@/lib/api/disease-reports";
import { plantKeys } from "@/lib/plants/queries";
import { toast } from "@/lib/toast";

function invalidatePlant(queryClient: ReturnType<typeof useQueryClient>, plantId: string) {
  void queryClient.invalidateQueries({ queryKey: plantKeys.detail(plantId) });
  void queryClient.invalidateQueries({ queryKey: ["plants", "list"] });
}

export function useRegisterPlantMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: plantsApi.registerPlant,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["plants", "list"] });
      toast.success("Plant registered");
    },
  });
}

export function useUpdatePlantProfileMutation(plantId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: plantsApi.UpdatePlantProfileRequest) => plantsApi.updatePlantProfile(plantId, body),
    onSuccess: () => {
      invalidatePlant(queryClient, plantId);
      toast.success("Plant profile updated");
    },
  });
}

/** A 409 (illegal transition per docs/ux/13-digital-twin-lifecycle.md's state machine) surfaces as a real API error toast, not a silently-ignored click. */
export function useTransitionStatusMutation(plantId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: plantsApi.TransitionStatusRequest) => plantsApi.transitionPlantStatus(plantId, body),
    onSuccess: () => {
      invalidatePlant(queryClient, plantId);
      void queryClient.invalidateQueries({ queryKey: plantKeys.timeline(plantId, 1) });
      toast.success("Status updated");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useMovePlantMutation(plantId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: plantsApi.MovePlantRequest) => plantsApi.movePlant(plantId, body),
    onSuccess: () => {
      invalidatePlant(queryClient, plantId);
      void queryClient.invalidateQueries({ queryKey: plantKeys.movementHistory(plantId) });
      void queryClient.invalidateQueries({ queryKey: plantKeys.timeline(plantId, 1) });
      toast.success("Plant moved");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useArchivePlantMutation(plantId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: plantsApi.ArchivePlantRequest) => plantsApi.archivePlant(plantId, body),
    onSuccess: () => {
      invalidatePlant(queryClient, plantId);
      toast.success("Plant archived");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useUploadPlantImageMutation(plantId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: plantsApi.UploadPlantImageRequest) => plantsApi.uploadPlantImage(plantId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: plantKeys.images(plantId) });
      toast.success("Image added");
    },
  });
}

export function useRecordGrowthMutation(plantId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: recordsApi.RecordGrowthRequest) => recordsApi.recordGrowth(plantId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...plantKeys.all, "growth", plantId] });
      void queryClient.invalidateQueries({ queryKey: plantKeys.timeline(plantId, 1) });
      toast.success("Growth measurement recorded");
    },
  });
}

export function useRecordHealthMutation(plantId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: recordsApi.RecordHealthRequest) => recordsApi.recordHealth(plantId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...plantKeys.all, "health", plantId] });
      void queryClient.invalidateQueries({ queryKey: plantKeys.timeline(plantId, 1) });
      toast.success("Health observation recorded");
    },
  });
}

export function useRecordWateringMutation(plantId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: recordsApi.RecordWateringRequest) => recordsApi.recordWatering(plantId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...plantKeys.all, "watering", plantId] });
      void queryClient.invalidateQueries({ queryKey: plantKeys.timeline(plantId, 1) });
      toast.success("Watering event recorded");
    },
  });
}

export function useRecordFertilizerMutation(plantId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: recordsApi.RecordFertilizerRequest) => recordsApi.recordFertilizer(plantId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...plantKeys.all, "fertilizer", plantId] });
      void queryClient.invalidateQueries({ queryKey: plantKeys.timeline(plantId, 1) });
      toast.success("Fertilizer application recorded");
    },
  });
}

export function useRecordEnvironmentalMutation(plantId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: recordsApi.RecordEnvironmentalRequest) => recordsApi.recordEnvironmental(plantId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...plantKeys.all, "environmental", plantId] });
      toast.success("Environmental reading recorded");
    },
  });
}

export function useCreateDiseaseReportMutation(plantId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: diseaseApi.CreateDiseaseReportRequest) => diseaseApi.createDiseaseReport(plantId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: plantKeys.diseaseReports(plantId) });
      toast.success("Disease report logged");
    },
  });
}

export function useConfirmDiseaseReportMutation(plantId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (reportId: string) => diseaseApi.confirmDiseaseReport(reportId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: plantKeys.diseaseReports(plantId) });
      invalidatePlant(queryClient, plantId);
      toast.success("Disease report confirmed");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useDismissDiseaseReportMutation(plantId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ reportId, reason }: { reportId: string; reason: string }) =>
      diseaseApi.dismissDiseaseReport(reportId, { dismissed_reason: reason }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: plantKeys.diseaseReports(plantId) });
      toast.success("Disease report dismissed");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useApplyTreatmentMutation(plantId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ reportId, body }: { reportId: string; body: diseaseApi.ApplyTreatmentRequest }) =>
      diseaseApi.applyTreatment(reportId, body),
    onSuccess: (_data, { reportId }) => {
      void queryClient.invalidateQueries({ queryKey: plantKeys.treatments(reportId) });
      void queryClient.invalidateQueries({ queryKey: plantKeys.diseaseReports(plantId) });
      invalidatePlant(queryClient, plantId);
      toast.success("Treatment applied");
    },
  });
}
