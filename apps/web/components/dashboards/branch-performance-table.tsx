import { Building2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { BranchSummaryResponse } from "@/lib/api/reports";
import { formatCurrency, formatNumber } from "@/lib/utils";

/**
 * Renders `ExecutiveDashboardResponse.branches` (org-wide) or the
 * standalone `GET /analytics/branch-performance` list (same
 * `BranchSummaryResponse` shape, ranked by MTD revenue server-side --
 * see reports.py's own summary text) -- shared here since both are the
 * exact same real per-branch rollup row.
 */
export function BranchPerformanceTable({
  branches,
  currency,
  loading,
}: {
  branches: BranchSummaryResponse[] | undefined;
  currency: string;
  loading?: boolean;
}) {
  if (loading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  if (!branches || branches.length === 0) {
    return <EmptyState icon={Building2} title="No branches yet" description="Branch performance appears here once your organization has at least one branch." />;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Branch</TableHead>
          <TableHead className="text-right">Revenue today</TableHead>
          <TableHead className="text-right">Revenue MTD</TableHead>
          <TableHead className="text-right">At-risk plants</TableHead>
          <TableHead className="text-right">Low stock</TableHead>
          <TableHead className="text-right">Disease reports</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {branches.map((b) => (
          <TableRow key={b.branch_id}>
            <TableCell className="font-medium text-foreground">{b.branch_name ?? "Unnamed branch"}</TableCell>
            <TableCell className="text-right tabular-nums">{formatCurrency(b.revenue_today, currency)}</TableCell>
            <TableCell className="text-right tabular-nums">{formatCurrency(b.revenue_mtd, currency)}</TableCell>
            <TableCell className="text-right">
              {b.at_risk_plant_count > 0 ? (
                <Badge tone="warning">{formatNumber(b.at_risk_plant_count)}</Badge>
              ) : (
                <span className="text-muted-foreground">0</span>
              )}
            </TableCell>
            <TableCell className="text-right">
              {b.low_stock_count > 0 ? (
                <Badge tone="warning">{formatNumber(b.low_stock_count)}</Badge>
              ) : (
                <span className="text-muted-foreground">0</span>
              )}
            </TableCell>
            <TableCell className="text-right">
              {b.pending_disease_reports > 0 ? (
                <Badge tone="danger">{formatNumber(b.pending_disease_reports)}</Badge>
              ) : (
                <span className="text-muted-foreground">0</span>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
