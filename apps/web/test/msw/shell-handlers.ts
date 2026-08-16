import { http, HttpResponse } from "msw";

import { makeBranch, makeNotification, makeNotificationPage, makeOrganization } from "@/test/fixtures/shell";
import { makePreference } from "@/test/fixtures/notifications";

const BASE = "http://localhost:8000";

/**
 * Default, happy-path handlers for the 7C Application Shell -- same
 * network-layer-interception approach as test/msw/handlers.ts (real
 * `apiClient`/`unwrap` code runs against these responses; nothing about
 * `lib/api/organizations.ts`, `branches.ts`, `notifications.ts`, or
 * `lib/search/api.ts` is mocked directly). Individual tests override
 * specific handlers with `server.use(...)` for empty/error/permission-
 * denied states.
 */
export const shellHandlers = [
  http.get(`${BASE}/api/v1/orgs/:id`, () => HttpResponse.json(makeOrganization())),
  http.get(`${BASE}/api/v1/orgs/:id/settings`, () => HttpResponse.json({})),

  http.get(`${BASE}/api/v1/branches`, () => HttpResponse.json([makeBranch()])),

  http.get(`${BASE}/api/v1/notifications`, () => HttpResponse.json(makeNotificationPage([makeNotification()]))),
  http.get(`${BASE}/api/v1/notifications/unread-count`, () => HttpResponse.json({ unread_count: 1 })),
  http.patch(`${BASE}/api/v1/notifications/:id/read`, () =>
    HttpResponse.json(makeNotification({ read_at: "2026-08-14T09:00:00Z" })),
  ),
  http.post(`${BASE}/api/v1/notifications/mark-all-read`, () => HttpResponse.json({ marked_read_count: 1 })),

  // 7M PG-58 -- empty by default (no saved preference rows yet); tests
  // override with `server.use(...)` to exercise the real saved-row/save
  // flows against `NotificationPreferencesPanel`.
  http.get(`${BASE}/api/v1/notifications/preferences`, () => HttpResponse.json([])),
  http.put(`${BASE}/api/v1/notifications/preferences`, async ({ request }) => {
    const body = (await request.json()) as Array<Partial<import("@/lib/api/notifications").NotificationPreferenceResponse>>;
    return HttpResponse.json(body.map((row, i) => makePreference({ id: `pref-${i}`, ...row })));
  }),

  // Global search fan-out targets -- empty by default; tests override per
  // case with `server.use(...)` to assert real result rendering.
  http.get(`${BASE}/api/v1/plants`, () =>
    HttpResponse.json({ items: [], meta: { page: 1, page_size: 5, total_items: 0, total_pages: 0 } }),
  ),
  http.get(`${BASE}/api/v1/species`, () =>
    HttpResponse.json({ items: [], meta: { page: 1, page_size: 5, total_items: 0, total_pages: 0 } }),
  ),
  http.get(`${BASE}/api/v1/customers`, () =>
    HttpResponse.json({ items: [], meta: { page: 1, page_size: 5, total_items: 0, total_pages: 0 } }),
  ),
  http.get(`${BASE}/api/v1/inventory`, () =>
    HttpResponse.json({ items: [], meta: { page: 1, page_size: 5, total_items: 0, total_pages: 0 } }),
  ),
];
