import {
  BarChart3,
  Bell,
  Droplets,
  LayoutDashboard,
  Leaf,
  Package,
  Settings,
  ShieldCheck,
  ShoppingCart,
  Sparkles,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

/**
 * The single source of truth for primary navigation, per
 * docs/ux/04-navigation-architecture.md's fixed order (§"Primary
 * Navigation"). Every entry's `permission`/`anyOf` is a real, seeded
 * permission code (migrations/versions/0002_seed_system_metadata.py) --
 * never an invented string -- so `lib/navigation/use-nav-items.ts` can
 * filter this against `usePermissions()` with no per-item special-casing.
 *
 * Two real backend gaps intentionally excluded here, not silently
 * papered over (see docs/frontend/07-application-shell.md's Known
 * Limitations):
 *
 * - **Invoices** and **Suppliers** (the UX doc's items 7 and 8) have
 *   seeded permission codes (`invoices:read/write/void`,
 *   `purchase_orders:read/write/receive`) but *no backend route file
 *   exists for either* (`apps/api/app/api/routes/` has no `invoices.py`,
 *   `suppliers.py`, or `purchase_orders.py`) -- confirmed by direct
 *   inspection, not assumed. Adding sidebar entries that point at
 *   endpoints which don't exist would be exactly the "fake" navigation
 *   the 7C kickoff prohibits. These were dropped rather than linked to a
 *   page that could never load real data.
 *
 * Notifications and AI Assistant are deliberately NOT here, per the UX
 * doc: they're persistent header overlays, not sidebar destinations.
 *
 * `Plants` nests `Species Catalog` as a real example of the sidebar's
 * nested-navigation support -- both are real, permissioned, working
 * destinations (`plants:read`, `species:read`), not a demo stub.
 */
export interface NavItem {
  id: string;
  label: string;
  href: string;
  icon: LucideIcon;
  /** Single required permission. Mutually exclusive with `anyOf`. */
  permission?: string;
  /** Visible if the user holds *any* of these. Mutually exclusive with `permission`. */
  anyOf?: readonly string[];
  children?: NavItem[];
}

export const NAV_ITEMS: NavItem[] = [
  {
    id: "dashboard",
    label: "Dashboard",
    href: "/",
    icon: LayoutDashboard,
    // No permission gate -- every authenticated user has a dashboard
    // (org-level for Owner/Admin, branch-level for everyone else, per
    // the UX doc's PG-07/PG-08 split); there is no seeded permission
    // code that means "may see a dashboard at all."
  },
  {
    id: "plants",
    label: "Plants",
    href: "/plants",
    icon: Leaf,
    permission: "plants:read",
    children: [
      { id: "plants-all", label: "All Plants", href: "/plants", icon: Leaf, permission: "plants:read" },
      {
        id: "plants-species",
        label: "Species Catalog",
        href: "/plants/species",
        icon: Leaf,
        permission: "species:read",
      },
    ],
  },
  {
    id: "ai-center",
    label: "AI Center",
    href: "/ai-center",
    icon: Sparkles,
    permission: "ai_predictions:read",
  },
  {
    id: "inventory",
    label: "Inventory",
    href: "/inventory",
    icon: Package,
    permission: "inventory:read",
  },
  {
    id: "sales",
    label: "Sales",
    href: "/sales",
    icon: ShoppingCart,
    permission: "sales:read",
  },
  {
    id: "customers",
    label: "Customers",
    href: "/customers",
    icon: Users,
    permission: "customers:read",
  },
  {
    id: "reports",
    label: "Reports",
    href: "/reports",
    icon: BarChart3,
    permission: "reports:read",
  },
  {
    id: "settings",
    label: "Settings",
    href: "/settings",
    icon: Settings,
    // Every authenticated user manages at least their own notification
    // preferences (`notifications:manage_preferences`, granted to all 6
    // system roles) -- Settings always has *something* real behind it
    // regardless of role, so it isn't gated. The Settings page itself
    // (7E) gates its individual tabs -- Org Profile, Branches, Employees,
    // Roles -- by their own real permissions.
  },
  {
    id: "admin",
    label: "Administration",
    href: "/admin",
    icon: ShieldCheck,
    // 7O -- no page-inventory entry exists for this at all (unlike every
    // other phase's pre-stubbed `ComingSoon` route), so this is a
    // from-scratch nav addition, not a doc-driven one. `employees:read`
    // is what a real Owner/Org Admin/Branch Manager account holds and is
    // enough to see the Users/Roles/Feature Flags tabs there;
    // `admin:read` covers the platform_admin-only System tab for an
    // account that somehow lacks `employees:read`. See
    // `app/(app)/admin/page.tsx` and docs/frontend/19-administration.md.
    anyOf: ["employees:read", "admin:read"],
  },
];

/** A flat lookup used by breadcrumb generation to resolve a path segment back to a label. */
export function flattenNavItems(items: NavItem[] = NAV_ITEMS): NavItem[] {
  return items.flatMap((item) => (item.children ? [item, ...flattenNavItems(item.children)] : [item]));
}

/**
 * Mobile's condensed bottom tab bar, per
 * docs/ux/04-navigation-architecture.md's "Mobile Navigation": "limited to
 * the 4 highest-frequency-for-field-roles destinations: Dashboard, Plants
 * (scan-first), Watering Tasks, Notifications." This is a *different* list
 * from `NAV_ITEMS`, not a filtered subset of it -- Watering Tasks has no
 * standalone entry in the primary desktop sidebar at all (it lives inside
 * the Plant Digital Twin's tabs, per PG-25, a later phase), but the UX
 * spec calls for it explicitly on mobile as a field-workflow shortcut.
 * The real `watering:read` permission (seeded, backing real
 * `apps/api/app/api/routes/plant_records.py` sub-routes) gates it the
 * same as everything else here. Notifications isn't a route at all --
 * `components/layout/mobile-nav.tsx` renders it as a button that opens
 * the notification Sheet in place, matching the header bell's behavior
 * exactly rather than inventing a second notification UI.
 */
export interface MobileTabItem {
  id: string;
  label: string;
  href?: string;
  icon: LucideIcon;
  permission?: string;
  isNotifications?: boolean;
}

export const MOBILE_TAB_ITEMS: MobileTabItem[] = [
  { id: "dashboard", label: "Dashboard", href: "/", icon: LayoutDashboard },
  { id: "plants", label: "Plants", href: "/plants", icon: Leaf, permission: "plants:read" },
  { id: "watering", label: "Watering", href: "/watering", icon: Droplets, permission: "watering:read" },
  { id: "notifications", label: "Alerts", icon: Bell, isNotifications: true, permission: "notifications:read" },
];
