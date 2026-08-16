"use client";

import * as React from "react";
/* eslint-disable @next/next/no-img-element */
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { ImageIcon, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { PermissionGate } from "@/components/auth/permission-gate";
import { useApiFormErrors } from "@/lib/forms/use-api-form-errors";
import { usePlantImagesQuery } from "@/lib/plants/queries";
import { useUploadPlantImageMutation } from "@/lib/plants/mutations";
import { uploadPlantImageSchema, type UploadPlantImageFormValues } from "@/lib/validation/plants";

const DEFAULT_VALUES: UploadPlantImageFormValues = { url: "", thumbnail_url: "", caption: "" };

/**
 * "Upload" here means registering an already-hosted image's URL with
 * `POST /plants/{id}/images` (`UploadPlantImageRequest` takes `url`/
 * `thumbnail_url`/`caption`, not raw file bytes) -- there is no binary
 * file-upload endpoint anywhere in Module 6's real API, so this is not a
 * client-side file picker with fake local preview; it's an honest URL
 *-registration form matching what the backend actually accepts.
 */
export function ImagesTab({ plantId }: { plantId: string }) {
  const [formOpen, setFormOpen] = React.useState(false);
  const query = usePlantImagesQuery(plantId);
  const mutation = useUploadPlantImageMutation(plantId);

  const form = useForm<UploadPlantImageFormValues>({ resolver: zodResolver(uploadPlantImageSchema), defaultValues: DEFAULT_VALUES });
  const handleApiError = useApiFormErrors(form.setError);

  React.useEffect(() => {
    if (formOpen) form.reset(DEFAULT_VALUES);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formOpen]);

  function onSubmit(values: UploadPlantImageFormValues) {
    mutation.mutate(
      { url: values.url, thumbnail_url: values.thumbnail_url || null, caption: values.caption || null },
      { onSuccess: () => setFormOpen(false), onError: handleApiError },
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-end">
        <PermissionGate permission="plants:write">
          <Button type="button" size="sm" onClick={() => setFormOpen(true)}>
            <Plus className="size-4" aria-hidden="true" />
            Add image
          </Button>
        </PermissionGate>
      </div>

      {query.isLoading && (
        <div className="grid grid-cols-2 gap-3 tablet:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="aspect-square w-full" />
          ))}
        </div>
      )}
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />}
      {query.data?.length === 0 && <EmptyState icon={ImageIcon} title="No images yet" description="Add a photo URL to start this plant's image gallery." />}

      {query.data && query.data.length > 0 && (
        <div className="grid grid-cols-2 gap-3 tablet:grid-cols-4">
          {query.data.map((image) => (
            <figure key={image.id} className="flex flex-col gap-1 overflow-hidden rounded-md border border-border">
              <img src={image.thumbnail_url ?? image.url} alt={image.caption ?? "Plant photo"} className="aspect-square w-full object-cover" />
              {image.caption && <figcaption className="px-2 pb-2 text-caption text-muted-foreground">{image.caption}</figcaption>}
            </figure>
          ))}
        </div>
      )}

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Add image</DialogTitle>
            <DialogDescription>Registers an already-hosted image URL against this plant.</DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4" noValidate>
              <FormField
                control={form.control}
                name="url"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Image URL</FormLabel>
                    <FormControl>
                      <Input placeholder="https://…" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="thumbnail_url"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Thumbnail URL (optional)</FormLabel>
                    <FormControl>
                      <Input placeholder="https://…" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="caption"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Caption (optional)</FormLabel>
                    <FormControl>
                      <Input {...field} />
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
                  Add image
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
