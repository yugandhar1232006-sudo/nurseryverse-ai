"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { useOrganizationQuery } from "@/lib/shell/queries";

/**
 * Displays the caller's organization -- name and, if set, logo. Per
 * lib/api/organizations.ts's docstring: this is deliberately *context*,
 * not a switcher. `create_organization` (Module 4) enforces one org per
 * user at the backend, and there is no "list my organizations" endpoint
 * to switch between, so a picker here would be UI for a capability that
 * doesn't exist. docs/frontend/07-application-shell.md documents this as
 * a scope decision matching the real backend contract.
 *
 * Renders nothing while there's no `org_id` yet (mid-signup, before
 * `POST /orgs` has ever run) rather than an empty-looking placeholder --
 * `useOrganizationQuery` is simply `enabled: false` in that state.
 */
export function OrgContext() {
  const orgQuery = useOrganizationQuery();

  if (orgQuery.isLoading) {
    return (
      <div className="flex items-center gap-2">
        <Skeleton className="size-7 rounded-md" />
        <Skeleton className="h-4 w-24" />
      </div>
    );
  }

  if (!orgQuery.data) {
    return null;
  }

  const org = orgQuery.data;

  return (
    <div className="flex items-center gap-2 overflow-hidden">
      {org.logo_url ? (
        // eslint-disable-next-line @next/next/no-img-element -- org-supplied external logo URL, not a static/optimizable asset
        <img src={org.logo_url} alt="" className="size-7 shrink-0 rounded-md object-contain" />
      ) : (
        <div className="flex size-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-body-sm font-semibold text-primary">
          {org.name.charAt(0).toUpperCase()}
        </div>
      )}
      <span className="truncate text-body-sm font-semibold text-foreground">{org.name}</span>
    </div>
  );
}
