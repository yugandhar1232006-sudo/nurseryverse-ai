import { Droplets } from "lucide-react";

import { ComingSoon } from "@/components/layout/coming-soon";
import { PermissionDenied } from "@/components/layout/permission-denied";
import { PermissionGate } from "@/components/auth/permission-gate";

/**
 * Only reachable from the mobile bottom tab bar (`MOBILE_TAB_ITEMS` in
 * nav-config.ts) -- there is deliberately no desktop sidebar entry for
 * this route; on larger screens watering tasks live inside the Plant
 * Digital Twin's tabs instead (a later phase). Still a real, permission-
 * checked route regardless of how a user arrives at it.
 */
export default function WateringPage() {
  return (
    <PermissionGate permission="watering:read" fallback={<PermissionDenied />}>
      <ComingSoon icon={Droplets} title="Watering tasks" description="Field watering task lists ship alongside Plant Lifecycle in Phase 7G." />
    </PermissionGate>
  );
}
