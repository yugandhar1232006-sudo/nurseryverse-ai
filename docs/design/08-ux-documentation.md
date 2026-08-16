# UX Documentation

Interaction-level rules that apply across the whole system, referenced by every screen spec rather than restated per page.

## 1. Interaction Patterns

**Click/tap targets:** the entire row of a DataTable/CardGrid item is clickable through to its detail page (not just a "view" link), with row-level actions (edit/delete) isolated to a trailing Dropdown/ContextMenu so the two don't conflict. **Inline editing:** used only for single, low-risk fields in an established record (rare in v1 — most edits go through a form); anything multi-field or consequential opens a Modal or navigates to a dedicated edit view. **Progressive disclosure:** AIExplanationPanel, collapsible FormSections, and TabNav are the system's primary progressive-disclosure mechanisms — the default view of any screen shows the common case; detail is one interaction away, not upfront. **Drag-and-drop:** not used anywhere in v1 (no drag-to-reorder, no drag-to-upload beyond a standard file-drop zone on PhotoUpload) — deliberately avoided as a primary interaction model given the field/touch-heavy usage pattern, where drag gestures are unreliable.

## 2. Keyboard Shortcuts

| Shortcut | Action | Scope |
|---|---|---|
| `/` | Focus global search | Any authenticated page |
| `g` then `d` | Go to Dashboard | Any authenticated page |
| `g` then `p` | Go to Plants | Any authenticated page |
| `g` then `i` | Go to Inventory | Any authenticated page |
| `n` | Open Notification Center | Any authenticated page |
| `a` | Open AI Assistant | Any authenticated page |
| `Esc` | Close active modal/panel | Modal, SlideOverPanel, Dropdown open |
| `Enter` | Submit the focused form | Any form |
| `?` | Show keyboard shortcut reference | Any authenticated page |

Shortcuts are a Desktop/Laptop enhancement only — they are never the *only* way to perform an action (every shortcut has a visible, clickable equivalent), and they're suppressed while focus is inside a text input (except `Esc` and `Enter`) to avoid interfering with typing.

## 3. Accessibility (interaction-level, extending `01-design-system.md` §10)

**Focus order:** follows visual/DOM reading order (top-to-bottom, left-to-right) on every page; modals and panels trap focus and restore it to the trigger element on close (per component specs). **Dynamic content announcements:** Toasts, AI results, notification arrivals, and form-submission outcomes are all announced via `aria-live` regions (`polite` for informational, `assertive` for errors) — a screen-reader user is never left unaware that something happened after an action. **Skip links:** "Skip to main content" is the first focusable element on every authenticated page. **Reduced motion:** `prefers-reduced-motion` disables non-essential animation system-wide (per `01-design-system.md` §9), with essential state confirmation (e.g., "saved") still delivered via a non-motion cue.

## 4. User Feedback

**Every mutating action produces feedback** — no silent successes and no silent failures anywhere in the system (Toast, inline confirmation, or a dedicated success screen per `07-ui-state-documentation.md` §5). **Feedback specificity:** messages name the actual entity/action ("Invoice #1042 voided," not "Success") wherever the context makes that possible, since generic confirmations don't help a user who performed several similar actions in a row (e.g., logging multiple watering events). **Undo where feasible:** low-risk reversible actions (dismissing a recommendation, marking a notification read) offer a brief undo window via the Toast's undo action; high-risk actions use ConfirmationDialog upfront instead of undo-after, since some actions (voiding an invoice, deactivating a branch) have external consequences (emails sent, access revoked) that can't be cleanly undone.

## 5. Confirmation Dialogs

Required before: deactivating a Branch or Employee, voiding a Sale or Invoice, marking a Plant Deceased, deleting a Species or Supplier, dismissing/overriding an AI disease detection result. **Tiering:** standard confirm/cancel for most of the above; typed-confirmation (re-type the entity's name) reserved specifically for Branch deactivation and Org deletion, the two highest-blast-radius actions in the system (per `02-component-library.md`'s ConfirmationDialog variants) — not applied indiscriminately, since over-using typed-confirmation trains users to click through it without reading. Every ConfirmationDialog states the specific consequence in plain language (what becomes inaccessible, what gets reversed, who gets notified), never a generic "Are you sure?"

## 6. Navigation Rules

Restates and extends `docs/ux/04-navigation-architecture.md`: RBAC filters navigation by absence, not disabled state; the AI Assistant and Notification Center are always-available overlays, not sidebar destinations; branch switching re-scopes visible data without a full page reload; breadcrumbs are the primary "go back up a level" mechanism on nested detail pages, supplementing (not replacing) the browser back button, which must also behave correctly (no navigation traps, no swallowed back-button presses).

## 7. Search Behavior

**Global search (Header):** debounced (300ms after last keystroke), searches across Plants, Species, Customers, Inventory, and Invoices simultaneously (per `docs/ux/08-information-architecture.md` §5), results grouped by entity type with the entity icon shown per group, keyboard-navigable (arrow keys + Enter), minimum 2 characters before querying. **Page-level search** (e.g., within Employees, Species, Customers lists): filters the current DataTable/CardGrid in place, does not navigate away; combined with active filters (AND logic, not OR) — searching "ficus" while a branch filter is applied searches only within that branch. **Empty search results:** the filtered-empty state pattern from `07-ui-state-documentation.md` §2, with the literal search query echoed back ("No results for 'ficuss'") so the user can spot a typo.

## 8. Filter Behavior

**Filter bars** persist within a session (not across sessions by default) so navigating away and back to a filtered list doesn't silently reset it. **Multi-select filters** (e.g., status, branch) use AND-across-categories, OR-within-a-category logic (e.g., "Status: Sold OR Deceased" AND "Branch: Main Branch"). **Active filter indication:** a filter-count badge on the filter trigger plus individually removable filter chips above the results, never a filter state that's applied but visually invisible. **Clear all:** always available as a single action once any filter is active.

## 9. Sorting Behavior

Every DataTable column that represents a sortable value (not free text like notes) supports ascending/descending sort via its header, with a visible sort-direction indicator (icon + not-color-alone). Default sort is defined per entity to match its most common use case (e.g., Sales History defaults to most-recent-first, Species List defaults to alphabetical, Disease Reports defaults to most-severe-and-most-recent-first) rather than a single system-wide default like "created date." Only one sort column is active at a time in v1 (no multi-column sort) — kept simple deliberately, since the target users are not power-spreadsheet users by default.

## 10. Pagination Behavior

**Standard lists** (Employees, Species, Customers, Suppliers): offset-based pagination, 25 rows per page default, page-size adjustable (25/50/100). **High-volume lists** (Sales History, Audit Log, Plants at scale): cursor-based pagination (per `docs/ux/08-information-architecture.md`'s SRS-level note on pagination convention) with infinite-scroll-style "load more" on mobile and traditional page controls on desktop/laptop. **State preservation:** pagination position resets when a filter/search/sort changes (returning to page 1 of the new result set) but is preserved on simple navigation-away-and-back within the same filtered view.
