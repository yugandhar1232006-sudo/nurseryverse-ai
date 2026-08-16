import { apiClient, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

/**
 * Thin typed wrappers for `/api/v1/orgs/*` (Module 4). Every user belongs
 * to at most one organization in this system -- `create_organization`
 * (apps/api/app/api/routes/organizations.py) explicitly rejects a second
 * org for the same caller ("v1's one-org-per-user constraint," per that
 * route's own docstring). There is deliberately no "list my organizations"
 * or "switch organization" endpoint anywhere in the backend, because there
 * is nothing to list or switch between -- see
 * docs/frontend/07-application-shell.md's Organization Context section
 * for why the shell shows the current org as context, not a picker.
 */

export type NurseryResponse = components["schemas"]["NurseryResponse"];
export type OrgSettingsResponse = components["schemas"]["OrgSettingsResponse"];
export type CreateNurseryRequest = components["schemas"]["CreateNurseryRequest"];
export type UpdateNurseryRequest = components["schemas"]["UpdateNurseryRequest"];
export type UpdateOrgSettingsRequest = components["schemas"]["UpdateOrgSettingsRequest"];

export async function getOrganization(id: string): Promise<NurseryResponse> {
  return unwrap(() => apiClient.GET("/api/v1/orgs/{id}", { params: { path: { id } } }));
}

export async function getOrganizationSettings(id: string): Promise<OrgSettingsResponse> {
  return unwrap(() => apiClient.GET("/api/v1/orgs/{id}/settings", { params: { path: { id } } }));
}

/**
 * Onboarding: `POST /orgs` -- the caller becomes the new org's Owner in
 * the same request (see organizations.py's own docstring: this is
 * atomic with `EmployeeService.provision_owner`, not a two-step
 * process). Rejects with 409 if the caller already belongs to an org
 * (v1's one-org-per-user constraint) -- surfaced to the UI as a real
 * conflict, not silently retried or hidden.
 */
export async function createOrganization(body: CreateNurseryRequest): Promise<NurseryResponse> {
  return unwrap(() => apiClient.POST("/api/v1/orgs", { body }));
}

export async function updateOrganization(id: string, body: UpdateNurseryRequest): Promise<NurseryResponse> {
  return unwrap(() => apiClient.PATCH("/api/v1/orgs/{id}", { params: { path: { id } }, body }));
}

export async function archiveOrganization(id: string): Promise<NurseryResponse> {
  return unwrap(() => apiClient.POST("/api/v1/orgs/{id}/archive", { params: { path: { id } } }));
}

export async function updateOrganizationSettings(id: string, body: UpdateOrgSettingsRequest): Promise<OrgSettingsResponse> {
  return unwrap(() => apiClient.PATCH("/api/v1/orgs/{id}/settings", { params: { path: { id } }, body }));
}

export async function transferOwnership(id: string, newOwnerUserId: string): Promise<void> {
  return unwrap(() =>
    apiClient.POST("/api/v1/orgs/{id}/transfer-ownership", { params: { path: { id } }, body: { new_owner_user_id: newOwnerUserId } }),
  );
}
