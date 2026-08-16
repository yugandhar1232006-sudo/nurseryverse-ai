# Component Inventory

Full design-system-level component build list for Phase 3 (UI/UX Design) and Phase 7 (Frontend). Grouped by category; each component notes the pages that use it most heavily (not exhaustive — many are used everywhere) and any domain-specific variants it needs. Visual spec (color, spacing, states) is defined in Phase 4's Design System, not here — this is the inventory of *what* to build, not yet *how it looks*.

## Layout & Shell
- **AppShell** — sidebar + header + content region; renders role-filtered navigation (all authenticated pages).
- **Sidebar / PrimaryNav** — collapsible, RBAC-filtered nav list (per `04-navigation-architecture.md`).
- **Header** — global search, branch switcher, notification bell, AI assistant icon, user menu.
- **BranchSwitcher** — dropdown, only rendered for multi-branch users.
- **BottomTabBar** — mobile-only, 4 primary destinations + "More."
- **Breadcrumbs** — nested detail pages (PG-22 tabs, PG-12, PG-15, etc.).
- **TabNav** — used within PG-22 (twin tabs) and Settings (PG-55–59).
- **PageHeader** — title, primary action button, contextual filters slot.

## Data Display
- **DataTable** — sortable/filterable table with pagination; variants: standard (Employees, Species, Customers, Suppliers), status-badged (Disease Reports, Invoices, Purchase Orders), scan-integrated (Inventory).
- **CardGrid** — alternative to DataTable for Plants List (photo-forward browsing).
- **StatCard** — dashboard summary metric (revenue, alerts count, at-risk count) — used on PG-07, PG-08.
- **StatusBadge** — plant/disease/invoice/PO status; color + icon + label per NFR-7.2 (never color-only).
- **HealthRiskBadge** — specific StatusBadge variant driven by AI survival-risk score, with confidence indicator.
- **Timeline** — chronological event list; variants: Growth Timeline, Health History, Watering Log, Audit Log detail.
- **PhotoGallery** — plant image history (PG-22 header).
- **EmptyState** — no-data illustration + primary action, used on every list/dashboard page on first use.

## Charts (Phase 4 defines exact chart library usage)
- **LineChart** — growth-over-time (PG-23), revenue actual-vs-forecast (PG-32).
- **AreaChart** — revenue forecast confidence interval band (PG-32).
- **BarChart** — sales summary, plant-loss-by-branch comparisons.
- **SparklineChart** — compact trend indicator inside StatCard.
- **ConfidenceIndicator** — visual (not purely numeric) representation of AI prediction confidence, reused across all AI result displays.

## Forms & Inputs
- **TextField, TextArea, NumberField, SelectField, MultiSelectField, DateField, DateRangeField** — base form primitives (shadcn/ui-based, per stack decision).
- **SpeciesSelector** — typeahead search + inline "create new species" affordance (used in PG-21, PG-19-linked flows).
- **BranchSelector, EmployeeSelector, CustomerSelector, SupplierSelector** — typeahead selectors following the same pattern.
- **PhotoUpload / CameraCapture** — mobile-camera-first capture component, used in PG-21, PG-23, PG-24, PG-28 — this is a high-priority component given how much of the AI value chain depends on photo quality/friction.
- **QuantityStepper** — inventory adjustment, sale line items.
- **FormSection, FormActions** — layout wrappers for multi-section forms (PG-02 signup, PG-46 invoice creation).
- **ConfirmationDialog** — required before any destructive/hard-to-reverse action (NFR-6.3): deactivate branch/employee, void sale/invoice, mark plant deceased.

## AI-Specific Components
- **AIResultCard** — condition/prediction, confidence, explanation, model version — the canonical way any AI output is displayed (Disease Detection, Growth, Survival, Water, Revenue).
- **AIExplanationPanel** — expandable "why" detail behind a prediction (contributing factors) — directly supports NFR requirement that AI never appears as an unexplained black box.
- **RecommendationCard** — actionable suggestion with dismiss/act buttons (PG-33).
- **AIScanCapture** — specialized PhotoUpload variant wired directly to the Disease Detection endpoint with inline result display (PG-28).
- **AssistantChatPanel** — slide-over chat UI, message bubbles, proposed-action confirmation card, source citations.
- **AssistantActionConfirmCard** — the specific "confirm before I do this" component required by FR-9.3 — appears inline in AssistantChatPanel whenever a write action is proposed.

## Commerce Components
- **POSCart** — line items, quantity, discount, totals (PG-39).
- **QRScanner** — camera-based QR capture, resolves to plant/inventory lookup (PG-39, PG-22 entry, mobile FAB).
- **ReceiptPreview** — printable/emailable receipt layout (PG-41).
- **InvoicePreview** — printable/emailable invoice layout with terms (PG-45, PG-46).
- **PassportPreview** — the Plant Passport document layout (PG-53) — visually distinct, customer-facing, must remain legible if printed in black-and-white.

## Feedback & System State
- **Toast** — transient success/error feedback, consistent across all mutating actions.
- **LoadingSpinner / SkeletonLoader** — page and component-level loading states; skeleton preferred over spinner for list/table content (perceived-performance best practice).
- **ProgressState** — long-running async operations (report export, batch AI forecast) with completion notification hook.
- **ErrorState** — page/section-level failure display, distinct from Toast (used for full data-fetch failures, e.g., "AI module unavailable, retry" per NFR-3.3).
- **NotificationListItem** — single notification row (PG-09), variant per category icon.
- **PermissionGate** — wrapper component that hides/disables children based on the current user's permissions (implements the "absence not disabled" nav rule and equivalent in-page action gating).

## Modals & Overlays
- **Modal** (base) — used by PG-13, PG-16, PG-19, PG-27, PG-35, PG-38 and others per the sitemap's "(modal)" designations.
- **SlideOverPanel** — used by NotificationCenter (PG-09) and AssistantChatPanel (PG-10) — persistent-context overlays rather than full navigations.
- **Dropdown / ContextMenu** — row-level actions in tables (edit/deactivate/delete).

## Design System Foundations (elaborated fully in Phase 4)
Typography scale, color tokens (including the health-status and growth-stage palettes), spacing scale, icon set, and dark-mode token mapping are defined in Phase 4 and consumed by every component above — not re-specified here.
