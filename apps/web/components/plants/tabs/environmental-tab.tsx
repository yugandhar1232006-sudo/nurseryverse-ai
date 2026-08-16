"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Thermometer, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { PermissionGate } from "@/components/auth/permission-gate";
import { RecordEntryList } from "@/components/plants/record-entry-list";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useEnvironmentalQuery } from "@/lib/plants/queries";
import { useRecordEnvironmentalMutation } from "@/lib/plants/mutations";
import { recordEnvironmentalSchema, type RecordEnvironmentalFormValues } from "@/lib/validation/plants";
import type { EnvironmentalRecordResponse } from "@/lib/api/plant-records";

const DEFAULT_VALUES: RecordEnvironmentalFormValues = {
  temperature_celsius: "",
  humidity_percent: "",
  soil_moisture_percent: "",
  light_lux: "",
  ph_level: "",
};

/**
 * `RecordEnvironmentalRequest.source` is a required field server-side
 * (default `"manual"`) that this form doesn't expose -- every reading
 * logged through this UI is, by definition, a manual one; automated
 * sensor readings (a different `source` value) would come from a
 * different, non-UI ingestion path this phase doesn't build.
 */
export function EnvironmentalTab({ plantId }: { plantId: string }) {
  const [page, setPage] = React.useState(1);
  const [formOpen, setFormOpen] = React.useState(false);
  const query = useEnvironmentalQuery(plantId, page);
  const mutation = useRecordEnvironmentalMutation(plantId);

  const form = useForm<RecordEnvironmentalFormValues>({ resolver: zodResolver(recordEnvironmentalSchema), defaultValues: DEFAULT_VALUES });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    if (formOpen) form.reset(DEFAULT_VALUES);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formOpen]);

  function onSubmit(values: RecordEnvironmentalFormValues) {
    mutation.mutate(
      {
        temperature_celsius: values.temperature_celsius === "" ? null : Number(values.temperature_celsius),
        humidity_percent: values.humidity_percent === "" ? null : Number(values.humidity_percent),
        soil_moisture_percent: values.soil_moisture_percent === "" ? null : Number(values.soil_moisture_percent),
        light_lux: values.light_lux === "" ? null : Number(values.light_lux),
        ph_level: values.ph_level === "" ? null : Number(values.ph_level),
        source: "manual",
      },
      { onSuccess: () => setFormOpen(false), onError: handleApiError },
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-end">
        <PermissionGate permission="environmental:write">
          <Button type="button" size="sm" onClick={() => setFormOpen(true)}>
            <Plus className="size-4" aria-hidden="true" />
            Record reading
          </Button>
        </PermissionGate>
      </div>

      <RecordEntryList<EnvironmentalRecordResponse>
        icon={Thermometer}
        emptyTitle="No environmental readings yet"
        emptyDescription="Record this plant's first environmental reading."
        items={query.data?.items ?? []}
        isLoading={query.isLoading}
        isError={query.isError}
        error={query.error}
        onRetry={() => query.refetch()}
        retrying={query.isFetching}
        page={page}
        totalPages={query.data?.meta.total_pages ?? 1}
        onPageChange={setPage}
        renderItem={(record) => (
          <div className="flex flex-col gap-1">
            <div className="flex flex-wrap gap-x-4 text-body-sm">
              {record.temperature_celsius != null && <span>{record.temperature_celsius}°C</span>}
              {record.humidity_percent != null && <span>Humidity: {record.humidity_percent}%</span>}
              {record.soil_moisture_percent != null && <span>Soil moisture: {record.soil_moisture_percent}%</span>}
              {record.light_lux != null && <span>Light: {record.light_lux} lux</span>}
              {record.ph_level != null && <span>pH: {record.ph_level}</span>}
            </div>
            <p className="text-caption text-muted-foreground">
              {record.source} · {new Date(record.recorded_at).toLocaleString()}
            </p>
          </div>
        )}
      />

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Record environmental reading</DialogTitle>
            <DialogDescription>Creates a new, permanent environmental log entry.</DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="temperature_celsius"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Temperature (°C)</FormLabel>
                      <FormControl>
                        <Input inputMode="decimal" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="humidity_percent"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Humidity (%)</FormLabel>
                      <FormControl>
                        <Input inputMode="decimal" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="soil_moisture_percent"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Soil moisture (%)</FormLabel>
                      <FormControl>
                        <Input inputMode="decimal" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="light_lux"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Light (lux)</FormLabel>
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
                name="ph_level"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>pH level (0–14)</FormLabel>
                    <FormControl>
                      <Input inputMode="decimal" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setFormOpen(false)} disabled={mutation.isPending}>
                  Cancel
                </Button>
                <Button type="submit" disabled={mutation.isPending} aria-busy={mutation.isPending}>
                  {mutation.isPending && <Spinner className="text-current" />}
                  Save
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
