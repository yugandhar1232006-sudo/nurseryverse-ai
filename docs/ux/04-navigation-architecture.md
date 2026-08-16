# Navigation Architecture

## Primary Navigation (persistent sidebar, desktop / collapsible drawer, mobile)

Grouped exactly as the sitemap's authenticated sections, in this fixed order (matches usage frequency by the majority of roles):

1. **Dashboard** (PG-07 org-level for Owner/Admin roles, PG-08 branch-level for Manager/Staff roles — role determines which lands by default; a branch switcher is always available to Owner/Admin)
2. **Plants** (PG-20 → digital twin drill-down)
3. **AI Center** (PG-31 predictions dashboard, PG-32 forecast, PG-33 recommendations, PG-10 assistant entry point)
4. **Inventory** (PG-36)
5. **Sales** (PG-39 POS, PG-40 history)
6. **Customers** (PG-42)
7. **Invoices** (PG-44)
8. **Suppliers** (PG-47, PG-49)
9. **Reports** (PG-51)
10. **Settings** (PG-55–59, plus Branches PG-11 and Employees PG-14 live under Settings for Owner/Admin)

Notifications (PG-09) and AI Assistant (PG-10) are **not** sidebar items — they are persistent header icons (bell, chat bubble) available from every authenticated screen, opening as a slide-over panel rather than a full page navigation, so context is never lost.

Sidebar items are filtered by RBAC at render time — a Sales Staff user sees only Dashboard, Sales, Customers, and a read-only Plants entry; they never see a disabled/greyed item for a page they can't access (absence, not disabled state, per NFR-6.2's "no confusing dead ends" principle).

## Secondary Navigation

**Branch switcher** — top-of-sidebar dropdown, visible only to users with access to more than one Branch (Owner/Admin always; Manager only if assigned multiple branches). Switching branch re-scopes Dashboard, Plants, Inventory, Sales, and all branch-level lists without a full page reload.

**Tabs within Plant Digital Twin (PG-22)** — Overview, Growth Timeline (PG-23), Health History (PG-24), Environmental & Watering (PG-25), AI Predictions (PG-26). Tabs are client-side routes (deep-linkable) so a link to "this plant's health history" is shareable/bookmarkable.

**Tabs within Settings** — Org Profile, Billing & Plan, Roles & Permissions, Notification Preferences, Integrations — same pattern, deep-linkable.

## Breadcrumbs

Used on all detail pages nested more than one level deep (e.g., `Plants / Ficus Lyrata #FLY-0142 / Health History`). Breadcrumbs are the primary "exit point" back to the parent list, in addition to a browser-standard back action.

## Mobile Navigation

Sidebar collapses to a bottom tab bar on mobile/tablet portrait, limited to the 4 highest-frequency-for-field-roles destinations: **Dashboard, Plants (scan-first), Watering Tasks, Notifications**. Everything else is reachable via a "More" tab that opens the full primary navigation as a slide-over — mobile is optimized for Priya's (Horticulturist) and Devon's (Sales) field/floor workflows first, per the personas' primary-device notes.

A persistent **QR scan** floating action button is present on mobile Dashboard and Plants screens — this is the fastest path into a Plant Digital Twin (PG-22) or POS add-to-cart (PG-39) and is treated as a first-class navigation entry point, not a buried feature.

## Global Search

A single global search (header, all screen sizes) queries across Plants, Species, Customers, Inventory, and Invoices simultaneously, scoped to the user's permitted entities and current Org (and Branch, where the entity is branch-scoped). Results are grouped by entity type.

## Navigation Rules Summary

| Rule | Rationale |
|---|---|
| RBAC filters navigation items, not just page access | Prevents confusing "you don't have permission" dead-ends (NFR-6.2) |
| Notifications and AI Assistant are always-available overlays, never full navigation | These are cross-cutting, used from any context, not a destination in themselves |
| Branch switching re-scopes data without full reload | Owner/Admin frequently compares branches; a reload would break that flow |
| Tabs are deep-linkable routes | Supports sharing/bookmarking specific views (e.g., "check this plant's health tab") |
| Mobile prioritizes field workflows over admin workflows | Matches primary-device usage per persona research |
