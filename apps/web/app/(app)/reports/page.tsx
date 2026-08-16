import { PermissionDenied } from "@/components/layout/permission-denied";
import { PermissionGate } from "@/components/auth/permission-gate";
import { ReportsContent } from "@/components/reports/reports-content";

export default function ReportsPage() {
  return (
    <PermissionGate permission="reports:read" fallback={<PermissionDenied />}>
      <ReportsContent />
    </PermissionGate>
  );
}
