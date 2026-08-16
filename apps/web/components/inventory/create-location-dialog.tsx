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
import { useCreateInventoryLocationMutation } from "@/lib/inventory/mutations";
import { createInventoryLocationSchema, type CreateInventoryLocationFormValues } from "@/lib/validation/inventory";
import type { InventoryLocationType } from "@/lib/api/inventory";

const LOCATION_TYPE_OPTIONS: { value: InventoryLocationType; label: string }[] = [
  { value: "zone", label: "Zone" },
  { value: "greenhouse", label: "Greenhouse" },
  { value: "outdoor_area", label: "Outdoor area" },
  { value: "rack", label: "Rack" },
  { value: "bench", label: "Bench" },
  { value: "section", label: "Section" },
];

/**
 * `InventoryLocation` is a sub-branch physical hierarchy (Zone/Greenhouse/
 * Outdoor Area/Rack/Bench/Section) -- always nested under a specific
 * `branch_id`, never a standalone location (see `InventoryLocationType`'s
 * docstring). `parent_location_id` is left unset here: nesting locations
 * under each other is real backend behavior (`create_location` validates
 * the parent belongs to the same branch), but no product requirement
 * called for a nested-location picker in this initial 7I build.
 */
export function CreateLocationDialog({
  open,
  onOpenChange,
  branchId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  branchId: string;
}) {
  const mutation = useCreateInventoryLocationMutation();
  const form = useForm<CreateInventoryLocationFormValues>({
    resolver: zodResolver(createInventoryLocationSchema),
    defaultValues: { branch_id: branchId, location_type: "zone", name: "", code: "", parent_location_id: "" },
  });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    if (open) form.reset({ branch_id: branchId, location_type: "zone", name: "", code: "", parent_location_id: "" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, branchId]);

  function onSubmit(values: CreateInventoryLocationFormValues) {
    mutation.mutate(
      { branch_id: values.branch_id, location_type: values.location_type, name: values.name, code: values.code || null, parent_location_id: null },
      { onSuccess: () => onOpenChange(false), onError: handleApiError },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Create location</DialogTitle>
          <DialogDescription>Adds a sub-branch physical location for organizing stock.</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g. Greenhouse 2" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="location_type"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Type</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {LOCATION_TYPE_OPTIONS.map((opt) => (
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
              name="code"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Code (optional)</FormLabel>
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
                Create location
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
