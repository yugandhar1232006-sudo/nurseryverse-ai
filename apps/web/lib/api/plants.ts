import { apiClient, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

/**
 * Thin typed wrappers for Module 6's Plant Registration/Profile/Movement/
 * Status/Archive/Images/Timeline REST API (`/plants/*`). `Plant` is
 * branch-scoped, not just org-scoped (see plants.py's module docstring)
 * -- `plants:read`/`write`/`transfer` are "B" (branch-scoped) for
 * Horticulturist/Sales Staff per docs/ux/07-role-permission-matrix.md, so
 * a caller's role may only cover some of an org's branches. The backend
 * enforces this on every route; this file adds no client-side branch
 * filtering of its own.
 */

export type PlantStatus = components["schemas"]["PlantStatus"];
export type PlantResponse = components["schemas"]["PlantResponse"];
export type PagePlantResponse = components["schemas"]["Page_PlantResponse_"];
export type RegisterPlantRequest = components["schemas"]["RegisterPlantRequest"];
export type UpdatePlantProfileRequest = components["schemas"]["UpdatePlantProfileRequest"];
export type TransitionStatusRequest = components["schemas"]["TransitionStatusRequest"];
export type MovePlantRequest = components["schemas"]["MovePlantRequest"];
export type ArchivePlantRequest = components["schemas"]["ArchivePlantRequest"];
export type UploadPlantImageRequest = components["schemas"]["UploadPlantImageRequest"];
export type PlantImageResponse = components["schemas"]["PlantImageResponse"];
export type PlantTransferResponse = components["schemas"]["PlantTransferResponse"];
export type PlantTimelineEntryResponse = components["schemas"]["PlantTimelineEntryResponse"];
export type PagePlantTimelineEntryResponse = components["schemas"]["Page_PlantTimelineEntryResponse_"];

export interface ListPlantsParams {
  page?: number;
  page_size?: number;
  branch_id?: string;
  species_id?: string;
  status_filter?: PlantStatus;
  zone?: string;
  batch_number?: string;
  search?: string;
  include_archived?: boolean;
  sort_by?: string;
  sort_dir?: string;
}

export async function listPlants(params: ListPlantsParams = {}): Promise<PagePlantResponse> {
  return unwrap(() => apiClient.GET("/api/v1/plants", { params: { query: params } }));
}

export async function registerPlant(body: RegisterPlantRequest): Promise<PlantResponse> {
  return unwrap(() => apiClient.POST("/api/v1/plants", { body }));
}

export async function getPlantByQr(token: string): Promise<PlantResponse> {
  return unwrap(() => apiClient.GET("/api/v1/plants/qr/{token}", { params: { path: { token } } }));
}

export async function getPlant(id: string): Promise<PlantResponse> {
  return unwrap(() => apiClient.GET("/api/v1/plants/{id}", { params: { path: { id } } }));
}

export async function updatePlantProfile(id: string, body: UpdatePlantProfileRequest): Promise<PlantResponse> {
  return unwrap(() => apiClient.PATCH("/api/v1/plants/{id}", { params: { path: { id } }, body }));
}

/** Illegal transitions (not matching docs/ux/13-digital-twin-lifecycle.md's state machine) come back as a real 409, surfaced to the user rather than validated client-side. */
export async function transitionPlantStatus(id: string, body: TransitionStatusRequest): Promise<PlantResponse> {
  return unwrap(() => apiClient.POST("/api/v1/plants/{id}/status", { params: { path: { id } }, body }));
}

export async function movePlant(id: string, body: MovePlantRequest): Promise<PlantResponse> {
  return unwrap(() => apiClient.POST("/api/v1/plants/{id}/move", { params: { path: { id } }, body }));
}

export async function getMovementHistory(id: string): Promise<PlantTransferResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/plants/{id}/movement-history", { params: { path: { id } } }));
}

export async function archivePlant(id: string, body: ArchivePlantRequest): Promise<PlantResponse> {
  return unwrap(() => apiClient.POST("/api/v1/plants/{id}/archive", { params: { path: { id } }, body }));
}

export async function uploadPlantImage(id: string, body: UploadPlantImageRequest): Promise<PlantImageResponse> {
  return unwrap(() => apiClient.POST("/api/v1/plants/{id}/images", { params: { path: { id } }, body }));
}

export async function listPlantImages(id: string): Promise<PlantImageResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/plants/{id}/images", { params: { path: { id } } }));
}

export async function getPlantTimeline(id: string, page = 1, pageSize = 30): Promise<PagePlantTimelineEntryResponse> {
  return unwrap(() =>
    apiClient.GET("/api/v1/plants/{id}/timeline", { params: { path: { id }, query: { page, page_size: pageSize } } }),
  );
}
