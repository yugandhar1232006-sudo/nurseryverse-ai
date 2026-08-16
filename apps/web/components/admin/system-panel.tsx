"use client";

import type { ReactNode } from "react";
import { AlertTriangle, Bot, Database, HeartPulse } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PermissionGate } from "@/components/auth/permission-gate";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useAIFailuresQuery,
  useAIModelsQuery,
  useAIUsageQuery,
  useDataRetentionQuery,
  useHealthQuery,
  useKnowledgeBaseStatusQuery,
  useSystemConfigQuery,
} from "@/lib/admin/queries";
import { useSessionStore } from "@/store/session-store";

function StatRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-border py-2 last:border-0">
      <span className="text-body-sm text-muted-foreground">{label}</span>
      <span className="text-body-sm font-medium text-foreground">{value}</span>
    </div>
  );
}

function BoolBadge({ ok }: { ok: boolean }) {
  return (
    <Badge tone={ok ? "success" : "warning"} variant="tone">
      {ok ? "Configured" : "Not configured"}
    </Badge>
  );
}

function HealthTab() {
  const query = useHealthQuery();
  if (query.isLoading) return <Skeleton className="h-64 w-full" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  if (!query.data) return null;
  const h = query.data;
  return (
    <div className="flex flex-col">
      <StatRow label="API" value={h.api} />
      <StatRow label="Database reachable" value={<BoolBadge ok={h.database_reachable} />} />
      <StatRow label="Cache reachable" value={<BoolBadge ok={h.cache_reachable} />} />
      <StatRow label="Cache backend" value={h.cache_backend} />
      <StatRow label="Storage" value={<BoolBadge ok={h.storage_configured} />} />
      <StatRow label="AI (Anthropic)" value={<BoolBadge ok={h.ai_anthropic_configured} />} />
      <StatRow label="AI model artifacts" value={<BoolBadge ok={h.ai_model_artifacts_configured} />} />
      <StatRow label="Email notifications" value={<BoolBadge ok={h.notifications_email_configured} />} />
      <StatRow label="SMS notifications" value={<BoolBadge ok={h.notifications_sms_configured} />} />
      <StatRow label="Push notifications" value={<BoolBadge ok={h.notifications_push_configured} />} />
      <StatRow label="Background processing" value={<BoolBadge ok={h.background_processing_configured} />} />
    </div>
  );
}

function SystemConfigTab() {
  const query = useSystemConfigQuery();
  if (query.isLoading) return <Skeleton className="h-48 w-full" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  const items = query.data ?? [];
  if (items.length === 0) return <EmptyState icon={Database} title="No configuration entries" description="Nothing has been set yet." />;
  return (
    <ul className="flex flex-col gap-2">
      {items.map((c) => (
        <li key={c.id} className="rounded-md border border-border p-3">
          <div className="flex flex-wrap items-center gap-2">
            <code className="text-caption text-foreground">{c.key}</code>
            <Badge tone="neutral" variant="tone">
              {c.category}
            </Badge>
            <Badge tone="neutral" variant="tone">
              {c.value_type}
            </Badge>
          </div>
          <pre className="mt-1 overflow-x-auto rounded-sm bg-muted p-2 text-caption">{JSON.stringify(c.value)}</pre>
          {c.description && <p className="text-caption text-muted-foreground">{c.description}</p>}
        </li>
      ))}
    </ul>
  );
}

function AiAdminTab({ orgId }: { orgId: string | null }) {
  const modelsQuery = useAIModelsQuery();
  const usageQuery = useAIUsageQuery(orgId);
  const failuresQuery = useAIFailuresQuery(orgId);
  const kbQuery = useKnowledgeBaseStatusQuery(orgId);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h3 className="mb-2 text-body-sm font-semibold text-foreground">Model capability status</h3>
        {modelsQuery.isLoading && <Skeleton className="h-16 w-full" />}
        {modelsQuery.isError && (
          <ErrorState error={modelsQuery.error} onRetry={() => modelsQuery.refetch()} retrying={modelsQuery.isFetching} />
        )}
        {modelsQuery.data && (
          <div className="flex flex-wrap gap-2">
            {modelsQuery.data.map((m) => (
              <Badge key={m.capability} tone={m.configured ? "success" : "warning"} variant="tone">
                {m.capability}: {m.configured ? "configured" : "not configured"}
              </Badge>
            ))}
          </div>
        )}
      </div>
      <div>
        <h3 className="mb-2 text-body-sm font-semibold text-foreground">Usage stats</h3>
        {usageQuery.isLoading && <Skeleton className="h-16 w-full" />}
        {usageQuery.isError && <ErrorState error={usageQuery.error} onRetry={() => usageQuery.refetch()} retrying={usageQuery.isFetching} />}
        {usageQuery.data && usageQuery.data.length === 0 && <p className="text-body-sm text-muted-foreground">No AI usage recorded yet.</p>}
        {usageQuery.data && usageQuery.data.length > 0 && (
          <ul className="flex flex-col gap-1">
            {usageQuery.data.map((u) => (
              <li key={u.prediction_type} className="flex justify-between text-body-sm">
                <span>{u.prediction_type}</span>
                <span className="text-muted-foreground">
                  {u.count} runs · avg {u.avg_latency_ms ?? "—"}ms · confidence {u.avg_confidence ?? "—"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <h3 className="mb-2 text-body-sm font-semibold text-foreground">Recent inference failures</h3>
        {failuresQuery.isLoading && <Skeleton className="h-16 w-full" />}
        {failuresQuery.isError && (
          <ErrorState error={failuresQuery.error} onRetry={() => failuresQuery.refetch()} retrying={failuresQuery.isFetching} />
        )}
        {failuresQuery.data && failuresQuery.data.items.length === 0 && (
          <p className="text-body-sm text-muted-foreground">No inference failures recorded.</p>
        )}
        {failuresQuery.data && failuresQuery.data.items.length > 0 && (
          <ul className="flex flex-col gap-1">
            {failuresQuery.data.items.map((f) => (
              <li key={f.id} className="rounded-md border border-border p-2 text-body-sm">
                <span className="font-medium text-foreground">
                  {f.capability} / {f.prediction_type}
                </span>{" "}
                <span className="text-muted-foreground">
                  {f.error_type}: {f.error_message}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <h3 className="mb-2 text-body-sm font-semibold text-foreground">Knowledge base status</h3>
        {kbQuery.isLoading && <Skeleton className="h-16 w-full" />}
        {kbQuery.isError && <ErrorState error={kbQuery.error} onRetry={() => kbQuery.refetch()} retrying={kbQuery.isFetching} />}
        {kbQuery.data && (
          <div className="flex flex-wrap gap-2">
            {kbQuery.data.map((k) => (
              <Badge key={k.source_type} tone="neutral" variant="tone">
                {k.source_type}: {k.count}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function DataRetentionTab({ orgId }: { orgId: string | null }) {
  const query = useDataRetentionQuery(orgId);
  if (query.isLoading) return <Skeleton className="h-32 w-full" />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  if (!query.data) return null;
  const d = query.data;
  return (
    <div className="flex flex-col">
      <StatRow label="Cutoff date" value={new Date(d.cutoff).toLocaleDateString()} />
      <StatRow label="Audit logs older than cutoff" value={d.audit_logs_older_than_cutoff} />
      <StatRow label="AI inference failures older than cutoff" value={d.ai_inference_failures_older_than_cutoff} />
      <StatRow label="AI predictions older than cutoff" value={d.ai_predictions_older_than_cutoff ?? "—"} />
      <p className="mt-2 text-caption text-muted-foreground">{d.note}</p>
    </div>
  );
}

/**
 * System Configuration / System Health / AI Administration / Data
 * Retention -- an entire real Module 13 surface with no corresponding
 * page anywhere in `docs/ux/09-page-inventory.md` (18 of the 31 real
 * admin routes, confirmed absent from the doc). Built from the real
 * schemas directly. Gated `admin:read` -- per the real seeded permission
 * matrix, only an internal `platform_admin` role holds this, so every
 * normal Owner/Org Admin/Branch Manager account in this app will see the
 * fallback below, not a bug -- see docs/frontend/19-administration.md.
 */
export function SystemPanel() {
  const orgId = useSessionStore((state) => state.user?.org_id ?? null);

  return (
    <PermissionGate
      permission="admin:read"
      fallback={
        <Card>
          <CardHeader>
            <CardTitle>System</CardTitle>
            <CardDescription>
              System Health, System Configuration, AI Administration, and Data Retention require a platform administrator account. Your
              role doesn&apos;t include admin:read.
            </CardDescription>
          </CardHeader>
        </Card>
      }
    >
      <Card>
        <CardHeader>
          <CardTitle>System</CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="health">
            <TabsList className="flex-wrap">
              <TabsTrigger value="health">
                <HeartPulse className="size-4" aria-hidden="true" />
                Health
              </TabsTrigger>
              <TabsTrigger value="config">
                <Database className="size-4" aria-hidden="true" />
                Configuration
              </TabsTrigger>
              <TabsTrigger value="ai">
                <Bot className="size-4" aria-hidden="true" />
                AI Administration
              </TabsTrigger>
              <TabsTrigger value="retention">
                <AlertTriangle className="size-4" aria-hidden="true" />
                Data Retention
              </TabsTrigger>
            </TabsList>
            <TabsContent value="health">
              <HealthTab />
            </TabsContent>
            <TabsContent value="config">
              <SystemConfigTab />
            </TabsContent>
            <TabsContent value="ai">
              <AiAdminTab orgId={orgId} />
            </TabsContent>
            <TabsContent value="retention">
              <DataRetentionTab orgId={orgId} />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </PermissionGate>
  );
}
