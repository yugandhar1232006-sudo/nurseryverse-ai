import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/**
 * StatCard, per docs/ux/10-component-inventory.md ("dashboard summary
 * metric ... used on PG-07, PG-08"). Deliberately generic across every
 * dashboard tab in this phase (revenue, plant counts, alert counts) --
 * a single real-data-driven primitive, not nine bespoke card components.
 *
 * `tone` only ever colors the icon chip -- it does NOT imply the number
 * itself is good/bad (a KPI card never editorializes a real business
 * figure), it's purely a visual grouping cue (e.g. "danger" for at-risk/
 * low-stock counts, "success" for revenue) matching the same tone
 * vocabulary Badge already uses.
 */
export interface KpiCardProps {
  label: string;
  value: string;
  icon: LucideIcon;
  tone?: "neutral" | "success" | "warning" | "danger" | "info";
  hint?: string;
  loading?: boolean;
  className?: string;
}

const TONE_CLASSES: Record<NonNullable<KpiCardProps["tone"]>, string> = {
  neutral: "bg-muted text-muted-foreground",
  success: "bg-success-light text-success-dark",
  warning: "bg-warning-light text-warning-dark",
  danger: "bg-danger-light text-danger-dark",
  info: "bg-info-light text-info-dark",
};

export function KpiCard({ label, value, icon: Icon, tone = "neutral", hint, loading, className }: KpiCardProps) {
  if (loading) {
    return (
      <Card className={className}>
        <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="size-8 rounded-full" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-7 w-20" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
        <CardTitle className="text-body-sm font-medium text-muted-foreground">{label}</CardTitle>
        <div className={cn("flex size-8 shrink-0 items-center justify-center rounded-full", TONE_CLASSES[tone])}>
          <Icon className="size-4" aria-hidden="true" />
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-h2 font-semibold tabular-nums text-foreground">{value}</p>
        {hint && <p className="mt-1 text-caption text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  );
}

export function KpiCardGrid({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("grid grid-cols-1 gap-4 tablet:grid-cols-2 laptop:grid-cols-4", className)}>{children}</div>;
}
