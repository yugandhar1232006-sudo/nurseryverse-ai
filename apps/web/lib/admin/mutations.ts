"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import * as adminApi from "@/lib/api/admin";
import * as notificationsApi from "@/lib/api/notifications";
import { adminKeys } from "@/lib/admin/queries";
import { toast } from "@/lib/toast";

function invalidateUser(queryClient: ReturnType<typeof useQueryClient>, userId: string) {
  void queryClient.invalidateQueries({ queryKey: adminKeys.users({}) });
  void queryClient.invalidateQueries({ queryKey: adminKeys.effectivePermissions(userId) });
}

export function useChangeUserRoleMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, newRoleCode }: { userId: string; newRoleCode: string }) =>
      adminApi.changeUserRole(userId, { new_role_code: newRoleCode }),
    onSuccess: (_data, { userId }) => {
      invalidateUser(queryClient, userId);
      toast.success("Role updated");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useActivateUserMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => adminApi.activateUser(userId),
    onSuccess: (_data, userId) => {
      invalidateUser(queryClient, userId);
      toast.success("Account activated");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useDeactivateUserMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => adminApi.deactivateUser(userId),
    onSuccess: (_data, userId) => {
      invalidateUser(queryClient, userId);
      toast.success("Account deactivated");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useLockUserMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, durationMinutes }: { userId: string; durationMinutes: number }) =>
      adminApi.lockUser(userId, { duration_minutes: durationMinutes }),
    onSuccess: (_data, { userId }) => {
      invalidateUser(queryClient, userId);
      toast.success("Account locked");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useUnlockUserMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => adminApi.unlockUser(userId),
    onSuccess: (_data, userId) => {
      invalidateUser(queryClient, userId);
      toast.success("Account unlocked");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useRevokeUserSessionMutation(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) => adminApi.revokeUserSession(userId, sessionId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.userSessions(userId) });
      toast.success("Session revoked");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useForceLogoutUserMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => adminApi.forceLogoutUser(userId),
    onSuccess: (_data, userId) => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.userSessions(userId) });
      toast.success("User logged out of all sessions");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useTriggerPasswordResetMutation() {
  return useMutation({
    mutationFn: (userId: string) => adminApi.triggerPasswordReset(userId),
    onSuccess: () => toast.success("Password reset email sent"),
    onError: (error) => toast.apiError(error),
  });
}

export function useTriggerEmailVerificationMutation() {
  return useMutation({
    mutationFn: (userId: string) => adminApi.triggerEmailVerification(userId),
    onSuccess: () => toast.success("Verification email sent"),
    onError: (error) => toast.apiError(error),
  });
}

export function useSetOrgFeatureFlagMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ key, body }: { key: string; body: adminApi.SetFeatureFlagRequest }) => adminApi.setOrgFeatureFlag(key, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.featureFlags() });
      toast.success("Feature flag updated");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useSetPlatformFeatureFlagMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ key, body }: { key: string; body: adminApi.SetFeatureFlagRequest }) => adminApi.setPlatformFeatureFlag(key, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.featureFlags() });
      toast.success("Platform feature flag updated");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useSetSystemConfigMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ key, body }: { key: string; body: adminApi.SetSystemConfigRequest }) => adminApi.setSystemConfig(key, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.systemConfig() });
      toast.success("System configuration updated");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useCreateTemplateMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: notificationsApi.NotificationTemplateCreateRequest) => notificationsApi.createTemplate(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.templates() });
      toast.success("Template created");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useSendSystemAlertMutation() {
  return useMutation({
    mutationFn: (body: notificationsApi.SystemAlertRequest) => notificationsApi.sendSystemAlert(body),
    onSuccess: () => toast.success("Alert broadcast to your organization"),
    onError: (error) => toast.apiError(error),
  });
}

export function useRetryDueNotificationsMutation() {
  return useMutation({
    mutationFn: () => notificationsApi.retryDueNotifications(),
    onSuccess: (data) => toast.success(`Retried ${data.retried_count} due notification(s)`),
    onError: (error) => toast.apiError(error),
  });
}
