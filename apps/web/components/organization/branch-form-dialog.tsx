"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useCreateBranchMutation, useUpdateBranchMutation } from "@/lib/organization/mutations";
import { branchSchema, WEEKDAYS, WEEKDAY_LABELS, type BranchFormValues } from "@/lib/validation/organization";
import type { BranchResponse, OperatingHoursWindow } from "@/lib/api/branches";

function defaultHours(existing: BranchResponse["operating_hours"]): BranchFormValues["hours"] {
  const record = (existing ?? {}) as Record<string, OperatingHoursWindow | null> | null;
  const hours: BranchFormValues["hours"] = {};
  for (const day of WEEKDAYS) {
    const window = record?.[day];
    hours[day] = window ? { closed: false, open: window.open, close: window.close } : { closed: true, open: "09:00", close: "17:00" };
  }
  return hours;
}

function toDefaultValues(branch: BranchResponse | null): BranchFormValues {
  return {
    name: branch?.name ?? "",
    address_line1: branch?.address_line1 ?? "",
    address_line2: branch?.address_line2 ?? "",
    city: branch?.city ?? "",
    region: branch?.region ?? "",
    postal_code: branch?.postal_code ?? "",
    country: branch?.country ?? "US",
    timezone: branch?.timezone ?? "America/Los_Angeles",
    phone: branch?.phone ?? "",
    email: branch?.email ?? "",
    latitude: branch?.latitude != null ? String(branch.latitude) : "",
    longitude: branch?.longitude != null ? String(branch.longitude) : "",
    hours: defaultHours(branch?.operating_hours ?? null),
  };
}

/**
 * Handles both create and edit -- `branch === null` means "create new."
 * Operating hours are edited as a real 7-row per-weekday open/close
 * editor (a "Closed" checkbox per day, matching
 * `CreateBranchRequest.operating_hours: dict[str, OperatingHoursWindow | None]`'s
 * real shape exactly: a closed day is submitted as `null`, not an empty
 * string pair).
 */
export function BranchFormDialog({
  open,
  onOpenChange,
  branch,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  branch: BranchResponse | null;
}) {
  const createMutation = useCreateBranchMutation();
  const updateMutation = useUpdateBranchMutation(branch?.id ?? "");
  const mutation = branch ? updateMutation : createMutation;

  const form = useForm<BranchFormValues>({
    resolver: zodResolver(branchSchema),
    defaultValues: toDefaultValues(branch),
  });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    if (open) form.reset(toDefaultValues(branch));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, branch?.id]);

  function onSubmit(values: BranchFormValues) {
    const operating_hours = Object.fromEntries(
      WEEKDAYS.map((day) => [day, values.hours[day].closed ? null : { open: values.hours[day].open, close: values.hours[day].close }]),
    );
    const body = {
      name: values.name,
      address_line1: values.address_line1,
      address_line2: values.address_line2 || null,
      city: values.city,
      region: values.region || null,
      postal_code: values.postal_code || null,
      country: values.country,
      timezone: values.timezone,
      phone: values.phone || null,
      email: values.email || null,
      latitude: values.latitude === "" ? null : Number(values.latitude),
      longitude: values.longitude === "" ? null : Number(values.longitude),
      operating_hours,
    };
    mutation.mutate(body, {
      onSuccess: () => onOpenChange(false),
      onError: handleApiError,
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{branch ? "Edit branch" : "Create branch"}</DialogTitle>
          <DialogDescription>
            {branch ? "Update this branch's details and operating hours." : "Add a new branch to your organization."}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Branch name</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="address_line1"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Address line 1</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="address_line2"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Address line 2 (optional)</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid grid-cols-1 gap-4 tablet:grid-cols-3">
              <FormField
                control={form.control}
                name="city"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>City</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="region"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Region/State</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="postal_code"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Postal code</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <div className="grid grid-cols-1 gap-4 tablet:grid-cols-2">
              <FormField
                control={form.control}
                name="country"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Country (ISO 3166-1 alpha-2)</FormLabel>
                    <FormControl>
                      <Input maxLength={2} placeholder="US" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="timezone"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Timezone (IANA)</FormLabel>
                    <FormControl>
                      <Input placeholder="America/Los_Angeles" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <div className="grid grid-cols-1 gap-4 tablet:grid-cols-2">
              <FormField
                control={form.control}
                name="phone"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Phone (optional)</FormLabel>
                    <FormControl>
                      <Input type="tel" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Email (optional)</FormLabel>
                    <FormControl>
                      <Input type="email" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <fieldset className="flex flex-col gap-2 rounded-md border border-border p-3">
              <legend className="px-1 text-body-sm font-medium">Operating hours</legend>
              {WEEKDAYS.map((day) => (
                <div key={day} className="flex flex-wrap items-center gap-3">
                  <span className="w-24 shrink-0 text-body-sm capitalize">{WEEKDAY_LABELS[day]}</span>
                  <FormField
                    control={form.control}
                    name={`hours.${day}.closed`}
                    render={({ field }) => (
                      <label className="flex items-center gap-2 text-body-sm text-muted-foreground">
                        <Checkbox checked={field.value} onCheckedChange={(checked) => field.onChange(checked === true)} />
                        Closed
                      </label>
                    )}
                  />
                  {!form.watch(`hours.${day}.closed`) && (
                    <>
                      <FormField
                        control={form.control}
                        name={`hours.${day}.open`}
                        render={({ field }) => <Input type="time" className="w-28" {...field} aria-label={`${day} opening time`} />}
                      />
                      <span className="text-muted-foreground">to</span>
                      <FormField
                        control={form.control}
                        name={`hours.${day}.close`}
                        render={({ field }) => <Input type="time" className="w-28" {...field} aria-label={`${day} closing time`} />}
                      />
                    </>
                  )}
                </div>
              ))}
            </fieldset>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={mutation.isPending}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending} aria-busy={mutation.isPending}>
                {mutation.isPending && <Spinner className="text-current" />}
                {branch ? "Save changes" : "Create branch"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
