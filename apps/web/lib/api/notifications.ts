import { apiClient, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

/**
 * Typed wrappers for `/api/v1/notifications/*` (Module 11). Every route
 * here operates on the caller's own notifications -- there is no
 * recipient-id parameter to pass, matching `GET /auth/me`'s shape.
 */
export type NotificationResponse = components["schemas"]["NotificationResponse"];
export type NotificationCategory = components["schemas"]["NotificationCategory"];
export type UnreadCountResponse = components["schemas"]["UnreadCountResponse"];
export type MarkAllReadResponse = components["schemas"]["MarkAllReadResponse"];
// openapi-typescript monomorphizes the backend's generic Page[T] envelope
// per response type rather than emitting one generic `Page` schema --
// this is the notification-specific one.
export type NotificationPage = components["schemas"]["Page_NotificationResponse_"];
export type NotificationChannel = components["schemas"]["NotificationChannel"];
export type NotificationFrequency = components["schemas"]["NotificationFrequency"];
export type NotificationPreferenceResponse = components["schemas"]["NotificationPreferenceResponse"];
export type NotificationPreferenceUpdateRequest = components["schemas"]["NotificationPreferenceUpdateRequest"];
export type NotificationTemplateResponse = components["schemas"]["NotificationTemplateResponse"];
export type NotificationTemplateCreateRequest = components["schemas"]["NotificationTemplateCreateRequest"];
export type SystemAlertRequest = components["schemas"]["SystemAlertRequest"];
export type RetryDueResponse = components["schemas"]["RetryDueResponse"];

export interface ListNotificationsParams {
  page?: number;
  pageSize?: number;
  unreadOnly?: boolean;
  category?: NotificationCategory;
}

export async function listNotifications(params: ListNotificationsParams = {}): Promise<NotificationPage> {
  return unwrap(() =>
    apiClient.GET("/api/v1/notifications", {
      params: {
        query: {
          page: params.page,
          page_size: params.pageSize,
          unread_only: params.unreadOnly,
          category: params.category,
        },
      },
    }),
  );
}

export async function getUnreadCount(): Promise<UnreadCountResponse> {
  return unwrap(() => apiClient.GET("/api/v1/notifications/unread-count", {}));
}

export async function markNotificationRead(id: string): Promise<NotificationResponse> {
  return unwrap(() => apiClient.PATCH("/api/v1/notifications/{id}/read", { params: { path: { id } } }));
}

export async function markAllRead(): Promise<MarkAllReadResponse> {
  return unwrap(() => apiClient.POST("/api/v1/notifications/mark-all-read", {}));
}

/** 7M -- the caller's own notification preferences (PG-58: channel selection, quiet hours, frequency), keyed by (category, channel). */
export async function listPreferences(): Promise<NotificationPreferenceResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/notifications/preferences", {}));
}

/**
 * 7M -- upserts one or more (category, channel) rows. The real route is
 * `PUT`, despite `docs/ux/09-page-inventory.md`'s PG-58 entry citing
 * `PATCH` -- verified directly against `notifications.py`'s
 * `update_preferences` route and `schema.d.ts`, not assumed from the doc.
 */
export async function updatePreferences(body: NotificationPreferenceUpdateRequest[]): Promise<NotificationPreferenceResponse[]> {
  return unwrap(() => apiClient.PUT("/api/v1/notifications/preferences", { body }));
}

/**
 * 7O -- the remaining four real `/notifications/*` routes, deferred from
 * 7M because they're admin/operator actions (template authoring, org-
 * wide alert broadcast, delivery-retry sweep), not end-user preference
 * management. All three gated `notifications:manage_preferences` (the
 * same permission 7M's own preferences routes use -- confirmed via
 * `notifications.py`, there is no separate "notifications admin"
 * permission).
 */
export async function listTemplates(): Promise<NotificationTemplateResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/notifications/templates", {}));
}

export async function createTemplate(body: NotificationTemplateCreateRequest): Promise<NotificationTemplateResponse> {
  return unwrap(() => apiClient.POST("/api/v1/notifications/templates", { body }));
}

/** Broadcasts to the org's active employees -- a real send, not a preview. */
export async function sendSystemAlert(body: SystemAlertRequest): Promise<void> {
  await unwrap(() => apiClient.POST("/api/v1/notifications/system-alerts", { body }));
}

/** Manually runs the same due-delivery retry sweep Module 14's Celery beat already runs on its own schedule -- same "real operator override, not a duplicate of the automatic job" reasoning as `runDueScheduledReports` in `lib/api/reports.ts`. */
export async function retryDueNotifications(): Promise<RetryDueResponse> {
  return unwrap(() => apiClient.POST("/api/v1/notifications/retry-due", {}));
}
