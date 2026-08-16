"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import * as orgsApi from "@/lib/api/organizations";
import * as branchesApi from "@/lib/api/branches";
import * as employeesApi from "@/lib/api/employees";
import { getMe } from "@/lib/api/auth";
import { authKeys } from "@/lib/auth/queries";
import { organizationKeys } from "@/lib/organization/queries";
import { shellKeys } from "@/lib/shell/queries";
import { toast } from "@/lib/toast";
import { useSessionStore } from "@/store/session-store";

/**
 * Onboarding: creates the org and makes the caller its Owner in one real
 * request (see lib/api/organizations.ts's docstring). On success, the
 * session's own `permissions`/`org_id` are stale (the backend just
 * granted Owner).
 *
 * This deliberately does NOT just `invalidateQueries({ queryKey:
 * authKeys.me() })` (the naive first version of this mutation did, and
 * broke). `invalidateQueries` only marks a query stale and refetches it if
 * it has an *active observer* mounted somewhere in the tree right now.
 * Nothing on the Settings page (where `CreateOrganizationForm` renders)
 * mounts `useMeQuery` -- `SettingsPage` reads `org_id` straight from
 * `useSessionStore`, and the only other place `useMeQuery` is mounted at
 * all is the unrelated Account page. An invalidate-only call here silently
 * no-ops: the mutation "succeeds" but the user stays stuck looking at this
 * same onboarding form until they happen to visit Account or hard-reload.
 * Found and fixed while writing 7E's tests (see
 * components/organization/__tests__/organization.test.tsx's create-org
 * test, which failed against the invalidate-only version). `fetchQuery`
 * forces the real request unconditionally regardless of observers, and the
 * explicit `setUser` mirrors it into `useSessionStore` synchronously --
 * the same effect `useMeQuery` itself uses -- so the sidebar/dashboard/
 * every permission gate reflects the real, server-confirmed new role on
 * the very next render no matter what else is mounted. (The pre-existing
 * `useConfirmEmailVerificationMutation` in lib/auth/mutations.ts has this
 * same latent gap; out of scope to touch here since 7B is approved/frozen
 * and that flow's consequence is milder -- a verified-email banner that
 * clears a little later rather than a user stuck mid-onboarding.)
 */
export function useCreateOrganizationMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: orgsApi.createOrganization,
    onSuccess: async () => {
      const me = await queryClient.fetchQuery({ queryKey: authKeys.me(), queryFn: getMe });
      useSessionStore.getState().setUser(me);
      toast.success("Organization created");
    },
  });
}

export function useUpdateOrganizationMutation(orgId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: orgsApi.UpdateNurseryRequest) => orgsApi.updateOrganization(orgId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: shellKeys.organization(orgId) });
      toast.success("Organization profile updated");
    },
  });
}

export function useUpdateOrganizationSettingsMutation(orgId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: orgsApi.UpdateOrgSettingsRequest) => orgsApi.updateOrganizationSettings(orgId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: shellKeys.organizationSettings(orgId) });
      toast.success("Organization settings updated");
    },
  });
}

export function useCreateBranchMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: branchesApi.createBranch,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: shellKeys.branches() });
      toast.success("Branch created");
    },
  });
}

export function useUpdateBranchMutation(branchId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: branchesApi.UpdateBranchRequest) => branchesApi.updateBranch(branchId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: shellKeys.branches() });
      void queryClient.invalidateQueries({ queryKey: organizationKeys.branch(branchId) });
      toast.success("Branch updated");
    },
  });
}

export function useArchiveBranchMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (branchId: string) => branchesApi.archiveBranch(branchId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: shellKeys.branches() });
      toast.success("Branch archived");
    },
    onError: (error) => toast.apiError(error),
  });
}

function invalidateEmployeeLists(queryClient: ReturnType<typeof useQueryClient>) {
  void queryClient.invalidateQueries({ queryKey: organizationKeys.all });
}

export function useInviteEmployeeMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: employeesApi.inviteEmployee,
    onSuccess: () => {
      invalidateEmployeeLists(queryClient);
      toast.success("Invitation sent");
    },
  });
}

export function useUpdateEmployeeProfileMutation(employeeId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: employeesApi.UpdateEmployeeProfileRequest) => employeesApi.updateEmployeeProfile(employeeId, body),
    onSuccess: () => {
      invalidateEmployeeLists(queryClient);
      toast.success("Employee profile updated");
    },
  });
}

export function useTransferEmployeeBranchesMutation(employeeId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (branchIds: string[]) => employeesApi.transferEmployeeBranches(employeeId, { branch_ids: branchIds }),
    onSuccess: () => {
      invalidateEmployeeLists(queryClient);
      toast.success("Branch assignment updated");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useDeactivateEmployeeMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ employeeId, reason }: { employeeId: string; reason?: string }) =>
      employeesApi.deactivateEmployee(employeeId, { reason: reason ?? null }),
    onSuccess: () => {
      invalidateEmployeeLists(queryClient);
      toast.success("Employee removed");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useReactivateEmployeeMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ employeeId, roleCode, branchIds }: { employeeId: string; roleCode: string; branchIds: string[] }) =>
      employeesApi.reactivateEmployee(employeeId, { role_code: roleCode, branch_ids: branchIds }),
    onSuccess: () => {
      invalidateEmployeeLists(queryClient);
      toast.success("Employee reactivated");
    },
    onError: (error) => toast.apiError(error),
  });
}
