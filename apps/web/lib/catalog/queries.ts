"use client";

import { useQuery } from "@tanstack/react-query";

import * as catalogApi from "@/lib/api/catalog";
import { useSessionStore } from "@/store/session-store";

/** Query key factory for 7F's Plant Catalog reads, mirroring lib/organization/queries.ts's pattern. */
export const catalogKeys = {
  all: ["catalog"] as const,
  categories: () => [...catalogKeys.all, "categories"] as const,
  species: (params: catalogApi.ListSpeciesParams) => [...catalogKeys.all, "species", params] as const,
  speciesDetail: (id: string) => [...catalogKeys.all, "species-detail", id] as const,
  varieties: (params: catalogApi.ListPlantVarietiesParams) => [...catalogKeys.all, "varieties", params] as const,
};

/** Global, system-seeded taxonomy -- rarely changes, long staleTime is appropriate (see lib/api/catalog.ts's docstring). */
export function usePlantCategoriesQuery() {
  return useQuery({
    queryKey: catalogKeys.categories(),
    queryFn: catalogApi.listPlantCategories,
    staleTime: 5 * 60 * 1000,
  });
}

export function useSpeciesListQuery(params: catalogApi.ListSpeciesParams) {
  const orgId = useSessionStore((state) => state.user?.org_id ?? null);

  return useQuery({
    queryKey: catalogKeys.species(params),
    queryFn: () => catalogApi.listSpecies(params),
    enabled: orgId !== null,
    staleTime: 30 * 1000,
  });
}

export function useSpeciesDetailQuery(id: string | null) {
  return useQuery({
    queryKey: catalogKeys.speciesDetail(id ?? "none"),
    queryFn: () => catalogApi.getSpecies(id as string),
    enabled: id !== null,
  });
}

/** Filtered to one species (the Species Detail page's varieties list) when `species_id` is supplied. */
export function usePlantVarietiesQuery(params: catalogApi.ListPlantVarietiesParams) {
  const orgId = useSessionStore((state) => state.user?.org_id ?? null);

  return useQuery({
    queryKey: catalogKeys.varieties(params),
    queryFn: () => catalogApi.listPlantVarieties(params),
    enabled: orgId !== null && (params.species_id === undefined || params.species_id.length > 0),
    staleTime: 30 * 1000,
  });
}
