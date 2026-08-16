"use client";

import * as React from "react";
import { Plus, Undo2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CreateRefundDialog } from "@/components/sales/create-refund-dialog";
import { useBranchesQuery } from "@/lib/shell/queries";
import { useRefundListQuery } from "@/lib/sales/queries";
import type { RefundStatus } from "@/lib/api/sales";

const ALL = "__all__";

const STATUS_TONE: Record<RefundStatus, "neutral" | "success" | "warning" | "danger" | "info"> = {
  pending: "warning",
  completed: "success",
  failed: "danger",
};

export function RefundsList() {
  const [page, setPage] = React.useState(1);
  const [branchId, setBranchId] = React.useState(ALL);
  const [status, setStatus] = React.useState(ALL);
  const [createOpen, setCreateOpen] = React.useState(false);

  const branchesQuery = useBranchesQuery();
  const query = useRefundListQuery({
    page,
    page_size: 20,
    branch_id: branchId === ALL ? undefined : branchId,
    status_filter: status === ALL ? undefined : (status as RefundStatus),
  });

  const items = query.data?.items ?? [];
  const meta = query.data?.meta;
  const branchNameById = new Map((branchesQuery.data ?? []).map((b) => [b.id, b.name]));

  return (
    <Card>
      <CardHeader className="flex-col items-stretch gap-4 space-y-0">
        <div className="flex items-center justify-between">
          <CardTitle>Refunds</CardTitle>
          <PermissionGate permission="invoices:write">
            <Button type="button" size="sm" onClick={() => setCreateOpen(true)}>
              <Plus className="size-4" aria-hidden="true" />
              Process refund
            </Button>
          </PermissionGate>
        </div>
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
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
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
          <EmptyState icon={Undo2} title="No refunds yet" description="Refunds processed against a sale, invoice, or return appear here." />
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Branch</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Method</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                  <TableHead>Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((refund) => (
                  <TableRow key={refund.id}>
                    <TableCell className="text-foreground">{branchNameById.get(refund.branch_id) ?? "—"}</TableCell>
                    <TableCell>
                      <Badge tone={STATUS_TONE[refund.status]} className="capitalize">
                        {refund.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="capitalize text-muted-foreground">{refund.method.replace("_", " ")}</TableCell>
                    <TableCell className="text-right font-medium text-foreground">${Number(refund.amount).toFixed(2)}</TableCell>
                    <TableCell className="text-muted-foreground">{new Date(refund.created_at).toLocaleDateString()}</TableCell>
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

      <CreateRefundDialog open={createOpen} onOpenChange={setCreateOpen} />
    </Card>
  );
}
