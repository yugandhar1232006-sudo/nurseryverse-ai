"use client";

import { Building } from "lucide-react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useCurrentBranch } from "@/lib/shell/use-current-branch";

/**
 * Branch context switcher, per the 7C kickoff: "Organization and branch
 * selection must use real backend APIs. Never trust a client-selected
 * tenant or branch without backend validation." `useCurrentBranch()`
 * (lib/shell/use-current-branch.ts) is the enforcement point for that --
 * this component only ever displays/selects a branch the real `GET
 * /branches` response actually returned, and the selection itself is UI
 * state only (every branch-scoped request the app makes still carries its
 * own `branch_id` that the backend independently re-authorizes).
 *
 * States:
 *  - Loading: skeleton, same footprint as the trigger so the header
 *    doesn't jump once real data arrives.
 *  - Zero branches (a brand-new org before any branch exists): renders
 *    nothing -- there's genuinely no context to switch, and a disabled
 *    dropdown with no options would be confusing, not helpful.
 *  - Exactly one branch: renders the name as static text, not an
 *    interactive control -- a one-option dropdown is UI noise.
 *  - 2+: a real `Select`.
 */
export function BranchSelector() {
  const { branch, branches, isLoading, select } = useCurrentBranch();

  if (isLoading) {
    return <Skeleton className="h-8 w-32" />;
  }

  if (branches.length === 0) {
    return null;
  }

  if (branches.length === 1) {
    return (
      <span className="flex items-center gap-1.5 px-2 text-body-sm text-muted-foreground">
        <Building className="size-4 shrink-0" aria-hidden="true" />
        {branch?.name}
      </span>
    );
  }

  return (
    <Select value={branch?.id} onValueChange={select}>
      <SelectTrigger size="sm" aria-label="Select branch" className="gap-1.5 border-none bg-transparent shadow-none">
        <Building className="size-4 shrink-0 opacity-70" aria-hidden="true" />
        <SelectValue placeholder="Select branch">{branch?.name}</SelectValue>
      </SelectTrigger>
      <SelectContent>
        {branches.map((b) => (
          <SelectItem key={b.id} value={b.id}>
            {b.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
