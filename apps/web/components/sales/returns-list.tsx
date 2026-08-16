"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Undo2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useBranchesQuery } from "@/lib/shell/queries";
import { useReturnListQuery } from "@/lib/sales/queries";
import type { ReturnStatus } from "@/lib/api/sales";

const ALL = "__all__";

const STATUS_TONE: Record<ReturnStatus, "neutral" | "success" | "warning" | "danger" | "info"> = {
  requested: "warning",
  approved: "info",
  rejected: "danger",
  completed: "success",
};

/** Returns are created from a completed Sale's detail page (`SaleHeader`'s "Request return" action), not from this list. */
export function ReturnsList() {
  const router = useRouter();
  const [page, setPage] = React.useState(1);
  const [branchId, setBranchId] = React.useState(ALL);
  const [status, setStatus] = React.useState(ALL);

  const branchesQuery = useBranchesQuery();
  const query = useReturnListQuery({
    page,
    page_size: 20,
    branch_id: branchId === ALL ? undefined : branchId,
    status_filter: status === ALL ? undefined : (status as ReturnStatus),
  });

  const items = query.data?.items ?? [];
  const meta = query.data?.meta;
  const branchNameById = new Map((branchesQuery.data ?? []).map((b) => [b.id, b.name]));

  return (
    <Card>
      <CardHeader className="flex-col items-stretch gap-4 space-y-0">
        <CardTitle>Returns</CardTitle>
        <div className="flex flex-col gap-2 tablet:flex-row">
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
          <Select
            value={status}
            onValueChange={(v) => {
              setStatus(v);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-full tablet:w-40" aria-label="Filter by status">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All statuses</SelectItem>
              <SelectItem value="requested">Requested</SelectItem>
              <SelectItem value="approved">Approved</SelectItem>
              <SelectItem value="rejected">Rejected</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
            </SelectContent>
          </Select>
        </div>
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
          <EmptyState icon={Undo2} title="No returns yet" description="Returns requested against a completed sale appear here." />
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Branch</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead>Requested</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((ret) => (
                  <TableRow key={ret.id} className="cursor-pointer" onClick={() => router.push(`/sales/returns/${ret.id}`)}>
                    <TableCell className="text-foreground">{branchNameById.get(ret.branch_id) ?? "—"}</TableCell>
                    <TableCell>
                      <Badge tone={STATUS_TONE[ret.status]} className="capitalize">
                        {ret.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{ret.reason ?? "—"}</TableCell>
                    <TableCell className="text-muted-foreground">{new Date(ret.created_at).toLocaleDateString()}</TableCell>
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
