"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { PermissionGate } from "@/components/auth/permission-gate";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { usePlantVarietiesQuery } from "@/lib/catalog/queries";
import { useUpdatePlantProfileMutation } from "@/lib/plants/mutations";
import { updatePlantProfileSchema, type UpdatePlantProfileFormValues } from "@/lib/validation/plants";
import type { PlantResponse } from "@/lib/api/plants";

const NO_VARIETY = "__none__";

function toDefaultValues(plant: PlantResponse): UpdatePlantProfileFormValues {
  return {
    common_label: plant.common_label ?? "",
    variety_id: plant.variety_id ?? "",
    batch_number: plant.batch_number ?? "",
    price: plant.price != null ? String(plant.price) : "",
  };
}

/**
 * Profile-editable fields only (`UpdatePlantProfileRequest`) -- identity
 * (species, branch, zone, status, QR token) is shown in `PlantHeader`
 * and changed only through the dedicated Move/Status actions, never
 * through this form, matching what the backend actually allows `PATCH
 * /plants/{id}` to touch.
 */
export function OverviewTab({ plant }: { plant: PlantResponse }) {
  const varietiesQuery = usePlantVarietiesQuery({ species_id: plant.species_id, page: 1, page_size: 100 });
  const mutation = useUpdatePlantProfileMutation(plant.id);

  const form = useForm<UpdatePlantProfileFormValues>({
    resolver: zodResolver(updatePlantProfileSchema),
    defaultValues: toDefaultValues(plant),
  });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    form.reset(toDefaultValues(plant));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plant.id, plant.common_label, plant.variety_id, plant.batch_number, plant.price]);

  function onSubmit(values: UpdatePlantProfileFormValues) {
    mutation.mutate(
      {
        common_label: values.common_label || null,
        variety_id: values.variety_id && values.variety_id !== NO_VARIETY ? values.variety_id : null,
        batch_number: values.batch_number || null,
        price: values.price === "" ? null : Number(values.price),
      },
      { onError: handleApiError },
    );
  }

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
            <dd className="text-body text-foreground">{plant.price != null ? plant.price : "—"}</dd>
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
                <FormLabel>Price</FormLabel>
                <FormControl>
                  <Input inputMode="decimal" {...field} />
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
