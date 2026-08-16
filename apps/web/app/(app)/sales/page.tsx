"use client";

import { PermissionDenied } from "@/components/layout/permission-denied";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { QuotationsList } from "@/components/sales/quotations-list";
import { SalesOrdersList } from "@/components/sales/sales-orders-list";
import { SalesList } from "@/components/sales/sales-list";
import { ReturnsList } from "@/components/sales/returns-list";
import { RefundsList } from "@/components/sales/refunds-list";
import { SalesReportsPanel } from "@/components/sales/reports-panel";

/**
 * The 7J `/sales` screen -- Quotations, Orders (Sales Orders), Sales
 * (completed transactions), Returns, Refunds, and Reports, all sharing
 * `sales:read`/`invoices:read` gates. Kept as one page with tabs, same
 * layout decision 7I made for `/inventory`.
 */
export default function SalesPage() {
  return (
    <PermissionGate permission="sales:read" fallback={<PermissionDenied />}>
      <div className="flex flex-col gap-4">
        <h1 className="text-h2 font-semibold text-foreground">Sales</h1>
        <Tabs defaultValue="quotations">
          <TabsList className="flex-wrap">
            <TabsTrigger value="quotations">Quotations</TabsTrigger>
            <TabsTrigger value="orders">Orders</TabsTrigger>
            <TabsTrigger value="sales">Sales</TabsTrigger>
            <TabsTrigger value="returns">Returns</TabsTrigger>
            <TabsTrigger value="refunds">Refunds</TabsTrigger>
            <TabsTrigger value="reports">Reports</TabsTrigger>
          </TabsList>
          <TabsContent value="quotations">
            <QuotationsList />
          </TabsContent>
          <TabsContent value="orders">
            <SalesOrdersList />
          </TabsContent>
          <TabsContent value="sales">
            <SalesList />
          </TabsContent>
          <TabsContent value="returns">
            <ReturnsList />
          </TabsContent>
          <TabsContent value="refunds">
            <RefundsList />
          </TabsContent>
          <TabsContent value="reports">
            <SalesReportsPanel />
          </TabsContent>
        </Tabs>
      </div>
    </PermissionGate>
  );
}
