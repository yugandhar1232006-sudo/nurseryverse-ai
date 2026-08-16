import { apiClient, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

/**
 * Thin typed wrappers for Module 5's Species Catalog (`/plant-categories`,
 * `/species/*`, `/plant-varieties/*`). `PlantCategory` is global,
 * system-seeded reference data (migration 0002) -- there is no create/
 * edit/archive for it anywhere in the backend, only the one read route,
 * gated on `species:read` "in service of the Species workflow" per
 * species.py's own module docstring (a category dropdown needs it, not
 * because categories are a real per-org CRUD resource). `PlantVariety` is
 * a flat `/plant-varieties` collection, not nested under `/species/{id}/`
 * -- `species_id` is a normal filter/body field, matching Module 4's
 * `/branches` precedent (see plant_varieties.py's module docstring).
 */

export type PlantCategoryResponse = components["schemas"]["PlantCategoryResponse"];
export type SpeciesResponse = components["schemas"]["SpeciesResponse"];
export type CreateSpeciesRequest = components["schemas"]["CreateSpeciesRequest"];
export type UpdateSpeciesRequest = components["schemas"]["UpdateSpeciesRequest"];
export type PageSpeciesResponse = components["schemas"]["Page_SpeciesResponse_"];
export type PlantVarietyResponse = components["schemas"]["PlantVarietyResponse"];
export type CreatePlantVarietyRequest = components["schemas"]["CreatePlantVarietyRequest"];
export type UpdatePlantVarietyRequest = components["schemas"]["UpdatePlantVarietyRequest"];
export type PagePlantVarietyResponse = components["schemas"]["Page_PlantVarietyResponse_"];

export async function listPlantCategories(): Promise<PlantCategoryResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/plant-categories"));
}

export interface ListSpeciesParams {
  page?: number;
  page_size?: number;
  search?: string;
  category_id?: string;
  light_requirement?: string;
}

export async function listSpecies(params: ListSpeciesParams = {}): Promise<PageSpeciesResponse> {
  return unwrap(() => apiClient.GET("/api/v1/species", { params: { query: params } }));
}

export async function getSpecies(id: string): Promise<SpeciesResponse> {
  return unwrap(() => apiClient.GET("/api/v1/species/{id}", { params: { path: { id } } }));
}

export async function createSpecies(body: CreateSpeciesRequest): Promise<SpeciesResponse> {
  return unwrap(() => apiClient.POST("/api/v1/species", { body }));
}

export async function updateSpecies(id: string, body: UpdateSpeciesRequest): Promise<SpeciesResponse> {
  return unwrap(() => apiClient.PATCH("/api/v1/species/{id}", { params: { path: { id } }, body }));
}

/** Backend blocks this with a 409 if any plant record still references the species -- surfaced as a real conflict, not silently retried. */
export async function deleteSpecies(id: string): Promise<SpeciesResponse> {
  return unwrap(() => apiClient.DELETE("/api/v1/species/{id}", { params: { path: { id } } }));
}

export interface ListPlantVarietiesParams {
  page?: number;
  page_size?: number;
  species_id?: string;
}

export async function listPlantVarieties(params: ListPlantVarietiesParams = {}): Promise<PagePlantVarietyResponse> {
  return unwrap(() => apiClient.GET("/api/v1/plant-varieties", { params: { query: params } }));
}

export async function createPlantVariety(body: CreatePlantVarietyRequest): Promise<PlantVarietyResponse> {
  return unwrap(() => apiClient.POST("/api/v1/plant-varieties", { body }));
}

export async function updatePlantVariety(id: string, body: UpdatePlantVarietyRequest): Promise<PlantVarietyResponse> {
  return unwrap(() => apiClient.PATCH("/api/v1/plant-varieties/{id}", { params: { path: { id } }, body }));
}

/** Backend blocks this with a 409 if any plant record still references the variety. */
export async function deletePlantVariety(id: string): Promise<PlantVarietyResponse> {
  return unwrap(() => apiClient.DELETE("/api/v1/plant-varieties/{id}", { params: { path: { id } } }));
}
