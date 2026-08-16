import type { AdminUserResponse, EffectivePermissionsResponse, PageAdminUserResponse, RoleResponse } from "@/lib/api/admin";
import type { OrgSettingsResponse } from "@/lib/api/organizations";

/** Shared fixtures for 7E Organization Management tests -- mirrors test/fixtures/shell.ts's pattern. */

export function makeRole(overrides: Partial<RoleResponse> = {}): RoleResponse {
  return {
    id: "66666666-6666-6666-6666-666666666601",
    nursery_id: null,
    code: "branch_manager",
    name: "Branch Manager",
    is_system_role: true,
    ...overrides,
  };
}

export function makeAdminUser(overrides: Partial<AdminUserResponse> = {}): AdminUserResponse {
  return {
    id: "11111111-1111-1111-1111-111111111112",
    employee_id: "77777777-7777-7777-7777-777777777701",
    email: "sam@greenthumb.test",
    full_name: "Sam Rivera",
    is_active: true,
    is_email_verified: true,
    locked_until: null,
    failed_login_attempts: 0,
    last_login_at: "2026-08-10T00:00:00Z",
    employee_status: "active",
    department: "Horticulture",
    position: "Grower",
    ...overrides,
  } as AdminUserResponse;
}

export function makeAdminUserPage(items: AdminUserResponse[] = [makeAdminUser()]): PageAdminUserResponse {
  return {
    items,
    meta: { page: 1, page_size: 50, total_items: items.length, total_pages: 1 },
  };
}

export function makeEffectivePermissions(overrides: Partial<EffectivePermissionsResponse> = {}): EffectivePermissionsResponse {
  return {
    org_id: "22222222-2222-2222-2222-222222222222",
    role_code: "branch_manager",
    branch_ids: ["44444444-4444-4444-4444-444444444444"],
    is_org_wide: false,
    permissions: ["employees:read", "employees:write"],
    ...overrides,
  };
}

export function makeOrgSettings(overrides: Partial<OrgSettingsResponse> = {}): OrgSettingsResponse {
  return {
    id: "88888888-8888-8888-8888-888888888801",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    default_currency: "USD",
    default_timezone: "America/Los_Angeles",
    branding_primary_color: "#2E7D32",
    email_sender_identity: null,
    sms_enabled: false,
    ...overrides,
  };
}
