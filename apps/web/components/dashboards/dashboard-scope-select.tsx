"use client";

import { Layers } from "lucide-react";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import type { BranchResponse } from "@/lib/api/branches";

export const ALL_BRANCHES = "__all__";

/**
 * Distinct from the shell's own `BranchSelector` (components/layout/
 * branch-selector.tsx): that one sets the app-wide "current working
 * branch" a user is operating in day-to-day (Plants/Inventory/Sales list
 * scoping, once 7F/7I/7J land). This control is dashboard-local and adds
 * an explicit "All branches" option the shell selector deliberately does
 * not have, because org-wide rollups (Executive/Nursery dashboards) are
 * a real, first-class view for Owner/Org Admin -- not merely "no branch
 * picked yet." Selecting a specific branch here filters the Plant/
 * Inventory/Sales/Customer/AI/Financial dashboard tabs via their real
 * `?branch_id=` query parameter; it never changes the shell's own
 * working-branch state.
 */
export function DashboardScopeSelect({
  branches,
  value,
  onChange,
  loading,
}: {
  branches: BranchResponse[];
  value: string;
  onChange: (value: string) => void;
  loading?: boolean;
}) {
  if (loading) {
    return <Skeleton className="h-9 w-40" />;
  }

  if (branches.length === 0) {
    return null;
  }

  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger size="sm" aria-label="Dashboard scope" className="w-full tablet:w-48">
        <Layers className="size-4 shrink-0 opacity-70" aria-hidden="true" />
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL_BRANCHES}>All branches</SelectItem>
        {branches.map((b) => (
          <SelectItem key={b.id} value={b.id}>
            {b.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
