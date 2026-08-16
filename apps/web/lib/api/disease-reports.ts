import { apiClient, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

/**
 * Thin typed wrappers for Module 6's Health & Disease routes
 * (`disease_reports.py`) -- this is a real part of a plant's Health
 * Records ("also its disease history for Health Records" / "also feeds
 * Health Records' treatment history," per that file's own route
 * summaries), distinct from 7L's AI Disease *Detection* (running a model
 * to produce an image-analysis prediction). `disease:approve` is a
 * separate, narrower permission than `disease:write` -- confirming or
 * dismissing a draft report requires it, logging one or applying a
 * treatment does not.
 */

export type DiseaseReportResponse = components["schemas"]["DiseaseReportResponse"];
export type CreateDiseaseReportRequest = components["schemas"]["CreateDiseaseReportRequest"];
export type DismissDiseaseReportRequest = components["schemas"]["DismissDiseaseReportRequest"];
export type TreatmentResponse = components["schemas"]["TreatmentResponse"];
export type ApplyTreatmentRequest = components["schemas"]["ApplyTreatmentRequest"];

export async function listDiseaseReportsForPlant(plantId: string): Promise<DiseaseReportResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/plants/{plant_id}/disease-reports", { params: { path: { plant_id: plantId } } }));
}

export async function createDiseaseReport(plantId: string, body: CreateDiseaseReportRequest): Promise<DiseaseReportResponse> {
  return unwrap(() => apiClient.POST("/api/v1/plants/{plant_id}/disease-reports", { params: { path: { plant_id: plantId } }, body }));
}

export async function confirmDiseaseReport(id: string): Promise<DiseaseReportResponse> {
  return unwrap(() => apiClient.POST("/api/v1/disease-reports/{id}/confirm", { params: { path: { id } } }));
}

export async function dismissDiseaseReport(id: string, body: DismissDiseaseReportRequest): Promise<DiseaseReportResponse> {
  return unwrap(() => apiClient.POST("/api/v1/disease-reports/{id}/dismiss", { params: { path: { id } }, body }));
}

export async function listTreatments(reportId: string): Promise<TreatmentResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/disease-reports/{id}/treatments", { params: { path: { id: reportId } } }));
}

export async function applyTreatment(reportId: string, body: ApplyTreatmentRequest): Promise<TreatmentResponse> {
  return unwrap(() => apiClient.POST("/api/v1/disease-reports/{id}/treatments", { params: { path: { id: reportId } }, body }));
}
