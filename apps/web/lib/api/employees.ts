import { apiClient, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

/**
 * Thin typed wrappers for `/api/v1/employees/*` (Module 4). `EmployeeResponse`
 * itself carries no name/email (just `user_id`) -- the real display-ready
 * join lives at `GET /admin/users` (`AdminUserResponse`, see
 * lib/api/admin.ts), which this app's Employees list actually renders.
 * These wrappers back the *action* routes (invite/update/transfer/
 * deactivate/reactivate), which all operate on `employee_id`.
 */

export type EmployeeResponse = components["schemas"]["EmployeeResponse"];
export type InviteEmployeeRequest = components["schemas"]["InviteEmployeeRequest"];
export type InviteResponse = components["schemas"]["InviteResponse"];
export type UpdateEmployeeProfileRequest = components["schemas"]["UpdateEmployeeProfileRequest"];
export type TransferBranchesRequest = components["schemas"]["TransferBranchesRequest"];
export type RemoveEmployeeRequest = components["schemas"]["RemoveEmployeeRequest"];
export type ReactivateEmployeeRequest = components["schemas"]["ReactivateEmployeeRequest"];

export async function inviteEmployee(body: InviteEmployeeRequest): Promise<InviteResponse> {
  return unwrap(() => apiClient.POST("/api/v1/employees/invite", { body }));
}

export async function getEmployee(id: string): Promise<EmployeeResponse> {
  return unwrap(() => apiClient.GET("/api/v1/employees/{id}", { params: { path: { id } } }));
}

export async function updateEmployeeProfile(id: string, body: UpdateEmployeeProfileRequest): Promise<EmployeeResponse> {
  return unwrap(() => apiClient.PATCH("/api/v1/employees/{id}", { params: { path: { id } }, body }));
}

export async function transferEmployeeBranches(id: string, body: TransferBranchesRequest): Promise<EmployeeResponse> {
  return unwrap(() => apiClient.POST("/api/v1/employees/{id}/transfer-branches", { params: { path: { id } }, body }));
}

export async function deactivateEmployee(id: string, body: RemoveEmployeeRequest): Promise<EmployeeResponse> {
  return unwrap(() => apiClient.POST("/api/v1/employees/{id}/deactivate", { params: { path: { id } }, body }));
}

export async function reactivateEmployee(id: string, body: ReactivateEmployeeRequest): Promise<EmployeeResponse> {
  return unwrap(() => apiClient.POST("/api/v1/employees/{id}/reactivate", { params: { path: { id } }, body }));
}
