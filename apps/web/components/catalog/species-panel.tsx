"use client";

import * as React from "react";
import { Leaf, Plus, Search } from "lucide-react";

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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Input } from "@/components/ui/input";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { SpeciesFormDialog } from "@/components/catalog/species-form-dialog";
import { SpeciesDetailDialog } from "@/components/catalog/species-detail-dialog";
import { usePlantCategoriesQuery, useSpeciesListQuery } from "@/lib/catalog/queries";
import { useDeleteSpeciesMutation } from "@/lib/catalog/mutations";
import type { SpeciesResponse } from "@/lib/api/catalog";

const ALL_CATEGORIES = "__all__";
const DEBOUNCE_MS = 300;

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = React.useState(value);
  React.useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

/**
 * The 7F Species Catalog screen at `/plants/species`. `PlantCategory` has
 * no per-org CRUD anywhere in the backend (see lib/api/catalog.ts's
 * docstring) -- it's used here purely as a read-only filter, not a
 * manageable resource with its own panel.
 */
export function SpeciesPanel() {
  const [page, setPage] = React.useState(1);
  const [rawSearch, setRawSearch] = React.useState("");
  const [categoryId, setCategoryId] = React.useState(ALL_CATEGORIES);
  const search = useDebouncedValue(rawSearch, DEBOUNCE_MS);

  // React's "adjusting state when a prop changes" pattern (not an Effect):
  // reset to page 1 whenever the *filters themselves* change, without the
  // cascading extra render an Effect-based setState would cause (same
  // pattern as employee-detail-dialog.tsx's `syncedPermsData`).
  const [syncedFilters, setSyncedFilters] = React.useState({ search, categoryId });
  if (syncedFilters.search !== search || syncedFilters.categoryId !== categoryId) {
    setSyncedFilters({ search, categoryId });
    if (page !== 1) setPage(1);
  }

  const categoriesQuery = usePlantCategoriesQuery();
  const query = useSpeciesListQuery({
    page,
    page_size: 20,
    search: search || undefined,
    category_id: categoryId === ALL_CATEGORIES ? undefined : categoryId,
  });
  const deleteMutation = useDeleteSpeciesMutation();

  const [formOpen, setFormOpen] = React.useState(false);
  const [editingSpecies, setEditingSpecies] = React.useState<SpeciesResponse | null>(null);
  const [detailSpecies, setDetailSpecies] = React.useState<SpeciesResponse | null>(null);
  const [archivingSpecies, setArchivingSpecies] = React.useState<SpeciesResponse | null>(null);

  const items = query.data?.items ?? [];
  const meta = query.data?.meta;
  const categoryNameById = new Map((categoriesQuery.data ?? []).map((c) => [c.id, c.name]));

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Species catalog</CardTitle>
        <PermissionGate permission="species:write">
          <Button
            type="button"
            size="sm"
            onClick={() => {
              setEditingSpecies(null);
              setFormOpen(true);
            }}
          >
            <Plus className="size-4" aria-hidden="true" />
            Add species
          </Button>
        </PermissionGate>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-2 tablet:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input
              value={rawSearch}
              onChange={(e) => setRawSearch(e.target.value)}
              placeholder="Search by common or botanical name…"
              className="pl-8"
              aria-label="Search species"
            />
          </div>
          <Select value={categoryId} onValueChange={setCategoryId}>
            <SelectTrigger className="w-full tablet:w-56" aria-label="Filter by category">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_CATEGORIES}>All categories</SelectItem>
              {(categoriesQuery.data ?? []).map((cat) => (
                <SelectItem key={cat.id} value={cat.id}>
                  {cat.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {query.isLoading ? (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={Leaf}
            title={search || categoryId !== ALL_CATEGORIES ? "No species match your filters" : "No species yet"}
            description={
              search || categoryId !== ALL_CATEGORIES
                ? "Try a different search term or category."
                : "Add your organization's first species to start building the catalog."
            }
          />
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Common name</TableHead>
                  <TableHead>Botanical name</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Light</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((species) => (
                  <TableRow key={species.id} className="cursor-pointer" onClick={() => setDetailSpecies(species)}>
                    <TableCell className="font-medium text-foreground">{species.common_name}</TableCell>
                    <TableCell className="italic text-muted-foreground">{species.botanical_name}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{categoryNameById.get(species.category_id) ?? "—"}</Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{species.light_requirement ?? "—"}</TableCell>
                    <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                      <PermissionGate permission="species:write">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setEditingSpecies(species);
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
                          onClick={() => setArchivingSpecies(species)}
                        >
                          Archive
                        </Button>
                      </PermissionGate>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            {meta && meta.total_pages > 1 && (
              <div className="flex items-center justify-between text-body-sm text-muted-foreground">
                <span>
                  Page {meta.page} of {meta.total_pages} ({meta.total_items} species)
                </span>
                <div className="flex gap-2">
                  <Button type="button" variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                    Previous
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={page >= meta.total_pages}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>

      <SpeciesFormDialog open={formOpen} onOpenChange={setFormOpen} species={editingSpecies} />
      <SpeciesDetailDialog open={detailSpecies !== null} onOpenChange={(open) => !open && setDetailSpecies(null)} species={detailSpecies} />

      <AlertDialog open={archivingSpecies !== null} onOpenChange={(open) => !open && setArchivingSpecies(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Archive {archivingSpecies?.common_name}?</AlertDialogTitle>
            <AlertDialogDescription>
              This is blocked if any plant record still references this species. This action cannot be undone from here.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteMutation.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={deleteMutation.isPending}
              onClick={() => {
                if (!archivingSpecies) return;
                deleteMutation.mutate(archivingSpecies.id, { onSuccess: () => setArchivingSpecies(null) });
              }}
            >
              Archive
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}
