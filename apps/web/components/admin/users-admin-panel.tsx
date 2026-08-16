"use client";

import * as React from "react";
import { KeyRound, Lock, LogOut, MailCheck, MoreHorizontal, ShieldCheck, Unlock, UserCheck, UserX } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ChangeRoleDialog } from "@/components/admin/change-role-dialog";
import { LockAccountDialog } from "@/components/admin/lock-account-dialog";
import { UserSessionsDialog } from "@/components/admin/user-sessions-dialog";
import { useAdminUsersQuery, useRolesQuery } from "@/lib/admin/queries";
import {
  useActivateUserMutation,
  useDeactivateUserMutation,
  useTriggerEmailVerificationMutation,
  useTriggerPasswordResetMutation,
  useUnlockUserMutation,
} from "@/lib/admin/mutations";
import type { AdminUserResponse } from "@/lib/api/admin";

function isLocked(user: AdminUserResponse): boolean {
  return user.locked_until !== null && new Date(user.locked_until).getTime() > Date.now();
}

/**
 * Account-level User Administration (`GET /admin/users` + the eight
 * account-action routes) -- deliberately distinct from 7E's
 * `EmployeesPanel` (HR roster: invite/deactivate-as-in-leave-the-company/
 * branch-transfer). This screen is "can this person authenticate right
 * now, and what role/sessions do they hold" -- see `lib/api/admin.ts`'s
 * docstring for the full real-vs-real distinction. Both screens list the
 * same underlying `User`/`Employee` records from two different angles.
 */
export function UsersAdminPanel() {
  const [page, setPage] = React.useState(1);
  const [roleDialogUser, setRoleDialogUser] = React.useState<AdminUserResponse | null>(null);
  const [lockDialogUser, setLockDialogUser] = React.useState<AdminUserResponse | null>(null);
  const [sessionsDialogUser, setSessionsDialogUser] = React.useState<AdminUserResponse | null>(null);

  const query = useAdminUsersQuery({ page });
  const rolesQuery = useRolesQuery();
  const activateMutation = useActivateUserMutation();
  const deactivateMutation = useDeactivateUserMutation();
  const unlockMutation = useUnlockUserMutation();
  const passwordResetMutation = useTriggerPasswordResetMutation();
  const emailVerificationMutation = useTriggerEmailVerificationMutation();

  const users = query.data?.items ?? [];
  const meta = query.data?.meta;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Users</CardTitle>
      </CardHeader>
      <CardContent>
        {query.isLoading && (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        )}
        {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />}
        {query.data && users.length === 0 && (
          <EmptyState icon={ShieldCheck} title="No users yet" description="Users appear here once employees are invited." />
        )}
        {query.data && users.length > 0 && (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last login</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell className="whitespace-nowrap font-medium text-foreground">{user.full_name}</TableCell>
                    <TableCell className="whitespace-nowrap">{user.email}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        <Badge tone={user.is_active ? "success" : "danger"} variant="tone">
                          {user.is_active ? "Active" : "Deactivated"}
                        </Badge>
                        {isLocked(user) && (
                          <Badge tone="warning" variant="tone">
                            Locked
                          </Badge>
                        )}
                        {!user.is_email_verified && (
                          <Badge tone="neutral" variant="tone">
                            Unverified email
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-caption text-muted-foreground">
                      {user.last_login_at ? new Date(user.last_login_at).toLocaleString() : "Never"}
                    </TableCell>
                    <TableCell className="text-right">
                      <PermissionGate permission="employees:write">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button type="button" variant="outline" size="sm" aria-label={`Actions for ${user.full_name}`}>
                              <MoreHorizontal className="size-4" aria-hidden="true" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => setRoleDialogUser(user)}>
                              <ShieldCheck className="size-4" aria-hidden="true" />
                              Change role
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            {user.is_active ? (
                              <DropdownMenuItem onClick={() => deactivateMutation.mutate(user.id)}>
                                <UserX className="size-4" aria-hidden="true" />
                                Deactivate account
                              </DropdownMenuItem>
                            ) : (
                              <DropdownMenuItem onClick={() => activateMutation.mutate(user.id)}>
                                <UserCheck className="size-4" aria-hidden="true" />
                                Activate account
                              </DropdownMenuItem>
                            )}
                            {isLocked(user) ? (
                              <DropdownMenuItem onClick={() => unlockMutation.mutate(user.id)}>
                                <Unlock className="size-4" aria-hidden="true" />
                                Unlock account
                              </DropdownMenuItem>
                            ) : (
                              <DropdownMenuItem onClick={() => setLockDialogUser(user)}>
                                <Lock className="size-4" aria-hidden="true" />
                                Lock account
                              </DropdownMenuItem>
                            )}
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onClick={() => setSessionsDialogUser(user)}>
                              <LogOut className="size-4" aria-hidden="true" />
                              View sessions
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => passwordResetMutation.mutate(user.id)}>
                              <KeyRound className="size-4" aria-hidden="true" />
                              Send password reset
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => emailVerificationMutation.mutate(user.id)}>
                              <MailCheck className="size-4" aria-hidden="true" />
                              Send email verification
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </PermissionGate>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {meta && meta.total_pages > 1 && (
              <div className="mt-3 flex items-center justify-between text-body-sm text-muted-foreground">
                <span>
                  Page {meta.page} of {meta.total_pages}
                </span>
                <div className="flex gap-2">
                  <Button type="button" variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                    Previous
                  </Button>
                  <Button type="button" variant="outline" size="sm" disabled={page >= meta.total_pages} onClick={() => setPage(page + 1)}>
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>

      <ChangeRoleDialog
        user={roleDialogUser}
        roles={rolesQuery.data ?? []}
        open={roleDialogUser !== null}
        onOpenChange={(open) => !open && setRoleDialogUser(null)}
      />
      <LockAccountDialog user={lockDialogUser} open={lockDialogUser !== null} onOpenChange={(open) => !open && setLockDialogUser(null)} />
      <UserSessionsDialog
        user={sessionsDialogUser}
        open={sessionsDialogUser !== null}
        onOpenChange={(open) => !open && setSessionsDialogUser(null)}
      />
    </Card>
  );
}
