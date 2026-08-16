"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ErrorState } from "@/components/error-state";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useEffectivePermissionsQuery, useRolesQuery } from "@/lib/organization/queries";
import { useBranchesQuery } from "@/lib/shell/queries";
import {
  useDeactivateEmployeeMutation,
  useReactivateEmployeeMutation,
  useTransferEmployeeBranchesMutation,
} from "@/lib/organization/mutations";
import { reactivateEmployeeSchema, type ReactivateEmployeeFormValues } from "@/lib/validation/organization";
import type { AdminUserResponse } from "@/lib/api/admin";

/**
 * Real role/branch scope for one user (`GET /admin/users/{id}/effective-permissions`),
 * plus the actions Employee Status/Branch Assignment/Employee Transfer
 * from the 7E kickoff map to: transfer branches, deactivate, reactivate.
 * `AdminUserResponse` itself carries no role/branch info (see
 * lib/api/employees.ts's docstring) -- this is fetched on demand only
 * when a user actually opens this dialog, not eagerly for every row in
 * the Employees list.
 */
export function EmployeeDetailDialog({
  open,
  onOpenChange,
  employee,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  employee: AdminUserResponse | null;
}) {
  const permsQuery = useEffectivePermissionsQuery(open ? (employee?.id ?? null) : null);
  const branchesQuery = useBranchesQuery();
  const rolesQuery = useRolesQuery();
  const transferMutation = useTransferEmployeeBranchesMutation(employee?.employee_id ?? "");
  const deactivateMutation = useDeactivateEmployeeMutation();
  const reactivateMutation = useReactivateEmployeeMutation();

  const [selectedBranchIds, setSelectedBranchIds] = React.useState<string[]>([]);
  const [confirmingDeactivate, setConfirmingDeactivate] = React.useState(false);

  // React's "adjusting state when a prop changes" pattern (not an Effect):
  // resets the editable branch-checkbox copy whenever a *new* permissions
  // response arrives, without the cascading extra render an Effect-based
  // setState would cause.
  const [syncedPermsData, setSyncedPermsData] = React.useState(permsQuery.data);
  if (permsQuery.data !== syncedPermsData) {
    setSyncedPermsData(permsQuery.data);
    if (permsQuery.data) setSelectedBranchIds(permsQuery.data.branch_ids);
  }

  const reactivateForm = useForm<ReactivateEmployeeFormValues>({
    resolver: zodResolver(reactivateEmployeeSchema),
    defaultValues: { role_code: "", branch_ids: [] },
  });
  const handleReactivateApiError = useApiFormErrors(reactivateForm.setError);

  if (!employee) return null;

  const isDeactivated = employee.employee_status === "deactivated";

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{employee.full_name}</DialogTitle>
            <DialogDescription>{employee.email}</DialogDescription>
          </DialogHeader>

          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={employee.employee_status === "active" ? "success" : employee.employee_status === "invited" ? "info" : "neutral"}>
              {employee.employee_status}
            </Badge>
            {employee.department && <Badge variant="outline">{employee.department}</Badge>}
            {employee.position && <Badge variant="outline">{employee.position}</Badge>}
          </div>

          {permsQuery.isLoading && <Skeleton className="h-24 w-full" />}
          {permsQuery.isError && <ErrorState error={permsQuery.error} onRetry={() => permsQuery.refetch()} />}

          {permsQuery.data && !isDeactivated && (
            <div className="flex flex-col gap-3">
              <div className="text-body-sm">
                <span className="text-muted-foreground">Role: </span>
                <span className="font-medium text-foreground">{permsQuery.data.role_code ?? "—"}</span>
              </div>

              <PermissionGate permission="employees:write">
                <div className="flex flex-col gap-2 rounded-md border border-border p-3">
                  <p className="text-body-sm font-medium">Branch access</p>
                  <p className="text-caption text-muted-foreground">
                    {permsQuery.data.is_org_wide ? "Currently org-wide." : "Currently scoped to the checked branches."}
                  </p>
                  {(branchesQuery.data ?? []).map((branch) => (
                    <label key={branch.id} className="flex items-center gap-2 text-body-sm">
                      <Checkbox
                        checked={selectedBranchIds.includes(branch.id)}
                        onCheckedChange={(checked) =>
                          setSelectedBranchIds((prev) =>
                            checked === true ? [...prev, branch.id] : prev.filter((id) => id !== branch.id),
                          )
                        }
                      />
                      {branch.name}
                    </label>
                  ))}
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="self-end"
                    disabled={transferMutation.isPending}
                    onClick={() => transferMutation.mutate(selectedBranchIds)}
                  >
                    {transferMutation.isPending && <Spinner className="text-current" />}
                    Save branch access
                  </Button>
                </div>
              </PermissionGate>
            </div>
          )}

          {isDeactivated && (
            <PermissionGate
              permission="employees:write"
              fallback={<p className="text-body-sm text-muted-foreground">This employee was removed from the organization.</p>}
            >
              <Form {...reactivateForm}>
                <form
                  onSubmit={reactivateForm.handleSubmit((values) =>
                    reactivateMutation.mutate(
                      { employeeId: employee.employee_id, roleCode: values.role_code, branchIds: values.branch_ids },
                      { onSuccess: () => onOpenChange(false), onError: handleReactivateApiError },
                    ),
                  )}
                  className="flex flex-col gap-3 rounded-md border border-border p-3"
                  noValidate
                >
                  <p className="text-body-sm font-medium">Reactivate this employee</p>
                  <FormField
                    control={reactivateForm.control}
                    name="role_code"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Role</FormLabel>
                        <Select value={field.value} onValueChange={field.onChange}>
                          <FormControl>
                            <SelectTrigger className="w-full">
                              <SelectValue placeholder="Select a role" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {(rolesQuery.data ?? []).map((role) => (
                              <SelectItem key={role.id} value={role.code}>
                                {role.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <Button type="submit" size="sm" className="self-end" disabled={reactivateMutation.isPending}>
                    {reactivateMutation.isPending && <Spinner className="text-current" />}
                    Reactivate
                  </Button>
                </form>
              </Form>
            </PermissionGate>
          )}

          <DialogFooter>
            {!isDeactivated && (
              <PermissionGate permission="employees:delete">
                <Button type="button" variant="destructive" onClick={() => setConfirmingDeactivate(true)}>
                  Remove from organization
                </Button>
              </PermissionGate>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={confirmingDeactivate} onOpenChange={setConfirmingDeactivate}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove {employee.full_name}?</AlertDialogTitle>
            <AlertDialogDescription>
              They&apos;ll lose access to this organization immediately. This can be reversed later by reactivating them
              with a role.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deactivateMutation.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={deactivateMutation.isPending}
              onClick={() =>
                deactivateMutation.mutate(
                  { employeeId: employee.employee_id },
                  {
                    onSuccess: () => {
                      setConfirmingDeactivate(false);
                      onOpenChange(false);
                    },
                  },
                )
              }
            >
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
