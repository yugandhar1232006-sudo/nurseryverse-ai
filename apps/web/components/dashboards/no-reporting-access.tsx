"use client";

import { BarChart3, Building2, Leaf, ShoppingCart, Users } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { usePermissions } from "@/lib/auth/use-permissions";
import { useSessionStore } from "@/store/session-store";

/**
 * What a Horticulturist or Sales Staff user sees on `/` (Dashboard). Per
 * docs/ux/07-role-permission-matrix.md, `reports:read` is granted only
 * to Owner/Org Admin (org-wide) and Branch Manager (their own branch) --
 * Horticulturist and Sales Staff hold neither permission at all, by
 * design, not as a backend gap. The Dashboard nav entry itself is
 * deliberately ungated (nav-config.ts: "every authenticated user has a
 * dashboard"), so this route must still render *something* real for
 * those roles rather than a hard permission-denied wall -- this is that
 * honest landing state: no fabricated widgets standing in for the
 * reporting surface they don't have, just real links to the actual
 * destinations their role does grant.
 */
export function NoReportingAccess() {
  const { can } = usePermissions();
  const orgId = useSessionStore((state) => state.user?.org_id ?? null);

  // A brand-new signup has no org at all (`POST /auth/signup` doesn't
  // create one) -- every permission check is fail-closed empty in that
  // state, so this isn't "wrong role," it's "nothing to have a role in
  // yet." Surface the real fix (Settings -> create an organization, 7E)
  // rather than the generic no-permissions copy below.
  if (orgId === null) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 px-4 py-16 text-center">
        <div className="flex size-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <Building2 className="size-5" aria-hidden="true" />
        </div>
        <div className="flex flex-col gap-1">
          <p className="text-body font-medium text-foreground">Set up your organization</p>
          <p className="max-w-sm text-body-sm text-muted-foreground">
            You&apos;re signed in, but not part of an organization yet. Create one to unlock dashboards, plants,
            inventory, and everything else.
          </p>
        </div>
        <Button asChild size="sm">
          <Link href="/settings">Set up your organization</Link>
        </Button>
      </div>
    );
  }

  const links: { href: string; label: string; icon: typeof Leaf; permission: string }[] = [
    { href: "/plants", label: "Plants", icon: Leaf, permission: "plants:read" },
    { href: "/sales", label: "Sales", icon: ShoppingCart, permission: "sales:read" },
    { href: "/customers", label: "Customers", icon: Users, permission: "customers:read" },
  ];
  const visibleLinks = links.filter((l) => can(l.permission));

  return (
    <div className="flex flex-col items-center justify-center gap-4 px-4 py-16 text-center">
      <div className="flex size-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <BarChart3 className="size-5" aria-hidden="true" />
      </div>
      <div className="flex flex-col gap-1">
        <p className="text-body font-medium text-foreground">Reporting is not part of your role</p>
        <p className="max-w-sm text-body-sm text-muted-foreground">
          Your role does not include dashboard/reporting access. Ask an Owner, Org Admin, or Branch Manager if you need it.
        </p>
      </div>
      {visibleLinks.length > 0 && (
        <div className="flex flex-wrap justify-center gap-2">
          {visibleLinks.map((l) => (
            <Button key={l.href} asChild variant="outline" size="sm">
              <Link href={l.href}>
                <l.icon className="size-4" aria-hidden="true" />
                {l.label}
              </Link>
            </Button>
          ))}
        </div>
      )}
    </div>
  );
}
