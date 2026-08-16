import type { PageSpeciesResponse, PagePlantVarietyResponse, PlantCategoryResponse, PlantVarietyResponse, SpeciesResponse } from "@/lib/api/catalog";

/** Shared fixtures for 7F Plant Catalog tests -- mirrors test/fixtures/organization.ts's pattern. */

export function makePlantCategory(overrides: Partial<PlantCategoryResponse> = {}): PlantCategoryResponse {
  return {
    id: "99999999-9999-9999-9999-999999999901",
    code: "houseplant",
    name: "Houseplant",
    description: "Indoor foliage and flowering plants.",
    ...overrides,
  };
}

export function makeSpecies(overrides: Partial<SpeciesResponse> = {}): SpeciesResponse {
  return {
    id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa01",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    category_id: "99999999-9999-9999-9999-999999999901",
    common_name: "Fiddle Leaf Fig",
    botanical_name: "Ficus lyrata",
    light_requirement: "bright_indirect",
    water_baseline_ml_per_week: 500,
    soil_type: "well_draining",
    temperature_min_celsius: 16,
    temperature_max_celsius: 27,
    growth_curve_baseline: [{ days_since_planting: 0, expected_height_cm: 30 }],
    disease_susceptibility: ["root rot"],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

export function makeSpeciesPage(items: SpeciesResponse[] = [makeSpecies()]): PageSpeciesResponse {
  return {
    items,
    meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 },
  };
}

export function makePlantVariety(overrides: Partial<PlantVarietyResponse> = {}): PlantVarietyResponse {
  return {
    id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb01",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    species_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa01",
    name: "Bambino",
    description: "A dwarf cultivar.",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

export function makePlantVarietyPage(items: PlantVarietyResponse[] = [makePlantVariety()]): PagePlantVarietyResponse {
  return {
    items,
    meta: { page: 1, page_size: 100, total_items: items.length, total_pages: 1 },
  };
}
