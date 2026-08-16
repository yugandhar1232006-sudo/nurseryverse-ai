"use client";

import * as React from "react";
import { MapPin, Plus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CreateLocationDialog } from "@/components/inventory/create-location-dialog";
import { useBranchesQuery } from "@/lib/shell/queries";
import { useInventoryLocationsQuery } from "@/lib/inventory/queries";
import { useDeactivateInventoryLocationMutation } from "@/lib/inventory/mutations";

/**
 * `GET /inventory-locations` requires a `branch_id` -- there is no
 * org-wide "all locations" listing route, so this panel always starts
 * from a branch picker (defaulting to the caller's first accessible
 * branch) rather than trying to fake a flat cross-branch table.
 */
export function LocationsPanel() {
  const branchesQuery = useBranchesQuery();
  const [branchId, setBranchId] = React.useState<string | null>(null);
  const [createOpen, setCreateOpen] = React.useState(false);

  // Auto-select the first accessible branch once the real branch list is
  // available -- React's "adjusting state during render" pattern (not an
  // Effect), guarded by `branchId === null` so it only ever fires once
  // and can't loop. Deliberately does NOT gate on a `branchesQuery.data`
  // reference-equality check (an earlier version did, mirroring 7G's
  // `ArchivePlantDialog` `syncedOpen` pattern) -- that guard is wrong
  // here: TanStack Query can hand back an already-cached `data` array on
  // this component's very *first* render (e.g. the Stock tab's
  // `InventoryList` already fetched+cached branches via the same
  // `useBranchesQuery` key before the user switches to this tab), so the
  // "did the reference just change" check is already satisfied before
  // the effect-free sync state is even initialized, and the auto-select
  // silently never runs. Found via a real test failure switching tabs
  // after the Stock tab's own branches fetch had already resolved.
  if (branchId === null && branchesQuery.data && branchesQuery.data.length > 0) {
    setBranchId(branchesQuery.data[0].id);
  }

  const locationsQuery = useInventoryLocationsQuery(branchId);
  const deactivateMutation = useDeactivateInventoryLocationMutation(branchId ?? "");

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Locations</CardTitle>
        <PermissionGate permission="inventory:write">
          <Button type="button" size="sm" disabled={!branchId} onClick={() => setCreateOpen(true)}>
            <Plus className="size-4" aria-hidden="true" />
            New location
          </Button>
        </PermissionGate>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {branchesQuery.isLoading ? (
          <Skeleton className="h-9 w-48" />
        ) : (
          <Select value={branchId ?? ""} onValueChange={setBranchId}>
            <SelectTrigger className="w-full tablet:w-64" aria-label="Branch">
              <SelectValue placeholder="Select a branch" />
            </SelectTrigger>
            <SelectContent>
              {(branchesQuery.data ?? []).map((branch) => (
                <SelectItem key={branch.id} value={branch.id}>
                  {branch.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        {locationsQuery.isLoading ? (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : locationsQuery.isError ? (
          <ErrorState error={locationsQuery.error} onRetry={() => locationsQuery.refetch()} retrying={locationsQuery.isFetching} />
        ) : !locationsQuery.data || locationsQuery.data.length === 0 ? (
          <EmptyState icon={MapPin} title="No locations yet" description="Create zones, greenhouses, racks, benches, or sections to organize this branch's stock." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Code</TableHead>
                <TableHead>Status</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {locationsQuery.data.map((location) => (
                <TableRow key={location.id}>
                  <TableCell className="font-medium text-foreground">{location.name}</TableCell>
                  <TableCell className="capitalize text-muted-foreground">{location.location_type.replace("_", " ")}</TableCell>
                  <TableCell className="text-muted-foreground">{location.code ?? "—"}</TableCell>
                  <TableCell>
                    <Badge tone={location.is_active ? "success" : "neutral"}>{location.is_active ? "Active" : "Inactive"}</Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    {location.is_active && (
                      <PermissionGate permission="inventory:write">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          disabled={deactivateMutation.isPending}
                          onClick={() => deactivateMutation.mutate(location.id)}
                        >
                          Deactivate
                        </Button>
                      </PermissionGate>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      {branchId && <CreateLocationDialog open={createOpen} onOpenChange={setCreateOpen} branchId={branchId} />}
    </Card>
  );
}
