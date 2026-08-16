"use client";

import { useQuery } from "@tanstack/react-query";

import * as passportApi from "@/lib/api/passport";

/** Query key factory for 7K's internal, authenticated Passport reads. */
export const passportKeys = {
  all: ["passports"] as const,
  plantList: (plantId: string) => [...passportKeys.all, "plant-list", plantId] as const,
};

/** Every version generated for this plant -- unpaginated, newest included, append-only per `PassportService.generate_passport`'s own docstring. */
export function usePlantPassportsQuery(plantId: string | null) {
  return useQuery({
    queryKey: passportKeys.plantList(plantId ?? "none"),
    queryFn: () => passportApi.listPlantPassports(plantId as string),
    enabled: plantId !== null,
  });
}
