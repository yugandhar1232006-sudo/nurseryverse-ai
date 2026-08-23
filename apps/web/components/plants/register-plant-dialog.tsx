"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Skeleton } from "@/components/ui/skeleton";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useBranchesQuery } from "@/lib/shell/queries";
import { useSpeciesListQuery, usePlantVarietiesQuery } from "@/lib/catalog/queries";
import { useSuppliersQuery } from "@/lib/suppliers/queries";
import { useRegisterPlantMutation } from "@/lib/plants/mutations";
import { registerPlantSchema, type RegisterPlantFormValues } from "@/lib/validation/plants";

const NO_VARIETY = "__none__";
const NO_SUPPLIER = "__none__";

const DEFAULT_VALUES: RegisterPlantFormValues = {
  branch_id: "",
  species_id: "",
  variety_id: "",
  common_label: "",
  zone: "",
  batch_number: "",
  supplier_id: "",
  purchase_price: "",
  purchase_date: "",
  planted_at: "",
  price: "",
  description: "",
};

export function RegisterPlantDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const branchesQuery = useBranchesQuery();
  const suppliersQuery = useSuppliersQuery();
  const mutation = useRegisterPlantMutation();

  const form = useForm<RegisterPlantFormValues>({
    resolver: zodResolver(registerPlantSchema),
    defaultValues: DEFAULT_VALUES,
  });
  const handleApiError = useApiFormErrors(form.setError);
  const speciesId = form.watch("species_id");

  const speciesQuery = useSpeciesListQuery({ page: 1, page_size: 100 });
  const varietiesQuery = usePlantVarietiesQuery({ species_id: speciesId || undefined, page: 1, page_size: 100 });

  React.useEffect(() => {
    if (open) form.reset(DEFAULT_VALUES);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function onSubmit(values: RegisterPlantFormValues) {
    mutation.mutate(
      {
        branch_id: values.branch_id,
        species_id: values.species_id,
        variety_id: values.variety_id && values.variety_id !== NO_VARIETY ? values.variety_id : null,
        common_label: values.common_label || null,
        zone: values.zone || null,
        batch_number: values.batch_number || null,
        supplier_id: values.supplier_id && values.supplier_id !== NO_SUPPLIER ? values.supplier_id : null,
        purchase_price: values.purchase_price === "" ? null : Number(values.purchase_price),
        purchase_date: values.purchase_date || null,
        planted_at: values.planted_at || null,
        price: values.price === "" ? null : Number(values.price),
        description: values.description || null,
      },
      { onSuccess: () => onOpenChange(false), onError: handleApiError },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Register a plant</DialogTitle>
          <DialogDescription>Creates a new plant record at a specific branch, tied to a species.</DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <FormField
              control={form.control}
              name="branch_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Branch</FormLabel>
                  {branchesQuery.isLoading ? (
                    <Skeleton className="h-9 w-full" />
                  ) : (
                    <Select value={field.value} onValueChange={field.onChange}>
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
              name="species_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Species</FormLabel>
                  {speciesQuery.isLoading ? (
                    <Skeleton className="h-9 w-full" />
                  ) : (
                    <Select
                      value={field.value}
                      onValueChange={(value) => {
                        field.onChange(value);
                        form.setValue("variety_id", "");
                      }}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select a species" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {(speciesQuery.data?.items ?? []).map((species) => (
                          <SelectItem key={species.id} value={species.id}>
                            {species.common_name}
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
              name="variety_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Variety (optional)</FormLabel>
                  <Select
                    value={field.value || NO_VARIETY}
                    onValueChange={(value) => field.onChange(value === NO_VARIETY ? "" : value)}
                    disabled={!speciesId}
                  >
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder={speciesId ? "Select a variety" : "Select a species first"} />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value={NO_VARIETY}>No variety</SelectItem>
                      {(varietiesQuery.data?.items ?? []).map((variety) => (
                        <SelectItem key={variety.id} value={variety.id}>
                          {variety.name}
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
                name="common_label"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Label (optional)</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g. Bench 3, Row A" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="zone"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Zone (optional)</FormLabel>
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
                name="batch_number"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Batch number (optional)</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="price"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Sale price (optional)</FormLabel>
                    <FormControl>
                      <Input inputMode="decimal" placeholder="0.00" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name="supplier_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Supplier (optional)</FormLabel>
                  {suppliersQuery.isLoading ? (
                    <Skeleton className="h-9 w-full" />
                  ) : (
                    <Select value={field.value || NO_SUPPLIER} onValueChange={(v) => field.onChange(v === NO_SUPPLIER ? "" : v)}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select a supplier" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value={NO_SUPPLIER}>No supplier</SelectItem>
                        {(suppliersQuery.data ?? []).map((supplier) => (
                          <SelectItem key={supplier.id} value={supplier.id}>
                            {supplier.name}
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
                name="purchase_price"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Purchase price (optional)</FormLabel>
                    <FormControl>
                      <Input inputMode="decimal" placeholder="0.00" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="purchase_date"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Purchase date (optional)</FormLabel>
                    <FormControl>
                      <Input type="date" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name="planted_at"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Planted date (optional)</FormLabel>
                  <FormControl>
                    <Input type="date" {...field} />
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
                    <Textarea placeholder="Notes about this plant..." rows={3} {...field} />
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
                Register plant
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
