import { apiClient, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

/**
 * Thin typed wrappers for `/api/v1/admin/*` (Module 13). This file started
 * small in 7E -- just the two read routes the Employees screen needs
 * (the real role catalog for the invite-employee role picker, and the
 * name/email-bearing user join `GET /employees` itself doesn't carry,
 * see lib/api/employees.ts's own docstring) -- and now covers the rest
 * of Module 13's real admin surface, built in 7O: user account-level
 * writes (activate/deactivate/lock/unlock/sessions/force-logout/
 * password-reset/email-verification/role-change), Roles & Permissions
 * (read-only -- there is no real create/edit-role route anywhere in
 * `admin.py`, despite `docs/ux/09-page-inventory.md`'s PG-57 claiming a
 * `roles:manage` permission and a "custom role builder"; verified absent
 * by reading the route file directly), Feature Flags (org- and
 * platform-scoped), Audit Logs + export, Security Events (org + the
 * separate platform-wide route), Authorization Denials, System Health,
 * System Configuration, AI Administration, and Data Retention.
 *
 * **Distinct from `lib/api/auth.ts`'s session routes**: those are
 * `GET/DELETE /auth/sessions*`, always the *caller's own* sessions
 * (7B's Account page). The routes here (`GET /admin/users/{id}/sessions`,
 * `DELETE .../sessions/{id}`, `POST .../force-logout`) view/revoke
 * *another* user's sessions, gated `employees:read`/`employees:write`,
 * not the caller's own identity -- two real, non-overlapping surfaces
 * sharing the same underlying session store.
 *
 * **Distinct from 7E's `EmployeesPanel`**: that screen's deactivate/
 * reactivate calls `employees.py`'s `employees:delete`-gated routes,
 * which flip `Employee.status` (an HR/roster field). The account-level
 * activate/deactivate/lock/unlock routes here flip `User.is_active` and
 * `User.locked_until` (an authentication-gate field) -- a different
 * model, a different real concern (can this person log in at all right
 * now), gated `employees:read`/`employees:write` on the same `User`
 * record 7E's panel already lists.
 *
 * **Permission reality check** (apps/api/migrations/0002_seed_system_metadata.py,
 * 0018_administration.py): `employees:read`/`write` and `audit:read` and
 * `feature_flags:read` are held by Owner/Org Admin (org-wide) and, for
 * `employees:*`/`feature_flags:read`, Branch Manager (their own branch).
 * `admin:read`/`admin:manage` and `feature_flags:manage`'s platform
 * variant are seeded only to an internal `platform_admin` role that no
 * normal tenant account ever holds -- so System Configuration, System
 * Health, AI Administration, Data Retention, the platform Security
 * Events route, and platform-level Feature Flag writes are real, fully
 * built, and correctly gated, but will render as a real permission-
 * denied state for every Owner/Org Admin/Branch Manager account in this
 * app. This is a deliberate, disclosed consequence of gating UI on the
 * real backend permission rather than inventing a looser one -- see
 * docs/frontend/19-administration.md.
 */

export type RoleResponse = components["schemas"]["RoleResponse"];
export type PermissionResponse = components["schemas"]["PermissionResponse"];
export type RolePermissionEntry = components["schemas"]["RolePermissionEntry"];
export type AdminUserResponse = components["schemas"]["AdminUserResponse"];
export type PageAdminUserResponse = components["schemas"]["Page_AdminUserResponse_"];
export type EffectivePermissionsResponse = components["schemas"]["EffectivePermissionsResponse"];
export type ChangeUserRoleRequest = components["schemas"]["ChangeUserRoleRequest"];
export type LockAccountRequest = components["schemas"]["LockAccountRequest"];
export type AdminSessionResponse = components["schemas"]["app__schemas__admin__SessionResponse"];
export type AdminAuditLogEntryResponse = components["schemas"]["AdminAuditLogEntryResponse"];
export type PageAdminAuditLogEntryResponse = components["schemas"]["Page_AdminAuditLogEntryResponse_"];
export type SecurityEventResponse = components["schemas"]["SecurityEventResponse"];
export type PageSecurityEventResponse = components["schemas"]["Page_SecurityEventResponse_"];
export type AuthorizationDenialResponse = components["schemas"]["AuthorizationDenialResponse"];
export type PageAuthorizationDenialResponse = components["schemas"]["Page_AuthorizationDenialResponse_"];
export type FeatureFlagResponse = components["schemas"]["FeatureFlagResponse"];
export type SetFeatureFlagRequest = components["schemas"]["SetFeatureFlagRequest"];
export type SystemConfigResponse = components["schemas"]["SystemConfigResponse"];
export type SetSystemConfigRequest = components["schemas"]["SetSystemConfigRequest"];
export type HealthReportResponse = components["schemas"]["HealthReportResponse"];
export type AIModelStatusResponse = components["schemas"]["AIModelStatusResponse"];
export type AIUsageStatsResponse = components["schemas"]["AIUsageStatsResponse"];
export type AIInferenceFailureResponse = components["schemas"]["AIInferenceFailureResponse"];
export type PageAIInferenceFailureResponse = components["schemas"]["Page_AIInferenceFailureResponse_"];
export type KnowledgeBaseStatusResponse = components["schemas"]["KnowledgeBaseStatusResponse"];
export type DataRetentionSummaryResponse = components["schemas"]["DataRetentionSummaryResponse"];

/** Hand-written -- `diff` is a real `dict[str, Any]`, always shaped `{before?, after?}` per every call site in `apps/api/app/services/admin_service.py` (role change, activate/deactivate, lock/unlock, feature flags, system config); empty `{}` for session/force-logout/password-reset/email-verification entries. */
export interface AdminAuditDiff {
  before?: Record<string, unknown>;
  after?: Record<string, unknown>;
}

/** Hand-written -- admin-initiated `SecurityEventResponse.event_metadata` is always `{initiated_by: "admin", admin_user_id}` per `admin_service.py`'s own construction; other event types carry other shapes this app doesn't originate, shown generically. */
export interface AdminSecurityEventMetadata {
  initiated_by?: string;
  admin_user_id?: string;
  [key: string]: unknown;
}

export async function listRoles(): Promise<RoleResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/admin/roles"));
}

export async function listPermissions(): Promise<PermissionResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/admin/permissions"));
}

export async function listRolePermissions(roleId: string): Promise<RolePermissionEntry[]> {
  return unwrap(() => apiClient.GET("/api/v1/admin/roles/{role_id}/permissions", { params: { path: { role_id: roleId } } }));
}

export async function changeUserRole(userId: string, body: ChangeUserRoleRequest): Promise<void> {
  await unwrap(() => apiClient.POST("/api/v1/admin/users/{user_id}/role", { params: { path: { user_id: userId } }, body }));
}

export async function searchUsers(params: { page?: number; page_size?: number }): Promise<PageAdminUserResponse> {
  return unwrap(() => apiClient.GET("/api/v1/admin/users", { params: { query: params } }));
}

export async function getAdminUser(userId: string): Promise<AdminUserResponse> {
  return unwrap(() => apiClient.GET("/api/v1/admin/users/{user_id}", { params: { path: { user_id: userId } } }));
}

/** A user's real, resolved role/branch-scope/permission set -- used on demand (e.g. opening an employee's detail) rather than eagerly per list row. */
export async function getEffectivePermissions(userId: string): Promise<EffectivePermissionsResponse> {
  return unwrap(() => apiClient.GET("/api/v1/admin/users/{user_id}/effective-permissions", { params: { path: { user_id: userId } } }));
}

export async function activateUser(userId: string): Promise<AdminUserResponse> {
  return unwrap(() => apiClient.POST("/api/v1/admin/users/{user_id}/activate", { params: { path: { user_id: userId } } }));
}

export async function deactivateUser(userId: string): Promise<AdminUserResponse> {
  return unwrap(() => apiClient.POST("/api/v1/admin/users/{user_id}/deactivate", { params: { path: { user_id: userId } } }));
}

export async function lockUser(userId: string, body: LockAccountRequest): Promise<AdminUserResponse> {
  return unwrap(() => apiClient.POST("/api/v1/admin/users/{user_id}/lock", { params: { path: { user_id: userId } }, body }));
}

export async function unlockUser(userId: string): Promise<AdminUserResponse> {
  return unwrap(() => apiClient.POST("/api/v1/admin/users/{user_id}/unlock", { params: { path: { user_id: userId } } }));
}

export async function listUserSessions(userId: string): Promise<AdminSessionResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/admin/users/{user_id}/sessions", { params: { path: { user_id: userId } } }));
}

export async function revokeUserSession(userId: string, sessionId: string): Promise<void> {
  await unwrap(() =>
    apiClient.DELETE("/api/v1/admin/users/{user_id}/sessions/{session_id}", { params: { path: { user_id: userId, session_id: sessionId } } }),
  );
}

export async function forceLogoutUser(userId: string): Promise<void> {
  await unwrap(() => apiClient.POST("/api/v1/admin/users/{user_id}/force-logout", { params: { path: { user_id: userId } } }));
}

export async function triggerPasswordReset(userId: string): Promise<void> {
  await unwrap(() => apiClient.POST("/api/v1/admin/users/{user_id}/password-reset", { params: { path: { user_id: userId } } }));
}

export async function triggerEmailVerification(userId: string): Promise<void> {
  await unwrap(() => apiClient.POST("/api/v1/admin/users/{user_id}/email-verification", { params: { path: { user_id: userId } } }));
}

// ----------------------------------------------------------------------
// Feature flags
// ----------------------------------------------------------------------

export async function listFeatureFlags(): Promise<FeatureFlagResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/admin/feature-flags"));
}

export async function setOrgFeatureFlag(key: string, body: SetFeatureFlagRequest): Promise<FeatureFlagResponse> {
  return unwrap(() => apiClient.PUT("/api/v1/admin/feature-flags/{key}/organization", { params: { path: { key } }, body }));
}

export async function setPlatformFeatureFlag(key: string, body: SetFeatureFlagRequest): Promise<FeatureFlagResponse> {
  return unwrap(() => apiClient.PUT("/api/v1/admin/feature-flags/{key}/platform", { params: { path: { key } }, body }));
}

// ----------------------------------------------------------------------
// Audit & security
// ----------------------------------------------------------------------

export interface ListAuditLogsParams {
  page?: number;
  page_size?: number;
  actor_user_id?: string;
  action?: string;
  entity_type?: string;
  result?: string;
  branch_id?: string;
  date_from?: string;
  date_to?: string;
}

export async function listAuditLogs(params: ListAuditLogsParams = {}): Promise<PageAdminAuditLogEntryResponse> {
  return unwrap(() => apiClient.GET("/api/v1/admin/audit-logs", { params: { query: params } }));
}

/** Real file-download URL, matching `reportDownloadUrl`'s precedent in `lib/api/reports.ts` -- an `<a href>`, not a fetch call, so the browser handles the binary response. */
export function auditLogsExportUrl(format: "csv" | "json" = "csv"): string {
  return `/api/v1/admin/audit-logs/export?format=${format}`;
}

export async function listSecurityEvents(params: { page?: number; page_size?: number } = {}): Promise<PageSecurityEventResponse> {
  return unwrap(() => apiClient.GET("/api/v1/admin/security-events", { params: { query: params } }));
}

/** Platform-wide, cross-org -- `admin:read`, not `audit:read` like the org-scoped route above (verified directly against `admin.py`'s route body). */
export async function listPlatformSecurityEvents(params: { page?: number; page_size?: number } = {}): Promise<PageSecurityEventResponse> {
  return unwrap(() => apiClient.GET("/api/v1/admin/security-events/platform", { params: { query: params } }));
}

export async function listAuthorizationDenials(
  params: { page?: number; page_size?: number } = {},
): Promise<PageAuthorizationDenialResponse> {
  return unwrap(() => apiClient.GET("/api/v1/admin/authorization-denials", { params: { query: params } }));
}

// ----------------------------------------------------------------------
// System health / configuration / AI administration / data retention
// (all `admin:read`/`admin:manage` -- see this file's docstring on why
// these are real but only ever usable by a `platform_admin` account)
// ----------------------------------------------------------------------

export async function getHealthReport(): Promise<HealthReportResponse> {
  return unwrap(() => apiClient.GET("/api/v1/admin/health"));
}

export async function listSystemConfig(category?: string): Promise<SystemConfigResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/admin/system-config", { params: { query: category ? { category } : {} } }));
}

export async function setSystemConfig(key: string, body: SetSystemConfigRequest): Promise<SystemConfigResponse> {
  return unwrap(() => apiClient.PUT("/api/v1/admin/system-config/{key}", { params: { path: { key } }, body }));
}

export async function listAIModelStatus(): Promise<AIModelStatusResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/admin/ai/models"));
}

/**
 * `nursery_id` is a genuinely *required* query param on these four
 * routes (confirmed against `schema.d.ts`'s real operation types, not
 * assumed) -- unlike every tenant-scoped route elsewhere in this app,
 * `platform_admin` isn't itself scoped to one nursery, so the platform
 * AI-admin/data-retention views need an explicit org to inspect. In this
 * app's own UI, that's always the caller's own `org_id` (see
 * `components/admin/system-panel.tsx`), since there is no cross-org
 * picker here -- a true platform operator console is out of scope.
 */
export async function listAIUsageStats(nurseryId: string, params: { date_from?: string; date_to?: string } = {}): Promise<
  AIUsageStatsResponse[]
> {
  return unwrap(() => apiClient.GET("/api/v1/admin/ai/usage", { params: { query: { nursery_id: nurseryId, ...params } } }));
}

export async function listAIFailures(
  nurseryId: string,
  params: { page?: number; page_size?: number; capability?: string } = {},
): Promise<PageAIInferenceFailureResponse> {
  return unwrap(() => apiClient.GET("/api/v1/admin/ai/failures", { params: { query: { nursery_id: nurseryId, ...params } } }));
}

export async function listKnowledgeBaseStatus(nurseryId: string): Promise<KnowledgeBaseStatusResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/admin/ai/knowledge-base", { params: { query: { nursery_id: nurseryId } } }));
}

export async function getDataRetentionSummary(nurseryId: string, olderThanDays?: number): Promise<DataRetentionSummaryResponse> {
  return unwrap(() =>
    apiClient.GET("/api/v1/admin/data-retention", { params: { query: { nursery_id: nurseryId, older_than_days: olderThanDays } } }),
  );
}
