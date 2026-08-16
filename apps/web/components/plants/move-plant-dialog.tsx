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
import { useBranchesQuery } from "@/lib/shell/queries";
import { useMovePlantMutation } from "@/lib/plants/mutations";
import { movePlantSchema, type MovePlantFormValues } from "@/lib/validation/plants";

const SAME_BRANCH = "__same__";

/**
 * `POST /plants/{id}/move` requires `plants:transfer` on both the
 * plant's current branch and (if different) the destination branch --
 * two separate backend authorization checks (see lib/api/plants.ts's
 * docstring). A 403 here means the caller lacks transfer rights on one
 * side of the move; surfaced as a toast, not validated client-side.
 */
export function MovePlantDialog({
  open,
  onOpenChange,
  plantId,
  currentBranchId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  plantId: string;
  currentBranchId: string;
}) {
  const branchesQuery = useBranchesQuery();
  const mutation = useMovePlantMutation(plantId);

  const form = useForm<MovePlantFormValues>({
    resolver: zodResolver(movePlantSchema),
    defaultValues: { to_branch_id: "", to_zone: "", note: "" },
  });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    if (open) form.reset({ to_branch_id: "", to_zone: "", note: "" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function onSubmit(values: MovePlantFormValues) {
    mutation.mutate(
      {
        to_branch_id: values.to_branch_id && values.to_branch_id !== SAME_BRANCH ? values.to_branch_id : null,
        to_zone: values.to_zone || null,
        note: values.note || null,
      },
      { onSuccess: () => onOpenChange(false), onError: handleApiError },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Move plant</DialogTitle>
          <DialogDescription>Relocate this plant to a different branch and/or zone.</DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
            <FormField
              control={form.control}
              name="to_branch_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Destination branch (optional)</FormLabel>
                  {branchesQuery.isLoading ? (
                    <Skeleton className="h-9 w-full" />
                  ) : (
                    <Select value={field.value || SAME_BRANCH} onValueChange={(v) => field.onChange(v === SAME_BRANCH ? "" : v)}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Keep current branch" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value={SAME_BRANCH}>Keep current branch</SelectItem>
                        {(branchesQuery.data ?? [])
                          .filter((b) => b.id !== currentBranchId)
                          .map((branch) => (
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
              name="to_zone"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Destination zone (optional)</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormDescription>Specify a branch, a zone, or both.</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="note"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Note (optional)</FormLabel>
                  <FormControl>
                    <Input {...field} />
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
                Move plant
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
