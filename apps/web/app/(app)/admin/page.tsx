import { AdministrationContent } from "@/components/admin/administration-content";
import { PermissionDenied } from "@/components/layout/permission-denied";
import { PermissionGate } from "@/components/auth/permission-gate";

/**
 * 7O -- gated `anyOf: ["employees:read", "admin:read"]` at the page
 * level: `employees:read` is what every real Owner/Org Admin/Branch
 * Manager account holds and is enough to see the Users/Roles/Feature
 * Flags tabs; `admin:read` covers the (rare, `platform_admin`-only) case
 * of an account that somehow holds System-level access without also
 * holding `employees:read`. Each tab still re-checks its own real
 * permission internally (see the individual panels), this outer gate
 * only keeps someone with neither from landing on an all-empty page.
 */
export default function AdminPage() {
  return (
    <PermissionGate anyOf={["employees:read", "admin:read"]} fallback={<PermissionDenied />}>
      <AdministrationContent />
    </PermissionGate>
  );
}
