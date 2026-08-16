"use client";

import * as React from "react";
import { Ban, Download, FileClock, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PermissionGate } from "@/components/auth/permission-gate";
import { RecordEntryList } from "@/components/plants/record-entry-list";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { auditLogsExportUrl } from "@/lib/api/admin";
import { useAuditLogsQuery, useAuthorizationDenialsQuery, usePlatformSecurityEventsQuery, useSecurityEventsQuery } from "@/lib/admin/queries";
import type {
  AdminAuditDiff,
  AdminAuditLogEntryResponse,
  AdminSecurityEventMetadata,
  AuthorizationDenialResponse,
  SecurityEventResponse,
} from "@/lib/api/admin";

const RESULT_TONE: Record<string, "success" | "danger" | "neutral"> = { success: "success", failure: "danger", denied: "danger" };

function DiffPreview({ diff }: { diff: unknown }) {
  const typed = diff as AdminAuditDiff | null;
  if (!typed || (!typed.before && !typed.after)) return null;
  return <pre className="mt-1 overflow-x-auto rounded-sm bg-muted p-2 text-caption">{JSON.stringify(typed, null, 2)}</pre>;
}

/**
 * PG-54 Audit Log Viewer + Security Events + Authorization Denials --
 * `audit:read` (Owner/Org Admin only, per the real seeded permission
 * matrix -- Branch Manager does not hold `audit:read`). The real route
 * paths/params (`/admin/audit-logs?actor_user_id=&result=&branch_id=`,
 * `/admin/audit-logs/export?format=`) differ from
 * `docs/ux/09-page-inventory.md`'s PG-54 entry, which omits the
 * `/admin` prefix and uses `actor` instead of the real `actor_user_id` --
 * built against the real route, not the doc (see `lib/api/admin.ts`).
 * The fourth tab, Platform Security Events, is `admin:read`-gated and
 * will show a real permission-denied fallback for every normal tenant
 * account -- see docs/frontend/19-administration.md.
 */
export function AuditSecurityPanel() {
  const [auditPage, setAuditPage] = React.useState(1);
  const [securityPage, setSecurityPage] = React.useState(1);
  const [denialsPage, setDenialsPage] = React.useState(1);
  const [platformPage, setPlatformPage] = React.useState(1);

  const auditQuery = useAuditLogsQuery({ page: auditPage });
  const securityQuery = useSecurityEventsQuery({ page: securityPage });
  const denialsQuery = useAuthorizationDenialsQuery({ page: denialsPage });
  const platformQuery = usePlatformSecurityEventsQuery({ page: platformPage });

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Audit &amp; Security</CardTitle>
        <Button asChild type="button" variant="outline" size="sm">
          <a href={auditLogsExportUrl("csv")}>
            <Download className="size-4" aria-hidden="true" />
            Export audit log (CSV)
          </a>
        </Button>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="audit">
          <TabsList className="flex-wrap">
            <TabsTrigger value="audit">Audit Log</TabsTrigger>
            <TabsTrigger value="security">Security Events</TabsTrigger>
            <TabsTrigger value="denials">Authorization Denials</TabsTrigger>
            <TabsTrigger value="platform">Platform Security Events</TabsTrigger>
          </TabsList>

          <TabsContent value="audit">
            <RecordEntryList<AdminAuditLogEntryResponse>
              icon={FileClock}
              emptyTitle="No audit log entries yet"
              emptyDescription="Real admin/employee actions will appear here as they happen."
              items={auditQuery.data?.items ?? []}
              isLoading={auditQuery.isLoading}
              isError={auditQuery.isError}
              error={auditQuery.error}
              onRetry={() => auditQuery.refetch()}
              retrying={auditQuery.isFetching}
              page={auditPage}
              totalPages={auditQuery.data?.meta.total_pages ?? 1}
              onPageChange={setAuditPage}
              renderItem={(entry) => (
                <div className="flex flex-col gap-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-body-sm font-medium text-foreground">{entry.action}</span>
                    <Badge tone={RESULT_TONE[entry.result] ?? "neutral"} variant="tone">
                      {entry.result}
                    </Badge>
                    <span className="text-caption text-muted-foreground">{entry.entity_type}</span>
                  </div>
                  <p className="text-caption text-muted-foreground">{new Date(entry.created_at).toLocaleString()}</p>
                  <DiffPreview diff={entry.diff} />
                </div>
              )}
            />
          </TabsContent>

          <TabsContent value="security">
            <RecordEntryList<SecurityEventResponse>
              icon={ShieldAlert}
              emptyTitle="No security events yet"
              emptyDescription="Login failures, lockouts, and other real security events appear here."
              items={securityQuery.data?.items ?? []}
              isLoading={securityQuery.isLoading}
              isError={securityQuery.isError}
              error={securityQuery.error}
              onRetry={() => securityQuery.refetch()}
              retrying={securityQuery.isFetching}
              page={securityPage}
              totalPages={securityQuery.data?.meta.total_pages ?? 1}
              onPageChange={setSecurityPage}
              renderItem={(event) => (
                <div className="flex flex-col gap-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-body-sm font-medium text-foreground">{event.event_type}</span>
                    {event.email && <span className="text-caption text-muted-foreground">{event.email}</span>}
                    {event.ip_address && <span className="text-caption text-muted-foreground">{event.ip_address}</span>}
                  </div>
                  <p className="text-caption text-muted-foreground">{new Date(event.created_at).toLocaleString()}</p>
                  {event.event_metadata && (
                    <pre className="mt-1 overflow-x-auto rounded-sm bg-muted p-2 text-caption">
                      {JSON.stringify(event.event_metadata as AdminSecurityEventMetadata, null, 2)}
                    </pre>
                  )}
                </div>
              )}
            />
          </TabsContent>

          <TabsContent value="denials">
            <RecordEntryList<AuthorizationDenialResponse>
              icon={Ban}
              emptyTitle="No authorization denials yet"
              emptyDescription="Real permission-denied attempts (403s) are logged here for review."
              items={denialsQuery.data?.items ?? []}
              isLoading={denialsQuery.isLoading}
              isError={denialsQuery.isError}
              error={denialsQuery.error}
              onRetry={() => denialsQuery.refetch()}
              retrying={denialsQuery.isFetching}
              page={denialsPage}
              totalPages={denialsQuery.data?.meta.total_pages ?? 1}
              onPageChange={setDenialsPage}
              renderItem={(denial) => (
                <div className="flex flex-col gap-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <code className="text-caption text-foreground">{denial.permission_code}</code>
                    <span className="text-caption text-muted-foreground">{denial.reason}</span>
                  </div>
                  <p className="text-body-sm text-foreground">{denial.explanation}</p>
                  <p className="text-caption text-muted-foreground">{new Date(denial.created_at).toLocaleString()}</p>
                </div>
              )}
            />
          </TabsContent>

          <TabsContent value="platform">
            <PermissionGate
              permission="admin:read"
              fallback={
                <p className="text-body-sm text-muted-foreground">
                  Platform-wide security events require a platform administrator account.
                </p>
              }
            >
              <RecordEntryList<SecurityEventResponse>
                icon={ShieldAlert}
                emptyTitle="No platform security events"
                emptyDescription="Cross-organization security events appear here."
                items={platformQuery.data?.items ?? []}
                isLoading={platformQuery.isLoading}
                isError={platformQuery.isError}
                error={platformQuery.error}
                onRetry={() => platformQuery.refetch()}
                retrying={platformQuery.isFetching}
                page={platformPage}
                totalPages={platformQuery.data?.meta.total_pages ?? 1}
                onPageChange={setPlatformPage}
                renderItem={(event) => (
                  <div className="flex flex-col gap-1">
                    <span className="text-body-sm font-medium text-foreground">{event.event_type}</span>
                    <p className="text-caption text-muted-foreground">{new Date(event.created_at).toLocaleString()}</p>
                  </div>
                )}
              />
            </PermissionGate>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
