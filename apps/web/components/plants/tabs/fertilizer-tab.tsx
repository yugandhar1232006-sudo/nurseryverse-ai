"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { FlaskConical, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/spinner";
import { PermissionGate } from "@/components/auth/permission-gate";
import { RecordEntryList } from "@/components/plants/record-entry-list";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useFertilizerQuery } from "@/lib/plants/queries";
import { useRecordFertilizerMutation } from "@/lib/plants/mutations";
import { recordFertilizerSchema, type RecordFertilizerFormValues } from "@/lib/validation/plants";
import type { FertilizerRecordResponse } from "@/lib/api/plant-records";

const DEFAULT_VALUES: RecordFertilizerFormValues = { product_name: "", quantity_ml: "", npk_ratio: "", method: "", notes: "" };

/**
 * Gated on `watering:write`, not a dedicated `fertilizer:*` permission --
 * see lib/api/plant-records.ts's docstring for why (no such permission
 * code was ever seeded server-side; fertilizing is folded under general
 * watering care).
 */
export function FertilizerTab({ plantId }: { plantId: string }) {
  const [page, setPage] = React.useState(1);
  const [formOpen, setFormOpen] = React.useState(false);
  const query = useFertilizerQuery(plantId, page);
  const mutation = useRecordFertilizerMutation(plantId);

  const form = useForm<RecordFertilizerFormValues>({ resolver: zodResolver(recordFertilizerSchema), defaultValues: DEFAULT_VALUES });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    if (formOpen) form.reset(DEFAULT_VALUES);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formOpen]);

  function onSubmit(values: RecordFertilizerFormValues) {
    mutation.mutate(
      {
        product_name: values.product_name,
        quantity_ml: values.quantity_ml === "" ? null : Number(values.quantity_ml),
        npk_ratio: values.npk_ratio || null,
        method: values.method || null,
        notes: values.notes || null,
      },
      { onSuccess: () => setFormOpen(false), onError: handleApiError },
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-end">
        <PermissionGate permission="watering:write">
          <Button type="button" size="sm" onClick={() => setFormOpen(true)}>
            <Plus className="size-4" aria-hidden="true" />
            Record application
          </Button>
        </PermissionGate>
      </div>

      <RecordEntryList<FertilizerRecordResponse>
        icon={FlaskConical}
        emptyTitle="No fertilizer applications yet"
        emptyDescription="Log this plant's first fertilizer application."
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
              <span className="font-medium text-foreground">{record.product_name}</span>
              {record.quantity_ml != null && <span>{record.quantity_ml} mL</span>}
              {record.npk_ratio && <span>NPK: {record.npk_ratio}</span>}
              {record.method && <span>Method: {record.method}</span>}
            </div>
            {record.notes && <p className="text-body-sm text-muted-foreground">{record.notes}</p>}
            <p className="text-caption text-muted-foreground">{new Date(record.recorded_at).toLocaleString()}</p>
          </div>
        )}
      />

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Record fertilizer application</DialogTitle>
            <DialogDescription>Creates a new, permanent fertilizer log entry.</DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
              <FormField
                control={form.control}
                name="product_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Product name</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="quantity_ml"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Quantity (mL, optional)</FormLabel>
                      <FormControl>
                        <Input inputMode="decimal" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="npk_ratio"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>NPK ratio (optional)</FormLabel>
                      <FormControl>
                        <Input placeholder="10-10-10" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={form.control}
                name="method"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Method (optional)</FormLabel>
                    <FormControl>
                      <Input {...field} />
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
