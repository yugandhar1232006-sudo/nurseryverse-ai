"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Receipt } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useBranchesQuery } from "@/lib/shell/queries";
import { useSaleListQuery } from "@/lib/sales/queries";

const ALL = "__all__";

/** Completed transactions (`Sale`) -- created only via Sales Order checkout, never directly, so this list has no "create" action of its own. */
export function SalesList() {
  const router = useRouter();
  const [page, setPage] = React.useState(1);
  const [branchId, setBranchId] = React.useState(ALL);

  const branchesQuery = useBranchesQuery();
  const query = useSaleListQuery({ page, page_size: 20, branch_id: branchId === ALL ? undefined : branchId });

  const items = query.data?.items ?? [];
  const meta = query.data?.meta;
  const branchNameById = new Map((branchesQuery.data ?? []).map((b) => [b.id, b.name]));

  return (
    <Card>
      <CardHeader className="flex-col items-stretch gap-4 space-y-0">
        <CardTitle>Sales</CardTitle>
        <Select
          value={branchId}
          onValueChange={(v) => {
            setBranchId(v);
            setPage(1);
          }}
        >
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
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {query.isLoading ? (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />
        ) : items.length === 0 ? (
          <EmptyState icon={Receipt} title="No completed sales yet" description="Sales appear here once a sales order is checked out." />
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Branch</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Total</TableHead>
                  <TableHead>Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((sale) => (
                  <TableRow key={sale.id} className="cursor-pointer" onClick={() => router.push(`/sales/${sale.id}`)}>
                    <TableCell className="text-foreground">{branchNameById.get(sale.branch_id) ?? "—"}</TableCell>
                    <TableCell>
                      <Badge tone={sale.status === "voided" ? "danger" : "success"} className="capitalize">
                        {sale.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right font-medium text-foreground">${Number(sale.total_amount).toFixed(2)}</TableCell>
                    <TableCell className="text-muted-foreground">{new Date(sale.created_at).toLocaleDateString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            {meta && meta.total_pages > 1 && (
              <div className="flex items-center justify-between text-body-sm text-muted-foreground">
                <span>
                  Page {meta.page} of {meta.total_pages}
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
    </Card>
  );
}
