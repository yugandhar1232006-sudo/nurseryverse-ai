# Responsive Design Specifications

Breakpoints per `01-design-system.md` §8: Mobile (<640px), Tablet (640–1023px), Laptop (1024–1439px), Desktop (≥1440px). This document defines layout behavior at each breakpoint for every recurring layout pattern — individual screens reference these patterns in `03-screen-specifications.md` rather than repeating layout rules per page.

## 1. App Shell

| Element | Desktop | Laptop | Tablet | Mobile |
|---|---|---|---|---|
| Sidebar | Persistent, expanded (icon+label) | Persistent, expanded | Collapsible drawer (icon-only default, tap to expand) | Replaced by BottomTabBar |
| Header | Full (search bar expanded, all icons) | Full | Full, search collapses to icon-triggered overlay | Condensed (logo, notification, assistant, avatar; search behind an icon) |
| Content max-width | Capped at ~1600px, centered | Fluid | Fluid | Fluid, full-bleed with safe-area padding |
| Content padding | 32px | 24px | 16px | 12px |

## 2. Grid & Card Layouts

| Pattern | Desktop | Laptop | Tablet | Mobile |
|---|---|---|---|---|
| StatCard row (dashboards) | 4–6 cards per row | 3–4 per row | 2 per row | 1 per row (stacked) |
| CardGrid (Plants List) | 4 columns | 3 columns | 2 columns | 1 column |
| Report-type CardGrid (PG-51) | 3 columns | 3 columns | 2 columns | 1 column |
| Form two-column layout (e.g., PG-12 profile fields) | 2 columns | 2 columns | 1 column | 1 column |

## 3. DataTable → Stacked Cards

The single most important responsive transformation in the system, applying to every DataTable instance (Employees, Species, Plants list-view, Disease Reports, Inventory, Sales History, Invoices, Suppliers, Purchase Orders, Audit Log): at Desktop/Laptop/Tablet, tables render as conventional rows/columns with horizontal scroll only as a last resort for very wide tables (e.g., Audit Log's Data Grid variant). Below Tablet (Mobile), every DataTable transforms into a **stacked card list** — each row becomes a card with labeled key-value pairs (column label: value), preserving the primary identifying column as the card's title and the status/badge column as a prominent top-right element. This is a deliberate choice over horizontal scroll or column-hiding, because Priya's and Devon's primary devices are mobile/tablet (per personas) and horizontal scroll on a data table is a poor field-use experience.

## 4. Plant Digital Twin (PG-22) — the most complex screen

| Element | Desktop/Laptop | Tablet | Mobile |
|---|---|---|---|
| Header (identity, QR, PhotoGallery) | Side-by-side: photo gallery left, identity/status/actions right | Stacked: photo gallery above identity block | Stacked, condensed — QR code accessible via a tap-to-expand rather than always-visible thumbnail |
| Quick-action buttons | Full row, all labeled | Full row, labeled | Icon-only row (labels in tooltip/long-press), horizontally scrollable if needed |
| TabNav | Horizontal, all tabs visible | Horizontal, all tabs visible | Horizontal, scrollable with fade-edge (per component spec) |
| Tab content charts | Full-width, detailed axis labels | Full-width, slightly simplified | Full-width, simplified axis labels, legend below chart |

## 5. POS / New Sale (PG-39)

| Element | Desktop/Laptop | Tablet | Mobile |
|---|---|---|---|
| Layout | Two-column: item search/scan (left, ~60%) + POSCart (right, persistent, ~40%) | Two-column, narrower cart column | Single column, stacked: scan/search area on top, POSCart below as a collapsible drawer that expands on "View Cart" |
| QRScanner | Embedded panel or connected hardware scanner input | Embedded camera panel | Full-screen camera capture on tap |

## 6. Forms

| Pattern | Desktop/Laptop | Tablet | Mobile |
|---|---|---|---|
| Multi-step forms (PG-02 signup) | Centered card, ~600px wide | Centered card, ~90% width | Full-width, full-screen per step |
| Standard create/edit forms | Modal, centered, ~560–720px wide | Modal, ~90% width | Full-screen takeover (per Modal component's mobile behavior) |
| FormActions | Inline, right-aligned within the form/modal | Inline | Sticky bottom bar |

## 7. Charts

| Element | Desktop/Laptop | Tablet | Mobile |
|---|---|---|---|
| Axis tick density | Full detail | Full detail | Reduced (fewer labeled ticks, per component spec) |
| Legend position | Beside chart | Beside or below, depending on width | Below chart |
| Multi-series overlays (e.g., actual vs. forecast) | All series visible with toggle | All series visible with toggle | Default to primary series only, others toggle-in via a compact legend to avoid clutter |

## 8. AI Assistant & Notification Panels

| Element | Desktop/Laptop | Tablet | Mobile |
|---|---|---|---|
| AssistantChatPanel | Right-anchored SlideOverPanel, ~420px | Right-anchored SlideOverPanel, ~380px | Full-screen takeover |
| NotificationCenter | Right-anchored SlideOverPanel | Right-anchored SlideOverPanel | Full-screen takeover |

## 9. Navigation Priority by Breakpoint

Per `docs/ux/04-navigation-architecture.md`, mobile's BottomTabBar surfaces only Dashboard, Plants (scan-first), Watering Tasks, and Notifications — the four highest-frequency field workflows (Priya, Devon personas). Everything else lives behind "More." Desktop/Laptop/Tablet retain the full Sidebar with every module visible (subject to RBAC filtering), since Owner/Manager/office workflows benefit from full navigational breadth rather than a curated subset.

## 10. Touch Target & Input Considerations (Tablet/Mobile)

All interactive elements meet the 44×44px minimum touch target regardless of visual size (per `01-design-system.md` §10). Hover-dependent interactions (tooltips, hover-reveal row actions in DataTable) always have a tap/long-press equivalent below Laptop breakpoint — nothing is hover-only reachable on touch devices. Camera-first components (PhotoUpload, QRScanner) default to the device camera on Tablet/Mobile and to file-picker on Desktop/Laptop, per their component specs.

## 11. Print Layouts (cross-cutting, not a screen breakpoint but a rendering mode)

ReceiptPreview, InvoicePreview, and PassportPreview each have a dedicated print stylesheet consideration (flagged for Phase 7 implementation): full-bleed removal of app chrome (no header/sidebar), black-and-white-safe contrast (no reliance on color alone, consistent with `02-component-library.md`'s PassportPreview accessibility note), and fixed page-break rules so line items don't split awkwardly across pages on multi-page invoices.
