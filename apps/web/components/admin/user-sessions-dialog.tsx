"use client";

import { LogOut, Monitor, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { useUserSessionsQuery } from "@/lib/admin/queries";
import { useForceLogoutUserMutation, useRevokeUserSessionMutation } from "@/lib/admin/mutations";
import type { AdminUserResponse } from "@/lib/api/admin";

/** `GET/DELETE /admin/users/{id}/sessions*` + `POST .../force-logout` -- viewing/revoking ANOTHER user's real active sessions, distinct from 7B's `/account` page (which only manages the caller's own). See `lib/api/admin.ts`'s docstring. */
export function UserSessionsDialog({
  user,
  open,
  onOpenChange,
}: {
  user: AdminUserResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const query = useUserSessionsQuery(user?.id ?? null);
  const revokeMutation = useRevokeUserSessionMutation(user?.id ?? "");
  const forceLogoutMutation = useForceLogoutUserMutation();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Active sessions</DialogTitle>
          <DialogDescription>{user ? `${user.full_name}'s real active login sessions.` : null}</DialogDescription>
        </DialogHeader>

        {query.isLoading && (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        )}
        {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />}
        {query.data && query.data.length === 0 && (
          <EmptyState icon={Monitor} title="No active sessions" description="This user isn't logged in anywhere right now." />
        )}
        {query.data && query.data.length > 0 && (
          <ul className="flex flex-col gap-2">
            {query.data.map((session) => (
              <li key={session.id} className="flex items-center justify-between gap-3 rounded-md border border-border p-3">
                <div className="flex flex-col gap-0.5">
                  <span className="text-body-sm font-medium text-foreground">{session.device_name ?? "Unknown device"}</span>
                  <span className="text-caption text-muted-foreground">
                    {session.ip_address ?? "Unknown IP"} · Last used{" "}
                    {session.last_used_at ? new Date(session.last_used_at).toLocaleString() : "never"}
                  </span>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={revokeMutation.isPending}
                  onClick={() => revokeMutation.mutate(session.id)}
                  aria-label="Revoke session"
                >
                  <X className="size-4" aria-hidden="true" />
                </Button>
              </li>
            ))}
          </ul>
        )}

        {user && query.data && query.data.length > 0 && (
          <Button
            type="button"
            variant="destructive"
            size="sm"
            className="self-start"
            disabled={forceLogoutMutation.isPending}
            onClick={() => forceLogoutMutation.mutate(user.id)}
          >
            {forceLogoutMutation.isPending ? <Spinner className="text-current" /> : <LogOut className="size-4" aria-hidden="true" />}
            Log out of all sessions
          </Button>
        )}
      </DialogContent>
    </Dialog>
  );
}
