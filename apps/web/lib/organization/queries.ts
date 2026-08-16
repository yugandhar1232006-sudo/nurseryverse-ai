"use client";

import { useQuery } from "@tanstack/react-query";

import { getEffectivePermissions, listRoles, searchUsers } from "@/lib/api/admin";
import { getBranch } from "@/lib/api/branches";
import { useSessionStore } from "@/store/session-store";

/** Query key factory for 7E's Organization Management reads, mirroring lib/shell/queries.ts's `shellKeys` pattern. */
export const organizationKeys = {
  all: ["organization"] as const,
  roles: () => [...organizationKeys.all, "roles"] as const,
  users: (page: number) => [...organizationKeys.all, "users", page] as const,
  branch: (branchId: string) => [...organizationKeys.all, "branch", branchId] as const,
  effectivePermissions: (userId: string) => [...organizationKeys.all, "effective-permissions", userId] as const,
};

/** The real role catalog (system roles + this org's own custom roles) for the invite-employee role picker. */
export function useRolesQuery() {
  const orgId = useSessionStore((state) => state.user?.org_id ?? null);

  return useQuery({
    queryKey: organizationKeys.roles(),
    queryFn: listRoles,
    enabled: orgId !== null,
    staleTime: 5 * 60 * 1000, // roles rarely change mid-session
  });
}

/**
 * The org's users with real name/email/status/department/position --
 * `GET /admin/users`, the join `GET /employees` alone doesn't provide
 * (see lib/api/employees.ts's docstring). This is what the Employees
 * list screen actually renders.
 */
export function useUsersQuery(page: number, pageSize = 50) {
  const orgId = useSessionStore((state) => state.user?.org_id ?? null);

  return useQuery({
    queryKey: organizationKeys.users(page),
    queryFn: () => searchUsers({ page, page_size: pageSize }),
    enabled: orgId !== null,
    staleTime: 30 * 1000,
  });
}

export function useBranchQuery(branchId: string | null) {
  return useQuery({
    queryKey: organizationKeys.branch(branchId ?? "none"),
    queryFn: () => getBranch(branchId as string),
    enabled: branchId !== null,
  });
}

/** On-demand only (e.g. opening an employee's detail dialog) -- never fetched eagerly per list row (see organization/employees-panel.tsx). */
export function useEffectivePermissionsQuery(userId: string | null) {
  return useQuery({
    queryKey: organizationKeys.effectivePermissions(userId ?? "none"),
    queryFn: () => getEffectivePermissions(userId as string),
    enabled: userId !== null,
  });
}
