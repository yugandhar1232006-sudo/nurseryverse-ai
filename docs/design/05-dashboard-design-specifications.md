# Dashboard Design Specifications

Deep-dive design detail for every dashboard-class screen — these carry disproportionate product value (they're where Renata, Marcus, and Priya spend the most recurring time per `docs/ux/02-user-journey-maps.md`) and warrant more design rigor than a standard list/detail page. Base structure for each is already defined in `03-screen-specifications.md`; this document adds layout composition, data-density rules, and interaction depth.

## 1. Executive Dashboard (Org Dashboard, PG-07)

**Audience:** Renata (Owner), Org Admin. **Design intent:** answer "how is my business doing, across every branch, in under 10 seconds" — this is a scanning screen, not a working screen.

**Layout composition (desktop):** a 3-row structure. Row 1 — four org-wide StatCards (Total Revenue MTD, Active Plants, At-Risk Count, Open Disease Reports), each with a trend delta against the prior period. Row 2 — a per-branch comparison grid: one StatCard per branch showing revenue, an inventory-alert count, and an AI-risk-flag count, sorted by attention-needed (branches with active alerts surface first, not alphabetically — the dashboard's job is to direct attention, not just display data). Row 3 — org-wide revenue LineChart (actual vs. AI forecast, toggleable overlay) alongside a compact cross-branch activity Timeline.

**Data density rule:** no more than 4 primary StatCards above the fold — additional metrics belong in Reports (PG-51), not crammed onto the dashboard. This is a deliberate constraint against "dashboard sprawl," where every stakeholder's favorite metric gets added until the screen is no longer scannable.

**Interaction depth:** every card and chart element is a drill-down entry point (per `docs/ux/03-screen-flow-diagrams.md` §1's journey) — nothing on this dashboard is a dead end; clicking a branch card goes to that Branch Dashboard (PG-08), clicking the at-risk StatCard goes to PG-31 pre-filtered.

**Freshness indicator:** per `docs/ux/18-analytics-workflow.md`'s pre-aggregation model, a small "as of [time]" indicator accompanies the dashboard, honest about the ~15-minute rollup lag rather than implying false real-time precision.

## 2. Nursery Dashboard (Branch Dashboard, PG-08)

**Audience:** Marcus (Branch Manager), also the default landing view for Horticulturist and Sales Staff (reduced widget set). **Design intent:** "what do I need to do today" — an action list, not a scanning screen. This is the single biggest design-intent difference from the Executive Dashboard: PG-07 is read-oriented, PG-08 is task-oriented.

**Layout composition:** Row 1 — today's task StatCards (Watering Due, Low Stock Items, Pending Disease Reviews), each directly clickable into the filtered underlying list. Row 2 — the task list itself, grouped by category (not a generic activity feed), each item actionable inline where possible (e.g., a watering task row has a "Log Now" button, not just a link). Row 3 — sales-today summary and quick-action buttons (New Sale, Log Watering, Scan Disease).

**Role-based widget reduction:** Horticulturist sees the task list and AI/health widgets but not the sales-today summary; Sales Staff sees sales-today and quick-actions but not the watering/health task list — each role's dashboard is a true subset, not the same dashboard with disabled sections (per the PermissionGate "absence not disabled" rule).

**Empty state design:** this dashboard's empty state ("All caught up") is deliberately positive/rewarding rather than a neutral "no data" pattern — for a task-oriented screen, an empty task list is a good outcome and should feel like one (distinct illustration/tone from a true first-run empty state).

## 3. Plant Digital Twin Dashboard (PG-22 Overview tab)

**Audience:** Priya (Horticulturist) primarily, all roles secondarily. **Design intent:** the complete story of one plant, readable top-to-bottom without tab-switching for the common case, with tabs reserved for going deep on one dimension.

**Layout composition:** the Overview tab (not a separate tab itself, but the default view of PG-22) is a condensed digest: identity/status header, a single-row summary of the latest AIResultCard per module (4 compact cards: Disease, Growth, Survival, Water), and a unified recent-activity Timeline merging growth/health/watering/environmental events chronologically (the only place in the system these four record types are interleaved together, rather than siloed per tab) — this merged view is what makes "the full story of this plant" readable without clicking through four separate tabs first.

**AI-forward design:** unlike other dashboards where AI is one section among several, this screen treats the AI summary row as equally prominent as the factual status header — reflecting the product's core differentiation (per BRD Product Vision: "health issues are caught before they're visible to the human eye"). Each AI summary card is tappable directly into its full tab (PG-26) rather than requiring TabNav navigation first.

## 4. Inventory Dashboard (PG-36, dashboard-style list view)

**Audience:** Marcus (Branch Manager), Owner/Admin. **Design intent:** surface what needs action (low stock) without burying it in a flat list of everything in stock.

**Layout composition:** a "needs attention" StatCard/banner at the top when low-stock items exist (dismissible only by resolving the underlying items, not by clicking away — this is intentionally persistent, distinct from a Toast), followed by the full DataTable with the low-stock filter available but not applied by default (so the manager sees the full picture, with attention-needed items visually flagged via StatusBadge within the table rather than hidden until filtered).

## 5. Sales Dashboard (Sales History summary, PG-40 top section)

**Audience:** Marcus (Branch Manager), Renata (Owner, via drill-down). **Design intent:** trend-and-total view over a selected period, feeding into (but distinct from) the transactional POS screen.

**Layout composition:** date-range selector at top (defaulting to "Today" for Marcus's end-of-day journey, per `docs/ux/02-user-journey-maps.md`), summary StatCards (Total Sales, Transaction Count, Average Sale Value) reacting to the selected range, followed by the sortable/filterable transaction DataTable below.

## 6. Analytics Dashboard (Reports Hub context, PG-51 + cross-references to PG-32/18-analytics-workflow.md)

**Audience:** Renata (Owner), Org Admin. **Design intent:** this is not a single screen but a composed experience across PG-51 (entry), PG-32 (revenue-specific deep dive), and report exports (PG-52) — the "Analytics Dashboard" as a concept is realized through this cluster rather than one monolithic screen, consistent with `docs/ux/18-analytics-workflow.md`'s distinction between fast pre-aggregated dashboard reads and flexible, async, deeper report queries. Design implication: PG-51's report-type cards each carry a small live preview stat (e.g., the Revenue card shows the current-period total inline) so the hub itself has some dashboard value even before a full report is generated.

## 7. AI Dashboard (PG-31 AI Predictions Dashboard)

**Audience:** Renata (Owner), Marcus (Branch Manager). **Design intent:** a ranked, explained worklist — this dashboard's entire design point is that a bare score is not enough; every entry must show *why*.

**Layout composition:** the ranked at-risk plant list is the dominant element (not competing with unrelated widgets on the same screen) — each row shows the plant, its HealthRiskBadge with ConfidenceIndicator, and the single top contributing factor inline (with an expand for the full AIExplanationPanel), so a manager can triage the list without opening every plant individually. A secondary growth-trend summary widget sits below, lower-priority than the risk list per the product's stated goal of reducing preventable plant loss (BRD Goal 1) — risk-avoidance ranks above growth-trend-awareness in this dashboard's visual hierarchy.

**Trust-building design pattern (applies across all AI surfaces, most visible here):** every AI-sourced number on this dashboard is visually distinguished via the AI accent color (per `01-design-system.md` §1) and never presented with the same visual weight/certainty as a factual StatusBadge — this is a deliberate, consistent design rule, not just a component-level detail, because the product's credibility depends on users never confusing "the AI thinks" with "this is confirmed."
