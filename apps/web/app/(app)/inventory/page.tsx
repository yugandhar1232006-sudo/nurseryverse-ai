"use client";

import { PermissionDenied } from "@/components/layout/permission-denied";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { InventoryList } from "@/components/inventory/inventory-list";
import { LocationsPanel } from "@/components/inventory/locations-panel";
import { ReportsPanel } from "@/components/inventory/reports-panel";

/**
 * The 7I `/inventory` screen -- Stock (the bulk-stock list, 7G's `/plants`
 * counterpart), Locations (branch-scoped sub-hierarchy), and Reports (the
 * six real reporting routes). Kept as one page with tabs, mirroring 7G's
 * Plant Profile tab layout, rather than three separate routes -- all three
 * views share the same `inventory:read` gate and none needs its own URL
 * for deep-linking in this initial build.
 */
export default function InventoryPage() {
  return (
    <PermissionGate permission="inventory:read" fallback={<PermissionDenied />}>
      <div className="flex flex-col gap-4">
        <h1 className="text-h2 font-semibold text-foreground">Inventory</h1>
        <Tabs defaultValue="stock">
          <TabsList>
            <TabsTrigger value="stock">Stock</TabsTrigger>
            <TabsTrigger value="locations">Locations</TabsTrigger>
            <TabsTrigger value="reports">Reports</TabsTrigger>
          </TabsList>
          <TabsContent value="stock">
            <InventoryList />
          </TabsContent>
          <TabsContent value="locations">
            <LocationsPanel />
          </TabsContent>
          <TabsContent value="reports">
            <ReportsPanel />
          </TabsContent>
        </Tabs>
      </div>
    </PermissionGate>
  );
}
