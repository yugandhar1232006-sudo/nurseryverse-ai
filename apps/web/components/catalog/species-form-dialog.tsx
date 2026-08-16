"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage, FormDescription } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Skeleton } from "@/components/ui/skeleton";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { usePlantCategoriesQuery } from "@/lib/catalog/queries";
import { useCreateSpeciesMutation, useUpdateSpeciesMutation } from "@/lib/catalog/mutations";
import { speciesSchema, type SpeciesFormValues } from "@/lib/validation/catalog";
import type { SpeciesResponse } from "@/lib/api/catalog";

function toDefaultValues(species: SpeciesResponse | null): SpeciesFormValues {
  return {
    category_id: species?.category_id ?? "",
    common_name: species?.common_name ?? "",
    botanical_name: species?.botanical_name ?? "",
    light_requirement: species?.light_requirement ?? "",
    water_baseline_ml_per_week: species?.water_baseline_ml_per_week != null ? String(species.water_baseline_ml_per_week) : "",
    soil_type: species?.soil_type ?? "",
    temperature_min_celsius: species?.temperature_min_celsius != null ? String(species.temperature_min_celsius) : "",
    temperature_max_celsius: species?.temperature_max_celsius != null ? String(species.temperature_max_celsius) : "",
    disease_susceptibility: Array.isArray(species?.disease_susceptibility) ? species.disease_susceptibility.join(", ") : "",
  };
}

/**
 * Handles both create and edit -- `species === null` means "create new."
 * `disease_susceptibility` is edited as a single comma-separated field
 * (matching the backend's `list[str] | None`) rather than a tag-picker
 * widget -- the backend has no controlled vocabulary for disease names to
 * pick from, so free-text-split-on-comma is the honest representation of
 * what this field actually is. `growth_curve_baseline` (a list of
 * `{days_since_planting, expected_height_cm}` points) is intentionally
 * not editable here -- see docs/frontend/10-plant-catalog.md's Known
 * Limitations; it's shown read-only in the detail view.
 */
export function SpeciesFormDialog({
  open,
  onOpenChange,
  species,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  species: SpeciesResponse | null;
}) {
  const categoriesQuery = usePlantCategoriesQuery();
  const createMutation = useCreateSpeciesMutation();
  const updateMutation = useUpdateSpeciesMutation(species?.id ?? "");
  const mutation = species ? updateMutation : createMutation;

  const form = useForm<SpeciesFormValues>({
    resolver: zodResolver(speciesSchema),
    defaultValues: toDefaultValues(species),
  });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    if (open) form.reset(toDefaultValues(species));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, species?.id]);

  function onSubmit(values: SpeciesFormValues) {
    const body = {
      category_id: values.category_id,
      common_name: values.common_name,
      botanical_name: values.botanical_name,
      light_requirement: values.light_requirement || null,
      water_baseline_ml_per_week: values.water_baseline_ml_per_week === "" ? null : Number(values.water_baseline_ml_per_week),
      soil_type: values.soil_type || null,
      temperature_min_celsius: values.temperature_min_celsius === "" ? null : Number(values.temperature_min_celsius),
      temperature_max_celsius: values.temperature_max_celsius === "" ? null : Number(values.temperature_max_celsius),
      disease_susceptibility:
        values.disease_susceptibility && values.disease_susceptibility.trim() !== ""
          ? values.disease_susceptibility.split(",").map((s) => s.trim()).filter(Boolean)
          : null,
    };
    mutation.mutate(body, { onSuccess: () => onOpenChange(false), onError: handleApiError });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{species ? "Edit species" : "Add species"}</DialogTitle>
          <DialogDescription>
            {species ? "Update this species' identity and care attributes." : "Add a species to your organization's catalog."}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <FormField
              control={form.control}
              name="category_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Category</FormLabel>
                  {categoriesQuery.isLoading ? (
                    <Skeleton className="h-9 w-full" />
                  ) : (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select a category" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {(categoriesQuery.data ?? []).map((cat) => (
                          <SelectItem key={cat.id} value={cat.id}>
                            {cat.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid grid-cols-1 gap-4 tablet:grid-cols-2">
              <FormField
                control={form.control}
                name="common_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Common name</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="botanical_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Botanical name</FormLabel>
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
                name="light_requirement"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Light requirement (optional)</FormLabel>
                    <FormControl>
                      <Input placeholder="full_sun, partial_shade, ..." {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="soil_type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Soil type (optional)</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name="water_baseline_ml_per_week"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Water baseline (mL/week, optional)</FormLabel>
                  <FormControl>
                    <Input inputMode="numeric" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid grid-cols-1 gap-4 tablet:grid-cols-2">
              <FormField
                control={form.control}
                name="temperature_min_celsius"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Min temperature (°C, optional)</FormLabel>
                    <FormControl>
                      <Input inputMode="decimal" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="temperature_max_celsius"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Max temperature (°C, optional)</FormLabel>
                    <FormControl>
                      <Input inputMode="decimal" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name="disease_susceptibility"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Disease susceptibility (optional)</FormLabel>
                  <FormControl>
                    <Input placeholder="root rot, powdery mildew" {...field} />
                  </FormControl>
                  <FormDescription>Comma-separated.</FormDescription>
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
                {species ? "Save changes" : "Add species"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
