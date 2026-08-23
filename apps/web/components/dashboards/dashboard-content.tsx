"use client";

import * as React from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ALL_BRANCHES, DashboardScopeSelect } from "@/components/dashboards/dashboard-scope-select";
import { ExecutiveTab } from "@/components/dashboards/executive-tab";
import { NurseryTab } from "@/components/dashboards/nursery-tab";
import { BranchTab } from "@/components/dashboards/branch-tab";
import { PlantTab } from "@/components/dashboards/plant-tab";
import { InventoryTab } from "@/components/dashboards/inventory-tab";
import { SalesTab } from "@/components/dashboards/sales-tab";
import { CustomerTab } from "@/components/dashboards/customer-tab";
import { AITab } from "@/components/dashboards/ai-tab";
import { FinancialTab } from "@/components/dashboards/financial-tab";
import { useBranchesQuery, useOrgSettingsQuery } from "@/lib/shell/queries";

/**
 * The real Dashboard route's content once `reports:read` is confirmed
 * (see app/(app)/page.tsx). Combines all 9 Module 12 dashboard endpoints
 * into one tabbed screen -- there is exactly one "Dashboard" entry in
 * `NAV_ITEMS` (nav-config.ts), so PG-07/PG-08/the seven additional
 * dashboard types the 7D kickoff names are presented as tabs of a single
 * destination rather than nine separate routes nothing in the sidebar
 * would ever link to.
 *
 * Executive/Nursery dashboards (and the Branches table inside Executive)
 * are always org-wide -- the real backend routes take no `branch_id` at
 * all (see lib/api/reports.ts) -- so the scope selector only affects
 * Branch/Plant/Inventory/Sales/Customer/AI/Financial.
 */
export function DashboardContent() {
  const branchesQuery = useBranchesQuery();
  const orgSettingsQuery = useOrgSettingsQuery();
  const [scope, setScope] = React.useState<string>(ALL_BRANCHES);

  const branches = branchesQuery.data ?? [];
  const currency = orgSettingsQuery.data?.default_currency ?? "INR";
  const scopeBranchId = scope === ALL_BRANCHES ? null : scope;
  const dateRange = React.useMemo(() => ({}), []); // no explicit date filter chosen yet -- backend default (trailing period) applies

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 tablet:flex-row tablet:items-center tablet:justify-between">
        <h1 className="text-h2 font-semibold text-foreground">Dashboard</h1>
        <DashboardScopeSelect branches={branches} value={scope} onChange={setScope} loading={branchesQuery.isLoading} />
      </div>

      <Tabs defaultValue="executive">
        <TabsList className="flex-wrap">
          <TabsTrigger value="executive">Executive</TabsTrigger>
          <TabsTrigger value="nursery">Nursery</TabsTrigger>
          <TabsTrigger value="branch">Branch</TabsTrigger>
          <TabsTrigger value="plant">Plants</TabsTrigger>
          <TabsTrigger value="inventory">Inventory</TabsTrigger>
          <TabsTrigger value="sales">Sales</TabsTrigger>
          <TabsTrigger value="customer">Customers</TabsTrigger>
          <TabsTrigger value="ai">AI</TabsTrigger>
          <TabsTrigger value="financial">Financial</TabsTrigger>
        </TabsList>

        <TabsContent value="executive">
          <ExecutiveTab currency={currency} />
        </TabsContent>
        <TabsContent value="nursery">
          <NurseryTab />
        </TabsContent>
        <TabsContent value="branch">
          <BranchTab branchId={scopeBranchId} currency={currency} />
        </TabsContent>
        <TabsContent value="plant">
          <PlantTab branchId={scopeBranchId} />
        </TabsContent>
        <TabsContent value="inventory">
          <InventoryTab branchId={scopeBranchId} currency={currency} />
        </TabsContent>
        <TabsContent value="sales">
          <SalesTab branchId={scopeBranchId} range={dateRange} currency={currency} />
        </TabsContent>
        <TabsContent value="customer">
          <CustomerTab branchId={scopeBranchId} currency={currency} />
        </TabsContent>
        <TabsContent value="ai">
          <AITab branchId={scopeBranchId} />
        </TabsContent>
        <TabsContent value="financial">
          <FinancialTab branchId={scopeBranchId} range={dateRange} currency={currency} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
