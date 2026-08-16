# High-Fidelity Screen Specifications

Every page from `docs/ux/01-sitemap.md`, fully specified at the design level. Builds directly on `docs/ux/09-page-inventory.md` (purpose/users/entry-exit/dependencies — not repeated here) and `02-component-library.md` (component names referenced, not redefined here). No page is skipped.

## Shared Chrome (defined once, applies to every authenticated page below)

**Header:** persistent, all authenticated pages — global search, BranchSwitcher (multi-branch users only), notification bell (→ PG-09 SlideOverPanel), AI Assistant icon (→ PG-10 SlideOverPanel), user menu. Not re-listed per page.

**Sidebar:** persistent PrimaryNav, RBAC-filtered per `docs/ux/04-navigation-architecture.md`. Not re-listed per page.

**Breadcrumbs:** rendered on every page nested more than one level deep from its sidebar entry point (detail pages, tabs, create/edit flows). Listed per page below only where the path isn't the obvious `Section / Entity Name`.

**Public pages (PG-01–06)** use a minimal header (logo + login/signup links only) instead of the authenticated Header/Sidebar — noted explicitly in that section.

Per-page entries below cover what's specific to that screen: sections, cards/tables/charts, primary actions, forms/dialogs, filters/search, and the four required states (empty, loading, error, success).

---

## Public

### PG-01 Landing / Marketing Page
- **Sections:** Hero (headline, CTA), feature highlights (3–4 cards summarizing Digital Twin / AI / Inventory / Reporting), pricing tier summary (3 PricingCards mirroring `docs/product/01-business-requirements-document.md` §5), footer.
- **Buttons:** "Start Free Trial" (primary, hero + pricing), "Log In" (header, secondary).
- **Empty/Loading/Error/Success:** N/A — static marketing content.

### PG-02 Sign Up
- **Sections:** Multi-step FormSection (1. account info, 2. org name, 3. first branch, 4. plan selection).
- **Forms:** Account form (name/email/password), Org form (name), Branch form (name/address/timezone).
- **Buttons:** "Continue" per step (primary), "Back," "Create Account" (final step).
- **Validation feedback:** Inline field errors (email format/uniqueness, password strength) shown on blur, not just on submit.
- **Loading state:** Button loading state on submit; step transitions use `standard` duration motion.
- **Error state:** Toast + inline field error for signup failures (e.g., email already registered).
- **Success state:** Redirect to PG-07 with a first-run EmptyState-driven onboarding checklist (invite employees, add species/plants).

### PG-03 Log In
- **Sections:** Single FormSection (email, password).
- **Buttons:** "Log In" (primary), "Forgot password?" (text link).
- **Loading state:** Button loading state.
- **Error state:** Generic inline error ("Incorrect email or password") — no user-enumeration detail, per NFR-4.6.
- **Success state:** Redirect to role-appropriate dashboard (PG-07 or PG-08).

### PG-04 Forgot Password
- **Sections:** Single FormSection (email).
- **Buttons:** "Send Reset Link" (primary).
- **Success state:** Confirmation message shown in place of the form ("If that email exists, a reset link is on its way") — same message regardless of whether the email exists.

### PG-05 Reset Password
- **Sections:** Single FormSection (new password, confirm password).
- **Buttons:** "Reset Password" (primary).
- **Error state:** Full-page ErrorState if the token is invalid/expired ("This link has expired — request a new one," linking back to PG-04).
- **Success state:** Confirmation + redirect to PG-03.

### PG-06 Accept Invite
- **Sections:** Invite context summary (org name, role, inviting branch), set-password FormSection (new users) or "log in to accept" prompt (existing account email).
- **Buttons:** "Accept & Set Password" / "Log In to Accept" (primary).
- **Error state:** Full-page ErrorState if the invite token is invalid/expired/already-accepted.
- **Success state:** Redirect to PG-08.

---

## Core

### PG-07 Org Dashboard
- **Sections (top to bottom):** PageHeader ("Dashboard," branch filter implicit as "All Branches"), StatCard row (org revenue, total active plants, at-risk count, open disease reports), per-branch StatCard grid (one card per branch: revenue, inventory alerts, AI risk flag), org-wide revenue LineChart, recent activity Timeline (compact), notification summary widget.
- **Charts:** Org revenue LineChart (actual, with AI forecast overlay toggle → links to PG-32).
- **Actions:** Click-through from any branch card to PG-08 (that branch); click-through from at-risk StatCard to PG-31 filtered.
- **Empty state:** First-run EmptyState if the org has zero branches with data yet, guiding to PG-13/PG-21.
- **Loading state:** SkeletonLoader matching the StatCard grid + chart shape.
- **Error state:** Section-level ErrorState per widget (a revenue-chart failure doesn't take down the whole dashboard) per NFR-3.3.
- **Success state:** N/A (read-only dashboard; success feedback belongs to the actions taken from it).

### PG-08 Branch Dashboard
- **Sections:** PageHeader (branch name, date), today's task StatCard row (watering due, low stock, pending disease reviews), sales-today StatCard, task list (Timeline-style, grouped by category, each item deep-linking to PG-34/36/29), quick-action button row (New Sale, Log Watering, Scan Disease).
- **Actions:** Quick-action buttons launch PG-39, PG-35, PG-28 respectively.
- **Empty state:** "All caught up" EmptyState variant when the task list is empty (a positive empty state, not a generic "no data").
- **Loading state:** SkeletonLoader for StatCards + task list.
- **Error state:** Section-level ErrorState per widget.
- **Success state:** Toast confirmations bubble up here from quick actions completed elsewhere (e.g., "Watering logged").

### PG-09 Notification Center
- **Layout:** SlideOverPanel (not a full page navigation).
- **Sections:** Filter tabs (All / Unread / by category), NotificationListItem list, "Mark all read" action, link to PG-58.
- **Filters:** Category filter tabs.
- **Empty state:** "No notifications yet" EmptyState.
- **Loading state:** SkeletonLoader list.
- **Error state:** Inline ErrorState with retry within the panel.
- **Success state:** Read-state toggles are instant/optimistic, no separate success toast needed.

### PG-10 AI Assistant
- **Layout:** SlideOverPanel (desktop/tablet) / full-screen (mobile).
- **Sections:** AssistantChatPanel (message thread, composer), suggested-prompts row (context-aware to current page).
- **Dialogs:** AssistantActionConfirmCard appears inline within the thread for any proposed write action.
- **Empty state:** Open-empty state shows 3–4 suggested prompts relevant to the page the user opened it from.
- **Loading state:** Assistant-typing indicator (AI thinking motion).
- **Error state:** Inline "message failed to send, retry" within the thread, not a full-panel error.
- **Success state:** Confirmed actions show an inline confirmation card within the chat thread (per AssistantActionConfirmCard spec).

---

## Organization & Branches

### PG-11 Branches List
- **Sections:** PageHeader ("Branches," "Add Branch" primary action), DataTable (name, address, employee count, status).
- **Filters/Search:** Search by name.
- **Empty state:** First-run EmptyState ("Add your first branch") for brand-new orgs.
- **Loading state:** DataTable skeleton rows.
- **Error state:** Full-section ErrorState with retry.

### PG-12 Branch Detail / Settings
- **Breadcrumbs:** Branches / [Branch Name].
- **Sections:** PageHeader (branch name, status badge), profile FormSection (name/address/timezone), operational thresholds FormSection (watering, low-stock defaults), employee roster preview (compact DataTable, link to PG-14 filtered), Danger Zone section (deactivate branch).
- **Dialogs:** ConfirmationDialog (typed-confirmation variant) for deactivation.
- **Loading state:** Form skeleton.
- **Error state:** Inline field errors on save failure; full ErrorState if the branch fails to load.
- **Success state:** Toast on successful save.

### PG-13 Create / Edit Branch
- **Layout:** Modal.
- **Forms:** Branch profile FormSection (name, address, timezone, initial thresholds).
- **Validation:** Required name/address inline errors; plan branch-limit error surfaced as a distinct, upgrade-prompting message (not a generic validation error) if the org is at its tier limit.
- **Success state:** Modal closes, Toast confirmation, redirect to PG-12 for the new branch.

---

## Employees

### PG-14 Employees List
- **Sections:** PageHeader ("Employees," "Invite Employee" primary action), DataTable (name, role, branch(es), status), filter bar (branch, role).
- **Filters/Search:** Search by name/email; filter by branch and role.
- **Empty state:** First-run EmptyState ("Invite your team").
- **Loading/Error states:** Standard DataTable skeleton / section ErrorState.

### PG-15 Employee Detail
- **Breadcrumbs:** Employees / [Employee Name].
- **Sections:** Profile summary card, role/branch assignment FormSection, Danger Zone (deactivate).
- **Dialogs:** ConfirmationDialog for deactivation; blocked with an explanatory ErrorState if this is the sole remaining Owner/Admin.
- **Success state:** Toast on role/assignment change.

### PG-16 Invite Employee
- **Layout:** Modal.
- **Forms:** Email + role + branch(es) FormSection.
- **Validation:** Valid email required; role selector only shows roles at or below the inviter's own permission ceiling; seat-limit error (Starter tier) surfaced distinctly, upgrade-prompting.
- **Success state:** Modal closes, Toast ("Invite sent"), PG-14 shows the new pending-invite row.

---

## Species Catalog

### PG-17 Species List
- **Sections:** PageHeader ("Species," "Add Species" action), DataTable/CardGrid toggle (photo-forward option), filter bar (category).
- **Filters/Search:** Search by name; filter by category.
- **Empty state:** First-run EmptyState.
- **Loading/Error states:** Standard.

### PG-18 Species Detail
- **Breadcrumbs:** Species / [Species Name].
- **Sections:** Identity header (common + botanical name, category), care-requirement FormSection (light/water/soil/temperature), typical growth-curve LineChart, disease-susceptibility list, linked-plants count (link to PG-20 filtered).
- **Validation:** Numeric range fields validated min ≤ max inline.
- **Success state:** Toast on save.

### PG-19 Create / Edit Species
- **Layout:** Modal (create) / inline edit mode (PG-18).
- **Forms:** Same fields as PG-18.
- **Success state:** Toast + redirect to PG-18 (create flow).

---

## Plants (Digital Twin)

### PG-20 Plants List
- **Sections:** PageHeader ("Plants," "Add Plant" action, QR scan shortcut), CardGrid (default) / DataTable (toggle), filter bar (branch, species, status, AI risk flag).
- **Filters/Search:** Search by plant ID/species/common name; multi-select filters.
- **Empty state:** First-run EmptyState ("Add your first plant") vs. filtered-empty ("No plants match these filters, clear filters").
- **Loading state:** CardGrid/DataTable skeleton.
- **Error state:** Section ErrorState with retry.

### PG-21 Create Plant
- **Sections:** SpeciesSelector (with inline create), branch/zone selector, PhotoUpload (initial photo), initial measurement fields.
- **Success state:** Redirect to PG-22 with the newly generated QR code prominently displayed (a distinct "here's your QR code" success moment, printable immediately).

### PG-22 Plant Digital Twin Detail
- **Breadcrumbs:** Plants / [Plant ID / Species Name].
- **Sections:** Header (identity, QR code thumbnail, StatusBadge, PhotoGallery), quick-action button row (Log Growth, Log Health, Scan Disease, Transfer, Generate Passport, Mark Sold/Deceased), TabNav (Overview, Growth, Health, Environmental/Watering, AI Predictions).
- **Overview tab sections:** Species reference summary (link to PG-18), latest AIResultCard summary row (one compact card per module), recent activity Timeline (compact, cross-cutting across all sub-record types).
- **Dialogs:** PG-27 Transfer modal, status-change ConfirmationDialogs (mark deceased especially — typed or explicit confirm).
- **Empty state:** New plant with no history yet shows an EmptyState per tab prompting the first log entry.
- **Loading state:** Full-page skeleton (header + tabs) on initial load.
- **Error state:** Section-level ErrorState per tab (an AI Predictions fetch failure doesn't block viewing Growth).
- **Success state:** Toast per quick action (e.g., "Growth logged," "Plant transferred to [Branch]").

### PG-23 Growth Timeline (tab)
- **Sections:** Growth LineChart (actual + AI-predicted overlay), "Log Growth" inline FormSection (collapsible), measurement Timeline/list below the chart.
- **Empty state:** "No growth entries yet — log the first measurement."
- **Success state:** Toast + chart/timeline updates optimistically on log.

### PG-24 Health History (tab)
- **Sections:** Health status Timeline, linked Disease Reports summary list (link to PG-30 per item), "Log Health Observation" inline FormSection.
- **Empty state:** "No health observations yet."
- **Success state:** Toast on log; a confirmed disease report appearing here shows a distinct visual treatment (not just another timeline entry) given its severity.

### PG-25 Environmental & Watering (tab)
- **Sections:** Environmental readings LineChart (multi-series: temp/humidity/moisture/light, toggleable), watering event list with next-due indicator, "Log Watering" quick action (opens PG-35).
- **Empty state:** Separate empty prompts for "no environmental readings yet" and "no watering logged yet" (two independent empty states within one tab, since they're independently useful).
- **Success state:** Toast on log.

### PG-26 AI Predictions (tab)
- **Sections:** One AIResultCard per module (Disease, Growth, Survival, Water) showing the latest prediction, "View History" toggle per card expanding to a compact Timeline of past predictions for that module.
- **Empty state:** "No AI predictions yet for this plant" — with an explanation that predictions begin once sufficient history exists (per `docs/ux/12-ai-workflow-diagrams.md` §2's "sufficient plant-specific history" branch), not presented as an error.
- **Loading state:** AI-thinking skeleton if a prediction is actively being generated.

### PG-27 Transfer Plant (modal)
- **Forms:** Destination BranchSelector, optional note TextArea.
- **Validation:** Destination must differ from current branch and be active; permission-checked against both branches.
- **Success state:** Modal closes, Toast, PG-22 header updates to the new branch.

---

## Disease & Health

### PG-28 AI Disease Detection Scan
- **Sections:** AIScanCapture (camera/upload), in-progress "analyzing" state, AIResultCard result.
- **Actions:** "Confirm as Disease Report" / "Dismiss" (if a draft report was auto-created), "Log another scan."
- **Loading state:** Analyzing state, target ≤5s (NFR-1.2), `aria-live` announced.
- **Error state:** "AI Disease Detection is temporarily unavailable — try again" (NFR-3.3 graceful degradation) with a manual "create disease report" fallback link so the workflow isn't fully blocked.
- **Success state:** Result card + Toast; redirect to PG-30 if a report was drafted.

### PG-29 Disease Reports List
- **Sections:** PageHeader, DataTable (status-badged rows), filter bar (status, severity, branch).
- **Filters/Search:** Status/severity/branch filters; search by plant ID.
- **Empty state:** "No disease reports" (positive empty state).
- **Loading/Error states:** Standard.

### PG-30 Disease Report Detail
- **Breadcrumbs:** Disease Reports / [Report ID].
- **Sections:** AI evidence panel (photo, AIResultCard, AIExplanationPanel), status Timeline (drafted → confirmed → treated → resolved), treatment log FormSection, outcome selector.
- **Dialogs:** Confirm/dismiss ConfirmationDialog (dismiss requires no reason if false-positive is obvious, but logs feedback silently for retraining).
- **Validation:** Outcome selection required to close the report; treatment entries require description.
- **Success state:** Toast per action; report status Timeline updates visibly.

---

## AI Predictions Center

### PG-31 AI Predictions Dashboard
- **Sections:** PageHeader, filter bar (branch, species), ranked at-risk plant list (each row: plant summary, HealthRiskBadge, top contributing factor, link to PG-22), growth-trend summary widget.
- **Filters:** Branch, species.
- **Empty state:** "No elevated-risk plants right now" (positive empty state).
- **Loading state:** SkeletonLoader list.
- **Error state:** ErrorState per NFR-3.3 pattern with retry.

### PG-32 Revenue Forecast
- **Sections:** PageHeader, branch selector, AreaChart (actual + forecast + confidence interval band), historical-vs-projected comparison table, "Export" action (→ PG-52 pre-filled).
- **Empty state:** "Not enough sales history yet to generate a forecast" (Starter/new-org case).
- **Loading state:** Chart skeleton.
- **Error state:** NFR-3.3 pattern.

### PG-33 Recommendation Feed
- **Sections:** PageHeader, filter bar (branch, priority), RecommendationCard list.
- **Actions:** Per-card act (deep-link) / dismiss (undo-able toast).
- **Empty state:** "No active recommendations" (positive empty state).
- **Loading/Error states:** Standard skeleton/NFR-3.3 pattern.

---

## Watering

### PG-34 Watering Schedule / Tasks
- **Sections:** PageHeader, grouped task list (by zone/branch), overdue items visually distinguished (not color-only — icon + "Overdue" label), "Log Watering" quick action per row.
- **Filters:** Branch, zone.
- **Empty state:** "All watering tasks complete" (positive empty state).
- **Loading/Error states:** Standard.

### PG-35 Log Watering Event (modal)
- **Forms:** Plant/zone selector (pre-filled if launched in context), volume/duration NumberField, notes TextArea.
- **Validation:** Target required, volume ≥ 0.
- **Success state:** Modal closes, Toast, task list updates (item removed from overdue view).

---

## Inventory

### PG-36 Inventory List
- **Sections:** PageHeader ("Inventory," "Adjust Stock" bulk action), DataTable (species/product, quantity, branch, low-stock StatusBadge), filter bar.
- **Filters/Search:** Branch, category, low-stock-only toggle; search by name/SKU.
- **Empty state:** First-run EmptyState.
- **Loading/Error states:** Standard.

### PG-37 Inventory Item Detail
- **Breadcrumbs:** Inventory / [Item Name].
- **Sections:** Quantity/threshold summary, adjustment history Timeline, linked purchase orders and sales (compact tables).
- **Actions:** "Adjust Stock" (→ PG-38).
- **Loading/Error states:** Standard.

### PG-38 Adjust Stock (modal)
- **Forms:** QuantityStepper (delta), reason SelectField (damage/correction/internal use/other), notes TextArea.
- **Validation:** Resulting quantity cannot go below 0 (inline blocking error); reason required.
- **Success state:** Modal closes, Toast, PG-36/37 quantity updates optimistically.

---

## Sales / POS

### PG-39 POS / New Sale
- **Sections:** Split layout — item search/QR-scan panel (left/top) + POSCart (right/bottom persistent panel).
- **Search:** QRScanner + text search for items.
- **Forms:** CustomerSelector (with inline create), discount field, payment method selector.
- **Dialogs:** Item-unavailable error surfaces inline in the search result, not a blocking modal (keeps the flow moving).
- **Validation:** Real-time availability check (FR-13.2) blocks add with an inline reason; at least one line item required to complete.
- **Loading state:** Item lookup spinner; "Complete Sale" button loading state.
- **Error state:** Toast + inline error on sale-completion failure (e.g., a race-condition stock conflict), cart preserved so the user doesn't lose their work.
- **Success state:** Redirect to PG-41 with a success Toast; cart clears.

### PG-40 Sales History
- **Sections:** PageHeader, date-range summary StatCards, DataTable (sortable/filterable), row-selection for bulk invoice creation.
- **Filters:** Date range, branch.
- **Actions:** "Create Invoice from Selected."
- **Empty/Loading/Error states:** Standard.

### PG-41 Sale / Receipt Detail
- **Breadcrumbs:** Sales / [Sale ID].
- **Sections:** ReceiptPreview, payment info, print/email action row.
- **Dialogs:** Void ConfirmationDialog (reason required, Manager+ only).
- **Actions:** "Generate Invoice" (→ PG-46).
- **Success state:** Toast on print/email/void actions.

---

## Customers

### PG-42 Customers List
- **Sections:** PageHeader ("Customers," "Add Customer"), DataTable (name, type badge, last purchase), search bar.
- **Empty state:** First-run EmptyState.
- **Loading/Error states:** Standard.

### PG-43 Customer Detail
- **Breadcrumbs:** Customers / [Customer Name].
- **Sections:** Contact FormSection, classification toggle (retail/wholesale), purchase-history DataTable (sales + invoices combined, filterable by type).
- **Validation:** Contact format validation inline; duplicate-customer warning (non-blocking, "similar customer found" suggestion) on create.
- **Success state:** Toast on save.

---

## Invoices

### PG-44 Invoices List
- **Sections:** PageHeader, DataTable (status-badged, overdue rows visually distinguished), filter bar (status, branch).
- **Empty/Loading/Error states:** Standard.

### PG-45 Invoice Detail
- **Breadcrumbs:** Invoices / [Invoice #].
- **Sections:** InvoicePreview, status Timeline (draft → sent → paid/overdue → void), action row (mark paid, resend, void).
- **Dialogs:** Void ConfirmationDialog (reason required).
- **Success state:** Toast per status action.

### PG-46 Create Invoice
- **Sections:** Selected-sales summary (from PG-40/41), terms FormSection (net 30/60, PO reference), customer confirm, "email on send" toggle.
- **Validation:** At least one sale required; customer required; terms required for wholesale.
- **Success state:** Redirect to PG-45 (new invoice), Toast.

---

## Suppliers & Purchasing

### PG-47 Suppliers List
- **Sections:** PageHeader, DataTable, search.
- **Empty/Loading/Error states:** Standard.

### PG-48 Supplier Detail
- **Breadcrumbs:** Suppliers / [Supplier Name].
- **Sections:** Contact FormSection, linked purchase orders DataTable (link to PG-49 filtered).
- **Success state:** Toast on save.

### PG-49 Purchase Orders List
- **Sections:** PageHeader ("Create PO" action), DataTable (status-badged), filter bar (status, supplier).
- **Empty/Loading/Error states:** Standard.

### PG-50 Purchase Order Detail / Create
- **Breadcrumbs:** Purchase Orders / [PO #] (detail) or "Create Purchase Order" (create).
- **Sections:** Supplier selector, line-item FormSection (repeatable rows: product/species, quantity, unit cost), running total, "Receive Stock" action (partial/full quantity entry per line).
- **Validation:** At least one line item; receive quantity ≤ ordered quantity per line.
- **Success state:** Toast on create/send; Toast + PG-36 inventory update confirmation on receipt.

---

## Reports

### PG-51 Reports Hub
- **Sections:** PageHeader, report-type CardGrid (Inventory, Sales, Revenue, Plant Loss, AI Summary, Plant Passport), recent-exports list (with re-download action).
- **Empty state:** "No reports generated yet" for the recent-exports list only (report-type cards are always shown).

### PG-52 Report Export / Builder
- **Sections:** Filter FormSection (date range, branch, category), format SelectField (PDF/Excel/CSV), "Generate" action, ProgressState for in-flight generation.
- **Validation:** Valid date range; at least one branch (or org-wide for Owner/Admin).
- **Loading state:** ProgressState (async, per `docs/ux/11-data-flow-diagrams.md` §5).
- **Success state:** Download-ready Toast/notification with a direct download link once generation completes.

### PG-53 Plant Passport View
- **Breadcrumbs:** Plants / [Plant ID] / Passport (internal) or none (public tokenized view).
- **Sections:** PassportPreview, generate/regenerate action, download/print/email row, version history (internal view only).
- **Error state:** "Passport not yet generated for this plant" prompt (internal view) if none exists.
- **Success state:** Toast on generate/regenerate.

---

## Audit Log

### PG-54 Audit Log Viewer
- **Sections:** PageHeader, filter bar (actor, entity type, date range), DataTable (Data Grid variant — high volume), before/after diff viewer (row expand or side panel).
- **Filters/Search:** Actor, entity type, date range, action type.
- **Empty state:** "No matching activity" for a filtered-empty result (the log itself is never truly empty once the org has any history).
- **Loading state:** Data Grid virtualized skeleton.

---

## Settings

### PG-55 Org Profile Settings
- **Layout:** TabNav within Settings.
- **Sections:** Org identity FormSection (name, logo upload, contact info).
- **Success state:** Toast on save.

### PG-56 Billing & Plan
- **Sections:** Current plan summary card, usage-vs-limit meters (branches, seats, AI credits — progress-bar style), upgrade/downgrade action, payment method FormSection, invoice history DataTable.
- **Dialogs:** Downgrade blocked with an explanatory ErrorState if current usage exceeds the target plan's limits (not a silent failure).
- **Success state:** Toast on plan change/payment method update.

### PG-57 Roles & Permissions
- **Sections:** System roles reference list (read-only), custom role builder (permission checkbox matrix grouped by module, mirroring `docs/ux/07-role-permission-matrix.md`'s structure), assigned-employee counts per role.
- **Validation:** Custom role permission ceiling enforced inline (cannot exceed `org_admin`); delete blocked with explanation if the role has active assignments.
- **Success state:** Toast on save.

### PG-58 Notification Preferences
- **Sections:** Category × channel matrix (toggle grid), org-defaults section (Owner/Admin only).
- **Validation:** SMS toggle disabled (with explanation) if the org hasn't enabled SMS at the plan/integration level.
- **Success state:** Toast on save (autosave-on-toggle pattern, no separate submit button).

### PG-59 Integrations Settings
- **Sections:** SMS provider FormSection (on/off + credentials), email sender identity FormSection, (Enterprise tier) API key management table.
- **Validation:** SMS enablement requires valid provider credentials verified before the toggle activates.
- **Success state:** Toast on save; explicit "test connection" action with its own success/error feedback before enabling.
