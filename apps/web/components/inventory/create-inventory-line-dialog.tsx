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
import { Skeleton } from "@/components/ui/skeleton";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useBranchesQuery } from "@/lib/shell/queries";
import { usePlantCategoriesQuery, useSpeciesListQuery } from "@/lib/catalog/queries";
import { useUnitsQuery, useInventoryLocationsQuery } from "@/lib/inventory/queries";
import { useCreateInventoryLineMutation } from "@/lib/inventory/mutations";
import { createInventoryLineSchema, type CreateInventoryLineFormValues } from "@/lib/validation/inventory";

const NO_SPECIES = "__none__";
const NO_LOCATION = "__none__";

const DEFAULT_VALUES: CreateInventoryLineFormValues = {
  branch_id: "",
  category_id: "",
  unit_id: "",
  name: "",
  species_id: "",
  location_id: "",
  unit_cost: "",
  unit_price: "",
  low_stock_threshold: "10",
  initial_quantity: "0",
};

/**
 * `CreateInventoryLineRequest` -- bulk stock (a supply/consumable line,
 * e.g. "4in nursery pots" or "10-10-10 fertilizer bags"), not an
 * individually-tracked `Plant` (that's 7G's `RegisterPlantDialog`).
 * `species_id` is optional here for exactly the reason Module 8's own
 * docstring gives: most inventory lines are pots/soil/fertilizer/tools
 * with no species at all, but a line CAN optionally tag a species when
 * the stock is itself a batch of unindividuated plant material.
 */
export function CreateInventoryLineDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const branchesQuery = useBranchesQuery();
  const categoriesQuery = usePlantCategoriesQuery();
  const unitsQuery = useUnitsQuery();
  const speciesQuery = useSpeciesListQuery({ page: 1, page_size: 100 });
  const mutation = useCreateInventoryLineMutation();

  const form = useForm<CreateInventoryLineFormValues>({
    resolver: zodResolver(createInventoryLineSchema),
    defaultValues: DEFAULT_VALUES,
  });
  const handleApiError = useApiFormErrors(form.setError);
  const branchId = form.watch("branch_id");

  const locationsQuery = useInventoryLocationsQuery(branchId || null);

  React.useEffect(() => {
    if (open) form.reset(DEFAULT_VALUES);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function onSubmit(values: CreateInventoryLineFormValues) {
    mutation.mutate(
      {
        branch_id: values.branch_id,
        category_id: values.category_id,
        unit_id: values.unit_id,
        name: values.name,
        species_id: values.species_id && values.species_id !== NO_SPECIES ? values.species_id : null,
        location_id: values.location_id && values.location_id !== NO_LOCATION ? values.location_id : null,
        unit_cost: values.unit_cost === "" ? null : Number(values.unit_cost),
        unit_price: values.unit_price === "" ? null : Number(values.unit_price),
        low_stock_threshold: values.low_stock_threshold === "" ? 10 : Number(values.low_stock_threshold),
        initial_quantity: values.initial_quantity === "" ? 0 : Number(values.initial_quantity),
      },
      { onSuccess: () => onOpenChange(false), onError: handleApiError },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create inventory line</DialogTitle>
          <DialogDescription>Adds a new bulk-stock line at a branch (e.g. pots, soil, fertilizer).</DialogDescription>
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
                    <Input placeholder="e.g. 4in nursery pots" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid grid-cols-1 gap-4 tablet:grid-cols-2">
              <FormField
                control={form.control}
                name="branch_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Branch</FormLabel>
                    {branchesQuery.isLoading ? (
                      <Skeleton className="h-9 w-full" />
                    ) : (
                      <Select
                        value={field.value}
                        onValueChange={(value) => {
                          field.onChange(value);
                          form.setValue("location_id", "");
                        }}
                      >
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select a branch" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {(branchesQuery.data ?? []).map((branch) => (
                            <SelectItem key={branch.id} value={branch.id}>
                              {branch.name}
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
                name="location_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Location (optional)</FormLabel>
                    <Select
                      value={field.value || NO_LOCATION}
                      onValueChange={(value) => field.onChange(value === NO_LOCATION ? "" : value)}
                      disabled={!branchId}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder={branchId ? "Select a location" : "Select a branch first"} />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value={NO_LOCATION}>No specific location</SelectItem>
                        {(locationsQuery.data ?? []).map((location) => (
                          <SelectItem key={location.id} value={location.id}>
                            {location.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <div className="grid grid-cols-1 gap-4 tablet:grid-cols-2">
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
                          {(categoriesQuery.data ?? []).map((category) => (
                            <SelectItem key={category.id} value={category.id}>
                              {category.name}
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
                name="unit_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Unit</FormLabel>
                    {unitsQuery.isLoading ? (
                      <Skeleton className="h-9 w-full" />
                    ) : (
                      <Select value={field.value} onValueChange={field.onChange}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select a unit" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {(unitsQuery.data ?? []).map((unit) => (
                            <SelectItem key={unit.id} value={unit.id}>
                              {unit.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name="species_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Species (optional)</FormLabel>
                  <Select value={field.value || NO_SPECIES} onValueChange={(value) => field.onChange(value === NO_SPECIES ? "" : value)}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="No specific species" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value={NO_SPECIES}>No specific species</SelectItem>
                      {(speciesQuery.data?.items ?? []).map((species) => (
                        <SelectItem key={species.id} value={species.id}>
                          {species.common_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid grid-cols-1 gap-4 tablet:grid-cols-2">
              <FormField
                control={form.control}
                name="unit_cost"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Unit cost (optional)</FormLabel>
                    <FormControl>
                      <Input inputMode="decimal" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="unit_price"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Unit price (optional)</FormLabel>
                    <FormControl>
                      <Input inputMode="decimal" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <div className="grid grid-cols-1 gap-4 tablet:grid-cols-2">
              <FormField
                control={form.control}
                name="low_stock_threshold"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Low stock threshold</FormLabel>
                    <FormControl>
                      <Input inputMode="numeric" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="initial_quantity"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Initial quantity</FormLabel>
                    <FormControl>
                      <Input inputMode="numeric" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={mutation.isPending}>
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending} aria-busy={mutation.isPending}>
                {mutation.isPending && <Spinner className="text-current" />}
                Create line
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
