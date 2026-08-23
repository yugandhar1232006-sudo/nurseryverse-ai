"use client";

import * as React from "react";
import { BarChart3, IndianRupee, Receipt, ShoppingBag, TrendingUp } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useBranchesQuery } from "@/lib/shell/queries";
import { useCustomerReportQuery } from "@/lib/customers/queries";
import { useRevenueReportQuery, useSalesReportQuery } from "@/lib/sales/queries";

const ALL = "__all__";

/**
 * `sales.py`'s two Sales reports (`getSalesReport`/`getRevenueReport`) plus
 * `customers.py`'s Top Customers report, surfaced as sub-tabs -- same
 * nested-Tabs `aria-label` disambiguation pattern established in 7H/7I.
 * All three exclude VOIDED sales server-side.
 */
export function SalesReportsPanel() {
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
        <Tabs defaultValue="summary">
          <TabsList aria-label="Sales reports">
            <TabsTrigger value="summary">Summary</TabsTrigger>
            <TabsTrigger value="revenue">Revenue</TabsTrigger>
            <TabsTrigger value="customers">Top Customers</TabsTrigger>
          </TabsList>
          <TabsContent value="summary">
            <SummaryReport branchId={resolvedBranchId} />
          </TabsContent>
          <TabsContent value="revenue">
            <RevenueReport branchId={resolvedBranchId} />
          </TabsContent>
          <TabsContent value="customers">
            <TopCustomersReport branchId={resolvedBranchId} />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}

function SummaryReport({ branchId }: { branchId: string | undefined }) {
  const query = useSalesReportQuery({ branch_id: branchId });

  if (query.isLoading) return <Skeleton className="h-24 w-full" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  const report = query.data;
  if (!report) return null;

  const cards = [
    { label: "Sales", value: report.sale_count, icon: ShoppingBag },
    { label: "Total revenue", value: `₹${report.total_revenue.toFixed(2)}`, icon: IndianRupee },
    { label: "Total tax", value: `₹${report.total_tax.toFixed(2)}`, icon: Receipt },
    { label: "Total discount", value: `₹${report.total_discount.toFixed(2)}`, icon: Receipt },
    { label: "Average sale value", value: `₹${report.average_sale_value.toFixed(2)}`, icon: BarChart3 },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 tablet:grid-cols-5">
      {cards.map((card) => (
        <div key={card.label} className="rounded-md border border-border p-3">
          <p className="text-body-sm text-muted-foreground">{card.label}</p>
          <p className="text-h4 font-semibold text-foreground">{card.value}</p>
        </div>
      ))}
    </div>
  );
}

function RevenueReport({ branchId }: { branchId: string | undefined }) {
  const query = useRevenueReportQuery({ branch_id: branchId });

  if (query.isLoading) return <Skeleton className="h-32 w-full" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  const rows = query.data ?? [];
  if (rows.length === 0) {
    return <EmptyState icon={TrendingUp} title="No revenue recorded yet" description="Day-by-day revenue will appear here once sales are completed." />;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Date</TableHead>
          <TableHead className="text-right">Revenue</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.date}>
            <TableCell className="text-foreground">{row.date}</TableCell>
            <TableCell className="text-right font-medium text-foreground">₹{row.revenue.toFixed(2)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function TopCustomersReport({ branchId }: { branchId: string | undefined }) {
  const query = useCustomerReportQuery(branchId ?? "");

  if (query.isLoading) return <Skeleton className="h-32 w-full" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  const rows = query.data ?? [];
  if (rows.length === 0) {
    return <EmptyState icon={ShoppingBag} title="No customer purchases yet" description="Top customers by spend will appear here." />;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Customer</TableHead>
          <TableHead className="text-right">Orders</TableHead>
          <TableHead className="text-right">Total spent</TableHead>
          <TableHead className="text-right">Avg. order value</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.customer_id}>
            <TableCell className="text-foreground">{row.name}</TableCell>
            <TableCell className="text-right">{row.total_orders}</TableCell>
            <TableCell className="text-right font-medium text-foreground">₹{row.total_spent.toFixed(2)}</TableCell>
            <TableCell className="text-right text-muted-foreground">₹{row.average_order_value.toFixed(2)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
