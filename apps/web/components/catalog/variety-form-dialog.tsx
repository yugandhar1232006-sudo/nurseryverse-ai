"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useCreatePlantVarietyMutation, useUpdatePlantVarietyMutation } from "@/lib/catalog/mutations";
import { plantVarietySchema, type PlantVarietyFormValues } from "@/lib/validation/catalog";
import type { PlantVarietyResponse } from "@/lib/api/catalog";

/** Handles both create and edit -- `variety === null` means "create new," scoped to `speciesId` (the species detail view this dialog is always opened from). */
export function VarietyFormDialog({
  open,
  onOpenChange,
  speciesId,
  variety,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  speciesId: string;
  variety: PlantVarietyResponse | null;
}) {
  const createMutation = useCreatePlantVarietyMutation();
  const updateMutation = useUpdatePlantVarietyMutation(variety?.id ?? "");
  const mutation = variety ? updateMutation : createMutation;

  const form = useForm<PlantVarietyFormValues>({
    resolver: zodResolver(plantVarietySchema),
    defaultValues: { species_id: speciesId, name: variety?.name ?? "", description: variety?.description ?? "" },
  });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    if (open) form.reset({ species_id: speciesId, name: variety?.name ?? "", description: variety?.description ?? "" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, variety?.id, speciesId]);

  function onSubmit(values: PlantVarietyFormValues) {
    if (variety) {
      updateMutation.mutate(
        { name: values.name, description: values.description || null },
        { onSuccess: () => onOpenChange(false), onError: handleApiError },
      );
    } else {
      createMutation.mutate(
        { species_id: values.species_id, name: values.name, description: values.description || null },
        { onSuccess: () => onOpenChange(false), onError: handleApiError },
      );
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{variety ? "Edit variety" : "Add variety"}</DialogTitle>
          <DialogDescription>
            {variety ? "Update this cultivar's name and description." : "Add a cultivar/variety under this species."}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Variety name</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Description (optional)</FormLabel>
                  <FormControl>
                    <Textarea rows={3} {...field} />
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
                {variety ? "Save changes" : "Add variety"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
