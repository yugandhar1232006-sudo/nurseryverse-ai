"use client";

import * as React from "react";
import { Plus, Sprout } from "lucide-react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { VarietyFormDialog } from "@/components/catalog/variety-form-dialog";
import { usePlantVarietiesQuery } from "@/lib/catalog/queries";
import { useDeletePlantVarietyMutation } from "@/lib/catalog/mutations";
import type { PlantVarietyResponse } from "@/lib/api/catalog";
import type { SpeciesResponse } from "@/lib/api/catalog";

function CareAttribute({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 text-body-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right text-foreground">{value ?? "—"}</span>
    </div>
  );
}

/**
 * Read-only care attributes (editing happens via `SpeciesFormDialog`) plus
 * the real varieties list for this species (`GET /plant-varieties?species_id=`),
 * with its own create/edit/archive. `growth_curve_baseline` is shown as a
 * real point count, not rendered as a chart or made editable here -- see
 * docs/frontend/10-plant-catalog.md's Known Limitations for why a full
 * curve editor is out of scope for this phase.
 */
export function SpeciesDetailDialog({
  open,
  onOpenChange,
  species,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  species: SpeciesResponse | null;
}) {
  const varietiesQuery = usePlantVarietiesQuery({ species_id: species?.id, page_size: 100 });
  const deleteMutation = useDeletePlantVarietyMutation();
  const [formOpen, setFormOpen] = React.useState(false);
  const [editingVariety, setEditingVariety] = React.useState<PlantVarietyResponse | null>(null);
  const [archivingVariety, setArchivingVariety] = React.useState<PlantVarietyResponse | null>(null);

  if (!species) return null;

  const varieties = varietiesQuery.data?.items ?? [];
  const growthCurvePointCount = Array.isArray(species.growth_curve_baseline) ? species.growth_curve_baseline.length : 0;
  // `disease_susceptibility` is typed as a bare `list | null` in the backend
  // schema (no generic -- see lib/api/catalog.ts's docstring on this same
  // class of OpenAPI looseness), so the generated type is `unknown[] | null`.
  // The service only ever writes `list[str]`, so this cast reflects the real
  // runtime contract, not a frontend assumption.
  const diseases = Array.isArray(species.disease_susceptibility) ? (species.disease_susceptibility as string[]) : [];

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{species.common_name}</DialogTitle>
            <DialogDescription className="italic">{species.botanical_name}</DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-2 rounded-md border border-border p-3">
            <CareAttribute label="Light requirement" value={species.light_requirement} />
            <CareAttribute
              label="Water baseline"
              value={species.water_baseline_ml_per_week != null ? `${species.water_baseline_ml_per_week} mL/week` : null}
            />
            <CareAttribute label="Soil type" value={species.soil_type} />
            <CareAttribute
              label="Temperature range"
              value={
                species.temperature_min_celsius != null || species.temperature_max_celsius != null
                  ? `${species.temperature_min_celsius ?? "—"}°C to ${species.temperature_max_celsius ?? "—"}°C`
                  : null
              }
            />
            <CareAttribute
              label="Growth curve baseline"
              value={growthCurvePointCount > 0 ? `${growthCurvePointCount} recorded points` : null}
            />
            {diseases.length > 0 && (
              <div className="flex flex-col gap-1 text-body-sm">
                <span className="text-muted-foreground">Disease susceptibility</span>
                <div className="flex flex-wrap gap-1">
                  {diseases.map((d) => (
                    <Badge key={d} variant="outline">
                      {d}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <h3 className="text-body font-medium text-foreground">Varieties</h3>
              <PermissionGate permission="species:write">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setEditingVariety(null);
                    setFormOpen(true);
                  }}
                >
                  <Plus className="size-4" aria-hidden="true" />
                  Add variety
                </Button>
              </PermissionGate>
            </div>

            {varietiesQuery.isLoading ? (
              <div className="flex flex-col gap-2">
                {Array.from({ length: 2 }).map((_, i) => (
                  <Skeleton key={i} className="h-9 w-full" />
                ))}
              </div>
            ) : varietiesQuery.isError ? (
              <ErrorState error={varietiesQuery.error} onRetry={() => varietiesQuery.refetch()} retrying={varietiesQuery.isFetching} />
            ) : varieties.length === 0 ? (
              <EmptyState icon={Sprout} title="No varieties yet" description="Add a cultivar/variety under this species." />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {varieties.map((variety) => (
                    <TableRow key={variety.id}>
                      <TableCell className="font-medium text-foreground">{variety.name}</TableCell>
                      <TableCell className="text-muted-foreground">{variety.description ?? "—"}</TableCell>
                      <TableCell className="text-right">
                        <PermissionGate permission="species:write">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setEditingVariety(variety);
                              setFormOpen(true);
                            }}
                          >
                            Edit
                          </Button>
                        </PermissionGate>
                        <PermissionGate permission="species:delete">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="text-destructive hover:text-destructive"
                            onClick={() => setArchivingVariety(variety)}
                          >
                            Archive
                          </Button>
                        </PermissionGate>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <VarietyFormDialog open={formOpen} onOpenChange={setFormOpen} speciesId={species.id} variety={editingVariety} />

      <AlertDialog open={archivingVariety !== null} onOpenChange={(open) => !open && setArchivingVariety(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Archive {archivingVariety?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              This is blocked if any plant record still references this variety. This action cannot be undone from here.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteMutation.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={deleteMutation.isPending}
              onClick={() => {
                if (!archivingVariety) return;
                deleteMutation.mutate(archivingVariety.id, { onSuccess: () => setArchivingVariety(null) });
              }}
            >
              Archive
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
