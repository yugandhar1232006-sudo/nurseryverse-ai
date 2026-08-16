import { Lock } from "lucide-react";

import { EmptyState } from "@/components/empty-state";

/**
 * Shown when a signed-in user navigates directly (by URL) to a route
 * their role doesn't hold the permission for -- the sidebar already
 * hides the link (per `use-nav-items.ts`'s "hidden, not disabled" rule),
 * but "hidden" is only a UX nicety, not a barrier: someone can still type
 * the URL, follow a stale bookmark, or a teammate can paste a link.
 *
 * This is the 7C kickoff's "Permission-denied" UI state, so a mistyped
 * or no-longer-authorized URL never renders a misleading blank page or
 * -- worse -- the "coming soon" placeholder a genuinely permitted user
 * would see, which would incorrectly imply the feature is just not built
 * yet rather than that this account can't use it.
 */
export function PermissionDenied() {
  return (
    <EmptyState
      icon={Lock}
      title="You don't have access to this page"
      description="If you think this is a mistake, ask your organization's admin to check your role and permissions."
    />
  );
}
