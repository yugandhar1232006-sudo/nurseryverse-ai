"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Leaf, Plus, Search } from "lucide-react";

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
import { useBranchesQuery } from "@/lib/shell/queries";
import { useSpeciesListQuery } from "@/lib/catalog/queries";
import { usePlantsListQuery } from "@/lib/plants/queries";
import type { PlantStatus } from "@/lib/api/plants";

const ALL = "__all__";
const DEBOUNCE_MS = 300;

const STATUS_OPTIONS: { value: PlantStatus; label: string }[] = [
  { value: "in_production", label: "In production" },
  { value: "ready_for_sale", label: "Ready for sale" },
  { value: "under_treatment", label: "Under treatment" },
  { value: "sold", label: "Sold" },
  { value: "deceased", label: "Deceased" },
];

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = React.useState(value);
  React.useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

/**
 * The 7G `/plants` screen -- the individual-plant-record counterpart to
 * 7F's Species Catalog. `Plant` is branch-scoped (see lib/api/plants.ts's
 * docstring), but this list intentionally does not filter by the
 * caller's own branch access client-side: the backend's `plants:read`
 * scoping already limits what `GET /plants` returns for a Branch-scoped
 * role, so an extra client-side filter would only risk drifting out of
 * sync with the real authorization rule.
 */
export function PlantsList() {
  const router = useRouter();
  const [page, setPage] = React.useState(1);
  const [rawSearch, setRawSearch] = React.useState("");
  const [branchId, setBranchId] = React.useState(ALL);
  const [speciesId, setSpeciesId] = React.useState(ALL);
  const [status, setStatus] = React.useState(ALL);
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
  const query = usePlantsListQuery({
    page,
    page_size: 20,
    search: search || undefined,
    branch_id: branchId === ALL ? undefined : branchId,
    species_id: speciesId === ALL ? undefined : speciesId,
    status_filter: status === ALL ? undefined : (status as PlantStatus),
  });

  const [registerOpen, setRegisterOpen] = React.useState(false);

  const items = query.data?.items ?? [];
  const meta = query.data?.meta;
  const branchNameById = new Map((branchesQuery.data ?? []).map((b) => [b.id, b.name]));
  const speciesNameById = new Map((speciesQuery.data?.items ?? []).map((s) => [s.id, s.common_name]));
  const hasFilters = search !== "" || branchId !== ALL || speciesId !== ALL || status !== ALL;

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Plants</CardTitle>
        <PermissionGate permission="plants:write">
          <Button type="button" size="sm" onClick={() => setRegisterOpen(true)}>
            <Plus className="size-4" aria-hidden="true" />
            Register plant
          </Button>
        </PermissionGate>
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
            title={hasFilters ? "No plants match your filters" : "No plants yet"}
            description={hasFilters ? "Try a different search term or filter." : "Register your organization's first plant to start tracking it."}
          />
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Label</TableHead>
                  <TableHead>Species</TableHead>
                  <TableHead>Branch</TableHead>
                  <TableHead>Zone</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Age</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((plant) => (
                  <TableRow key={plant.id} className="cursor-pointer" onClick={() => router.push(`/plants/${plant.id}`)}>
                    <TableCell className="font-medium text-foreground">{plant.common_label ?? "Unlabeled"}</TableCell>
                    <TableCell>{speciesNameById.get(plant.species_id) ?? "—"}</TableCell>
                    <TableCell className="text-muted-foreground">{branchNameById.get(plant.branch_id) ?? "—"}</TableCell>
                    <TableCell className="text-muted-foreground">{plant.zone ?? "—"}</TableCell>
                    <TableCell>
                      <PlantStatusBadge status={plant.status} />
                    </TableCell>
                    <TableCell className="text-right text-muted-foreground">{plant.age_days} days</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

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
    </Card>
  );
}
