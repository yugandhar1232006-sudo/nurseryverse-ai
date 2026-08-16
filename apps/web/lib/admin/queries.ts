"use client";

import { useQuery } from "@tanstack/react-query";

import * as adminApi from "@/lib/api/admin";
import { listTemplates } from "@/lib/api/notifications";
import { useSessionStore } from "@/store/session-store";

/** 7O -- query-key factory for the whole Module 13 admin surface, mirroring every prior phase's `<domain>Keys` pattern. */
export const adminKeys = {
  all: ["admin"] as const,
  roles: () => [...adminKeys.all, "roles"] as const,
  permissions: () => [...adminKeys.all, "permissions"] as const,
  rolePermissions: (roleId: string) => [...adminKeys.all, "role-permissions", roleId] as const,
  users: (params: { page?: number }) => [...adminKeys.all, "users", params] as const,
  effectivePermissions: (userId: string) => [...adminKeys.all, "effective-permissions", userId] as const,
  userSessions: (userId: string) => [...adminKeys.all, "user-sessions", userId] as const,
  featureFlags: () => [...adminKeys.all, "feature-flags"] as const,
  auditLogs: (params: adminApi.ListAuditLogsParams) => [...adminKeys.all, "audit-logs", params] as const,
  securityEvents: (params: { page?: number }) => [...adminKeys.all, "security-events", params] as const,
  platformSecurityEvents: (params: { page?: number }) => [...adminKeys.all, "platform-security-events", params] as const,
  authorizationDenials: (params: { page?: number }) => [...adminKeys.all, "authorization-denials", params] as const,
  health: () => [...adminKeys.all, "health"] as const,
  systemConfig: (category?: string) => [...adminKeys.all, "system-config", category ?? "all"] as const,
  aiModels: () => [...adminKeys.all, "ai-models"] as const,
  aiUsage: (nurseryId: string) => [...adminKeys.all, "ai-usage", nurseryId] as const,
  aiFailures: (nurseryId: string, params: { page?: number }) => [...adminKeys.all, "ai-failures", nurseryId, params] as const,
  knowledgeBase: (nurseryId: string) => [...adminKeys.all, "knowledge-base", nurseryId] as const,
  dataRetention: (nurseryId: string) => [...adminKeys.all, "data-retention", nurseryId] as const,
  templates: () => [...adminKeys.all, "templates"] as const,
};

function useAuthed(): boolean {
  return useSessionStore((state) => state.status === "authenticated");
}

export function useRolesQuery() {
  const enabled = useAuthed();
  return useQuery({ queryKey: adminKeys.roles(), queryFn: adminApi.listRoles, enabled, staleTime: 10 * 60 * 1000 });
}

export function usePermissionsQuery() {
  const enabled = useAuthed();
  return useQuery({ queryKey: adminKeys.permissions(), queryFn: adminApi.listPermissions, enabled, staleTime: 10 * 60 * 1000 });
}

export function useRolePermissionsQuery(roleId: string | null) {
  return useQuery({
    queryKey: adminKeys.rolePermissions(roleId ?? "none"),
    queryFn: () => adminApi.listRolePermissions(roleId as string),
    enabled: roleId !== null,
  });
}

export function useAdminUsersQuery(params: { page?: number } = {}) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: adminKeys.users(params),
    queryFn: () => adminApi.searchUsers({ page: params.page ?? 1, page_size: 20 }),
    enabled,
  });
}

export function useEffectivePermissionsQuery(userId: string | null) {
  return useQuery({
    queryKey: adminKeys.effectivePermissions(userId ?? "none"),
    queryFn: () => adminApi.getEffectivePermissions(userId as string),
    enabled: userId !== null,
  });
}

export function useUserSessionsQuery(userId: string | null) {
  return useQuery({
    queryKey: adminKeys.userSessions(userId ?? "none"),
    queryFn: () => adminApi.listUserSessions(userId as string),
    enabled: userId !== null,
  });
}

export function useFeatureFlagsQuery() {
  const enabled = useAuthed();
  return useQuery({ queryKey: adminKeys.featureFlags(), queryFn: adminApi.listFeatureFlags, enabled });
}

export function useAuditLogsQuery(params: adminApi.ListAuditLogsParams = {}) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: adminKeys.auditLogs(params),
    queryFn: () => adminApi.listAuditLogs({ page: params.page ?? 1, page_size: 20, ...params }),
    enabled,
  });
}

export function useSecurityEventsQuery(params: { page?: number } = {}) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: adminKeys.securityEvents(params),
    queryFn: () => adminApi.listSecurityEvents({ page: params.page ?? 1, page_size: 20 }),
    enabled,
  });
}

/** `admin:read`-gated -- see `lib/api/admin.ts`'s docstring on why this will 403 for every normal tenant account. */
export function usePlatformSecurityEventsQuery(params: { page?: number } = {}) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: adminKeys.platformSecurityEvents(params),
    queryFn: () => adminApi.listPlatformSecurityEvents({ page: params.page ?? 1, page_size: 20 }),
    enabled,
    retry: false,
  });
}

export function useAuthorizationDenialsQuery(params: { page?: number } = {}) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: adminKeys.authorizationDenials(params),
    queryFn: () => adminApi.listAuthorizationDenials({ page: params.page ?? 1, page_size: 20 }),
    enabled,
  });
}

/** `admin:read`-gated; `retry: false` since a 403 here is an expected, permanent outcome for every non-`platform_admin` account, not a transient failure worth retrying. */
export function useHealthQuery() {
  const enabled = useAuthed();
  return useQuery({ queryKey: adminKeys.health(), queryFn: adminApi.getHealthReport, enabled, retry: false });
}

export function useSystemConfigQuery(category?: string) {
  const enabled = useAuthed();
  return useQuery({
    queryKey: adminKeys.systemConfig(category),
    queryFn: () => adminApi.listSystemConfig(category),
    enabled,
    retry: false,
  });
}

export function useAIModelsQuery() {
  const enabled = useAuthed();
  return useQuery({ queryKey: adminKeys.aiModels(), queryFn: adminApi.listAIModelStatus, enabled, retry: false });
}

export function useAIUsageQuery(nurseryId: string | null) {
  return useQuery({
    queryKey: adminKeys.aiUsage(nurseryId ?? "none"),
    queryFn: () => adminApi.listAIUsageStats(nurseryId as string),
    enabled: nurseryId !== null,
    retry: false,
  });
}

export function useAIFailuresQuery(nurseryId: string | null, params: { page?: number } = {}) {
  return useQuery({
    queryKey: adminKeys.aiFailures(nurseryId ?? "none", params),
    queryFn: () => adminApi.listAIFailures(nurseryId as string, { page: params.page ?? 1, page_size: 20 }),
    enabled: nurseryId !== null,
    retry: false,
  });
}

export function useKnowledgeBaseStatusQuery(nurseryId: string | null) {
  return useQuery({
    queryKey: adminKeys.knowledgeBase(nurseryId ?? "none"),
    queryFn: () => adminApi.listKnowledgeBaseStatus(nurseryId as string),
    enabled: nurseryId !== null,
    retry: false,
  });
}

export function useDataRetentionQuery(nurseryId: string | null) {
  return useQuery({
    queryKey: adminKeys.dataRetention(nurseryId ?? "none"),
    queryFn: () => adminApi.getDataRetentionSummary(nurseryId as string),
    enabled: nurseryId !== null,
    retry: false,
  });
}

export function useNotificationTemplatesQuery() {
  const enabled = useAuthed();
  return useQuery({ queryKey: adminKeys.templates(), queryFn: listTemplates, enabled });
}
