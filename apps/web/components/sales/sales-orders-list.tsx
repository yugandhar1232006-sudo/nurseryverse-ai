"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { ClipboardList, Plus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CreateSalesOrderDialog } from "@/components/sales/create-sales-order-dialog";
import { useBranchesQuery } from "@/lib/shell/queries";
import { useSalesOrderListQuery } from "@/lib/sales/queries";
import type { SalesOrderStatus } from "@/lib/api/sales";

const ALL = "__all__";

const STATUS_TONE: Record<SalesOrderStatus, "neutral" | "success" | "warning" | "danger" | "info"> = {
  draft: "neutral",
  confirmed: "info",
  processing: "warning",
  fulfilled: "success",
  cancelled: "danger",
};

export function SalesOrdersList() {
  const router = useRouter();
  const [page, setPage] = React.useState(1);
  const [branchId, setBranchId] = React.useState(ALL);
  const [status, setStatus] = React.useState(ALL);
  const [createOpen, setCreateOpen] = React.useState(false);

  const branchesQuery = useBranchesQuery();
  const query = useSalesOrderListQuery({
    page,
    page_size: 20,
    branch_id: branchId === ALL ? undefined : branchId,
    order_status: status === ALL ? undefined : (status as SalesOrderStatus),
  });

  const items = query.data?.items ?? [];
  const meta = query.data?.meta;
  const branchNameById = new Map((branchesQuery.data ?? []).map((b) => [b.id, b.name]));

  return (
    <Card>
      <CardHeader className="flex-col items-stretch gap-4 space-y-0">
        <div className="flex items-center justify-between">
          <CardTitle>Sales Orders</CardTitle>
          <PermissionGate permission="sales:write">
            <Button type="button" size="sm" onClick={() => setCreateOpen(true)}>
              <Plus className="size-4" aria-hidden="true" />
              New order
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
              <SelectItem value="draft">Draft</SelectItem>
              <SelectItem value="confirmed">Confirmed</SelectItem>
              <SelectItem value="processing">Processing</SelectItem>
              <SelectItem value="fulfilled">Fulfilled</SelectItem>
              <SelectItem value="cancelled">Cancelled</SelectItem>
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
          <EmptyState icon={ClipboardList} title="No sales orders yet" description="Create a sales order to reserve stock and check out a customer's purchase." />
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Branch</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Payment</TableHead>
                  <TableHead className="text-right">Total</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((order) => (
                  <TableRow key={order.id} className="cursor-pointer" onClick={() => router.push(`/sales/orders/${order.id}`)}>
                    <TableCell className="text-foreground">{branchNameById.get(order.branch_id) ?? "—"}</TableCell>
                    <TableCell>
                      <Badge tone={STATUS_TONE[order.order_status]} className="capitalize">
                        {order.order_status}
                      </Badge>
                    </TableCell>
                    <TableCell className="capitalize text-muted-foreground">{order.payment_status.replace("_", " ")}</TableCell>
                    <TableCell className="text-right font-medium text-foreground">₹{Number(order.total_amount).toFixed(2)}</TableCell>
                    <TableCell className="text-muted-foreground">{new Date(order.created_at).toLocaleDateString()}</TableCell>
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

      <CreateSalesOrderDialog open={createOpen} onOpenChange={setCreateOpen} />
    </Card>
  );
}
