"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useLockUserMutation } from "@/lib/admin/mutations";
import { lockAccountSchema, type LockAccountFormValues } from "@/lib/validation/admin";
import type { AdminUserResponse } from "@/lib/api/admin";

/** `POST /admin/users/{id}/lock`, `employees:write`. Real constraint: 1 to 10080 minutes (7 days), matching `LockAccountRequest`'s own docstring. */
export function LockAccountDialog({
  user,
  open,
  onOpenChange,
}: {
  user: AdminUserResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const mutation = useLockUserMutation();
  const form = useForm<LockAccountFormValues>({ resolver: zodResolver(lockAccountSchema), defaultValues: { duration_minutes: "15" } });
  const handleApiError = useApiFormErrors(form.setError);

  function onSubmit(values: LockAccountFormValues) {
    if (!user) return;
    mutation.mutate(
      { userId: user.id, durationMinutes: Number(values.duration_minutes) },
      { onSuccess: () => onOpenChange(false), onError: handleApiError },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Lock account</DialogTitle>
          <DialogDescription>{user ? `Prevents ${user.full_name} from logging in until the lock expires.` : null}</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <FormField
              control={form.control}
              name="duration_minutes"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Duration (minutes)</FormLabel>
                  <FormControl>
                    <Input type="number" min={1} max={10080} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={mutation.isPending}>
                Cancel
              </Button>
              <Button type="submit" variant="destructive" disabled={mutation.isPending} aria-busy={mutation.isPending}>
                {mutation.isPending && <Spinner className="text-current" />}
                Lock account
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
