import { apiClient, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

export type BranchResponse = components["schemas"]["BranchResponse"];
export type CreateBranchRequest = components["schemas"]["CreateBranchRequest"];
export type UpdateBranchRequest = components["schemas"]["UpdateBranchRequest"];
export type OperatingHoursWindow = components["schemas"]["OperatingHoursWindow"];

/**
 * `GET /branches` is a flat collection scoped to the caller's own org via
 * `TenantContext` server-side (apps/api/app/api/routes/branches.py) --
 * there is no org id to pass, and no way to ask for another org's
 * branches. `include_inactive` defaults to `false` on the backend, which
 * this wrapper mirrors by simply not passing it unless explicitly asked
 * for (the branch switcher never wants archived branches).
 */
export async function listBranches(includeInactive = false): Promise<BranchResponse[]> {
  return unwrap(() =>
    apiClient.GET("/api/v1/branches", { params: { query: { include_inactive: includeInactive } } }),
  );
}

export async function getBranch(id: string): Promise<BranchResponse> {
  return unwrap(() => apiClient.GET("/api/v1/branches/{id}", { params: { path: { id } } }));
}

export async function createBranch(body: CreateBranchRequest): Promise<BranchResponse> {
  return unwrap(() => apiClient.POST("/api/v1/branches", { body }));
}

export async function updateBranch(id: string, body: UpdateBranchRequest): Promise<BranchResponse> {
  return unwrap(() => apiClient.PATCH("/api/v1/branches/{id}", { params: { path: { id } }, body }));
}

/** Archive (soft delete) -- `DELETE /branches/{id}` returns the archived BranchResponse, not 204. */
export async function archiveBranch(id: string): Promise<BranchResponse> {
  return unwrap(() => apiClient.DELETE("/api/v1/branches/{id}", { params: { path: { id } } }));
}
