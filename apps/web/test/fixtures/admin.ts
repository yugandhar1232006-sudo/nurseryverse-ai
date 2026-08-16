import type {
  AdminAuditLogEntryResponse,
  AdminSessionResponse,
  AdminUserResponse,
  AIInferenceFailureResponse,
  AIModelStatusResponse,
  AIUsageStatsResponse,
  AuthorizationDenialResponse,
  DataRetentionSummaryResponse,
  EffectivePermissionsResponse,
  FeatureFlagResponse,
  HealthReportResponse,
  KnowledgeBaseStatusResponse,
  PermissionResponse,
  RolePermissionEntry,
  RoleResponse,
  SecurityEventResponse,
  SystemConfigResponse,
} from "@/lib/api/admin";
import type { NotificationTemplateResponse } from "@/lib/api/notifications";

/** 7O -- fixtures for the whole Module 13 admin surface, mirroring test/fixtures/reports.ts's pattern. */

export function makeRole(overrides: Partial<RoleResponse> = {}): RoleResponse {
  return {
    id: "99999999-0001-0001-0001-000000000001",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    code: "branch_manager",
    name: "Branch Manager",
    is_system_role: true,
    ...overrides,
  };
}

export function makePermission(overrides: Partial<PermissionResponse> = {}): PermissionResponse {
  return {
    id: "99999999-0002-0001-0001-000000000001",
    code: "plants:read",
    module: "plants",
    action: "read",
    description: "View plant records",
    ...overrides,
  };
}

export function makeRolePermissionEntry(overrides: Partial<RolePermissionEntry> = {}): RolePermissionEntry {
  return { permission_code: "plants:read", scope: "branch", ...overrides };
}

export function makeAdminUser(overrides: Partial<AdminUserResponse> = {}): AdminUserResponse {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    employee_id: "33333333-3333-3333-3333-333333333333",
    email: "jane@example.com",
    full_name: "Jane Grower",
    is_active: true,
    is_email_verified: true,
    locked_until: null,
    failed_login_attempts: 0,
    last_login_at: "2026-08-14T08:00:00Z",
    employee_status: "active",
    department: "Operations",
    position: "Branch Manager",
    ...overrides,
  };
}

export function makeAdminUserPage(items: AdminUserResponse[] = [makeAdminUser()]) {
  return { items, meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 } };
}

export function makeEffectivePermissions(overrides: Partial<EffectivePermissionsResponse> = {}): EffectivePermissionsResponse {
  return {
    org_id: "22222222-2222-2222-2222-222222222222",
    role_code: "branch_manager",
    branch_ids: ["44444444-4444-4444-4444-444444444444"],
    is_org_wide: false,
    permissions: ["plants:read", "inventory:read"],
    ...overrides,
  };
}

export function makeAdminSession(overrides: Partial<AdminSessionResponse> = {}): AdminSessionResponse {
  return {
    id: "55555555-5555-5555-5555-555555555555",
    device_name: "Chrome on macOS",
    user_agent: "Mozilla/5.0",
    ip_address: "203.0.113.10",
    issued_at: "2026-08-14T08:00:00Z",
    expires_at: "2026-08-21T08:00:00Z",
    last_used_at: "2026-08-14T09:00:00Z",
    ...overrides,
  };
}

export function makeAuditLogEntry(overrides: Partial<AdminAuditLogEntryResponse> = {}): AdminAuditLogEntryResponse {
  return {
    id: "66666666-6666-6666-6666-666666666666",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    branch_id: null,
    actor_user_id: "11111111-1111-1111-1111-111111111111",
    action: "user.role_changed",
    entity_type: "user",
    entity_id: "11111111-1111-1111-1111-111111111111",
    diff: { before: { role: "employee" }, after: { role: "branch_manager" } } as unknown as Record<string, never>,
    result: "success",
    request_id: "req-123",
    created_at: "2026-08-14T08:00:00Z",
    ...overrides,
  };
}

export function makeAuditLogPage(items: AdminAuditLogEntryResponse[] = [makeAuditLogEntry()]) {
  return { items, meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 } };
}

export function makeSecurityEvent(overrides: Partial<SecurityEventResponse> = {}): SecurityEventResponse {
  return {
    id: "77777777-7777-7777-7777-777777777777",
    user_id: "11111111-1111-1111-1111-111111111111",
    email: "jane@example.com",
    event_type: "login_failed",
    ip_address: "203.0.113.10",
    event_metadata: { initiated_by: "admin", admin_user_id: "11111111-1111-1111-1111-111111111111" } as unknown as Record<string, never>,
    created_at: "2026-08-14T08:00:00Z",
    ...overrides,
  };
}

export function makeSecurityEventPage(items: SecurityEventResponse[] = [makeSecurityEvent()]) {
  return { items, meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 } };
}

export function makeAuthorizationDenial(overrides: Partial<AuthorizationDenialResponse> = {}): AuthorizationDenialResponse {
  return {
    id: "88888888-8888-8888-8888-888888888888",
    user_id: "11111111-1111-1111-1111-111111111111",
    permission_code: "admin:read",
    resource_type: null,
    resource_id: null,
    nursery_id: "22222222-2222-2222-2222-222222222222",
    branch_id: null,
    reason: "missing_permission",
    explanation: "User's role does not include admin:read.",
    request_id: "req-456",
    created_at: "2026-08-14T08:00:00Z",
    ...overrides,
  };
}

export function makeAuthorizationDenialPage(items: AuthorizationDenialResponse[] = [makeAuthorizationDenial()]) {
  return { items, meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 } };
}

export function makeFeatureFlag(overrides: Partial<FeatureFlagResponse> = {}): FeatureFlagResponse {
  return {
    id: "99999999-0003-0001-0001-000000000001",
    key: "ai_disease_scan_v2",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    branch_id: null,
    is_enabled: true,
    description: "Enables the v2 disease scan model",
    updated_by_user_id: "11111111-1111-1111-1111-111111111111",
    created_at: "2026-08-01T08:00:00Z",
    updated_at: "2026-08-14T08:00:00Z",
    ...overrides,
  };
}

export function makeSystemConfig(overrides: Partial<SystemConfigResponse> = {}): SystemConfigResponse {
  return {
    id: "99999999-0004-0001-0001-000000000001",
    key: "max_upload_size_mb",
    value: 25,
    value_type: "int",
    category: "uploads",
    description: "Maximum upload size in megabytes",
    updated_by_user_id: null,
    created_at: "2026-08-01T08:00:00Z",
    updated_at: "2026-08-01T08:00:00Z",
    ...overrides,
  };
}

export function makeHealthReport(overrides: Partial<HealthReportResponse> = {}): HealthReportResponse {
  return {
    api: "ok",
    database_reachable: true,
    cache_reachable: true,
    cache_backend: "redis",
    storage_configured: true,
    ai_anthropic_configured: true,
    ai_model_artifacts_configured: true,
    notifications_email_configured: true,
    notifications_sms_configured: false,
    notifications_push_configured: false,
    background_processing_configured: true,
    ...overrides,
  };
}

export function makeAIModelStatus(overrides: Partial<AIModelStatusResponse> = {}): AIModelStatusResponse {
  return { capability: "disease_detection", configured: true, ...overrides };
}

export function makeAIUsageStats(overrides: Partial<AIUsageStatsResponse> = {}): AIUsageStatsResponse {
  return { prediction_type: "disease_detection", count: 42, avg_latency_ms: 380, avg_confidence: 0.91, ...overrides };
}

export function makeAIInferenceFailure(overrides: Partial<AIInferenceFailureResponse> = {}): AIInferenceFailureResponse {
  return {
    id: "99999999-0005-0001-0001-000000000001",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    branch_id: null,
    capability: "disease_detection",
    prediction_type: "disease_detection",
    error_type: "timeout",
    error_message: "Model inference timed out after 30s",
    latency_ms: 30000,
    created_at: "2026-08-14T08:00:00Z",
    ...overrides,
  };
}

export function makeAIInferenceFailurePage(items: AIInferenceFailureResponse[] = [makeAIInferenceFailure()]) {
  return { items, meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 } };
}

export function makeKnowledgeBaseStatus(overrides: Partial<KnowledgeBaseStatusResponse> = {}): KnowledgeBaseStatusResponse {
  return { source_type: "care_guide", count: 128, ...overrides };
}

export function makeDataRetentionSummary(overrides: Partial<DataRetentionSummaryResponse> = {}): DataRetentionSummaryResponse {
  return {
    cutoff: "2026-05-16T00:00:00Z",
    audit_logs_older_than_cutoff: 12,
    ai_inference_failures_older_than_cutoff: 3,
    ai_predictions_older_than_cutoff: 150,
    note: "Retention sweep has not run for these yet -- these are eligible, not already purged.",
    ...overrides,
  };
}

export function makeNotificationTemplate(overrides: Partial<NotificationTemplateResponse> = {}): NotificationTemplateResponse {
  return {
    id: "99999999-0006-0001-0001-000000000001",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    category: "watering_overdue",
    channel: "email",
    format: "text",
    locale: "en",
    version: 1,
    subject_template: "{{ plant_name }} needs watering",
    body_template: "{{ plant_name }} in {{ location }} hasn't been watered in {{ days }} days.",
    is_active: true,
    created_at: "2026-08-01T08:00:00Z",
    updated_at: "2026-08-01T08:00:00Z",
    ...overrides,
  };
}
