"use client";

import * as React from "react";
import { useRouter, usePathname } from "next/navigation";

import { useSession } from "@/lib/auth/use-session";
import { Skeleton } from "@/components/ui/skeleton";
import { AppShell } from "@/components/layout/app-shell";

/**
 * The actual, authoritative auth gate -- unlike middleware.ts (which is
 * best-effort defense-in-depth and can't see real session state in
 * bearer mode), this reads the real `useSessionStore` state. Every route
 * under this layout is protected by virtue of being here; there is no
 * separate per-page auth check to remember to add.
 *
 * Phase 7B's minimal header (`AppHeader`, kept in the tree only for its
 * own now-superseded tests) is replaced here by 7C's full `AppShell` --
 * sidebar, top nav, breadcrumbs, mobile nav, notification center, global
 * search. `AppShell` itself owns the email-verification banner
 * (previously rendered inline here) since it needs the same `useSession`
 * read the rest of the shell already makes.
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isResolving, isAuthenticated } = useSession();

  React.useEffect(() => {
    if (!isResolving && !isAuthenticated) {
      const next = encodeURIComponent(pathname);
      router.replace(`/login?next=${next}`);
    }
  }, [isResolving, isAuthenticated, pathname, router]);

  if (isResolving) {
    return (
      <div role="status" aria-busy="true" aria-live="polite" className="flex flex-col gap-4 p-6">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (!isAuthenticated) {
    // Redirect above is in flight (useEffect runs after this render) --
    // render nothing rather than flashing protected content.
    return null;
  }

  return <AppShell>{children}</AppShell>;
}

// Referenced by the effect above only for its type; kept out of the
// component to avoid an unused-import lint warning if status is ever
// trimmed from the destructure during future edits.
void (0 as unknown as ReturnType<typeof useSession>["status"]);
