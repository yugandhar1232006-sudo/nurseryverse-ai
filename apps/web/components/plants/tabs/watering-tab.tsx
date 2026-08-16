"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Droplets, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/spinner";
import { PermissionGate } from "@/components/auth/permission-gate";
import { RecordEntryList } from "@/components/plants/record-entry-list";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { useWateringQuery } from "@/lib/plants/queries";
import { useRecordWateringMutation } from "@/lib/plants/mutations";
import { recordWateringSchema, type RecordWateringFormValues } from "@/lib/validation/plants";
import type { WateringRecordResponse } from "@/lib/api/plant-records";

const DEFAULT_VALUES: RecordWateringFormValues = { volume_ml: "", method: "", notes: "" };

export function WateringTab({ plantId }: { plantId: string }) {
  const [page, setPage] = React.useState(1);
  const [formOpen, setFormOpen] = React.useState(false);
  const query = useWateringQuery(plantId, page);
  const mutation = useRecordWateringMutation(plantId);

  const form = useForm<RecordWateringFormValues>({ resolver: zodResolver(recordWateringSchema), defaultValues: DEFAULT_VALUES });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    if (formOpen) form.reset(DEFAULT_VALUES);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formOpen]);

  function onSubmit(values: RecordWateringFormValues) {
    mutation.mutate(
      { volume_ml: values.volume_ml === "" ? null : Number(values.volume_ml), method: values.method || null, notes: values.notes || null },
      { onSuccess: () => setFormOpen(false), onError: handleApiError },
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-end">
        <PermissionGate permission="watering:write">
          <Button type="button" size="sm" onClick={() => setFormOpen(true)}>
            <Plus className="size-4" aria-hidden="true" />
            Record watering
          </Button>
        </PermissionGate>
      </div>

      <RecordEntryList<WateringRecordResponse>
        icon={Droplets}
        emptyTitle="No watering events yet"
        emptyDescription="Log this plant's first watering event."
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
              {record.volume_ml != null && <span>{record.volume_ml} mL</span>}
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
            <DialogTitle>Record watering</DialogTitle>
            <DialogDescription>Creates a new, permanent watering log entry.</DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
              <FormField
                control={form.control}
                name="volume_ml"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Volume (mL, optional)</FormLabel>
                    <FormControl>
                      <Input inputMode="decimal" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="method"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Method (optional)</FormLabel>
                    <FormControl>
                      <Input placeholder="drip, hand, sprinkler…" {...field} />
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
