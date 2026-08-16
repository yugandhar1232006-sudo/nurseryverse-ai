"use client";

import * as React from "react";

import { useBranchesQuery } from "@/lib/shell/queries";
import { useBranchContextStore } from "@/store/branch-context-store";
import type { BranchResponse } from "@/lib/api/branches";

/**
 * The authoritative "which branch is currently selected" read, reconciling
 * the persisted preference (`store/branch-context-store.ts`) against the
 * real `GET /branches` response -- never trusting the stored id on its
 * own. A stored id that doesn't appear in the real, backend-returned
 * branch list (stale after switching accounts, a branch that's since been
 * archived, or a directly-edited localStorage value) is treated as if
 * nothing were selected, not as a request for a branch the backend never
 * confirmed exists.
 *
 * Defaults to the first branch once real data loads and nothing valid is
 * selected yet, for orgs with exactly one branch (the common case) --
 * so branch-scoped views never have to handle "no branch selected but
 * there's only one anyway" as a separate empty state.
 */
export function useCurrentBranch(): {
  branch: BranchResponse | null;
  branches: BranchResponse[];
  isLoading: boolean;
  select: (branchId: string) => void;
} {
  const branchesQuery = useBranchesQuery();
  const selectedBranchId = useBranchContextStore((state) => state.selectedBranchId);
  const setSelectedBranchId = useBranchContextStore((state) => state.setSelectedBranchId);

  const branches = React.useMemo(() => branchesQuery.data ?? [], [branchesQuery.data]);

  const validSelected = React.useMemo(
    () => branches.find((b) => b.id === selectedBranchId) ?? null,
    [branches, selectedBranchId],
  );

  React.useEffect(() => {
    if (branchesQuery.isSuccess && !validSelected && branches.length > 0) {
      setSelectedBranchId(branches[0].id);
    }
  }, [branchesQuery.isSuccess, validSelected, branches, setSelectedBranchId]);

  return {
    branch: validSelected ?? (branches.length > 0 ? branches[0] : null),
    branches,
    isLoading: branchesQuery.isLoading,
    select: setSelectedBranchId,
  };
}
