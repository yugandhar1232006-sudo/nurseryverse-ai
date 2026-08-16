"use client";

import { Users } from "lucide-react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PermissionGate } from "@/components/auth/permission-gate";
import { ComingSoon } from "@/components/layout/coming-soon";
import { CreateOrganizationForm } from "@/components/organization/create-organization-form";
import { OrgProfileCard } from "@/components/organization/org-profile-card";
import { OrgSettingsCard } from "@/components/organization/org-settings-card";
import { BranchesPanel } from "@/components/organization/branches-panel";
import { EmployeesPanel } from "@/components/organization/employees-panel";
import { NotificationPreferencesPanel } from "@/components/settings/notification-preferences-panel";
import { useSessionStore } from "@/store/session-store";

/**
 * Ungated at the route level, matching `nav-config.ts`'s reasoning:
 * every authenticated user has *something* real here. What that
 * "something" is now genuinely depends on whether they belong to an
 * org yet -- an org-less user (a brand-new signup; `POST /auth/signup`
 * never creates one) sees only the real onboarding form
 * (`CreateOrganizationForm`, `POST /orgs`), since there is nothing else
 * to manage without an org. Once an org exists, the real tabbed
 * settings surface renders: Organization (profile + business settings,
 * `org:read` -- granted R to every role per
 * docs/ux/07-role-permission-matrix.md, so this tab is always visible;
 * editing is gated on `org:write` inside the cards themselves), Branches
 * (`branch:read`, also granted to every role), and Employees
 * (`employees:read`, Owner/Org Admin/Branch Manager only -- gated here,
 * not inside `EmployeesPanel`, since Horticulturist/Sales Staff should
 * never even see a real API call attempted for a permission they don't
 * hold).
 */
export default function SettingsPage() {
  const orgId = useSessionStore((state) => state.user?.org_id ?? null);

  if (orgId === null) {
    return <CreateOrganizationForm />;
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-h2 font-semibold text-foreground">Settings</h1>

      <Tabs defaultValue="organization">
        <TabsList className="flex-wrap">
          <TabsTrigger value="organization">Organization</TabsTrigger>
          <TabsTrigger value="branches">Branches</TabsTrigger>
          <TabsTrigger value="employees">Employees</TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
        </TabsList>

        <TabsContent value="organization" className="flex flex-col gap-4">
          <OrgProfileCard orgId={orgId} />
          <OrgSettingsCard orgId={orgId} />
        </TabsContent>

        <TabsContent value="branches">
          <BranchesPanel />
        </TabsContent>

        <TabsContent value="employees">
          <PermissionGate
            permission="employees:read"
            fallback={
              <ComingSoon
                icon={Users}
                title="Employees"
                description="Your role doesn't include employee management access."
              />
            }
          >
            <EmployeesPanel />
          </PermissionGate>
        </TabsContent>

        <TabsContent value="notifications">
          <NotificationPreferencesPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
