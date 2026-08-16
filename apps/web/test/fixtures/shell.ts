import type { NurseryResponse } from "@/lib/api/organizations";
import type { BranchResponse } from "@/lib/api/branches";
import type { NotificationResponse, NotificationPage } from "@/lib/api/notifications";

/** Shared fixtures for 7C Application Shell tests -- mirrors test/fixtures/auth.ts's pattern. */

export function makeOrganization(overrides: Partial<NurseryResponse> = {}): NurseryResponse {
  return {
    id: "22222222-2222-2222-2222-222222222222",
    name: "Green Thumb Nursery",
    contact_email: "hello@greenthumb.test",
    contact_phone: null,
    logo_url: null,
    status: "active",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

export function makeBranch(overrides: Partial<BranchResponse> = {}): BranchResponse {
  return {
    id: "44444444-4444-4444-4444-444444444444",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    name: "Main Branch",
    address_line1: "1 Greenhouse Way",
    address_line2: null,
    city: "Portland",
    region: "OR",
    postal_code: "97201",
    country: "US",
    timezone: "America/Los_Angeles",
    status: "active",
    phone: null,
    email: null,
    latitude: null,
    longitude: null,
    operating_hours: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  } as BranchResponse;
}

export function makeNotification(overrides: Partial<NotificationResponse> = {}): NotificationResponse {
  return {
    id: "55555555-5555-5555-5555-555555555555",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    recipient_user_id: "11111111-1111-1111-1111-111111111111",
    category: "watering_overdue",
    message: "A plant batch needs watering.",
    deep_link: "/watering",
    read_at: null,
    created_at: "2026-08-14T08:00:00Z",
    ...overrides,
  } as NotificationResponse;
}

export function makeNotificationPage(items: NotificationResponse[] = [makeNotification()]): NotificationPage {
  return {
    items,
    meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 },
  } as NotificationPage;
}
