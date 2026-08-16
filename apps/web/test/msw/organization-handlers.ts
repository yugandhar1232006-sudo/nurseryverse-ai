import { http, HttpResponse } from "msw";

import { makeAdminUserPage, makeEffectivePermissions, makeOrgSettings, makeRole } from "@/test/fixtures/organization";
import { makeBranch, makeOrganization } from "@/test/fixtures/shell";

const BASE = "http://localhost:8000";

/**
 * Default, happy-path handlers for 7E's Organization Management routes
 * (Module 4 orgs/branches/employees + the two Module 13 admin reads it
 * borrows) -- same real-`apiClient` interception approach as
 * shell-handlers.ts/dashboard-handlers.ts. Individual tests override
 * specific handlers with `server.use(...)` for create/error/empty cases.
 */
export const organizationHandlers = [
  http.post(`${BASE}/api/v1/orgs`, () => HttpResponse.json(makeOrganization())),
  http.patch(`${BASE}/api/v1/orgs/:id`, () => HttpResponse.json(makeOrganization())),
  http.post(`${BASE}/api/v1/orgs/:id/archive`, () => HttpResponse.json(makeOrganization({ status: "archived" }))),
  http.patch(`${BASE}/api/v1/orgs/:id/settings`, () => HttpResponse.json(makeOrgSettings())),

  http.get(`${BASE}/api/v1/branches/:id`, () => HttpResponse.json(makeBranch())),
  http.post(`${BASE}/api/v1/branches`, () => HttpResponse.json(makeBranch({ id: "44444444-4444-4444-4444-444444444499", name: "New Branch" }))),
  http.patch(`${BASE}/api/v1/branches/:id`, () => HttpResponse.json(makeBranch())),
  http.delete(`${BASE}/api/v1/branches/:id`, () => HttpResponse.json(makeBranch({ status: "archived" }))),

  http.get(`${BASE}/api/v1/admin/roles`, () => HttpResponse.json([makeRole(), makeRole({ id: "role-2", code: "sales_staff", name: "Sales Staff" })])),
  http.get(`${BASE}/api/v1/admin/users`, () => HttpResponse.json(makeAdminUserPage())),
  http.get(`${BASE}/api/v1/admin/users/:userId/effective-permissions`, () => HttpResponse.json(makeEffectivePermissions())),

  http.post(`${BASE}/api/v1/employees/invite`, () =>
    HttpResponse.json({ employee_id: "77777777-7777-7777-7777-777777777799", email: "new@greenthumb.test", status: "invited" }),
  ),
  http.post(`${BASE}/api/v1/employees/:id/transfer-branches`, () => HttpResponse.json({})),
  http.post(`${BASE}/api/v1/employees/:id/deactivate`, () => HttpResponse.json({})),
  http.post(`${BASE}/api/v1/employees/:id/reactivate`, () => HttpResponse.json({})),
];
