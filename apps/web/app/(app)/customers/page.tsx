"use client";

import { PermissionDenied } from "@/components/layout/permission-denied";
import { PermissionGate } from "@/components/auth/permission-gate";
import { CustomerList } from "@/components/customers/customer-list";

export default function CustomersPage() {
  return (
    <PermissionGate permission="customers:read" fallback={<PermissionDenied />}>
      <div className="flex flex-col gap-4">
        <h1 className="text-h2 font-semibold text-foreground">Customers</h1>
        <CustomerList />
      </div>
    </PermissionGate>
  );
}
