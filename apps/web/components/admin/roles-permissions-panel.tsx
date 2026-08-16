"use client";

import * as React from "react";
import { ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useRolePermissionsQuery, useRolesQuery } from "@/lib/admin/queries";

/**
 * PG-57 Roles & Permissions -- entirely read-only, matching the real
 * backend: `GET /admin/roles`, `GET /admin/roles/{id}/permissions`, and
 * (for reference) `GET /admin/permissions`. There is no create/edit-role
 * route anywhere in `admin.py` -- `docs/ux/09-page-inventory.md`'s PG-57
 * entry claims a `roles:manage` permission and a "custom role builder,"
 * neither of which exists server-side (see `lib/api/admin.ts`'s
 * docstring). Role *assignment* to a specific user (`POST /admin/users/
 * {id}/role`) lives on the Users tab instead, next to the rest of that
 * user's account actions, not here.
 */
export function RolesPermissionsPanel() {
  const [selectedRoleId, setSelectedRoleId] = React.useState<string | null>(null);

  const rolesQuery = useRolesQuery();
  const rolePermissionsQuery = useRolePermissionsQuery(selectedRoleId);

  const roles = rolesQuery.data ?? [];
  const selectedRole = roles.find((r) => r.id === selectedRoleId) ?? null;

  return (
    <div className="grid grid-cols-1 gap-4 desktop:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Roles</CardTitle>
          <CardDescription>Select a role to see its real permission set.</CardDescription>
        </CardHeader>
        <CardContent>
          {rolesQuery.isLoading && <Skeleton className="h-48 w-full" />}
          {rolesQuery.isError && (
            <ErrorState error={rolesQuery.error} onRetry={() => rolesQuery.refetch()} retrying={rolesQuery.isFetching} />
          )}
          {rolesQuery.data && roles.length === 0 && <EmptyState icon={ShieldCheck} title="No roles" description="No roles found." />}
          {rolesQuery.data && roles.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Role</TableHead>
                  <TableHead>Code</TableHead>
                  <TableHead>Type</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {roles.map((role) => (
                  <TableRow
                    key={role.id}
                    className={role.id === selectedRoleId ? "bg-muted/50 cursor-pointer" : "cursor-pointer"}
                    onClick={() => setSelectedRoleId(role.id)}
                  >
                    <TableCell className="font-medium text-foreground">{role.name}</TableCell>
                    <TableCell className="text-caption text-muted-foreground">{role.code}</TableCell>
                    <TableCell>
                      <Badge tone={role.is_system_role ? "info" : "neutral"} variant="tone">
                        {role.is_system_role ? "System" : "Custom"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{selectedRole ? `${selectedRole.name}'s permissions` : "Permissions"}</CardTitle>
          <CardDescription>{selectedRole ? "Real, resolved permission codes and scope for this role." : "Select a role."}</CardDescription>
        </CardHeader>
        <CardContent>
          {!selectedRoleId && <EmptyState icon={ShieldCheck} title="No role selected" description="Choose a role from the list." />}
          {selectedRoleId && rolePermissionsQuery.isLoading && <Skeleton className="h-48 w-full" />}
          {selectedRoleId && rolePermissionsQuery.isError && (
            <ErrorState
              error={rolePermissionsQuery.error}
              onRetry={() => rolePermissionsQuery.refetch()}
              retrying={rolePermissionsQuery.isFetching}
            />
          )}
          {rolePermissionsQuery.data && (
            <ul className="flex flex-col gap-1.5">
              {rolePermissionsQuery.data.map((entry) => (
                <li key={entry.permission_code} className="flex items-center justify-between gap-2 rounded-md border border-border p-2">
                  <code className="text-caption text-foreground">{entry.permission_code}</code>
                  <Badge tone="neutral" variant="tone">
                    {entry.scope}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
