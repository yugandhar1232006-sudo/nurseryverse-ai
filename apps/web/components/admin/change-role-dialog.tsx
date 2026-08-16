"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useChangeUserRoleMutation } from "@/lib/admin/mutations";
import { changeRoleSchema, type ChangeRoleFormValues } from "@/lib/validation/admin";
import type { AdminUserResponse, RoleResponse } from "@/lib/api/admin";

/** `POST /admin/users/{id}/role`, `employees:write` -- assigns an existing real role to a user. There is no create/edit-role route (verified against `admin.py`; see `lib/api/admin.ts`'s docstring on PG-57's fabricated `roles:manage`/"custom role builder" claim), so this dialog's only real job is picking one of the org's existing roles. */
export function ChangeRoleDialog({
  user,
  roles,
  open,
  onOpenChange,
}: {
  user: AdminUserResponse | null;
  roles: RoleResponse[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const mutation = useChangeUserRoleMutation();
  const form = useForm<ChangeRoleFormValues>({ resolver: zodResolver(changeRoleSchema), defaultValues: { new_role_code: "" } });
  const handleApiError = useApiFormErrors(form.setError);

  function onSubmit(values: ChangeRoleFormValues) {
    if (!user) return;
    mutation.mutate(
      { userId: user.id, newRoleCode: values.new_role_code },
      { onSuccess: () => onOpenChange(false), onError: handleApiError },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Change role</DialogTitle>
          <DialogDescription>{user ? `Assign a new role to ${user.full_name}.` : null}</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <FormField
              control={form.control}
              name="new_role_code"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Role</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger className="w-full" aria-label="Role">
                        <SelectValue placeholder="Choose a role" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {roles.map((role) => (
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
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={mutation.isPending}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending} aria-busy={mutation.isPending}>
                {mutation.isPending && <Spinner className="text-current" />}
                Change role
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
