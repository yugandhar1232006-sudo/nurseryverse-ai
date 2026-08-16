# Component Library

Every component from `docs/ux/10-component-inventory.md`, fully specified. This is the design contract Phase 7 (Frontend) implements against — no visual/behavioral decision is left for implementation time to invent. Built on shadcn/ui (Radix primitives) per the stack decision; "Properties" below are the design-level API (not final TypeScript prop names, which Phase 7 owns).

---

## Layout & Shell

### AppShell
- **Purpose:** Root authenticated layout — sidebar + header + content region.
- **Variants:** Desktop (persistent sidebar), Tablet (collapsible sidebar), Mobile (bottom tab bar, no sidebar).
- **States:** Sidebar expanded/collapsed, loading (initial auth check).
- **Properties:** current user/role, active branch, nav items (role-filtered).
- **Accessibility:** Landmark roles (`nav`, `main`, `banner`); skip-to-content link as the first focusable element.
- **Responsive:** Sidebar → drawer at tablet; → bottom tab bar at mobile (per `04-navigation-architecture.md`).

### Sidebar / PrimaryNav
- **Purpose:** Primary navigation, RBAC-filtered.
- **Variants:** Expanded (icon + label), collapsed (icon only, tooltip on hover).
- **States:** Item active/inactive/hover/focus; collapsed/expanded.
- **Properties:** nav item list, active route, collapse toggle state.
- **Accessibility:** `nav` landmark, current page indicated via `aria-current="page"`, full keyboard arrow-key navigation between items.
- **Responsive:** Hidden entirely below tablet breakpoint (replaced by BottomTabBar + slide-over "More").

### Header
- **Purpose:** Global search, branch switcher, notifications, AI assistant, user menu.
- **Variants:** None (single persistent layout).
- **States:** Search focused/unfocused, notification badge present/absent.
- **Properties:** unread notification count, current branch, user profile summary.
- **Accessibility:** Search is a labeled combobox with keyboard-navigable results; notification/assistant icons have accessible names including unread count ("Notifications, 3 unread").
- **Responsive:** Search collapses to an icon-triggered overlay below tablet; branch switcher moves into the "More" drawer on mobile.

### BranchSwitcher
- **Purpose:** Switch active branch context (multi-branch users only).
- **Variants:** Dropdown (desktop/tablet), full-screen selector (mobile).
- **States:** Single branch (component not rendered), multiple branches (dropdown), switching (brief loading state while data re-scopes).
- **Properties:** branch list, current branch, org-wide "All Branches" option (Owner/Admin only).
- **Accessibility:** Native `select`-equivalent semantics (Radix Select), keyboard operable, announces the new branch on change.
- **Responsive:** Dropdown → full-screen modal picker on mobile for larger touch targets.

### BottomTabBar
- **Purpose:** Mobile primary navigation.
- **Variants:** N/A (mobile-only, single layout).
- **States:** Active tab indicator, notification badge on relevant tab.
- **Properties:** 4 fixed destinations + "More."
- **Accessibility:** `tablist`/`tab` roles, minimum 44×44px touch targets.
- **Responsive:** Only rendered below tablet breakpoint.

### Breadcrumbs
- **Purpose:** Hierarchical wayfinding on nested detail pages.
- **Variants:** Standard (text links), truncated (long hierarchies collapse the middle with an ellipsis menu).
- **States:** Default, hover/focus per crumb.
- **Properties:** crumb list (label + route).
- **Accessibility:** `nav aria-label="Breadcrumb"`, ordered list markup, current page not a link.
- **Responsive:** Truncates more aggressively on mobile (first + last crumb only, others in an overflow menu).

### TabNav
- **Purpose:** Sub-navigation within a detail page (Plant Twin tabs, Settings tabs).
- **Variants:** Underline style (default), pill style (used within cards/panels where underline would clash with a card border).
- **States:** Active/inactive/hover/focus/disabled (permission-gated tab).
- **Properties:** tab list, active tab, deep-linkable route per tab.
- **Accessibility:** `tablist`/`tab`/`tabpanel` roles, arrow-key navigation, each panel labeled by its tab.
- **Responsive:** Horizontally scrollable with a fade-edge affordance on mobile rather than wrapping.

### PageHeader
- **Purpose:** Page title, primary action, contextual filter slot.
- **Variants:** Standard (title + action), with-tabs (title + TabNav below), with-filters (title + filter bar).
- **States:** N/A (structural component).
- **Properties:** title, primary action button, optional secondary actions (overflow menu).
- **Accessibility:** Title rendered as the page's `h1`.
- **Responsive:** Primary action collapses to icon-only on mobile if space-constrained; secondary actions always in overflow menu on mobile.

---

## Data Display

### DataTable (incl. Data Grid variant)
- **Purpose:** Sortable/filterable tabular data — the default list view for most entities.
- **Variants:** Standard (client/server-paginated), Data Grid (virtualized for very large datasets — e.g., Audit Log, high-volume Sales History), status-badged rows, selectable rows (bulk actions).
- **States:** Loading (skeleton rows), empty, error, populated, row hover/selected.
- **Properties:** columns (label, sort key, width, alignment), rows, sort state, pagination state, row-click action, bulk-selection state.
- **Accessibility:** Semantic `table` markup, sortable headers announce sort direction, keyboard-navigable row selection.
- **Responsive:** Below tablet, transforms into a stacked card-per-row layout (each row's columns become labeled key-value pairs) rather than horizontal scroll, per the mobile-first field-use priority.

### CardGrid
- **Purpose:** Photo-forward browsing (Plants List).
- **Variants:** Compact (dense, list-adjacent), comfortable (larger photo, default).
- **States:** Loading (skeleton cards), empty, populated.
- **Properties:** card data (image, title, status badge, key metadata), grid column count per breakpoint.
- **Accessibility:** Each card is a single focusable unit (not multiple nested interactive elements) linking to the detail page.
- **Responsive:** 4 columns desktop → 3 laptop → 2 tablet → 1 mobile.

### StatCard
- **Purpose:** Dashboard summary metric.
- **Variants:** Simple (number + label), trend (number + sparkline + delta), alert (number + severity color, e.g., "3 at-risk plants").
- **States:** Loading (skeleton), populated, zero-state (0 is a valid, non-error value — rendered plainly, not as an empty state).
- **Properties:** label, value, trend delta, icon, severity level, click-through destination.
- **Accessibility:** Value and label read together as one accessible unit; trend direction has a text equivalent ("up 12%"), not just an arrow icon.
- **Responsive:** Grid reflows per §6 Grid System column-span rules per breakpoint.

### StatusBadge
- **Purpose:** Compact status indicator (plant status, invoice status, PO status, disease report status).
- **Variants:** One per status vocabulary (plant lifecycle, invoice lifecycle, disease report lifecycle, PO lifecycle) — each a fixed color+icon+label mapping, not freely styled per use.
- **States:** N/A (static display component).
- **Properties:** status value (enum-constrained per entity type).
- **Accessibility:** Icon + text label always together (never icon-only); sufficient contrast per §10.
- **Responsive:** Label may abbreviate on narrow table columns (icon + tooltip-on-tap for full label) but never drops to icon-only on primary detail views.

### HealthRiskBadge
- **Purpose:** AI survival-risk indicator specifically (distinct from StatusBadge's factual statuses — this one represents a prediction).
- **Variants:** 5-step health-status scale (excellent → critical), each with confidence-level sub-indicator.
- **States:** Loading (prediction pending), stale (prediction older than a freshness threshold — visually flagged), current.
- **Properties:** risk level, confidence score, last-updated timestamp.
- **Accessibility:** Announces as "AI-predicted [level] risk, [confidence]% confidence" — never presented as unqualified fact.
- **Responsive:** Full badge (level + confidence) on desktop/tablet; level-only with confidence in a tap-tooltip on mobile.

### Timeline
- **Purpose:** Chronological event history (Growth, Health, Watering, Audit Log detail).
- **Variants:** Compact (dashboard preview, last N events), full (dedicated tab view with filtering).
- **States:** Loading, empty, populated, load-more/paginated.
- **Properties:** event list (timestamp, actor, type, summary, optional photo/attachment).
- **Accessibility:** Semantic ordered list; timestamps in both relative ("2 days ago") and absolute (on hover/focus) form.
- **Responsive:** Vertical single-column on all breakpoints (no horizontal timeline variant — avoids a common mobile-unfriendly pattern).

### PhotoGallery
- **Purpose:** Plant image history display.
- **Variants:** Grid (thumbnail overview), lightbox (full-size viewer on selection).
- **States:** Loading, empty (prompts first photo upload), populated.
- **Properties:** image list (URL, captured date, linked event e.g. "from this growth entry").
- **Accessibility:** All images require alt text (auto-generated default: "[Plant name] photo, [date]," editable); lightbox is keyboard-navigable (arrow keys, Esc to close) and traps focus while open.
- **Responsive:** Grid column count reflows per breakpoint; lightbox is full-screen on mobile.

### EmptyState
- **Purpose:** No-data guidance with a clear next action.
- **Variants:** First-use (org/branch has no data yet — onboarding-flavored), filtered-empty (results filtered to nothing — offers "clear filters" not a creation CTA), error-adjacent (data failed to load — see ErrorState instead for true errors).
- **States:** N/A (static per variant).
- **Properties:** illustration/icon, headline, supporting text, primary action.
- **Accessibility:** Headline is a proper heading level for its context; action button is a real button/link, not a styled div.
- **Responsive:** Illustration scales down or is omitted on mobile to preserve vertical space; text/action always present.

---

## Charts

### LineChart / AreaChart / BarChart
- **Purpose:** Time-series and comparative data visualization (growth curves, revenue, sales comparisons).
- **Variants:** Single-series, multi-series (actual vs. AI-predicted overlay), stacked (BarChart only, e.g., sales by category).
- **States:** Loading (skeleton chart shape), empty (no data in range), populated, hover (tooltip with exact values).
- **Properties:** data series, axis labels/ranges, legend, confidence-interval band (AreaChart, forecast use).
- **Accessibility:** Underlying data is also available as a table (visually hidden or in a "view as table" toggle) — charts alone are not an accessible data presentation for screen-reader users; color-coded series also differ by line style/pattern, not hue alone.
- **Responsive:** Simplifies axis labeling density on mobile (fewer tick labels), legend moves below the chart rather than beside it.

### SparklineChart
- **Purpose:** Compact inline trend indicator (inside StatCard).
- **Variants:** Line, bar (mini).
- **States:** Loading, populated.
- **Properties:** data points, trend direction color.
- **Accessibility:** Decorative if the StatCard's text delta already conveys the trend (in which case `aria-hidden`); otherwise carries its own accessible summary.
- **Responsive:** Fixed small size regardless of breakpoint (it's already compact by design).

### ConfidenceIndicator
- **Purpose:** Visual representation of AI prediction confidence — reused across every AI output.
- **Variants:** Bar (proportional fill), qualitative label (High/Medium/Low bucketed from the numeric score, used where space is tight).
- **States:** N/A (static per value).
- **Properties:** confidence score (0–100).
- **Accessibility:** Numeric percentage always available (not just a visual fill), announced alongside the prediction it belongs to.
- **Responsive:** Bar variant on desktop/tablet; qualitative label variant preferred on mobile/dense contexts.

---

## Forms & Inputs

### Button
- **Purpose:** Primary interactive trigger.
- **Variants:** Primary (brand-filled, one per screen/section max), secondary (outlined), ghost (text-only, low-emphasis), destructive (danger-colored, paired with ConfirmationDialog for anything non-trivial), icon-only (with mandatory `aria-label`).
- **States:** Default, hover, focus-visible, active/pressed, disabled, loading (inline spinner replaces label, width preserved to avoid layout shift).
- **Properties:** label, icon (leading/trailing), size (sm/md/lg), variant, disabled/loading flags.
- **Accessibility:** Real `button` element; loading state announces via `aria-busy`; disabled buttons still have a tooltip explaining why where the reason isn't obvious (not just inert).
- **Responsive:** Minimum 44×44px touch target on mobile/tablet regardless of visual size.

### TextField / TextArea / NumberField / SelectField / MultiSelectField / DateField / DateRangeField
- **Purpose:** Base form input primitives.
- **Variants:** With/without leading icon, with/without inline validation message, DateField includes a calendar-popover date picker variant.
- **States:** Default, focus, filled, disabled, read-only, error (with message), success (subtle, used sparingly — e.g., "username available").
- **Properties:** label (always visible, never placeholder-only), placeholder (supplementary only), helper text, error message, required flag.
- **Accessibility:** Label programmatically associated via `for`/`id`; error messages linked via `aria-describedby` and announced on appearance; DateField's calendar popover is fully keyboard-operable (arrow keys to navigate days).
- **Responsive:** Full-width on mobile; fixed/percentage width per form layout on larger breakpoints; DateRangeField collapses to two stacked DateFields on mobile instead of a side-by-side dual calendar.

### SpeciesSelector / BranchSelector / EmployeeSelector / CustomerSelector / SupplierSelector
- **Purpose:** Typeahead search-and-select for common entity references.
- **Variants:** Single-select, with inline "create new" affordance (SpeciesSelector, CustomerSelector only — others reference existing records only).
- **States:** Default, typing/loading results, results found, no results (with create-new prompt where applicable), selected.
- **Properties:** search query, result list, selected value, create-new handler.
- **Accessibility:** Combobox pattern (`role="combobox"`, `aria-expanded`, `aria-activedescendant`), results announced as they load.
- **Responsive:** Full-screen search overlay on mobile rather than an inline dropdown, for a better touch-typing experience.

### PhotoUpload / CameraCapture
- **Purpose:** Photo capture/upload — the highest-priority input component given how much of the AI value chain depends on it.
- **Variants:** Camera-first (mobile, opens device camera directly), file-picker (desktop fallback), multi-photo (growth/health logs), single-photo-required (disease scan).
- **States:** Empty (prompt), capturing, uploading (progress bar), uploaded (thumbnail + retake/remove), error (upload failed, retry).
- **Properties:** max file size/count, accepted types, upload progress.
- **Accessibility:** Upload progress announced via `aria-live`; retake/remove actions are clearly labeled buttons, not icon-only without labels.
- **Responsive:** Camera-first behavior only on mobile/tablet (devices with a camera); desktop always shows file-picker.

### QuantityStepper
- **Purpose:** Numeric quantity input with increment/decrement (inventory adjustment, sale line items).
- **Variants:** Standard, with min/max bounds shown.
- **States:** Default, at-minimum (decrement disabled), at-maximum (increment disabled), invalid manual entry.
- **Properties:** value, min, max, step.
- **Accessibility:** Buttons have accessible names ("Increase quantity," "Decrease quantity"); current value announced on change.
- **Responsive:** Larger touch targets for +/- buttons on mobile.

### FormSection / FormActions
- **Purpose:** Layout wrappers for multi-section forms.
- **Variants:** FormSection with/without collapsible behavior (long forms like PG-02 signup); FormActions sticky-footer (long forms) vs. inline (short forms).
- **States:** Section expanded/collapsed.
- **Properties:** section title/description, action buttons (primary/cancel).
- **Accessibility:** Collapsible sections use `aria-expanded` on their toggle; FormActions' primary button is the form's natural submit target (Enter key works from any field).
- **Responsive:** FormActions becomes a sticky bottom bar on mobile for long forms so actions remain reachable without scrolling to the bottom.

### ConfirmationDialog
- **Purpose:** Required gate before destructive/hard-to-reverse actions (NFR-6.3).
- **Variants:** Standard confirm/cancel, typed-confirmation (for the highest-stakes actions — e.g., deactivating a branch requires typing the branch name).
- **States:** Default, submitting (button loading state, dialog cannot be dismissed mid-submit).
- **Properties:** title, consequence description (explicit about what will happen, not vague), confirm/cancel labels (action-specific, e.g., "Void Invoice" not generic "OK").
- **Accessibility:** Focus trapped within the dialog, focus returns to the triggering element on close, `role="alertdialog"` for destructive variants.
- **Responsive:** Full-width bottom sheet on mobile rather than a centered modal, for easier thumb reach.

---

## AI-Specific Components

### AIResultCard
- **Purpose:** The canonical display for any AI output (disease detection, growth, survival, water, revenue).
- **Variants:** Compact (inline in a list), full (dedicated result view, e.g., post-scan).
- **States:** Generating (AI "thinking" motion per §9 of the design system), result-ready, stale (superseded by a newer prediction), error (inference failed — see ErrorState, module-specific messaging).
- **Properties:** prediction summary, ConfidenceIndicator, model version, generated timestamp, "why" expand trigger (opens AIExplanationPanel).
- **Accessibility:** Clearly announced as AI-generated content (not conflated with human-entered data), per the AI-accent color rule in §1.
- **Responsive:** Full variant on desktop/tablet; compact-only on mobile with a tap-through to full detail.

### AIExplanationPanel
- **Purpose:** Expandable "why" behind a prediction — contributing factors, not just a score.
- **Variants:** Inline expand (within AIResultCard), standalone panel (PG-31 at-risk list detail).
- **States:** Collapsed, expanded, loading (if explanation is generated asynchronously from the score).
- **Properties:** factor list (each with a weight/contribution indicator), plain-language summary.
- **Accessibility:** Expand/collapse via `aria-expanded` button; content is real DOM (not display:none-only) so it's still in the accessibility tree once expanded.
- **Responsive:** Full detail at all breakpoints (this is not a component that gets simplified on mobile — the explanation is the point).

### RecommendationCard
- **Purpose:** Actionable AI suggestion (PG-33 feed).
- **Variants:** Standard, high-priority (visually elevated).
- **States:** New, dismissed (removed from feed, undo-able briefly via toast), acted-upon (marked complete).
- **Properties:** recommendation text, explanation, priority level, primary action (deep-link), dismiss control.
- **Accessibility:** Dismiss action confirms via a brief undo toast rather than an irreversible silent removal.
- **Responsive:** Card list stacks single-column at all breakpoints below desktop.

### AIScanCapture
- **Purpose:** Disease-detection-specific capture flow — PhotoUpload wired directly to inference with inline result.
- **Variants:** N/A (single specialized flow).
- **States:** Capture, uploading, analyzing (AI thinking motion, target ≤5s per NFR-1.2), result (AIResultCard), error/retry.
- **Properties:** inherits PhotoUpload properties; plus inference status.
- **Accessibility:** Analyzing state announced via `aria-live="polite"` so screen-reader users know a result is coming, not just watching a silent spinner.
- **Responsive:** Full-screen camera-first flow on mobile (this is the primary Priya-persona use case).

### AssistantChatPanel
- **Purpose:** Conversational AI Assistant interface.
- **Variants:** Slide-over (desktop/tablet), full-screen (mobile).
- **States:** Closed, open-empty (suggested prompts shown), conversing, assistant-typing, error (message failed to send, retry).
- **Properties:** message thread, composer input, suggested prompts (context-aware, e.g. different defaults on a Plant Twin page vs. Dashboard).
- **Accessibility:** New messages announced via `aria-live="polite"`; composer is reachable and usable via keyboard alone; conversation history is screen-reader navigable as a list, not a single opaque block.
- **Responsive:** Slide-over panel (desktop/tablet, ~400px wide) → full-screen takeover (mobile).

### AssistantActionConfirmCard
- **Purpose:** The mandatory human-confirmation gate for any assistant-proposed write action (FR-9.3).
- **Variants:** N/A (single pattern, content varies by proposed action type).
- **States:** Proposed (awaiting confirm/cancel), confirming (loading), confirmed (result shown inline in chat), cancelled.
- **Properties:** action description (plain language, specific — "Log 500ml watering for Zone 3, Ficus #FLY-0142" not "Update record"), confirm/cancel buttons.
- **Accessibility:** Rendered as a real interactive card within the chat's accessible list structure, not a transient overlay that could be missed.
- **Responsive:** Same card pattern at all breakpoints, full-width within whichever chat panel variant is active.

---

## Commerce Components

### POSCart
- **Purpose:** Active sale line items and totals.
- **Variants:** N/A (single pattern).
- **States:** Empty (prompt to scan/search), populated, item-unavailable-error (blocked add, per FR-13.2), submitting.
- **Properties:** line items (item, quantity, price, subtotal), discount field, running total.
- **Accessibility:** Total updates announced via `aria-live="polite"` on change; each line item's remove action is a labeled button.
- **Responsive:** Persistent side panel on desktop/tablet POS layout; full-width stacked section on mobile (cart below the scan/search area).

### QRScanner
- **Purpose:** Camera-based QR capture resolving to a plant/inventory record.
- **Variants:** Modal overlay (triggered from a scan button), embedded (persistent on the mobile POS/Dashboard FAB).
- **States:** Requesting camera permission, scanning, resolved (found), not-found (invalid/unrecognized code), permission-denied (fallback to manual search).
- **Properties:** viewfinder, torch toggle (low-light), manual-entry fallback link.
- **Accessibility:** Manual-entry fallback is always available and clearly presented, not buried, so camera access is never a hard blocker to completing a task.
- **Responsive:** Mobile/tablet only (desktop POS uses a connected barcode/QR hardware scanner or manual search instead of a webcam flow, noted for Phase 7).

### ReceiptPreview / InvoicePreview
- **Purpose:** Printable/emailable document layout for a completed sale or invoice.
- **Variants:** Screen preview, print-optimized (separate print stylesheet considerations flagged for Phase 7), email-embedded.
- **States:** Loading (generating), ready, error.
- **Properties:** line items, totals, org branding, terms (InvoicePreview only).
- **Accessibility:** Print version maintains sufficient contrast for black-and-white printing (no reliance on color to convey the total or terms).
- **Responsive:** Screen preview is scrollable/zoomable on mobile rather than shrunk to fit.

### PassportPreview
- **Purpose:** The Plant Passport document layout — visually distinct, customer-facing.
- **Variants:** Internal preview (staff, pre-generation), public tokenized view (customer, post-generation via QR scan).
- **States:** Loading, ready, error (passport not yet generated for this plant).
- **Properties:** species/provenance block, health/treatment summary, identity block with QR, generation date/version.
- **Accessibility:** Must remain legible printed in black-and-white (per `docs/ux/15-plant-passport-workflow.md`'s compliance note) — verified via a grayscale contrast check in the Phase 3 design review.
- **Responsive:** Public tokenized view is mobile-first by default (customers scan with a phone) with a print-optimized layout available via an explicit print action.

---

## Feedback & System State

### Toast
- **Purpose:** Transient success/error feedback after a mutating action.
- **Variants:** Success, error, info, with-undo (e.g., recommendation dismissal).
- **States:** Entering, visible, auto-dismissing, dismissed (manual close).
- **Properties:** message, variant, optional undo action, auto-dismiss duration.
- **Accessibility:** Announced via `aria-live="polite"` (assertive for errors); does not auto-dismiss before a reasonable reading time, and never auto-dismisses if it contains an undo action the user might still need.
- **Responsive:** Bottom-anchored on mobile (thumb-reachable), top-right on desktop/tablet.

### LoadingSpinner / SkeletonLoader
- **Purpose:** In-progress data states.
- **Variants:** SkeletonLoader preferred for list/table/card content (matches final layout shape); LoadingSpinner for indeterminate short waits (button loading, small inline fetches).
- **States:** N/A (the loading state itself).
- **Properties:** shape/size matching the content it precedes.
- **Accessibility:** `aria-busy="true"` on the loading region; SkeletonLoader is marked decorative (`aria-hidden`) since it conveys no information beyond "loading."
- **Responsive:** Skeleton shapes adapt to the same responsive layout as their eventual content (e.g., table skeleton → card skeleton on mobile).

### ProgressState
- **Purpose:** Long-running async operation feedback (report export, batch forecast).
- **Variants:** Determinate (known progress %), indeterminate (unknown duration).
- **States:** In-progress, complete (with result action), failed (with retry).
- **Properties:** progress percentage, status message, estimated completion (if available).
- **Accessibility:** `role="progressbar"` with `aria-valuenow` for determinate variant; completion announced via `aria-live`.
- **Responsive:** Same pattern at all breakpoints; typically surfaced via Toast/NotificationCenter rather than blocking the UI, so responsiveness of the indicator itself is low-stakes.

### ErrorState
- **Purpose:** Page/section-level failure display (data fetch failed, AI module unavailable per NFR-3.3).
- **Variants:** Full-page (critical failure), section-level (one widget failed, rest of page usable), AI-module-specific ("AI predictions temporarily unavailable, retry").
- **States:** Displayed, retrying.
- **Properties:** error summary (plain language, per NFR-6.2 — no raw stack traces), retry action.
- **Accessibility:** Announced via `aria-live="assertive"` when it appears as a result of a user action; role="alert" region.
- **Responsive:** Same pattern at all breakpoints.

### NotificationListItem
- **Purpose:** Single row within the Notification Center.
- **Variants:** One per category (icon mapping per §3 domain icon dictionary), read/unread visual state.
- **States:** Unread (emphasized), read, hover/focus.
- **Properties:** category icon, message, timestamp, deep-link target.
- **Accessibility:** Unread state conveyed by more than color/weight alone (a visible dot indicator with an accessible "unread" label).
- **Responsive:** Same list pattern at all breakpoints within the SlideOverPanel/full-screen NotificationCenter.

### PermissionGate
- **Purpose:** Wrapper that hides/disables children based on the current user's permissions.
- **Variants:** Hide (element absent entirely — default, per the nav "absence not disabled" rule), disable-with-tooltip (used only where absence would be confusing, e.g., a visible-but-locked Enterprise feature upsell).
- **States:** Permitted (renders children), not-permitted (hidden or disabled per variant).
- **Properties:** required permission code(s), fallback behavior.
- **Accessibility:** Disabled variant's tooltip is reachable via keyboard focus, not hover-only.
- **Responsive:** N/A (behavioral wrapper, not a visual layout component).

---

## Modals & Overlays

### Modal (base)
- **Purpose:** Focused single-task overlay (create/edit forms — PG-13, PG-16, PG-19, PG-27, PG-35, PG-38, etc.).
- **Variants:** Standard (centered), form (with FormActions footer), confirmation (see ConfirmationDialog, a specialized Modal).
- **States:** Opening, open, closing, submitting (blocks dismiss).
- **Properties:** title, content, footer actions, dismissible (click-outside/Esc) flag — false for in-progress destructive actions.
- **Accessibility:** Focus trap, `role="dialog"` with `aria-labelledby` pointing to the title, focus returns to trigger on close, Esc closes unless explicitly blocked mid-submit.
- **Responsive:** Full-screen on mobile rather than a centered overlay (more usable form-filling space, avoids double-scrolling).

### SlideOverPanel
- **Purpose:** Persistent-context overlay (NotificationCenter, AssistantChatPanel) — doesn't feel like leaving the current page.
- **Variants:** Right-anchored (desktop/tablet), full-screen (mobile).
- **States:** Same as Modal (opening/open/closing).
- **Properties:** same as Modal, plus a persistent-vs-dismiss-on-navigate flag (Assistant panel can remain open across navigation; Notification panel closes on navigate).
- **Accessibility:** Same focus-trap rules as Modal.
- **Responsive:** Right-anchored panel (desktop/tablet, ~400–480px) → full-screen (mobile).

### Dropdown / ContextMenu
- **Purpose:** Row-level actions in tables, header menus.
- **Variants:** Icon-trigger (kebab menu), text-trigger (labeled button with chevron).
- **States:** Closed, open, item-hover/focus, item-disabled (permission-gated).
- **Properties:** trigger, item list (label, icon, destructive flag for red-colored items like "Delete").
- **Accessibility:** `menu`/`menuitem` roles, full keyboard operability (arrow keys, Esc to close, Enter to select), destructive items require a subsequent ConfirmationDialog rather than executing directly from the menu.
- **Responsive:** Converts to a bottom-sheet action list on mobile rather than a small anchored popover, for easier tap targeting.
