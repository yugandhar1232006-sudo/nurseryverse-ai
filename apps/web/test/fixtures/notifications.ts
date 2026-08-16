import type { NotificationPreferenceResponse } from "@/lib/api/notifications";

/** 7M -- PG-58 notification preference row fixtures, mirrors test/fixtures/shell.ts's pattern. */
export function makePreference(overrides: Partial<NotificationPreferenceResponse> = {}): NotificationPreferenceResponse {
  return {
    id: "66666666-6666-6666-6666-666666666601",
    user_id: "11111111-1111-1111-1111-111111111111",
    category: "watering_overdue",
    channel: "in_app",
    enabled: true,
    quiet_hours_start: null,
    quiet_hours_end: null,
    quiet_hours_timezone: null,
    frequency: "immediate",
    ...overrides,
  } as NotificationPreferenceResponse;
}
