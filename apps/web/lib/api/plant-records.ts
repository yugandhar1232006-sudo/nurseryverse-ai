import { apiClient, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

/**
 * Thin typed wrappers for Module 6's Growth/Health/Watering/Fertilizer/
 * Environmental record routes (`/plants/{id}/...`). Every record type
 * here is immutable once created -- no update/delete anywhere in the
 * backend (plant_records.py's own module docstring) -- so this file
 * exposes only `list*`/`record*`, never an edit or archive function; the
 * UI must not offer editing a past record.
 */

export type GrowthRecordResponse = components["schemas"]["GrowthRecordResponse"];
export type RecordGrowthRequest = components["schemas"]["RecordGrowthRequest"];
export type PageGrowthRecordResponse = components["schemas"]["Page_GrowthRecordResponse_"];

export type HealthRecordResponse = components["schemas"]["HealthRecordResponse"];
export type RecordHealthRequest = components["schemas"]["RecordHealthRequest"];
export type PageHealthRecordResponse = components["schemas"]["Page_HealthRecordResponse_"];

export type WateringRecordResponse = components["schemas"]["WateringRecordResponse"];
export type RecordWateringRequest = components["schemas"]["RecordWateringRequest"];
export type PageWateringRecordResponse = components["schemas"]["Page_WateringRecordResponse_"];

export type FertilizerRecordResponse = components["schemas"]["FertilizerRecordResponse"];
export type RecordFertilizerRequest = components["schemas"]["RecordFertilizerRequest"];
export type PageFertilizerRecordResponse = components["schemas"]["Page_FertilizerRecordResponse_"];

export type EnvironmentalRecordResponse = components["schemas"]["EnvironmentalRecordResponse"];
export type RecordEnvironmentalRequest = components["schemas"]["RecordEnvironmentalRequest"];
export type PageEnvironmentalRecordResponse = components["schemas"]["Page_EnvironmentalRecordResponse_"];

export async function listGrowth(plantId: string, page = 1, pageSize = 20): Promise<PageGrowthRecordResponse> {
  return unwrap(() =>
    apiClient.GET("/api/v1/plants/{plant_id}/growth-timeline", { params: { path: { plant_id: plantId }, query: { page, page_size: pageSize } } }),
  );
}

export async function recordGrowth(plantId: string, body: RecordGrowthRequest): Promise<GrowthRecordResponse> {
  return unwrap(() => apiClient.POST("/api/v1/plants/{plant_id}/growth-timeline", { params: { path: { plant_id: plantId } }, body }));
}

export async function listHealth(plantId: string, page = 1, pageSize = 20): Promise<PageHealthRecordResponse> {
  return unwrap(() =>
    apiClient.GET("/api/v1/plants/{plant_id}/health-history", { params: { path: { plant_id: plantId }, query: { page, page_size: pageSize } } }),
  );
}

export async function recordHealth(plantId: string, body: RecordHealthRequest): Promise<HealthRecordResponse> {
  return unwrap(() => apiClient.POST("/api/v1/plants/{plant_id}/health-history", { params: { path: { plant_id: plantId } }, body }));
}

export async function listWatering(plantId: string, page = 1, pageSize = 20): Promise<PageWateringRecordResponse> {
  return unwrap(() =>
    apiClient.GET("/api/v1/plants/{plant_id}/watering-logs", { params: { path: { plant_id: plantId }, query: { page, page_size: pageSize } } }),
  );
}

export async function recordWatering(plantId: string, body: RecordWateringRequest): Promise<WateringRecordResponse> {
  return unwrap(() => apiClient.POST("/api/v1/plants/{plant_id}/watering-logs", { params: { path: { plant_id: plantId } }, body }));
}

/** Gated on `watering:read`/`watering:write` on the backend -- see lib's own callers for why (no dedicated `fertilizer:*` permission was ever seeded). */
export async function listFertilizer(plantId: string, page = 1, pageSize = 20): Promise<PageFertilizerRecordResponse> {
  return unwrap(() =>
    apiClient.GET("/api/v1/plants/{plant_id}/fertilizer-logs", { params: { path: { plant_id: plantId }, query: { page, page_size: pageSize } } }),
  );
}

export async function recordFertilizer(plantId: string, body: RecordFertilizerRequest): Promise<FertilizerRecordResponse> {
  return unwrap(() => apiClient.POST("/api/v1/plants/{plant_id}/fertilizer-logs", { params: { path: { plant_id: plantId } }, body }));
}

export async function listEnvironmental(plantId: string, page = 1, pageSize = 20): Promise<PageEnvironmentalRecordResponse> {
  return unwrap(() =>
    apiClient.GET("/api/v1/plants/{plant_id}/environmental-readings", { params: { path: { plant_id: plantId }, query: { page, page_size: pageSize } } }),
  );
}

export async function recordEnvironmental(plantId: string, body: RecordEnvironmentalRequest): Promise<EnvironmentalRecordResponse> {
  return unwrap(() => apiClient.POST("/api/v1/plants/{plant_id}/environmental-readings", { params: { path: { plant_id: plantId } }, body }));
}
