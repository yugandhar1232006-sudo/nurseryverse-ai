"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AuditSecurityPanel } from "@/components/admin/audit-security-panel";
import { FeatureFlagsPanel } from "@/components/admin/feature-flags-panel";
import { NotificationAdminPanel } from "@/components/admin/notification-admin-panel";
import { RolesPermissionsPanel } from "@/components/admin/roles-permissions-panel";
import { SystemPanel } from "@/components/admin/system-panel";
import { UsersAdminPanel } from "@/components/admin/users-admin-panel";

/**
 * 7O -- real `/admin` route content, wiring Module 13's six sections
 * into one tabbed page (mirroring 7N's `ReportsContent` container
 * pattern). Users/Roles/Feature Flags/Audit are usable by any Owner/Org
 * Admin/Branch Manager account holding the relevant real permission;
 * System and parts of Audit's "Platform Security Events" tab are
 * `admin:read`-gated and will show a real, honest permission-denied
 * fallback for every normal tenant account (see each panel's own
 * docstring, and docs/frontend/19-administration.md's Known
 * Limitations) -- not hidden, since a normal account's Users/Roles/Flags
 * tabs are still fully real and useful even though System never will be
 * for them.
 */
export function AdministrationContent() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-h2 font-semibold text-foreground">Administration</h1>

      <Tabs defaultValue="users">
        <TabsList className="flex-wrap">
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="roles">Roles &amp; Permissions</TabsTrigger>
          <TabsTrigger value="flags">Feature Flags</TabsTrigger>
          <TabsTrigger value="audit">Audit &amp; Security</TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
          <TabsTrigger value="system">System</TabsTrigger>
        </TabsList>

        <TabsContent value="users">
          <UsersAdminPanel />
        </TabsContent>
        <TabsContent value="roles">
          <RolesPermissionsPanel />
        </TabsContent>
        <TabsContent value="flags">
          <FeatureFlagsPanel />
        </TabsContent>
        <TabsContent value="audit">
          <AuditSecurityPanel />
        </TabsContent>
        <TabsContent value="notifications">
          <NotificationAdminPanel />
        </TabsContent>
        <TabsContent value="system">
          <SystemPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
