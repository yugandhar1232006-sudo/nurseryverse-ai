import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * Holds only the *preference* of which branch is "active" for scoping
 * branch-level views (dashboard, plants, inventory, etc. -- most of which
 * land in later phases). This is a UI convenience, never a security
 * decision: a branch id persisted here is validated against the real
 * `GET /branches` response by `lib/shell/use-current-branch.ts` before
 * it's ever used or displayed (a stale id from a previous org, a since-
 * archived branch, or a tampered localStorage value all fail that check
 * and fall back safely) -- see that hook's docstring for the full
 * reasoning. Every branch-scoped request this preference eventually
 * drives still carries its own `branch_id` that the backend independently
 * re-authorizes per request; nothing here is ever trusted as proof of
 * access.
 *
 * Not sensitive data (just an id, not a credential), so -- unlike
 * store/session-store.ts's tokens -- persisting it to localStorage is
 * fine, matching store/ui-store.ts's existing precedent for durable UI
 * preferences.
 */
interface BranchContextState {
  selectedBranchId: string | null;
}

interface BranchContextActions {
  setSelectedBranchId: (branchId: string | null) => void;
}

export const useBranchContextStore = create<BranchContextState & BranchContextActions>()(
  persist(
    (set) => ({
      selectedBranchId: null,
      setSelectedBranchId: (branchId) => set({ selectedBranchId: branchId }),
    }),
    { name: "nurseryverse-branch-context" },
  ),
);
