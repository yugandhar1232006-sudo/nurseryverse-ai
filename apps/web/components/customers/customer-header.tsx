"use client";

import * as React from "react";
import { Pencil } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PermissionGate } from "@/components/auth/permission-gate";
import { EditCustomerDialog } from "@/components/customers/edit-customer-dialog";
import { useBranchesQuery } from "@/lib/shell/queries";
import type { CustomerResponse } from "@/lib/api/customers";

/** Customer identity strip -- the 7J counterpart to 7I's `InventoryHeader` / 7G's `PlantHeader`. */
export function CustomerHeader({ customer }: { customer: CustomerResponse }) {
  const branchesQuery = useBranchesQuery();
  const [editOpen, setEditOpen] = React.useState(false);
  const branchName = (branchesQuery.data ?? []).find((b) => b.id === customer.branch_id)?.name ?? "—";

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-h2 font-semibold text-foreground">{customer.name}</h1>
          <p className="text-body-sm text-muted-foreground">Branch: {branchName}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={customer.customer_type === "wholesale" ? "info" : "neutral"} className="capitalize">
            {customer.customer_type}
          </Badge>
          <PermissionGate permission="customers:write">
            <Button type="button" variant="outline" size="sm" onClick={() => setEditOpen(true)}>
              <Pencil className="size-4" aria-hidden="true" />
              Edit
            </Button>
          </PermissionGate>
        </div>
      </div>
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-body-sm text-muted-foreground">
        <span>
          Email: <span className="text-foreground">{customer.email ?? "—"}</span>
        </span>
        <span>
          Phone: <span className="text-foreground">{customer.phone ?? "—"}</span>
        </span>
      </div>

      <EditCustomerDialog open={editOpen} onOpenChange={setEditOpen} customer={customer} />
    </div>
  );
}
