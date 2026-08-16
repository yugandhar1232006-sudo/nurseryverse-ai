"use client";

import { PermissionDenied } from "@/components/layout/permission-denied";
import { PermissionGate } from "@/components/auth/permission-gate";
import { SpeciesPanel } from "@/components/catalog/species-panel";

export default function SpeciesCatalogPage() {
  return (
    <PermissionGate permission="species:read" fallback={<PermissionDenied />}>
      <div className="flex flex-col gap-4">
        <h1 className="text-h2 font-semibold text-foreground">Species catalog</h1>
        <SpeciesPanel />
      </div>
    </PermissionGate>
  );
}
