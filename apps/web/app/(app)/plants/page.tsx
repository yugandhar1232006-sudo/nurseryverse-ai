"use client";

import { PermissionDenied } from "@/components/layout/permission-denied";
import { PermissionGate } from "@/components/auth/permission-gate";
import { PlantsList } from "@/components/plants/plants-list";

export default function PlantsPage() {
  return (
    <PermissionGate permission="plants:read" fallback={<PermissionDenied />}>
      <div className="flex flex-col gap-4">
        <h1 className="text-h2 font-semibold text-foreground">Plants</h1>
        <PlantsList />
      </div>
    </PermissionGate>
  );
}
