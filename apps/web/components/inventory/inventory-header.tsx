"use client";

import * as React from "react";
import { Archive, ArrowLeftRight, PackagePlus, ShoppingCart } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PermissionGate } from "@/components/auth/permission-gate";
import { ReceiveStockDialog } from "@/components/inventory/receive-stock-dialog";
import { TransferStockDialog } from "@/components/inventory/transfer-stock-dialog";
import { ReserveStockDialog } from "@/components/inventory/reserve-stock-dialog";
import { AdjustStockDialog } from "@/components/inventory/adjust-stock-dialog";
import { MarkDamagedDialog } from "@/components/inventory/mark-damaged-dialog";
import { DisposeStockDialog } from "@/components/inventory/dispose-stock-dialog";
import { SellStockDialog } from "@/components/inventory/sell-stock-dialog";
import { ArchiveInventoryDialog } from "@/components/inventory/archive-inventory-dialog";
import { useBranchesQuery } from "@/lib/shell/queries";
import type { InventoryResponse } from "@/lib/api/inventory";

type ActionDialog = "receive" | "transfer" | "reserve" | "adjust" | "damage" | "dispose" | "sell" | "archive" | null;

/**
 * Inventory Line identity strip + action buttons -- the 7I counterpart to
 * 7G's `PlantHeader`. `inventory:write` gates the normal operational flows
 * (Receive, Transfer, Reserve, Sell); `inventory:adjust` gates the
 * quantity-correcting/write-off actions (Adjust, Mark damaged, Dispose,
 * Archive) -- see lib/api/inventory.ts's docstring.
 */
export function InventoryHeader({ item }: { item: InventoryResponse }) {
  const branchesQuery = useBranchesQuery();
  const [activeDialog, setActiveDialog] = React.useState<ActionDialog>(null);

  const branchName = (branchesQuery.data ?? []).find((b) => b.id === item.branch_id)?.name ?? "—";
  const isArchived = item.archived_at !== null;
  const isLow = item.quantity <= item.low_stock_threshold;

  function close() {
    setActiveDialog(null);
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-h2 font-semibold text-foreground">{item.name}</h1>
          <p className="text-body-sm text-muted-foreground">Branch: {branchName}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {isArchived && <Badge tone="neutral">Archived</Badge>}
          {!isArchived && isLow && <Badge tone="warning">Low stock</Badge>}
        </div>
      </div>

      <div className="flex flex-wrap gap-x-6 gap-y-1 text-body-sm text-muted-foreground">
        <span>
          Available: <span className="text-foreground">{item.available_quantity}</span>
        </span>
        <span>
          On hand: <span className="text-foreground">{item.quantity}</span>
        </span>
        <span>
          Reserved: <span className="text-foreground">{item.reserved_quantity}</span>
        </span>
        <span>
          Damaged: <span className="text-foreground">{item.damaged_quantity}</span>
        </span>
        <span>
          Disposed: <span className="text-foreground">{item.disposed_quantity}</span>
        </span>
        {item.unit_cost != null && (
          <span>
            Unit cost: <span className="text-foreground">${item.unit_cost.toFixed(2)}</span>
          </span>
        )}
        {item.unit_price != null && (
          <span>
            Unit price: <span className="text-foreground">${item.unit_price.toFixed(2)}</span>
          </span>
        )}
      </div>

      {!isArchived && (
        <div className="flex flex-wrap gap-2">
          <PermissionGate permission="inventory:write">
            <Button type="button" variant="outline" size="sm" onClick={() => setActiveDialog("receive")}>
              <PackagePlus className="size-4" aria-hidden="true" />
              Receive
            </Button>
          </PermissionGate>
          <PermissionGate permission="inventory:write">
            <Button type="button" variant="outline" size="sm" onClick={() => setActiveDialog("transfer")}>
              <ArrowLeftRight className="size-4" aria-hidden="true" />
              Transfer
            </Button>
          </PermissionGate>
          <PermissionGate permission="inventory:write">
            <Button type="button" variant="outline" size="sm" onClick={() => setActiveDialog("reserve")}>
              Reserve
            </Button>
          </PermissionGate>
          <PermissionGate permission="inventory:write">
            <Button type="button" variant="outline" size="sm" onClick={() => setActiveDialog("sell")}>
              <ShoppingCart className="size-4" aria-hidden="true" />
              Sell
            </Button>
          </PermissionGate>
          <PermissionGate permission="inventory:adjust">
            <Button type="button" variant="outline" size="sm" onClick={() => setActiveDialog("adjust")}>
              Adjust
            </Button>
          </PermissionGate>
          <PermissionGate permission="inventory:adjust">
            <Button type="button" variant="outline" size="sm" onClick={() => setActiveDialog("damage")}>
              Mark damaged
            </Button>
          </PermissionGate>
          <PermissionGate permission="inventory:adjust">
            <Button type="button" variant="outline" size="sm" onClick={() => setActiveDialog("dispose")}>
              Dispose
            </Button>
          </PermissionGate>
          <PermissionGate permission="inventory:adjust">
            <Button type="button" variant="outline" size="sm" className="text-destructive hover:text-destructive" onClick={() => setActiveDialog("archive")}>
              <Archive className="size-4" aria-hidden="true" />
              Archive
            </Button>
          </PermissionGate>
        </div>
      )}

      <ReceiveStockDialog open={activeDialog === "receive"} onOpenChange={(o) => (o ? setActiveDialog("receive") : close())} lineId={item.id} branchId={item.branch_id} />
      <TransferStockDialog open={activeDialog === "transfer"} onOpenChange={(o) => (o ? setActiveDialog("transfer") : close())} lineId={item.id} currentBranchId={item.branch_id} />
      <ReserveStockDialog open={activeDialog === "reserve"} onOpenChange={(o) => (o ? setActiveDialog("reserve") : close())} lineId={item.id} />
      <AdjustStockDialog open={activeDialog === "adjust"} onOpenChange={(o) => (o ? setActiveDialog("adjust") : close())} lineId={item.id} />
      <MarkDamagedDialog open={activeDialog === "damage"} onOpenChange={(o) => (o ? setActiveDialog("damage") : close())} lineId={item.id} />
      <DisposeStockDialog open={activeDialog === "dispose"} onOpenChange={(o) => (o ? setActiveDialog("dispose") : close())} lineId={item.id} />
      <SellStockDialog open={activeDialog === "sell"} onOpenChange={(o) => (o ? setActiveDialog("sell") : close())} lineId={item.id} />
      <ArchiveInventoryDialog open={activeDialog === "archive"} onOpenChange={(o) => (o ? setActiveDialog("archive") : close())} lineId={item.id} lineName={item.name} />
    </div>
  );
}
