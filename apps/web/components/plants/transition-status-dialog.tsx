"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useTransitionStatusMutation } from "@/lib/plants/mutations";
import { transitionStatusSchema, type TransitionStatusFormValues } from "@/lib/validation/plants";
import type { PlantStatus } from "@/lib/api/plants";

const STATUS_OPTIONS: { value: PlantStatus; label: string }[] = [
  { value: "in_production", label: "In production" },
  { value: "ready_for_sale", label: "Ready for sale" },
  { value: "under_treatment", label: "Under treatment" },
  { value: "sold", label: "Sold" },
  { value: "deceased", label: "Deceased" },
];

/**
 * Every option is always offered -- the frontend does not attempt to
 * pre-filter to only "legal" next states, since the real state machine
 * (docs/ux/13-digital-twin-lifecycle.md) lives entirely server-side. An
 * illegal choice comes back as a real 409, shown as a toast via
 * `useTransitionStatusMutation`'s `onError`, and the dialog stays open
 * so the user can pick a different status.
 */
export function TransitionStatusDialog({
  open,
  onOpenChange,
  plantId,
  currentStatus,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  plantId: string;
  currentStatus: PlantStatus;
}) {
  const mutation = useTransitionStatusMutation(plantId);

  const form = useForm<TransitionStatusFormValues>({
    resolver: zodResolver(transitionStatusSchema),
    defaultValues: { to_status: currentStatus, reason: "" },
  });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    if (open) form.reset({ to_status: currentStatus, reason: "" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, currentStatus]);

  function onSubmit(values: TransitionStatusFormValues) {
    mutation.mutate(
      { to_status: values.to_status, reason: values.reason || null },
      { onSuccess: () => onOpenChange(false), onError: handleApiError },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Change status</DialogTitle>
          <DialogDescription>The backend enforces the valid lifecycle transitions and will reject an illegal one.</DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <FormField
              control={form.control}
              name="to_status"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>New status</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {STATUS_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="reason"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Reason (optional)</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
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
                Update status
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
