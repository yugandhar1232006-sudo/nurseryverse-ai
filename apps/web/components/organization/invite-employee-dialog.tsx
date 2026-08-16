"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Skeleton } from "@/components/ui/skeleton";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useRolesQuery } from "@/lib/organization/queries";
import { useBranchesQuery } from "@/lib/shell/queries";
import { useInviteEmployeeMutation } from "@/lib/organization/mutations";
import { inviteEmployeeSchema, type InviteEmployeeFormValues } from "@/lib/validation/organization";

/**
 * `POST /employees/invite` -- the role picker is the real
 * `GET /admin/roles` catalog (system roles + this org's own custom
 * roles), never a hardcoded role-name list, so a custom role created
 * elsewhere (Growth/Enterprise tier, per docs/ux/07-role-permission-matrix.md)
 * shows up here automatically.
 */
export function InviteEmployeeDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const rolesQuery = useRolesQuery();
  const branchesQuery = useBranchesQuery();
  const mutation = useInviteEmployeeMutation();

  const form = useForm<InviteEmployeeFormValues>({
    resolver: zodResolver(inviteEmployeeSchema),
    defaultValues: { email: "", role_code: "", branch_ids: [] },
  });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    if (open) form.reset({ email: "", role_code: "", branch_ids: [] });
  }, [open, form]);

  function onSubmit(values: InviteEmployeeFormValues) {
    mutation.mutate(
      { email: values.email, role_code: values.role_code, branch_ids: values.branch_ids },
      { onSuccess: () => onOpenChange(false), onError: handleApiError },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Invite an employee</DialogTitle>
          <DialogDescription>They&apos;ll receive an invitation to join your organization with the role and branch access you choose.</DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email</FormLabel>
                  <FormControl>
                    <Input type="email" autoComplete="email" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="role_code"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Role</FormLabel>
                  {rolesQuery.isLoading ? (
                    <Skeleton className="h-9 w-full" />
                  ) : (
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
                  )}
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="branch_ids"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Branch access</FormLabel>
                  <p className="text-caption text-muted-foreground">Leave unchecked for org-wide roles (Owner/Org Admin).</p>
                  <div className="flex flex-col gap-2">
                    {(branchesQuery.data ?? []).map((branch) => (
                      <label key={branch.id} className="flex items-center gap-2 text-body-sm">
                        <Checkbox
                          checked={field.value.includes(branch.id)}
                          onCheckedChange={(checked) =>
                            field.onChange(
                              checked === true ? [...field.value, branch.id] : field.value.filter((id) => id !== branch.id),
                            )
                          }
                        />
                        {branch.name}
                      </label>
                    ))}
                  </div>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={mutation.isPending}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending} aria-busy={mutation.isPending}>
                {mutation.isPending && <Spinner className="text-current" />}
                Send invitation
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
