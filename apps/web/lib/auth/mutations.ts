"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import * as authApi from "@/lib/api/auth";
import { authKeys } from "@/lib/auth/queries";
import { useSessionStore } from "@/store/session-store";
import { useNotificationStore } from "@/store/notification-store";

/**
 * Logs in, stores the resulting tokens, then fetches `/auth/me` in the
 * same flow (login only returns a token pair -- the permission/profile
 * data every route guard and `usePermissions()` needs comes from a
 * second call, exactly like `lib/auth/session-boot.ts`'s restoration
 * path does). Callers get the resolved `MeResponse` back so a submit
 * handler can redirect immediately without waiting on a separate query.
 */
export function useLoginMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (input: authApi.LoginInput) => {
      const tokens = await authApi.login(input);
      useSessionStore.getState().setSession({
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
        expiresIn: tokens.expires_in,
      });
      const me = await authApi.getMe();
      useSessionStore.getState().setUser(me);
      queryClient.setQueryData(authKeys.me(), me);
      return me;
    },
  });
}

/**
 * Clears local session state unconditionally in `onSettled`, regardless
 * of whether the backend call itself succeeded -- the user's intent
 * ("log me out") should always be honored locally even if the network
 * request failed (offline, token already expired, etc.); leaving stale
 * "authenticated" UI up because a logout *request* didn't land would be
 * the wrong failure mode for a security-sensitive action.
 */
export function useLogoutMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => authApi.logout(useSessionStore.getState().refreshToken),
    onSettled: () => {
      useSessionStore.getState().clearSession();
      useNotificationStore.getState().reset();
      queryClient.removeQueries({ queryKey: authKeys.all });
    },
  });
}

export function useLogoutAllMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => authApi.logoutAll(),
    onSettled: () => {
      useSessionStore.getState().clearSession();
      useNotificationStore.getState().reset();
      queryClient.removeQueries({ queryKey: authKeys.all });
    },
  });
}

/**
 * The backend revokes every refresh token (this session included) on a
 * successful password change (apps/api/app/services/auth_service.py's
 * `change_password`: "treated as this account may have been
 * compromised"). Rather than leave the UI showing "still logged in"
 * until the next silent-refresh attempt surprises the user with a forced
 * logout, this proactively clears the session on success so the app
 * immediately reflects reality and can redirect to login with a clear
 * "please sign in with your new password" message.
 */
export function useChangePasswordMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: authApi.ChangePasswordInput) => authApi.changePassword(input),
    onSuccess: () => {
      useSessionStore.getState().clearSession();
      useNotificationStore.getState().reset();
      queryClient.removeQueries({ queryKey: authKeys.all });
    },
  });
}

export function useRevokeSessionMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (sessionId: string) => authApi.revokeSession(sessionId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: authKeys.sessions() });
    },
  });
}

export function useRequestPasswordResetMutation() {
  return useMutation({
    mutationFn: (email: string) => authApi.requestPasswordReset(email),
  });
}

export function useConfirmPasswordResetMutation() {
  return useMutation({
    mutationFn: ({ token, newPassword }: { token: string; newPassword: string }) =>
      authApi.confirmPasswordReset(token, newPassword),
  });
}

export function useRequestEmailVerificationMutation() {
  return useMutation({
    mutationFn: () => authApi.requestEmailVerification(),
  });
}

export function useConfirmEmailVerificationMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (token: string) => authApi.confirmEmailVerification(token),
    onSuccess: async () => {
      // Confirming doesn't change tokens, just the `is_email_verified`
      // flag on the account -- refetch `/auth/me` so the verified-email
      // banner (if the user is logged in during confirmation) clears
      // immediately instead of waiting on the query's normal staleness.
      await queryClient.invalidateQueries({ queryKey: authKeys.me() });
    },
  });
}
