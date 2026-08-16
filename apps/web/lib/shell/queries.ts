"use client";

import { useQuery } from "@tanstack/react-query";

import { getOrganization, getOrganizationSettings } from "@/lib/api/organizations";
import { listBranches } from "@/lib/api/branches";
import { useSessionStore } from "@/store/session-store";

/**
 * Query key factory, mirroring lib/auth/queries.ts's `authKeys` pattern.
 */
export const shellKeys = {
  all: ["shell"] as const,
  organization: (orgId: string) => [...shellKeys.all, "organization", orgId] as const,
  organizationSettings: (orgId: string) => [...shellKeys.all, "organization-settings", orgId] as const,
  branches: () => [...shellKeys.all, "branches"] as const,
};

/**
 * The current user's organization -- `GET /orgs/{id}` using
 * `MeResponse.org_id` (the only org id there is; see lib/api/organizations.ts's
 * docstring on the one-org-per-user constraint). Not enabled until
 * `org_id` is known, which also naturally covers the pre-restoration
 * ("resolving") and org-less (mid-signup, before `POST /orgs` ever runs)
 * states without a separate loading branch here.
 */
export function useOrganizationQuery() {
  const orgId = useSessionStore((state) => state.user?.org_id ?? null);

  return useQuery({
    queryKey: shellKeys.organization(orgId ?? "none"),
    queryFn: () => getOrganization(orgId as string),
    enabled: orgId !== null,
    staleTime: 5 * 60 * 1000, // org identity/branding changes rarely
  });
}

/**
 * `OrgSettingsResponse.default_currency` -- the one real source for how
 * every monetary figure in the app (dashboards, sales, inventory
 * valuation, invoices) should be formatted (lib/utils.ts's
 * `formatCurrency`). Never hardcode "USD" outside that function's own
 * brief-loading-window fallback.
 */
export function useOrgSettingsQuery() {
  const orgId = useSessionStore((state) => state.user?.org_id ?? null);

  return useQuery({
    queryKey: shellKeys.organizationSettings(orgId ?? "none"),
    queryFn: () => getOrganizationSettings(orgId as string),
    enabled: orgId !== null,
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * The org's active branches, for the branch switcher (top nav) and any
 * future branch-scoped list/dashboard view. Enabled on the same
 * `org_id !== null` condition as `useOrganizationQuery` -- there is
 * nothing to list without an org.
 */
export function useBranchesQuery() {
  const orgId = useSessionStore((state) => state.user?.org_id ?? null);

  return useQuery({
    queryKey: shellKeys.branches(),
    queryFn: () => listBranches(),
    enabled: orgId !== null,
    staleTime: 60 * 1000,
  });
}
