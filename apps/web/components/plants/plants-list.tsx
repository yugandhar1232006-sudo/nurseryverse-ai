"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Leaf, Plus, Search, Pencil, Archive, LayoutGrid, List, Sun, Droplets } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Input } from "@/components/ui/input";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PlantStatusBadge } from "@/components/plants/plant-status-badge";
import { RegisterPlantDialog } from "@/components/plants/register-plant-dialog";
import { EditPlantDialog } from "@/components/plants/edit-plant-dialog";
import { ArchivePlantDialog } from "@/components/plants/archive-plant-dialog";
import { useBranchesQuery } from "@/lib/shell/queries";
import { useSpeciesListQuery, usePlantCategoriesQuery } from "@/lib/catalog/queries";
import { useSuppliersQuery } from "@/lib/suppliers/queries";
import { usePlantsListQuery } from "@/lib/plants/queries";
import type { PlantStatus, PlantResponse } from "@/lib/api/plants";
import type { SpeciesResponse } from "@/lib/api/catalog";

const ALL = "__all__";
const DEBOUNCE_MS = 300;

const STATUS_OPTIONS: { value: PlantStatus; label: string }[] = [
  { value: "in_production", label: "In production" },
  { value: "ready_for_sale", label: "Ready for sale" },
  { value: "under_treatment", label: "Under treatment" },
  { value: "sold", label: "Sold" },
  { value: "deceased", label: "Deceased" },
];

const CATEGORY_COLORS: Record<string, string> = {
  herb: "bg-emerald-100 text-emerald-800",
  annual_flower: "bg-pink-100 text-pink-800",
  perennial_flower: "bg-purple-100 text-purple-800",
  shrub: "bg-amber-100 text-amber-800",
  tree: "bg-green-100 text-green-800",
  fruit: "bg-red-100 text-red-800",
  vegetable_start: "bg-lime-100 text-lime-800",
  houseplant: "bg-teal-100 text-teal-800",
  ornamental_grass: "bg-yellow-100 text-yellow-800",
  succulent_cactus: "bg-orange-100 text-orange-800",
  vine_climber: "bg-indigo-100 text-indigo-800",
  fern: "bg-cyan-100 text-cyan-800",
  bulb: "bg-fuchsia-100 text-fuchsia-800",
};

const CATEGORY_LABELS: Record<string, string> = {
  herb: "Herb",
  annual_flower: "Annual",
  perennial_flower: "Perennial",
  shrub: "Shrub",
  tree: "Tree",
  fruit: "Fruit",
  vegetable_start: "Vegetable",
  houseplant: "Houseplant",
  ornamental_grass: "Grass",
  succulent_cactus: "Succulent",
  vine_climber: "Vine",
  fern: "Fern",
  bulb: "Bulb",
};

const SPECIES_EMOJI: Record<string, string> = {
  herb: "\uD83C\uDF3F",
  annual_flower: "\uD83C\uDF38",
  perennial_flower: "\uD83C\uDF3B",
  shrub: "\uD83C\uDF33",
  tree: "\uD83C\uDF32",
  fruit: "\uD83C\uDF4E",
  vegetable_start: "\uD83E\uDD51",
  houseplant: "\uD83C\uDF31",
  ornamental_grass: "\uD83C\uDF3E",
  succulent_cactus: "\uD83C\uDF35",
  vine_climber: "\uD83C\uDF37",
  fern: "\uD83C\uDF3F",
  bulb: "\uD83C\uDF3C",
};

type ViewMode = "grid" | "table";

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = React.useState(value);
  React.useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

function PlantCard({
  plant,
  species,
  branchName,
  categoryIdToCode,
  onClick,
}: {
  plant: PlantResponse;
  species?: SpeciesResponse;
  branchName?: string;
  categoryIdToCode: Map<string, string>;
  onClick: () => void;
}) {
  const catCode = species ? categoryIdToCode.get(species.category_id) : undefined;
  const catColor = catCode ? CATEGORY_COLORS[catCode] ?? "bg-gray-100 text-gray-800" : "bg-gray-100 text-gray-800";
  const catLabel = catCode ? CATEGORY_LABELS[catCode] ?? catCode : undefined;
  const emoji = catCode ? SPECIES_EMOJI[catCode] ?? "\uD83C\uDF31" : "\uD83C\uDF31";

  return (
    <div
      className="group cursor-pointer rounded-xl border bg-card p-4 transition-shadow hover:shadow-md"
      onClick={onClick}
    >
      <div className="mb-3 flex items-start justify-between">
        <div className="flex items-center gap-2">
          <span className="text-2xl" aria-hidden="true">{emoji}</span>
          <div className="min-w-0">
            <h3 className="truncate font-semibold text-foreground group-hover:underline">
              {plant.common_label ?? "Unlabeled"}
            </h3>
            <p className="truncate text-sm text-muted-foreground">
              {species?.common_name ?? "Unknown species"}
            </p>
          </div>
        </div>
        <PlantStatusBadge status={plant.status} />
      </div>

      {catLabel && (
        <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${catColor}`}>
          {catLabel}
        </span>
      )}

      <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
        {species?.light_requirement && (
          <span className="flex items-center gap-1">
            <Sun className="size-3" aria-hidden="true" />
            {species.light_requirement}
          </span>
        )}
        {species?.water_baseline_ml_per_week != null && (
          <span className="flex items-center gap-1">
            <Droplets className="size-3" aria-hidden="true" />
            {species.water_baseline_ml_per_week} ml/wk
          </span>
        )}
      </div>

      <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
        <span>{branchName ?? "—"}</span>
        <span>{plant.age_days}d old</span>
      </div>

      {plant.price != null && (
        <div className="mt-2 text-sm font-medium text-foreground">
          ₹{plant.price.toFixed(2)}
        </div>
      )}
    </div>
  );
}

export function PlantsList() {
  const router = useRouter();
  const [page, setPage] = React.useState(1);
  const [rawSearch, setRawSearch] = React.useState("");
  const [branchId, setBranchId] = React.useState(ALL);
  const [speciesId, setSpeciesId] = React.useState(ALL);
  const [status, setStatus] = React.useState(ALL);
  const [viewMode, setViewMode] = React.useState<ViewMode>("grid");
  const search = useDebouncedValue(rawSearch, DEBOUNCE_MS);

  const [syncedFilters, setSyncedFilters] = React.useState({ search, branchId, speciesId, status });
  if (
    syncedFilters.search !== search ||
    syncedFilters.branchId !== branchId ||
    syncedFilters.speciesId !== speciesId ||
    syncedFilters.status !== status
  ) {
    setSyncedFilters({ search, branchId, speciesId, status });
    if (page !== 1) setPage(1);
  }

  const branchesQuery = useBranchesQuery();
  const speciesQuery = useSpeciesListQuery({ page: 1, page_size: 100 });
  const categoriesQuery = usePlantCategoriesQuery();
  const suppliersQuery = useSuppliersQuery();
  const query = usePlantsListQuery({
    page,
    page_size: 20,
    search: search || undefined,
    branch_id: branchId === ALL ? undefined : branchId,
    species_id: speciesId === ALL ? undefined : speciesId,
    status_filter: status === ALL ? undefined : (status as PlantStatus),
  });

  const [registerOpen, setRegisterOpen] = React.useState(false);
  const [editPlant, setEditPlant] = React.useState<PlantResponse | null>(null);
  const [archivePlant, setArchivePlant] = React.useState<PlantResponse | null>(null);

  const items = query.data?.items ?? [];
  const meta = query.data?.meta;
  const branchNameById = new Map((branchesQuery.data ?? []).map((b) => [b.id, b.name]));
  const speciesById = new Map((speciesQuery.data?.items ?? []).map((s) => [s.id, s]));
  const supplierNameById = new Map((suppliersQuery.data ?? []).map((s) => [s.id, s.name]));
  const categoryIdToCode = new Map((categoriesQuery.data ?? []).map((c) => [c.id, c.code]));
  const hasFilters = search !== "" || branchId !== ALL || speciesId !== ALL || status !== ALL;

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Plants</CardTitle>
        <div className="flex items-center gap-2">
          <div className="flex rounded-md border">
            <button
              type="button"
              className={`flex items-center gap-1 rounded-l-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                viewMode === "grid" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"
              }`}
              onClick={() => setViewMode("grid")}
              aria-label="Grid view"
            >
              <LayoutGrid className="size-3.5" />
              Grid
            </button>
            <button
              type="button"
              className={`flex items-center gap-1 rounded-r-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                viewMode === "table" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"
              }`}
              onClick={() => setViewMode("table")}
              aria-label="Table view"
            >
              <List className="size-3.5" />
              Table
            </button>
          </div>
          <PermissionGate permission="plants:write">
            <Button type="button" size="sm" onClick={() => setRegisterOpen(true)}>
              <Plus className="size-4" aria-hidden="true" />
              Register plant
            </Button>
          </PermissionGate>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-2 tablet:flex-row tablet:flex-wrap">
          <div className="relative flex-1 tablet:min-w-[220px]">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input
              value={rawSearch}
              onChange={(e) => setRawSearch(e.target.value)}
              placeholder="Search by label, batch, or zone…"
              className="pl-8"
              aria-label="Search plants"
            />
          </div>
          <Select value={branchId} onValueChange={setBranchId}>
            <SelectTrigger className="w-full tablet:w-48" aria-label="Filter by branch">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All branches</SelectItem>
              {(branchesQuery.data ?? []).map((branch) => (
                <SelectItem key={branch.id} value={branch.id}>
                  {branch.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={speciesId} onValueChange={setSpeciesId}>
            <SelectTrigger className="w-full tablet:w-48" aria-label="Filter by species">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All species</SelectItem>
              {(speciesQuery.data?.items ?? []).map((species) => (
                <SelectItem key={species.id} value={species.id}>
                  {species.common_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger className="w-full tablet:w-48" aria-label="Filter by status">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All statuses</SelectItem>
              {STATUS_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {query.isLoading ? (
          <div className={viewMode === "grid" ? "grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3" : "flex flex-col gap-2"}>
            {Array.from({ length: viewMode === "grid" ? 6 : 5 }).map((_, i) => (
              viewMode === "grid" ? (
                <Skeleton key={i} className="h-40 rounded-xl" />
              ) : (
                <Skeleton key={i} className="h-10 w-full" />
              )
            ))}
          </div>
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={Leaf}
            title={hasFilters ? "No plants match your filters" : "No plants yet"}
            description={hasFilters ? "Try a different search term or filter." : "Register your organization's first plant to start tracking it."}
          />
        ) : (
          <>
            {viewMode === "grid" ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {items.map((plant) => (
                  <PlantCard
                    key={plant.id}
                    plant={plant}
                    species={speciesById.get(plant.species_id)}
                    branchName={branchNameById.get(plant.branch_id)}
                    categoryIdToCode={categoryIdToCode}
                    onClick={() => router.push(`/plants/${plant.id}`)}
                  />
                ))}
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Label</TableHead>
                    <TableHead>Species</TableHead>
                    <TableHead>Branch</TableHead>
                    <TableHead>Zone</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Age</TableHead>
                    <TableHead className="w-[100px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((plant) => (
                    <TableRow key={plant.id}>
                      <TableCell
                        className="cursor-pointer font-medium text-foreground hover:underline"
                        onClick={() => router.push(`/plants/${plant.id}`)}
                      >
                        {plant.common_label ?? "Unlabeled"}
                      </TableCell>
                      <TableCell className="cursor-pointer hover:underline" onClick={() => router.push(`/plants/${plant.id}`)}>
                        {speciesById.get(plant.species_id)?.common_name ?? "—"}
                      </TableCell>
                      <TableCell className="cursor-pointer text-muted-foreground hover:underline" onClick={() => router.push(`/plants/${plant.id}`)}>
                        {branchNameById.get(plant.branch_id) ?? "—"}
                      </TableCell>
                      <TableCell className="cursor-pointer text-muted-foreground hover:underline" onClick={() => router.push(`/plants/${plant.id}`)}>
                        {plant.zone ?? "—"}
                      </TableCell>
                      <TableCell>
                        <PlantStatusBadge status={plant.status} />
                      </TableCell>
                      <TableCell className="cursor-pointer text-right text-muted-foreground hover:underline" onClick={() => router.push(`/plants/${plant.id}`)}>
                        {plant.age_days} days
                      </TableCell>
                      <TableCell>
                        {plant.archived_at === null && (
                          <div className="flex gap-1">
                            <PermissionGate permission="plants:write">
                              <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                className="size-7"
                                onClick={() => setEditPlant(plant)}
                                aria-label={`Edit ${plant.common_label ?? "plant"}`}
                              >
                                <Pencil className="size-3.5" />
                              </Button>
                            </PermissionGate>
                            <PermissionGate permission="plants:write">
                              <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                className="size-7 text-destructive hover:text-destructive"
                                onClick={() => setArchivePlant(plant)}
                                aria-label={`Archive ${plant.common_label ?? "plant"}`}
                              >
                                <Archive className="size-3.5" />
                              </Button>
                            </PermissionGate>
                          </div>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}

            {meta && meta.total_pages > 1 && (
              <div className="flex items-center justify-between text-body-sm text-muted-foreground">
                <span>
                  Page {meta.page} of {meta.total_pages} ({meta.total_items} plants)
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

      <RegisterPlantDialog open={registerOpen} onOpenChange={setRegisterOpen} />
      {editPlant && <EditPlantDialog open={!!editPlant} onOpenChange={(open) => { if (!open) setEditPlant(null); }} plant={editPlant} />}
      {archivePlant && <ArchivePlantDialog open={!!archivePlant} onOpenChange={(open) => { if (!open) setArchivePlant(null); }} plantId={archivePlant.id} plantLabel={archivePlant.common_label ?? "Unlabeled plant"} />}
    </Card>
  );
}
