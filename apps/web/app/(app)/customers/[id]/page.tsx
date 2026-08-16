"use client";

import { useParams } from "next/navigation";

import { ErrorState } from "@/components/error-state";
import { PermissionDenied } from "@/components/layout/permission-denied";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CustomerHeader } from "@/components/customers/customer-header";
import { OverviewTab } from "@/components/customers/tabs/overview-tab";
import { ContactsTab } from "@/components/customers/tabs/contacts-tab";
import { AddressesTab } from "@/components/customers/tabs/addresses-tab";
import { TagsTab } from "@/components/customers/tabs/tags-tab";
import { NotesTab } from "@/components/customers/tabs/notes-tab";
import { CommunicationsTab } from "@/components/customers/tabs/communications-tab";
import { PurchaseHistoryTab } from "@/components/customers/tabs/purchase-history-tab";
import { useCustomerDetailQuery } from "@/lib/customers/queries";

/** The Customer Profile page -- `/customers/[id]`, the 7J counterpart to 7G's `/plants/[id]` and 7I's `/inventory/[id]`. */
export default function CustomerDetailPage() {
  const params = useParams<{ id: string }>();
  const customerId = params.id;

  const customerQuery = useCustomerDetailQuery(customerId);

  return (
    <PermissionGate permission="customers:read" fallback={<PermissionDenied />}>
      <div className="flex flex-col gap-6">
        {customerQuery.isLoading && (
          <div className="flex flex-col gap-4">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
        )}
        {customerQuery.isError && (
          <ErrorState variant="full-page" error={customerQuery.error} onRetry={() => customerQuery.refetch()} retrying={customerQuery.isFetching} />
        )}
        {customerQuery.data && (
          <>
            <CustomerHeader customer={customerQuery.data} />

            <Tabs defaultValue="overview">
              <TabsList className="flex-wrap">
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="purchase-history">Purchase History</TabsTrigger>
                <TabsTrigger value="contacts">Contacts</TabsTrigger>
                <TabsTrigger value="addresses">Addresses</TabsTrigger>
                <TabsTrigger value="tags">Tags</TabsTrigger>
                <TabsTrigger value="notes">Notes</TabsTrigger>
                <TabsTrigger value="communications">Communications</TabsTrigger>
              </TabsList>
              <TabsContent value="overview">
                <OverviewTab customerId={customerId} />
              </TabsContent>
              <TabsContent value="purchase-history">
                <PurchaseHistoryTab customerId={customerId} />
              </TabsContent>
              <TabsContent value="contacts">
                <ContactsTab customerId={customerId} />
              </TabsContent>
              <TabsContent value="addresses">
                <AddressesTab customerId={customerId} />
              </TabsContent>
              <TabsContent value="tags">
                <TagsTab customerId={customerId} />
              </TabsContent>
              <TabsContent value="notes">
                <NotesTab customerId={customerId} />
              </TabsContent>
              <TabsContent value="communications">
                <CommunicationsTab customerId={customerId} />
              </TabsContent>
            </Tabs>
          </>
        )}
      </div>
    </PermissionGate>
  );
}
