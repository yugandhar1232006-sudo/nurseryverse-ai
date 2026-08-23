"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Skeleton } from "@/components/ui/skeleton";
import { PermissionGate } from "@/components/auth/permission-gate";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { usePlantVarietiesQuery } from "@/lib/catalog/queries";
import { useSuppliersQuery } from "@/lib/suppliers/queries";
import { useUpdatePlantProfileMutation } from "@/lib/plants/mutations";
import { updatePlantProfileSchema, type UpdatePlantProfileFormValues } from "@/lib/validation/plants";
import { formatCurrency } from "@/lib/utils";
import type { PlantResponse } from "@/lib/api/plants";

const NO_VARIETY = "__none__";
const NO_SUPPLIER = "__none__";

function toDefaultValues(plant: PlantResponse): UpdatePlantProfileFormValues {
  return {
    common_label: plant.common_label ?? "",
    variety_id: plant.variety_id ?? "",
    batch_number: plant.batch_number ?? "",
    supplier_id: plant.supplier_id ?? "",
    purchase_price: plant.purchase_price != null ? String(plant.purchase_price) : "",
    purchase_date: plant.purchase_date ?? "",
    price: plant.price != null ? String(plant.price) : "",
    description: plant.description ?? "",
  };
}

export function OverviewTab({ plant }: { plant: PlantResponse }) {
  const varietiesQuery = usePlantVarietiesQuery({ species_id: plant.species_id, page: 1, page_size: 100 });
  const suppliersQuery = useSuppliersQuery();
  const mutation = useUpdatePlantProfileMutation(plant.id);

  const form = useForm<UpdatePlantProfileFormValues>({
    resolver: zodResolver(updatePlantProfileSchema),
    defaultValues: toDefaultValues(plant),
  });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    form.reset(toDefaultValues(plant));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plant.id, plant.common_label, plant.variety_id, plant.batch_number, plant.price, plant.supplier_id, plant.purchase_price, plant.purchase_date, plant.description]);

  function onSubmit(values: UpdatePlantProfileFormValues) {
    mutation.mutate(
      {
        common_label: values.common_label || null,
        variety_id: values.variety_id && values.variety_id !== NO_VARIETY ? values.variety_id : null,
        batch_number: values.batch_number || null,
        supplier_id: values.supplier_id && values.supplier_id !== NO_SUPPLIER ? values.supplier_id : null,
        purchase_price: values.purchase_price === "" ? null : Number(values.purchase_price),
        purchase_date: values.purchase_date || null,
        price: values.price === "" ? null : Number(values.price),
        description: values.description,
      },
      { onError: handleApiError },
    );
  }

  const supplierName = plant.supplier_id
    ? (suppliersQuery.data ?? []).find((s) => s.id === plant.supplier_id)?.name ?? "—"
    : null;

  return (
    <PermissionGate
      permission="plants:write"
      fallback={
        <dl className="grid grid-cols-1 gap-4 tablet:grid-cols-2">
          <div>
            <dt className="text-caption text-muted-foreground">Label</dt>
            <dd className="text-body text-foreground">{plant.common_label ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-caption text-muted-foreground">Batch number</dt>
            <dd className="text-body text-foreground">{plant.batch_number ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-caption text-muted-foreground">Price</dt>
            <dd className="text-body text-foreground">{plant.price != null ? formatCurrency(plant.price) : "—"}</dd>
          </div>
          <div>
            <dt className="text-caption text-muted-foreground">Supplier</dt>
            <dd className="text-body text-foreground">{supplierName ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-caption text-muted-foreground">Purchase price</dt>
            <dd className="text-body text-foreground">{plant.purchase_price != null ? formatCurrency(plant.purchase_price) : "—"}</dd>
          </div>
          <div>
            <dt className="text-caption text-muted-foreground">Purchase date</dt>
            <dd className="text-body text-foreground">{plant.purchase_date ?? "—"}</dd>
          </div>
          <div className="tablet:col-span-2">
            <dt className="text-caption text-muted-foreground">Description</dt>
            <dd className="text-body text-foreground">{plant.description ?? "—"}</dd>
          </div>
        </dl>
      }
    >
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="flex max-w-lg flex-col gap-4" noValidate>
          <FormField
            control={form.control}
            name="common_label"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Label</FormLabel>
                <FormControl>
                  <Input {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="variety_id"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Variety</FormLabel>
                <Select value={field.value || NO_VARIETY} onValueChange={(v) => field.onChange(v === NO_VARIETY ? "" : v)}>
                  <FormControl>
                    <SelectTrigger className="w-full">
                      <SelectValue />
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
          <FormField
            control={form.control}
            name="batch_number"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Batch number</FormLabel>
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
                <FormLabel>Sale price</FormLabel>
                <FormControl>
                  <Input inputMode="decimal" placeholder="0.00" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="supplier_id"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Supplier</FormLabel>
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
                  <FormLabel>Purchase price</FormLabel>
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
                  <FormLabel>Purchase date</FormLabel>
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
            name="description"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Description</FormLabel>
                <FormControl>
                  <Textarea placeholder="Notes about this plant..." rows={3} {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <Button type="submit" size="sm" className="self-start" disabled={mutation.isPending} aria-busy={mutation.isPending}>
            {mutation.isPending && <Spinner className="text-current" />}
            Save changes
          </Button>
        </form>
      </Form>
    </PermissionGate>
  );
}
