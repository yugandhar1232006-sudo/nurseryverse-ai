import { http, HttpResponse } from "msw";

import {
  makeAdminSession,
  makeAdminUser,
  makeAIInferenceFailurePage,
  makeAIModelStatus,
  makeAIUsageStats,
  makeAuditLogPage,
  makeAuthorizationDenialPage,
  makeDataRetentionSummary,
  makeFeatureFlag,
  makeHealthReport,
  makeKnowledgeBaseStatus,
  makeNotificationTemplate,
  makePermission,
  makeRolePermissionEntry,
  makeSecurityEventPage,
  makeSystemConfig,
} from "@/test/fixtures/admin";

const BASE = "http://localhost:8000";

/**
 * Default, happy-path handlers for 7O's Module 13 admin surface. Does
 * NOT redefine `GET /admin/roles`, `GET /admin/users`, or `GET
 * /admin/users/{id}/effective-permissions` -- `organization-handlers.ts`
 * (7E) already owns those three (it borrows them for the Employees
 * screen's role picker/effective-permissions view), and per
 * `server.ts`'s own shadowing discipline, a second definition here would
 * silently steal them for every existing 7E test relying on that file's
 * two-role fixture as its default. 7O's own component tests either rely
 * on those same 7E defaults or override per-test with `server.use(...)`
 * using this file's richer `makeAdminUserPage`/`makeRole` fixtures where
 * a specific shape is needed.
 *
 * The System-tab routes (health/system-config/ai/*, data-retention,
 * security-events/platform) return real success payloads here by
 * default -- individual `admin:read`-gated fallback tests override these
 * per-test with a 403 to exercise `usePlatformSecurityEventsQuery`-style
 * `retry:false` + fallback-copy behavior, matching the pattern already
 * established for 7N/7M.
 */
export const adminHandlers = [
  http.get(`${BASE}/api/v1/admin/permissions`, () => HttpResponse.json([makePermission()])),
  http.get(`${BASE}/api/v1/admin/roles/:roleId/permissions`, () => HttpResponse.json([makeRolePermissionEntry()])),

  http.get(`${BASE}/api/v1/admin/users/:userId`, () => HttpResponse.json(makeAdminUser())),
  http.post(`${BASE}/api/v1/admin/users/:userId/role`, () => new HttpResponse(null, { status: 204 })),
  http.post(`${BASE}/api/v1/admin/users/:userId/activate`, () => HttpResponse.json(makeAdminUser({ is_active: true }))),
  http.post(`${BASE}/api/v1/admin/users/:userId/deactivate`, () => HttpResponse.json(makeAdminUser({ is_active: false }))),
  http.post(`${BASE}/api/v1/admin/users/:userId/lock`, () =>
    HttpResponse.json(makeAdminUser({ locked_until: "2026-08-15T08:00:00Z" })),
  ),
  http.post(`${BASE}/api/v1/admin/users/:userId/unlock`, () => HttpResponse.json(makeAdminUser({ locked_until: null }))),
  http.get(`${BASE}/api/v1/admin/users/:userId/sessions`, () => HttpResponse.json([makeAdminSession()])),
  http.delete(`${BASE}/api/v1/admin/users/:userId/sessions/:sessionId`, () => new HttpResponse(null, { status: 204 })),
  http.post(`${BASE}/api/v1/admin/users/:userId/force-logout`, () => new HttpResponse(null, { status: 204 })),
  http.post(`${BASE}/api/v1/admin/users/:userId/password-reset`, () => new HttpResponse(null, { status: 204 })),
  http.post(`${BASE}/api/v1/admin/users/:userId/email-verification`, () => new HttpResponse(null, { status: 204 })),

  http.get(`${BASE}/api/v1/admin/feature-flags`, () =>
    HttpResponse.json([makeFeatureFlag(), makeFeatureFlag({ key: "platform_maintenance_mode", nursery_id: null, is_enabled: false })]),
  ),
  http.put(`${BASE}/api/v1/admin/feature-flags/:key/organization`, () => HttpResponse.json(makeFeatureFlag())),
  http.put(`${BASE}/api/v1/admin/feature-flags/:key/platform`, () =>
    HttpResponse.json(makeFeatureFlag({ nursery_id: null, key: "platform_maintenance_mode" })),
  ),

  http.get(`${BASE}/api/v1/admin/audit-logs`, () => HttpResponse.json(makeAuditLogPage())),
  http.get(`${BASE}/api/v1/admin/security-events`, () => HttpResponse.json(makeSecurityEventPage())),
  http.get(`${BASE}/api/v1/admin/security-events/platform`, () => HttpResponse.json(makeSecurityEventPage())),
  http.get(`${BASE}/api/v1/admin/authorization-denials`, () => HttpResponse.json(makeAuthorizationDenialPage())),

  http.get(`${BASE}/api/v1/admin/health`, () => HttpResponse.json(makeHealthReport())),
  http.get(`${BASE}/api/v1/admin/system-config`, () => HttpResponse.json([makeSystemConfig()])),
  http.put(`${BASE}/api/v1/admin/system-config/:key`, () => HttpResponse.json(makeSystemConfig())),
  http.get(`${BASE}/api/v1/admin/ai/models`, () => HttpResponse.json([makeAIModelStatus()])),
  http.get(`${BASE}/api/v1/admin/ai/usage`, () => HttpResponse.json([makeAIUsageStats()])),
  http.get(`${BASE}/api/v1/admin/ai/failures`, () => HttpResponse.json(makeAIInferenceFailurePage())),
  http.get(`${BASE}/api/v1/admin/ai/knowledge-base`, () => HttpResponse.json([makeKnowledgeBaseStatus()])),
  http.get(`${BASE}/api/v1/admin/data-retention`, () => HttpResponse.json(makeDataRetentionSummary())),

  http.get(`${BASE}/api/v1/notifications/templates`, () => HttpResponse.json([makeNotificationTemplate()])),
  http.post(`${BASE}/api/v1/notifications/templates`, () => HttpResponse.json(makeNotificationTemplate(), { status: 201 })),
  http.post(`${BASE}/api/v1/notifications/system-alerts`, () => new HttpResponse(null, { status: 204 })),
  http.post(`${BASE}/api/v1/notifications/retry-due`, () => HttpResponse.json({ retried_count: 3, results: [] })),
];

/** A real 403, for tests exercising the `admin:read`-gated fallback UI (System panel, Platform Security Events tab). */
export function forbiddenJson() {
  return HttpResponse.json({ detail: "Forbidden" }, { status: 403 });
}
