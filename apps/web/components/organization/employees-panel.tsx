"use client";

import * as React from "react";
import { Plus, Users } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { InviteEmployeeDialog } from "@/components/organization/invite-employee-dialog";
import { EmployeeDetailDialog } from "@/components/organization/employee-detail-dialog";
import { useUsersQuery } from "@/lib/organization/queries";
import type { AdminUserResponse } from "@/lib/api/admin";

const STATUS_TONE: Record<string, "success" | "info" | "neutral"> = {
  active: "success",
  invited: "info",
  deactivated: "neutral",
};

export function EmployeesPanel() {
  const [page, setPage] = React.useState(1);
  const query = useUsersQuery(page);
  const [inviteOpen, setInviteOpen] = React.useState(false);
  const [selectedEmployee, setSelectedEmployee] = React.useState<AdminUserResponse | null>(null);

  const items = query.data?.items ?? [];
  const meta = query.data?.meta;

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Employees</CardTitle>
        <PermissionGate permission="employees:write">
          <Button type="button" size="sm" onClick={() => setInviteOpen(true)}>
            <Plus className="size-4" aria-hidden="true" />
            Invite employee
          </Button>
        </PermissionGate>
      </CardHeader>
      <CardContent>
        {query.isLoading ? (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />
        ) : items.length === 0 ? (
          <EmptyState icon={Users} title="No employees yet" description="Invite someone to join your organization." />
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Department</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((employee) => (
                  <TableRow key={employee.id}>
                    <TableCell className="font-medium text-foreground">{employee.full_name}</TableCell>
                    <TableCell className="text-muted-foreground">{employee.email}</TableCell>
                    <TableCell>
                      <Badge tone={STATUS_TONE[employee.employee_status] ?? "neutral"}>{employee.employee_status}</Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{employee.department ?? "—"}</TableCell>
                    <TableCell className="text-right">
                      <Button type="button" variant="ghost" size="sm" onClick={() => setSelectedEmployee(employee)}>
                        Manage
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            {meta && meta.total_pages > 1 && (
              <div className="mt-4 flex items-center justify-between text-body-sm text-muted-foreground">
                <span>
                  Page {meta.page} of {meta.total_pages} ({meta.total_items} employees)
                </span>
                <div className="flex gap-2">
                  <Button type="button" variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                    Previous
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={page >= meta.total_pages}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>

      <InviteEmployeeDialog open={inviteOpen} onOpenChange={setInviteOpen} />
      <EmployeeDetailDialog open={selectedEmployee !== null} onOpenChange={(open) => !open && setSelectedEmployee(null)} employee={selectedEmployee} />
    </Card>
  );
}
