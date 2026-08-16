"use client";

import { ToggleLeft } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { useFeatureFlagsQuery } from "@/lib/admin/queries";
import { useSetOrgFeatureFlagMutation, useSetPlatformFeatureFlagMutation } from "@/lib/admin/mutations";
import type { FeatureFlagResponse } from "@/lib/api/admin";

/**
 * PG-?? Feature Flags -- `GET /admin/feature-flags` (`feature_flags:read`,
 * Owner/Org Admin/Branch Manager) plus two distinct write routes: org-
 * scoped (`PUT .../organization`, `feature_flags:manage`, Owner/Org Admin
 * only) and platform-scoped (`PUT .../platform`, `admin:manage`, only a
 * `platform_admin` account -- see `lib/api/admin.ts`'s docstring). A
 * flag's real scope is inferred from which id fields are null: no
 * `nursery_id` means platform-wide; a `branch_id` means it's scoped
 * further than this org-wide toggle can reach, shown read-only.
 */
export function FeatureFlagsPanel() {
  const query = useFeatureFlagsQuery();
  const orgMutation = useSetOrgFeatureFlagMutation();
  const platformMutation = useSetPlatformFeatureFlagMutation();

  const flags = query.data ?? [];

  function toggle(flag: FeatureFlagResponse, isEnabled: boolean) {
    const body = { is_enabled: isEnabled, description: flag.description ?? undefined };
    if (flag.nursery_id === null) {
      platformMutation.mutate({ key: flag.key, body });
    } else {
      orgMutation.mutate({ key: flag.key, body });
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Feature Flags</CardTitle>
        <CardDescription>Real, live toggles -- flipping one takes effect immediately for whatever it gates.</CardDescription>
      </CardHeader>
      <CardContent>
        {query.isLoading && <Skeleton className="h-40 w-full" />}
        {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />}
        {query.data && flags.length === 0 && (
          <EmptyState icon={ToggleLeft} title="No feature flags" description="No flags have been created yet." />
        )}
        {query.data && flags.length > 0 && (
          <ul className="flex flex-col gap-2">
            {flags.map((flag) => {
              const isPlatform = flag.nursery_id === null;
              const isBranchScoped = flag.branch_id !== null;
              const permission = isPlatform ? "admin:manage" : "feature_flags:manage";
              return (
                <li key={flag.id} className="flex items-center justify-between gap-4 rounded-md border border-border p-3">
                  <div className="flex flex-col gap-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-body-sm font-medium text-foreground">{flag.key}</span>
                      <Badge tone={isPlatform ? "info" : "neutral"} variant="tone">
                        {isPlatform ? "Platform" : "Organization"}
                      </Badge>
                      {isBranchScoped && (
                        <Badge tone="neutral" variant="tone">
                          Branch-scoped
                        </Badge>
                      )}
                    </div>
                    {flag.description && <p className="text-caption text-muted-foreground">{flag.description}</p>}
                  </div>
                  <PermissionGate permission={permission} fallback={<Badge tone={flag.is_enabled ? "success" : "neutral"} variant="tone">{flag.is_enabled ? "On" : "Off"}</Badge>}>
                    <Switch
                      checked={flag.is_enabled}
                      onCheckedChange={(checked) => toggle(flag, checked)}
                      disabled={orgMutation.isPending || platformMutation.isPending}
                      aria-label={`Toggle ${flag.key}`}
                    />
                  </PermissionGate>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
