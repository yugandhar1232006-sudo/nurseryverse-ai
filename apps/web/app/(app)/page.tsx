import { DashboardContent } from "@/components/dashboards/dashboard-content";
import { NoReportingAccess } from "@/components/dashboards/no-reporting-access";
import { PermissionGate } from "@/components/auth/permission-gate";

/**
 * The real post-login landing route (`/`), inside `(app)`, protected by
 * `app/(app)/layout.tsx`/`AppShell` like every other page -- see 7C's
 * commit history on this file for why it wasn't always so.
 *
 * No `PermissionGate` wraps this *route* itself -- per `nav-config.ts`'s
 * docstring, every authenticated user has *some* dashboard destination.
 * What actually varies by role is whether `reports:read` is held at all
 * (see docs/ux/07-role-permission-matrix.md: only Owner/Org
 * Admin/Branch Manager hold it; Horticulturist/Sales Staff hold
 * neither) -- that's gated here, one level down, with an honest
 * `NoReportingAccess` fallback rather than a hard "Permission denied"
 * wall on the one route every signed-in user lands on after login.
 */
export default function DashboardPage() {
  return (
    <PermissionGate permission="reports:read" fallback={<NoReportingAccess />}>
      <DashboardContent />
    </PermissionGate>
  );
}
