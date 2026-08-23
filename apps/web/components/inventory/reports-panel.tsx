"use client";

import * as React from "react";
import { AlertTriangle, ArrowLeftRight, Boxes, IndianRupee, History, PackageCheck, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useBranchesQuery } from "@/lib/shell/queries";
import {
  useLowStockReportQuery,
  useStockValuationQuery,
  useWasteReportQuery,
  useTransferReportQuery,
  useMovementHistoryReportQuery,
  useReservationReportQuery,
} from "@/lib/inventory/queries";

const ALL = "__all__";

/**
 * `inventory.py`'s six real reporting routes (Low Stock, Valuation,
 * Waste, Transfer, Movement History, Reservations) surfaced as sub-tabs
 * of one Reports tab -- all org-wide (optionally branch-filtered), all
 * genuinely different report shapes, so kept as six small renderers
 * rather than one generic table. `aria-label` on the inner `TabsList`
 * follows the nested-Tabs disambiguation pattern established in 7H's
 * `DigitalTwinTab` (see docs/frontend/12-digital-twin.md).
 */
export function ReportsPanel() {
  const branchesQuery = useBranchesQuery();
  const [branchId, setBranchId] = React.useState(ALL);
  const resolvedBranchId = branchId === ALL ? undefined : branchId;

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Reports</CardTitle>
        {branchesQuery.isLoading ? (
          <Skeleton className="h-9 w-48" />
        ) : (
          <Select value={branchId} onValueChange={setBranchId}>
            <SelectTrigger className="w-48" aria-label="Filter reports by branch">
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
        )}
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="low-stock">
          <TabsList aria-label="Inventory reports" className="flex-wrap">
            <TabsTrigger value="low-stock">Low Stock</TabsTrigger>
            <TabsTrigger value="valuation">Valuation</TabsTrigger>
            <TabsTrigger value="waste">Waste</TabsTrigger>
            <TabsTrigger value="transfers">Transfers</TabsTrigger>
            <TabsTrigger value="movements">Movement History</TabsTrigger>
            <TabsTrigger value="reservations">Reservations</TabsTrigger>
          </TabsList>
          <TabsContent value="low-stock">
            <LowStockReport branchId={resolvedBranchId} />
          </TabsContent>
          <TabsContent value="valuation">
            <ValuationReport branchId={resolvedBranchId} />
          </TabsContent>
          <TabsContent value="waste">
            <WasteReport branchId={resolvedBranchId} />
          </TabsContent>
          <TabsContent value="transfers">
            <TransferReport branchId={resolvedBranchId} />
          </TabsContent>
          <TabsContent value="movements">
            <MovementHistoryReport branchId={resolvedBranchId} />
          </TabsContent>
          <TabsContent value="reservations">
            <ReservationReport branchId={resolvedBranchId} />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}

function LowStockReport({ branchId }: { branchId: string | undefined }) {
  const query = useLowStockReportQuery(branchId ?? "");

  if (query.isLoading) return <Skeleton className="h-32 w-full" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  if (!query.data || query.data.length === 0) {
    return <EmptyState icon={AlertTriangle} title="Nothing is low on stock" description="Every inventory line is at or above its low-stock threshold." />;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead className="text-right">On hand</TableHead>
          <TableHead className="text-right">Threshold</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {query.data.map((item) => (
          <TableRow key={item.id}>
            <TableCell className="font-medium text-foreground">{item.name}</TableCell>
            <TableCell className="text-right">
              <Badge tone="warning">{item.quantity}</Badge>
            </TableCell>
            <TableCell className="text-right text-muted-foreground">{item.low_stock_threshold}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function ValuationReport({ branchId }: { branchId: string | undefined }) {
  const query = useStockValuationQuery(branchId ?? "");

  if (query.isLoading) return <Skeleton className="h-24 w-full" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  const valuation = query.data;
  if (!valuation) return null;

  const cards = [
    { label: "Lines", value: valuation.line_count, icon: Boxes },
    { label: "Cost value", value: `₹${valuation.total_cost_value.toFixed(2)}`, icon: IndianRupee },
    { label: "Retail value", value: `₹${valuation.total_retail_value.toFixed(2)}`, icon: IndianRupee },
    { label: "Potential margin", value: `₹${valuation.potential_margin.toFixed(2)}`, icon: IndianRupee },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 tablet:grid-cols-4">
      {cards.map((card) => (
        <div key={card.label} className="rounded-md border border-border p-3">
          <p className="text-body-sm text-muted-foreground">{card.label}</p>
          <p className="text-h4 font-semibold text-foreground">{card.value}</p>
        </div>
      ))}
    </div>
  );
}

function WasteReport({ branchId }: { branchId: string | undefined }) {
  const query = useWasteReportQuery({ branch_id: branchId });

  if (query.isLoading) return <Skeleton className="h-32 w-full" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  const report = query.data;
  if (!report || report.movement_count === 0) {
    return <EmptyState icon={Trash2} title="No waste recorded" description="Disposed stock will appear here." />;
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-body-sm text-muted-foreground">
        {report.movement_count} disposal{report.movement_count === 1 ? "" : "s"}, {report.total_quantity_disposed} units total.
      </p>
      <ul className="flex flex-col gap-2">
        {report.movements.map((movement) => (
          <li key={movement.id} className="rounded-md border border-border p-3 text-body-sm">
            <span className="font-medium text-foreground">{Math.abs(movement.quantity_delta)} units disposed</span>
            {movement.note && <p className="text-muted-foreground">{movement.note}</p>}
            <p className="text-caption text-muted-foreground">{new Date(movement.created_at).toLocaleString()}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

function TransferReport({ branchId }: { branchId: string | undefined }) {
  const query = useTransferReportQuery({ branch_id: branchId });

  if (query.isLoading) return <Skeleton className="h-32 w-full" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  const report = query.data;
  if (!report || report.movement_count === 0) {
    return <EmptyState icon={ArrowLeftRight} title="No transfers recorded" description="Stock moved between locations or branches will appear here." />;
  }

  return (
    <ul className="flex flex-col gap-2">
      {report.movements.map((movement) => (
        <li key={movement.id} className="rounded-md border border-border p-3 text-body-sm">
          <span className="font-medium text-foreground">{movement.quantity_delta > 0 ? "+" : ""}{movement.quantity_delta} units</span>
          {movement.note && <p className="text-muted-foreground">{movement.note}</p>}
          <p className="text-caption text-muted-foreground">{new Date(movement.created_at).toLocaleString()}</p>
        </li>
      ))}
    </ul>
  );
}

function MovementHistoryReport({ branchId }: { branchId: string | undefined }) {
  const [page, setPage] = React.useState(1);
  const query = useMovementHistoryReportQuery({ branch_id: branchId, page, page_size: 20 });

  if (query.isLoading) return <Skeleton className="h-32 w-full" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  const items = query.data?.items ?? [];
  if (items.length === 0) {
    return <EmptyState icon={History} title="No movements yet" description="Every stock movement across this org appears here." />;
  }

  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-col gap-2">
        {items.map((movement) => (
          <li key={movement.id} className="rounded-md border border-border p-3 text-body-sm">
            <span className="font-medium capitalize text-foreground">{movement.movement_type}</span>{" "}
            <span className={movement.quantity_delta >= 0 ? "text-success-dark" : "text-danger-dark"}>
              {movement.quantity_delta >= 0 ? "+" : ""}
              {movement.quantity_delta}
            </span>
            <p className="text-caption text-muted-foreground">{new Date(movement.created_at).toLocaleString()}</p>
          </li>
        ))}
      </ul>
      {query.data && query.data.meta.total_pages > 1 && (
        <div className="flex items-center justify-between text-body-sm text-muted-foreground">
          <span>
            Page {query.data.meta.page} of {query.data.meta.total_pages}
          </span>
          <div className="flex gap-2">
            <button type="button" className="text-primary disabled:opacity-50" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </button>
            <button
              type="button"
              className="text-primary disabled:opacity-50"
              disabled={page >= query.data.meta.total_pages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function ReservationReport({ branchId }: { branchId: string | undefined }) {
  const query = useReservationReportQuery({ branch_id: branchId, page: 1, page_size: 20 });

  if (query.isLoading) return <Skeleton className="h-32 w-full" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  const items = query.data?.items ?? [];
  if (items.length === 0) {
    return <EmptyState icon={PackageCheck} title="No active reservations" description="Stock held for pending sales or orders across this org appears here." />;
  }

  return (
    <ul className="flex flex-col gap-2">
      {items.map((reservation) => (
        <li key={reservation.id} className="rounded-md border border-border p-3 text-body-sm">
          <span className="font-medium text-foreground">{reservation.quantity} units</span>{" "}
          <Badge tone="info">{reservation.status}</Badge>
          <p className="text-caption text-muted-foreground">Reserved {new Date(reservation.reserved_at).toLocaleString()}</p>
        </li>
      ))}
    </ul>
  );
}
