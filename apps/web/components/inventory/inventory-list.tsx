"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Boxes, Plus, Search } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Input } from "@/components/ui/input";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { InventorySummaryCards } from "@/components/inventory/inventory-summary-cards";
import { CreateInventoryLineDialog } from "@/components/inventory/create-inventory-line-dialog";
import { useBranchesQuery } from "@/lib/shell/queries";
import { usePlantCategoriesQuery } from "@/lib/catalog/queries";
import { useInventoryListQuery } from "@/lib/inventory/queries";

const ALL = "__all__";
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
 * The 7I `/inventory` Stock tab -- the bulk-stock counterpart to 7G's
 * `/plants` list. `Inventory` lines are branch-scoped the same way
 * `Plant` is (see lib/api/inventory.ts's docstring): the backend's
 * `inventory:read` scoping already limits what `GET /inventory` returns,
 * so this list adds no client-side branch filtering of its own beyond the
 * explicit branch filter dropdown, which is a user-chosen narrowing, not
 * an authorization boundary.
 */
export function InventoryList() {
  const router = useRouter();
  const [page, setPage] = React.useState(1);
  const [rawSearch, setRawSearch] = React.useState("");
  const [branchId, setBranchId] = React.useState(ALL);
  const [categoryId, setCategoryId] = React.useState(ALL);
  const [lowStockOnly, setLowStockOnly] = React.useState(false);
  const search = useDebouncedValue(rawSearch, DEBOUNCE_MS);

  const [syncedFilters, setSyncedFilters] = React.useState({ search, branchId, categoryId, lowStockOnly });
  if (
    syncedFilters.search !== search ||
    syncedFilters.branchId !== branchId ||
    syncedFilters.categoryId !== categoryId ||
    syncedFilters.lowStockOnly !== lowStockOnly
  ) {
    setSyncedFilters({ search, branchId, categoryId, lowStockOnly });
    if (page !== 1) setPage(1);
  }

  const branchesQuery = useBranchesQuery();
  const categoriesQuery = usePlantCategoriesQuery();
  const query = useInventoryListQuery({
    page,
    page_size: 20,
    search: search || undefined,
    branch_id: branchId === ALL ? undefined : branchId,
    category_id: categoryId === ALL ? undefined : categoryId,
    low_stock_only: lowStockOnly || undefined,
  });

  const [createOpen, setCreateOpen] = React.useState(false);

  const items = query.data?.items ?? [];
  const meta = query.data?.meta;
  const branchNameById = new Map((branchesQuery.data ?? []).map((b) => [b.id, b.name]));
  const categoryNameById = new Map((categoriesQuery.data ?? []).map((c) => [c.id, c.name]));
  const hasFilters = search !== "" || branchId !== ALL || categoryId !== ALL || lowStockOnly;

  return (
    <Card>
      <CardHeader className="flex-col items-stretch gap-4 space-y-0">
        <div className="flex items-center justify-between">
          <CardTitle>Stock</CardTitle>
          <PermissionGate permission="inventory:write">
            <Button type="button" size="sm" onClick={() => setCreateOpen(true)}>
              <Plus className="size-4" aria-hidden="true" />
              Create line
            </Button>
          </PermissionGate>
        </div>
        <InventorySummaryCards branchId={branchId === ALL ? "" : branchId} />
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-2 tablet:flex-row tablet:flex-wrap tablet:items-center">
          <div className="relative flex-1 tablet:min-w-[220px]">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input
              value={rawSearch}
              onChange={(e) => setRawSearch(e.target.value)}
              placeholder="Search by name…"
              className="pl-8"
              aria-label="Search inventory"
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
          <Select value={categoryId} onValueChange={setCategoryId}>
            <SelectTrigger className="w-full tablet:w-48" aria-label="Filter by category">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All categories</SelectItem>
              {(categoriesQuery.data ?? []).map((category) => (
                <SelectItem key={category.id} value={category.id}>
                  {category.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <label className="flex items-center gap-2 text-body-sm text-foreground">
            <Checkbox checked={lowStockOnly} onCheckedChange={(checked) => setLowStockOnly(checked === true)} />
            Low stock only
          </label>
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
            icon={Boxes}
            title={hasFilters ? "No inventory lines match your filters" : "No inventory yet"}
            description={hasFilters ? "Try a different search term or filter." : "Create your organization's first inventory line to start tracking stock."}
          />
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Branch</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead className="text-right">Available</TableHead>
                  <TableHead className="text-right">Reserved</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => {
                  const isLow = item.quantity <= item.low_stock_threshold;
                  return (
                    <TableRow key={item.id} className="cursor-pointer" onClick={() => router.push(`/inventory/${item.id}`)}>
                      <TableCell className="font-medium text-foreground">{item.name}</TableCell>
                      <TableCell className="text-muted-foreground">{branchNameById.get(item.branch_id) ?? "—"}</TableCell>
                      <TableCell className="text-muted-foreground">{categoryNameById.get(item.category_id) ?? "—"}</TableCell>
                      <TableCell className="text-right">{item.available_quantity}</TableCell>
                      <TableCell className="text-right text-muted-foreground">{item.reserved_quantity}</TableCell>
                      <TableCell>
                        {item.archived_at ? (
                          <Badge tone="neutral">Archived</Badge>
                        ) : isLow ? (
                          <Badge tone="warning">Low stock</Badge>
                        ) : (
                          <Badge tone="success">In stock</Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>

            {meta && meta.total_pages > 1 && (
              <div className="flex items-center justify-between text-body-sm text-muted-foreground">
                <span>
                  Page {meta.page} of {meta.total_pages} ({meta.total_items} lines)
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

      <CreateInventoryLineDialog open={createOpen} onOpenChange={setCreateOpen} />
    </Card>
  );
}
