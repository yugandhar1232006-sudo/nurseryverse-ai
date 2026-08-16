# UI State Documentation

Every state a screen or component can be in, defined once here as the canonical behavior — `03-screen-specifications.md` references these patterns per page rather than redefining them. Components implementing each state are named per `02-component-library.md`.

## 1. Loading

**Initial page load:** full-page or section-level SkeletonLoader matching the eventual content's shape (never a generic centered spinner for content that has a known layout — per component spec, skeleton is preferred over spinner for list/table/card content).
**Inline action loading (button click):** Button enters its loading state (spinner replaces label, width preserved, disabled to prevent double-submit).
**Background/async loading (report export, batch forecast):** ProgressState, non-blocking — user can navigate away and be notified on completion (per `docs/ux/11-data-flow-diagrams.md` §5).
**Rule:** loading states never block the entire app shell (Header/Sidebar remain interactive) except during initial auth resolution on first load.

## 2. Empty

**First-use empty (no data exists yet):** EmptyState with an onboarding-flavored illustration/copy and a primary creation action — always actionable, never just "nothing here."
**Filtered-empty (data exists, current filters return nothing):** distinct EmptyState variant — "No results match your filters" with a "Clear filters" action, not a creation CTA (creating a new record isn't the right next step when the user was searching for an existing one).
**Positive empty (task list fully cleared — PG-08, PG-34, PG-33):** a deliberately rewarding variant ("All caught up," "No active recommendations") — distinct tone from the neutral first-use/filtered variants, since an empty task list is a good outcome.
**Rule:** every empty state names the reason (no data vs. filtered vs. cleared) — a single generic "No data" message is never used across these three distinct situations.

## 3. Error

**Field-level validation error:** inline message directly beneath the field, red/`danger` token, appears on blur or submit (not on every keystroke — avoid punishing the user mid-typing).
**Section-level error (one widget/panel fails to load):** ErrorState scoped to that section only; rest of the page remains usable (NFR-3.3 graceful degradation — most visible on dashboards where an AI widget failing shouldn't take down the whole page).
**Full-page error (critical failure, e.g., entity not found or fatal fetch failure):** full-page ErrorState with a retry action and, where sensible, a link back to the parent list.
**Mutation error (save/submit failed):** Toast (error variant) + the form remains populated with the user's input intact (never clear a form on a failed submit).
**AI-module-specific error:** a distinct message pattern ("AI Disease Detection is temporarily unavailable — try again") rather than a generic error, plus a manual fallback path where one exists (e.g., manually creating a Disease Report when the scan itself is down) — per NFR-3.3's graceful-degradation requirement.
**Rule:** error messages are always plain-language and actionable (NFR-6.2) — never a raw exception string or status code shown to the user; technical detail goes to logging (NFR-10.1), not the UI.

## 4. Offline

**Detection:** a persistent, dismissible-but-reappearing banner at the top of the app shell when connectivity is lost ("You're offline — changes won't be saved until you're back online"), not a silent failure per action.
**Read access:** already-loaded data (current page's content) remains viewable while offline; navigation to un-cached pages shows the offline banner plus an explanation rather than a generic load failure.
**Write access:** mutating actions (forms, quick-logs) are disabled with an inline explanation while offline rather than allowed to fail silently — this matters specifically for Priya's field-logging workflow, where a plant photo/health log submitted with no connectivity must not be silently lost. v1 does not implement full offline queueing/sync (noted as an explicit v1 limitation, not a gap — offline-first field logging is a candidate for the v2 roadmap per BRD §10); v1's behavior is "clearly blocked with an honest message," not "appears to work, silently fails."
**Reconnection:** banner clears automatically on reconnect; any screen with stale data auto-refreshes or shows a "reconnected — refresh to see the latest" prompt.

## 5. Success

**Mutation success:** Toast (success variant), auto-dismissing after a reasonable reading window, non-blocking.
**Multi-step flow completion (e.g., PG-21 create plant, PG-02 signup):** a dedicated success moment rather than just a toast — e.g., PG-21 redirects to the new plant's twin with its QR code prominently displayed, not just a generic "Plant created" toast, because that QR code is immediately actionable (print it now).
**Destructive-action success (void, deactivate, delete):** Toast confirming what happened, phrased specifically ("Invoice voided," not generic "Success") since these actions have real consequences worth confirming precisely.
**Optimistic updates:** for low-risk, easily reversible actions (marking a notification read, dismissing a recommendation), the UI updates immediately without waiting for server confirmation, with silent rollback + error toast only if the request ultimately fails.

## 6. Validation

**Real-time format validation** (email, phone, numeric ranges): on blur, not on every keystroke.
**Cross-field validation** (e.g., date range end ≥ start, min ≤ max in Species care ranges): evaluated on blur of the second relevant field, error attached to the field most likely at fault (the one edited last).
**Server-side-only validation** (uniqueness checks, plan-limit checks, permission ceiling checks): surfaced as a field or form-level error only after submit, clearly distinguished from client-side format errors as "we checked with the server and..." level detail — plan-limit and permission-ceiling errors specifically get a distinct visual treatment (an upgrade-prompt or explanation card rather than a plain red field error) since they're not something the user can fix by typing differently.
**Required-field indication:** required fields are marked at the label level (not just enforced on submit), consistent with `01-design-system.md`'s always-visible-label rule.

## 7. AI Processing

**Short synchronous inference (disease scan, single water recommendation — target ≤5s per NFR-1.2):** the AI-thinking motion pattern (per `01-design-system.md` §9), `aria-live="polite"` announced, result replaces the thinking state in place (no jarring layout jump).
**Long asynchronous inference (revenue forecast batch, org-wide survival re-scan):** ProgressState or a "processing, we'll notify you" pattern — user is never made to wait on a blocking spinner for a multi-minute operation.
**Stale prediction indicator:** any AI result older than its module's expected refresh interval is visually flagged (per HealthRiskBadge's "stale" state) rather than silently presented as current.
**AI unavailable:** per Error §3 above — module-specific message, manual fallback where one exists, rest of the page unaffected.

## 8. Upload Progress

**Single-file upload (plant photo):** inline progress bar within the PhotoUpload component, thumbnail preview appears once upload completes, retry action on failure without losing the selected file.
**Multi-file/batch context** (rare in v1, e.g., multiple growth photos): per-file progress within a list, independent success/failure per file (one failed upload doesn't block the others from completing).
**Size/type validation:** checked client-side before upload begins (immediate feedback, no wasted upload attempt) and re-validated server-side (NFR-4.5) — a server-side rejection after upload shows a clear, specific reason ("File exceeds 10MB limit"), not a generic failure.

## 9. Notification States

**Unread:** visually emphasized (bold text + dot indicator, not color alone per NFR-7.2) within NotificationListItem.
**Read:** de-emphasized, remains in the list (notifications are not deleted on read).
**Real-time arrival:** new notifications animate into the NotificationCenter list and increment the header bell badge live via WebSocket (per `docs/ux/11-data-flow-diagrams.md` §4) — no manual refresh needed.
**Actioned (deep-linked, action taken from the notification):** marked read automatically on click-through.
**Escalated (per `docs/ux/14-notification-workflow.md`'s escalation model, v1.1):** visually distinguished as "escalated" if/when that feature ships — flagged here so the notification state model already accommodates it without redesign.
