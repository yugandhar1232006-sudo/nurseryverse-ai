"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import * as catalogApi from "@/lib/api/catalog";
import { catalogKeys } from "@/lib/catalog/queries";
import { toast } from "@/lib/toast";

function invalidateSpecies(queryClient: ReturnType<typeof useQueryClient>) {
  void queryClient.invalidateQueries({ queryKey: catalogKeys.all });
}

export function useCreateSpeciesMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: catalogApi.createSpecies,
    onSuccess: () => {
      invalidateSpecies(queryClient);
      toast.success("Species created");
    },
  });
}

export function useUpdateSpeciesMutation(speciesId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: catalogApi.UpdateSpeciesRequest) => catalogApi.updateSpecies(speciesId, body),
    onSuccess: () => {
      invalidateSpecies(queryClient);
      toast.success("Species updated");
    },
  });
}

export function useDeleteSpeciesMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (speciesId: string) => catalogApi.deleteSpecies(speciesId),
    onSuccess: () => {
      invalidateSpecies(queryClient);
      toast.success("Species archived");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useCreatePlantVarietyMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: catalogApi.createPlantVariety,
    onSuccess: () => {
      invalidateSpecies(queryClient);
      toast.success("Variety created");
    },
  });
}

export function useUpdatePlantVarietyMutation(varietyId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: catalogApi.UpdatePlantVarietyRequest) => catalogApi.updatePlantVariety(varietyId, body),
    onSuccess: () => {
      invalidateSpecies(queryClient);
      toast.success("Variety updated");
    },
  });
}

export function useDeletePlantVarietyMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (varietyId: string) => catalogApi.deletePlantVariety(varietyId),
    onSuccess: () => {
      invalidateSpecies(queryClient);
      toast.success("Variety archived");
    },
    onError: (error) => toast.apiError(error),
  });
}
