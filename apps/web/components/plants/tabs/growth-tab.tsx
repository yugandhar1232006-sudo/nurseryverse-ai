"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Sprout, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/spinner";
import { PermissionGate } from "@/components/auth/permission-gate";
import { RecordEntryList } from "@/components/plants/record-entry-list";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useGrowthQuery } from "@/lib/plants/queries";
import { useRecordGrowthMutation } from "@/lib/plants/mutations";
import { recordGrowthSchema, type RecordGrowthFormValues } from "@/lib/validation/plants";
import type { GrowthRecordResponse } from "@/lib/api/plant-records";

const DEFAULT_VALUES: RecordGrowthFormValues = {
  height_cm: "",
  spread_cm: "",
  leaf_count: "",
  flower_count: "",
  fruit_count: "",
  growth_stage: "",
  notes: "",
};

/**
 * Growth is immutable-once-recorded (no PATCH/DELETE anywhere in the
 * backend, see lib/api/plant-records.ts's docstring) -- this tab is a
 * real paginated read of `growth-timeline` plus a one-way "Record
 * measurement" form, never an editor for a past entry. The record form
 * and list are combined in this one file (unlike 7F's separate Species
 * form/panel files) because a growth measurement has exactly one
 * consumer and four numeric fields -- splitting it into two files would
 * add indirection without reuse.
 */
export function GrowthTab({ plantId }: { plantId: string }) {
  const [page, setPage] = React.useState(1);
  const [formOpen, setFormOpen] = React.useState(false);
  const query = useGrowthQuery(plantId, page);
  const mutation = useRecordGrowthMutation(plantId);

  const form = useForm<RecordGrowthFormValues>({
    resolver: zodResolver(recordGrowthSchema),
    defaultValues: DEFAULT_VALUES,
  });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    if (formOpen) form.reset(DEFAULT_VALUES);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formOpen]);

  function onSubmit(values: RecordGrowthFormValues) {
    mutation.mutate(
      {
        height_cm: values.height_cm === "" ? null : Number(values.height_cm),
        spread_cm: values.spread_cm === "" ? null : Number(values.spread_cm),
        leaf_count: values.leaf_count === "" ? null : Number(values.leaf_count),
        flower_count: values.flower_count === "" ? null : Number(values.flower_count),
        fruit_count: values.fruit_count === "" ? null : Number(values.fruit_count),
        growth_stage: values.growth_stage || null,
        notes: values.notes || null,
      },
      { onSuccess: () => setFormOpen(false), onError: handleApiError },
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-end">
        <PermissionGate permission="growth:write">
          <Button type="button" size="sm" onClick={() => setFormOpen(true)}>
            <Plus className="size-4" aria-hidden="true" />
            Record measurement
          </Button>
        </PermissionGate>
      </div>

      <RecordEntryList<GrowthRecordResponse>
        icon={Sprout}
        emptyTitle="No growth measurements yet"
        emptyDescription="Record this plant's first height/spread measurement to start its growth timeline."
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
              {record.height_cm != null && <span>Height: {record.height_cm} cm</span>}
              {record.spread_cm != null && <span>Spread: {record.spread_cm} cm</span>}
              {record.leaf_count != null && <span>Leaves: {record.leaf_count}</span>}
              {record.flower_count != null && <span>Flowers: {record.flower_count}</span>}
              {record.fruit_count != null && <span>Fruit: {record.fruit_count}</span>}
              {record.growth_stage && <span>Stage: {record.growth_stage}</span>}
            </div>
            {record.notes && <p className="text-body-sm text-muted-foreground">{record.notes}</p>}
            <p className="text-caption text-muted-foreground">{new Date(record.recorded_at).toLocaleString()}</p>
          </div>
        )}
      />

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Record growth measurement</DialogTitle>
            <DialogDescription>Creates a new, permanent entry in this plant&apos;s growth timeline.</DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="height_cm"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Height (cm)</FormLabel>
                      <FormControl>
                        <Input inputMode="decimal" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="spread_cm"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Spread (cm)</FormLabel>
                      <FormControl>
                        <Input inputMode="decimal" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <div className="grid grid-cols-3 gap-4">
                <FormField
                  control={form.control}
                  name="leaf_count"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Leaves</FormLabel>
                      <FormControl>
                        <Input inputMode="numeric" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="flower_count"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Flowers</FormLabel>
                      <FormControl>
                        <Input inputMode="numeric" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="fruit_count"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Fruit</FormLabel>
                      <FormControl>
                        <Input inputMode="numeric" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={form.control}
                name="growth_stage"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Growth stage (optional)</FormLabel>
                    <FormControl>
                      <Input placeholder="seedling, growing, mature…" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="notes"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Notes (optional)</FormLabel>
                    <FormControl>
                      <Textarea rows={3} {...field} />
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
                  Save measurement
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
