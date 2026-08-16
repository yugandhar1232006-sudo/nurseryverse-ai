# 7D — Dashboards

## Architecture

```
lib/api/reports.ts              Typed wrappers for every Module 12 /dashboards, /analytics,
                                 /reports/* route (dashboards + analytics used by 7D; report
                                 catalog/generation/scheduled-report wrappers land fully in 7N)
lib/dashboards/queries.ts       TanStack Query hooks, one per dashboard endpoint, keyed by
                                 branch scope + date range
lib/shell/queries.ts            + useOrgSettingsQuery() (added this phase) -- real
                                 OrgSettingsResponse.default_currency for money formatting
lib/utils.ts                    + formatCurrency/formatNumber/formatCompactNumber/formatPercent

components/dashboards/
  dashboard-content.tsx          Tabbed orchestrator: 9 tabs, one per Module 12 dashboard type
  dashboard-scope-select.tsx     "All branches" / a specific branch -- dashboard-local, distinct
                                  from the shell's own BranchSelector (see its own docstring)
  no-reporting-access.tsx        Honest landing state for roles with no reports:read at all
  kpi-card.tsx                   StatCard primitive (docs/ux/10-component-inventory.md)
  revenue-trend-chart.tsx        Recharts AreaChart over ExecutiveDashboardResponse.revenue_trend
  branch-performance-table.tsx   Shared by the Executive tab and (later) branch-performance list
  executive-tab.tsx / nursery-tab.tsx / branch-tab.tsx / plant-tab.tsx / inventory-tab.tsx /
  sales-tab.tsx / customer-tab.tsx / ai-tab.tsx / financial-tab.tsx

app/(app)/page.tsx               PermissionGate(reports:read) -> DashboardContent : NoReportingAccess
```

## Why one route, nine tabs

`NAV_ITEMS` (nav-config.ts, 7C) has exactly one "Dashboard" entry (`/`). The 7D kickoff names nine
dashboard types (Executive/Nursery/Branch/Plant/Inventory/Sales/Customer/AI/Financial), which map
1:1 onto the nine real `GET /dashboards/*` routes in `apps/api/app/api/routes/reports.py` — but
there was never a plan for nine separate sidebar destinations nothing links to. They're presented as
tabs of the one real Dashboard route instead. Radix `Tabs` only mounts the active panel's content
(no `forceMount`), so switching tabs is also what triggers each dashboard's real network request —
inactive tabs never fetch.

## Permission model (real, not invented)

Per `docs/ux/07-role-permission-matrix.md`, `reports:read` is granted **F** (full, org-wide) to
Owner/Org Admin, **B** (branch-scoped) to Branch Manager, and **not at all** to Horticulturist or
Sales Staff. `nav-config.ts` leaves the Dashboard nav entry ungated ("every authenticated user has
*some* dashboard destination"), but the actual reporting content requires `reports:read` — a real
gap between "has a landing page" and "has reporting data," not a bug. `app/(app)/page.tsx` resolves
this with a `PermissionGate` one level down: users without `reports:read` see `NoReportingAccess`
(a plain-language explanation plus real links to whatever they *do* have permission for — Plants,
Sales, Customers), never a hard "Permission denied" wall on the one route every signed-in user lands
on immediately after login, and never fabricated dashboard widgets standing in for data they have no
access to.

## Scope: org-wide vs. branch

Three routes are **always** org-wide with no `branch_id` parameter at all: Executive, Nursery, and
the standalone branch-performance list (see `_authorize_branch_or_org(branch_id=None, ...)` calls in
`reports.py`). One route, Branch Dashboard, **requires** a specific branch id (404s without one). The
remaining five (Plant/Inventory/Sales/Customer/AI/Financial) take an *optional* `branch_id` filter.
`DashboardScopeSelect` is a dashboard-local control (not the shell's `BranchSelector`) with an
explicit "All branches" option the shell selector deliberately doesn't have — org-wide rollups are a
first-class view here, not merely "no branch picked yet." Selecting "All branches" on the Branch tab
shows a real prompt to pick one, rather than silently defaulting to an arbitrary branch.

## Data honesty

- Every figure comes from a real Module 12 dashboard/analytics endpoint — no invented metrics, no
  static JSON, no client-side aggregation standing in for a missing backend endpoint.
- `last_refreshed_at` (Executive tab) is surfaced verbatim as "as of \<timestamp\>," never implied as
  live — dashboards read pre-aggregated rollups on a ~15-minute refresh cycle
  (`docs/ux/18-analytics-workflow.md`), not raw transactional queries.
- `FinancialDashboardResponse`'s `estimated_cogs`/`estimated_gross_profit`/`estimated_gross_margin`
  are labeled "Estimated" in the UI exactly as the backend schema itself names them — a real computed
  estimate from recorded cost/sale data, not a full accounting close.
- AI Dashboard: `AtRiskPlantResponse.confidence` is labeled "Confidence score," never "probability" or
  "accuracy" — it's the model's own self-reported score, not a calibrated statistical guarantee.
  "Prediction accuracy" is a separately-real, computed ratio (`correct_prediction_count /
  scored_prediction_count`) over predictions that were actually scored against a real outcome. Both
  the at-risk list and the accuracy stat carry an explicit "AI-generated ... not confirmed diagnoses"
  disclaimer.
- Currency formatting uses `OrgSettingsResponse.default_currency` (fetched via the new
  `useOrgSettingsQuery`), never a hardcoded "USD," since NurseryVerse is multi-currency across orgs.

## UI states

Every tab: loading (skeleton KPI cards / skeleton rows), real empty states (`EmptyState`, e.g. "No
plants currently flagged," "Nothing low on stock"), error state with retry (`ErrorState`, wraps the
real `ApiError`), and the populated real-data state. `DashboardScopeSelect` itself has loading
(skeleton), zero-branches (renders nothing), and populated states, mirroring `BranchSelector`'s
established pattern from 7C.

## Responsive & accessibility

KPI grids collapse from 4 columns (laptop+) to 2 (tablet) to 1 (mobile) via the same
`tablet:`/`laptop:` custom breakpoints established in 7C. Tables scroll horizontally on narrow
viewports (`Table`'s own `overflow-x-auto` wrapper). The revenue trend chart is a Recharts
`ResponsiveContainer`; its data is also available in the adjacent KPI cards and the branch table, so
the same information isn't chart-only. `Tabs`/`TabsTrigger`/`TabsContent` are Radix primitives with
correct `role="tab"`/`role="tabpanel"`/keyboard arrow-key navigation out of the box.

## Testing

- **Vitest/RTL** (`components/dashboards/__tests__/dashboard-page.test.tsx`, 11 tests, all passing):
  no-reporting-access state and its permission-filtered quick links; Executive tab real KPI/branch
  rendering; tab-switch triggers a real fetch for that tab's own data; error state + retry recovery;
  Branch tab's "pick a branch" prompt and real branch-scoped data once one is selected; `branch_id`
  query-parameter scoping verified end-to-end through the scope selector; AI tab empty state and
  confidence-score labeling; Financial tab's "Estimated" labeling.
  - **Discovered and fixed while writing these tests (not a pre-existing defect in 7C's own code,
    but a real gap this phase's testing needed closed):** exercising `DashboardScopeSelect` via
    `userEvent.click` threw `TypeError: target.hasPointerCapture is not a function` — jsdom
    implements no Pointer Events capture API and no `scrollIntoView`, both of which Radix's `Select`
    calls on open. `BranchSelector`'s own 7C tests had sidestepped this by only asserting the
    trigger's closed-state text, never actually opening it. Since 7E–7O will introduce many more
    Select-driven filters and forms, this was fixed at the root — `test/setup.ts` now stubs
    `hasPointerCapture`/`setPointerCapture`/`releasePointerCapture`/`scrollIntoView` on
    `Element.prototype`, the same category of fix as the pre-existing `matchMedia`/`ResizeObserver`
    stubs (a missing browser API, not a change to any app behavior). This unblocks real Select
    interaction testing for the rest of Phase 7, not just this phase.
- **Full regression**: all 135 Vitest/RTL tests across the app (124 from 7A–7C + 11 new) pass.
  `npx eslint .` clean across the entire repo. `npx tsc --noEmit` clean.
- **Playwright** (`e2e/dashboards.spec.ts`, 2 tests): written and reviewed against the real
  components/routes; **not execution-verified** in this sandbox (no Postgres/Docker — same disclosed
  constraint as `e2e/auth.spec.ts`/`e2e/shell.spec.ts`). Covers the org-less
  `NoReportingAccess` degradation and the auth-required redirect. Full dashboard-content assertions
  (real KPI figures, branch-scoped filtering) would additionally need a seeded org+branch+role
  fixture this sandbox cannot provision either way — that coverage lives in the Vitest/RTL suite
  above, against real component code with MSW-mocked network responses, per this project's
  established "Written / Collected / Executed / Passed / Blocked" distinction.

## Known limitations

- No date-range picker UI yet for Sales/Financial/trend endpoints — they call the backend with no
  explicit `date_from`/`date_to`, so the backend's own default (trailing period) applies. A real
  date-range control is straightforward to add on top of the existing `DateRangeQuery` plumbing but
  wasn't part of this phase's minimum real-data-driven scope.
- `PlantDashboardResponse.by_species`/`AIDashboardResponse.at_risk_plants` entries don't yet link to
  a plant detail page — there is no plant detail route until 7G/7H ship. Same "link to the real
  parent list, not a fabricated per-id URL" precedent 7C's global search established for the same
  reason.
