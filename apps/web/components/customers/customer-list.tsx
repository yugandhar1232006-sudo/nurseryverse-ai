"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Plus, Search, Users } from "lucide-react";

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
import { CreateCustomerDialog } from "@/components/customers/create-customer-dialog";
import { useBranchesQuery } from "@/lib/shell/queries";
import { useCustomerListQuery } from "@/lib/customers/queries";

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

/** The 7J `/customers` list -- same search/filter/paginate shape as 7G's `/plants` and 7I's `/inventory`. */
export function CustomerList() {
  const router = useRouter();
  const [page, setPage] = React.useState(1);
  const [rawSearch, setRawSearch] = React.useState("");
  const [branchId, setBranchId] = React.useState(ALL);
  const [customerType, setCustomerType] = React.useState(ALL);
  const search = useDebouncedValue(rawSearch, DEBOUNCE_MS);

  const [syncedFilters, setSyncedFilters] = React.useState({ search, branchId, customerType });
  if (syncedFilters.search !== search || syncedFilters.branchId !== branchId || syncedFilters.customerType !== customerType) {
    setSyncedFilters({ search, branchId, customerType });
    if (page !== 1) setPage(1);
  }

  const branchesQuery = useBranchesQuery();
  const query = useCustomerListQuery({
    page,
    page_size: 20,
    search: search || undefined,
    branch_id: branchId === ALL ? undefined : branchId,
    customer_type: customerType === ALL ? undefined : (customerType as "retail" | "wholesale"),
  });

  const [createOpen, setCreateOpen] = React.useState(false);

  const items = query.data?.items ?? [];
  const meta = query.data?.meta;
  const branchNameById = new Map((branchesQuery.data ?? []).map((b) => [b.id, b.name]));
  const hasFilters = search !== "" || branchId !== ALL || customerType !== ALL;

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Customers</CardTitle>
        <PermissionGate permission="customers:write">
          <Button type="button" size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="size-4" aria-hidden="true" />
            Add customer
          </Button>
        </PermissionGate>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-2 tablet:flex-row tablet:flex-wrap tablet:items-center">
          <div className="relative flex-1 tablet:min-w-[220px]">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input
              value={rawSearch}
              onChange={(e) => setRawSearch(e.target.value)}
              placeholder="Search by name, email, phone…"
              className="pl-8"
              aria-label="Search customers"
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
          <Select value={customerType} onValueChange={setCustomerType}>
            <SelectTrigger className="w-full tablet:w-40" aria-label="Filter by customer type">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All types</SelectItem>
              <SelectItem value="retail">Retail</SelectItem>
              <SelectItem value="wholesale">Wholesale</SelectItem>
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
            icon={Users}
            title={hasFilters ? "No customers match your filters" : "No customers yet"}
            description={hasFilters ? "Try a different search term or filter." : "Add your organization's first customer to start tracking sales."}
          />
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Branch</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Phone</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((customer) => (
                  <TableRow key={customer.id} className="cursor-pointer" onClick={() => router.push(`/customers/${customer.id}`)}>
                    <TableCell className="font-medium text-foreground">{customer.name}</TableCell>
                    <TableCell className="text-muted-foreground">{branchNameById.get(customer.branch_id) ?? "—"}</TableCell>
                    <TableCell>
                      <Badge tone={customer.customer_type === "wholesale" ? "info" : "neutral"} className="capitalize">
                        {customer.customer_type}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{customer.email ?? "—"}</TableCell>
                    <TableCell className="text-muted-foreground">{customer.phone ?? "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            {meta && meta.total_pages > 1 && (
              <div className="flex items-center justify-between text-body-sm text-muted-foreground">
                <span>
                  Page {meta.page} of {meta.total_pages} ({meta.total_items} customers)
                </span>
                <div className="flex gap-2">
                  <Button type="button" variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                    Previous
                  </Button>
                  <Button type="button" variant="outline" size="sm" disabled={page >= meta.total_pages} onClick={() => setPage((p) => p + 1)}>
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>

      <CreateCustomerDialog open={createOpen} onOpenChange={setCreateOpen} />
    </Card>
  );
}
