# Complete Page Inventory

Every page from `01-sitemap.md`, fully specified. Permission codes reference `07-role-permission-matrix.md`. This is the contract Phase 3 (UI/UX Design) and Phase 4 (Architecture) build against — API dependencies here are logical operations, not final endpoint paths (those are fixed in Phase 4/6).

---

## Public

### PG-01 Landing / Marketing Page
- **Purpose:** Explain the product, drive signups; not part of the authenticated app.
- **Users:** Anonymous visitors (prospective Owners).
- **Entry points:** Direct URL, marketing links.
- **Exit points:** PG-02 Sign Up, PG-03 Log In.
- **Key components:** Hero, feature highlights, pricing tier summary, CTA buttons.
- **API dependencies:** None (static content) or a lightweight public plans endpoint.
- **DB entities:** None.
- **AI dependencies:** None.
- **Validation rules:** N/A.
- **Permissions:** Public, no auth required.

### PG-02 Sign Up
- **Purpose:** Create a new Org + Owner account (US-A.1).
- **Users:** Prospective Owner.
- **Entry points:** PG-01, direct link.
- **Exit points:** PG-07 Org Dashboard (on success, guided empty state).
- **Key components:** Multi-step form (account info → org name → first branch), plan selector.
- **API dependencies:** `POST /auth/signup`, `POST /orgs`, `POST /branches`.
- **DB entities:** `users`, `nurseries`, `branches`, `roles`.
- **AI dependencies:** None.
- **Validation rules:** Valid email (unique), password strength policy, required org/branch name fields.
- **Permissions:** Public, no auth required; creates the `owner` role for the new user.

### PG-03 Log In
- **Purpose:** Authenticate an existing user.
- **Users:** All roles.
- **Entry points:** PG-01, direct link, session expiry redirect.
- **Exit points:** Role-appropriate dashboard (PG-07 or PG-08).
- **Key components:** Email/password form, "forgot password" link.
- **API dependencies:** `POST /auth/login`.
- **DB entities:** `users`.
- **AI dependencies:** None.
- **Validation rules:** Required fields; generic error message on failure (no user-enumeration leak).
- **Permissions:** Public, no auth required.

### PG-04 Forgot Password
- **Purpose:** Initiate password reset (US-A.3).
- **Users:** All roles.
- **Entry points:** PG-03.
- **Exit points:** Confirmation state ("check your email"); PG-05 via emailed link.
- **Key components:** Email input form.
- **API dependencies:** `POST /auth/password-reset/request`.
- **DB entities:** `users`, `password_reset_tokens`.
- **AI dependencies:** None.
- **Validation rules:** Same generic confirmation shown whether or not the email exists (no enumeration).
- **Permissions:** Public.

### PG-05 Reset Password
- **Purpose:** Set a new password via emailed token.
- **Users:** All roles.
- **Entry points:** Emailed reset link only.
- **Exit points:** PG-03 (log in with new password).
- **Key components:** New password + confirm form.
- **API dependencies:** `POST /auth/password-reset/confirm`.
- **DB entities:** `users`, `password_reset_tokens`.
- **AI dependencies:** None.
- **Validation rules:** Token must be valid/unexpired/single-use; password strength policy; invalidates all existing sessions on success.
- **Permissions:** Public (token-gated).

### PG-06 Accept Invite
- **Purpose:** Employee accepts an org invite and sets up access (US-A.2).
- **Users:** Invited employee (any staff role).
- **Entry points:** Emailed invite link only.
- **Exit points:** PG-08 Branch Dashboard.
- **Key components:** Set-password form (new users) or confirm-and-login (existing account email).
- **API dependencies:** `POST /auth/invite/accept`.
- **DB entities:** `users`, `employees`, `invites`, `role_assignments`.
- **AI dependencies:** None.
- **Validation rules:** Invite token valid/unexpired; password policy for new accounts.
- **Permissions:** Public (token-gated); role/branch scope pre-set by the inviter.

---

## Core

### PG-07 Org Dashboard
- **Purpose:** Cross-branch business overview (US-B.2).
- **Users:** Owner, Org Admin.
- **Entry points:** Login redirect, sidebar "Dashboard."
- **Exit points:** Drill into any branch (PG-08), Plants (PG-20), AI Predictions (PG-31), Reports (PG-51).
- **Key components:** Per-branch summary cards (revenue, inventory alerts, AI risk flags), org-wide revenue chart, recent activity feed, notification summary.
- **API dependencies:** `GET /orgs/{id}/dashboard-summary`, `GET /branches?org_id=`, `GET /ai/predictions/summary`.
- **DB entities:** `nurseries`, `branches`, `sales`, `inventory`, `ai_predictions`, `notifications`.
- **AI dependencies:** Survival risk summary (FR-8.3), revenue forecast preview (FR-8.5).
- **Validation rules:** N/A (read-only view).
- **Permissions:** `org:read`.

### PG-08 Branch Dashboard
- **Purpose:** Single-branch daily operational overview (US-B.1, Marcus's journey).
- **Users:** Branch Manager, Horticulturist, Sales Staff (reduced widget set for Staff).
- **Entry points:** Login redirect (default for non-admin roles), branch switcher, sidebar "Dashboard."
- **Exit points:** Watering (PG-34), Inventory (PG-36), Disease Reports (PG-29), Sales (PG-39, PG-40).
- **Key components:** Today's task list (watering due, low stock, disease reports pending review), sales-today summary, quick-action buttons.
- **API dependencies:** `GET /branches/{id}/dashboard-summary`, `GET /watering/tasks?branch_id=`, `GET /inventory?branch_id=&low_stock=true`.
- **DB entities:** `branches`, `watering_logs`, `inventory`, `disease_reports`, `sales`.
- **AI dependencies:** Watering schedule recommendations (FR-8.4).
- **Validation rules:** N/A (read-only view).
- **Permissions:** `branch:read`, `plants:read` (own branch, `B` scope).

### PG-09 Notification Center
- **Purpose:** View and manage all notifications (FR-17).
- **Users:** All roles.
- **Entry points:** Header bell icon (any page).
- **Exit points:** Deep-links into the triggering entity (e.g., a disease notification opens PG-30).
- **Key components:** Notification list (grouped by category), read/unread state, mark-all-read, link to Notification Preferences (PG-58).
- **API dependencies:** `GET /notifications`, `PATCH /notifications/{id}/read`.
- **DB entities:** `notifications`.
- **AI dependencies:** None directly (notifications may reference AI-triggered events).
- **Validation rules:** N/A.
- **Permissions:** `notifications:read` (own-user scoped).

### PG-10 AI Assistant
- **Purpose:** Conversational query/action interface (US-E.5, US-E.6).
- **Users:** All roles (query scope varies; write-confirmation scope per role, see permission matrix).
- **Entry points:** Header chat icon (any page).
- **Exit points:** Deep-links into referenced entities from assistant responses; stays open as a persistent panel.
- **Key components:** Chat thread, message composer, proposed-action confirmation card, source/data citation on answers.
- **API dependencies:** `POST /ai/assistant/message`, `POST /ai/assistant/actions/{id}/confirm`.
- **DB entities:** `ai_assistant_conversations`, `ai_assistant_messages` (read access spans nearly every entity per role scope).
- **AI dependencies:** LLM-backed conversational engine with tool-calling into internal services (FR-9.1–9.3).
- **Validation rules:** Any proposed write action re-validates against the same rules as its native page (e.g., a proposed watering log follows PG-35's validation) before it can be confirmed.
- **Permissions:** `ai_assistant:use`; `ai_assistant:confirm_write` gates whether proposed actions can be confirmed vs. read-only.

---

## Organization & Branches

### PG-11 Branches List
- **Purpose:** View/manage all branches in the Org (US-B.1).
- **Users:** Owner, Org Admin.
- **Entry points:** Sidebar Settings → Branches.
- **Exit points:** PG-12 (view/edit), PG-13 (create).
- **Key components:** Branch table (name, address, employee count, status), "Add Branch" button.
- **API dependencies:** `GET /branches`.
- **DB entities:** `branches`.
- **AI dependencies:** None.
- **Validation rules:** N/A.
- **Permissions:** `branch:read`.

### PG-12 Branch Detail / Settings
- **Purpose:** View/edit a single branch's profile and operational settings (FR-2.3, FR-20.2).
- **Users:** Owner, Org Admin (full), Branch Manager (own branch only).
- **Entry points:** PG-11, branch switcher "manage."
- **Exit points:** PG-11 (back), PG-14 (filtered to this branch).
- **Key components:** Branch profile form, timezone/threshold settings, employee roster preview, deactivate-branch action (confirmation required, NFR-6.3).
- **API dependencies:** `GET /branches/{id}`, `PATCH /branches/{id}`, `DELETE /branches/{id}` (soft delete).
- **DB entities:** `branches`.
- **AI dependencies:** None.
- **Validation rules:** Required name/address; timezone must be valid IANA identifier; deactivation requires typed confirmation.
- **Permissions:** `branch:read` to view, `branch:write` to edit, `branch:delete` to deactivate.

### PG-13 Create / Edit Branch
- **Purpose:** Add a new branch to the Org (FR-2.2).
- **Users:** Owner, Org Admin.
- **Entry points:** PG-11 "Add Branch."
- **Exit points:** PG-12 (new branch detail) on success.
- **Key components:** Branch profile form (name, address, timezone, initial thresholds).
- **API dependencies:** `POST /branches`.
- **DB entities:** `branches`.
- **AI dependencies:** None.
- **Validation rules:** Required name/address; plan branch-limit enforced server-side (BRD §5 tier limits).
- **Permissions:** `branch:write`.

---

## Employees

### PG-14 Employees List
- **Purpose:** View/manage staff (FR-3).
- **Users:** Owner, Org Admin (all branches), Branch Manager (own branch).
- **Entry points:** Sidebar Settings → Employees.
- **Exit points:** PG-15, PG-16.
- **Key components:** Employee table (name, role, branch(es), status), "Invite Employee" button, filters by branch/role.
- **API dependencies:** `GET /employees`.
- **DB entities:** `employees`, `users`, `role_assignments`.
- **AI dependencies:** None.
- **Validation rules:** N/A.
- **Permissions:** `employees:read`.

### PG-15 Employee Detail
- **Purpose:** View/edit an employee's role, branch assignment, and status (FR-3.3).
- **Users:** Owner, Org Admin, Branch Manager (own branch, non-admin roles only).
- **Entry points:** PG-14.
- **Exit points:** PG-14 (back).
- **Key components:** Profile summary, role/branch assignment editor, deactivate action (confirmation required).
- **API dependencies:** `GET /employees/{id}`, `PATCH /employees/{id}`, `POST /employees/{id}/deactivate`.
- **DB entities:** `employees`, `role_assignments`, `audit_logs` (deactivation logged).
- **AI dependencies:** None.
- **Validation rules:** Cannot deactivate the sole remaining Owner/Admin; role change validated against permission ceiling of the assigning user.
- **Permissions:** `employees:write`.

### PG-16 Invite Employee
- **Purpose:** Invite a new staff member (US-A.2).
- **Users:** Owner, Org Admin, Branch Manager (limited to non-admin roles).
- **Entry points:** PG-14 "Invite Employee."
- **Exit points:** PG-14 (back, pending-invite state shown).
- **Key components:** Email + role + branch(es) form.
- **API dependencies:** `POST /employees/invite`.
- **DB entities:** `invites`, `role_assignments`.
- **AI dependencies:** None.
- **Validation rules:** Valid email; role selectable is capped by the inviter's own permission ceiling; plan seat-limit enforced server-side (Starter tier).
- **Permissions:** `employees:write`.

---

## Species Catalog

### PG-17 Species List
- **Purpose:** Browse the org-wide species catalog (FR-4).
- **Users:** Owner, Org Admin, Branch Manager (full); Horticulturist, Sales Staff (read).
- **Entry points:** Sidebar (under Plants or Settings, per nav grouping).
- **Exit points:** PG-18, PG-19.
- **Key components:** Searchable/filterable species table, "Add Species" button.
- **API dependencies:** `GET /species`.
- **DB entities:** `species`.
- **AI dependencies:** None.
- **Validation rules:** N/A.
- **Permissions:** `species:read`.

### PG-18 Species Detail
- **Purpose:** View/edit a species' care requirements and reference data (FR-4.1).
- **Users:** Owner, Org Admin, Branch Manager.
- **Entry points:** PG-17, linked from PG-22 (a plant's species reference).
- **Exit points:** PG-17 (back).
- **Key components:** Care-requirement fields (light, water baseline, soil, temperature range), typical growth curve chart, known disease susceptibilities list, linked plants count.
- **API dependencies:** `GET /species/{id}`, `PATCH /species/{id}`.
- **DB entities:** `species`.
- **AI dependencies:** Growth curve baseline informs FR-8.2 growth prediction; disease susceptibility list informs FR-8.1 disease detection prior.
- **Validation rules:** Required botanical name (unique per org); numeric ranges must be internally consistent (min ≤ max).
- **Permissions:** `species:read` to view, `species:write` to edit.

### PG-19 Create / Edit Species
- **Purpose:** Add a new species to the catalog.
- **Users:** Owner, Org Admin, Branch Manager.
- **Entry points:** PG-17 "Add Species."
- **Exit points:** PG-18 (new species detail) on success.
- **Key components:** Same form as PG-18's edit mode.
- **API dependencies:** `POST /species`.
- **DB entities:** `species`.
- **AI dependencies:** None.
- **Validation rules:** Same as PG-18.
- **Permissions:** `species:write`.

---

## Plants (Digital Twin)

### PG-20 Plants List
- **Purpose:** Browse/search all individually tracked plants (FR-5).
- **Users:** Owner, Org Admin, Branch Manager, Horticulturist (full within scope); Sales Staff (read).
- **Entry points:** Sidebar "Plants," global search results, QR scan (mobile FAB) resolving to a specific plant.
- **Exit points:** PG-21, PG-22.
- **Key components:** Filterable/searchable plant table or card grid (species, status, branch, health flag badge), "Add Plant" button, bulk-filter by AI risk flag.
- **API dependencies:** `GET /plants?branch_id=&status=&species_id=`.
- **DB entities:** `plants`, `species`, `branches`.
- **AI dependencies:** Health/risk badge sourced from latest `ai_predictions` per plant.
- **Validation rules:** N/A.
- **Permissions:** `plants:read`.

### PG-21 Create Plant
- **Purpose:** Register a new individual plant and generate its Digital Twin (FR-5.1, FR-5.2).
- **Users:** Owner, Org Admin, Branch Manager, Horticulturist.
- **Entry points:** PG-20 "Add Plant."
- **Exit points:** PG-22 (new plant's digital twin) on success, showing the generated QR code.
- **Key components:** Species selector (or inline create), branch/zone selector, initial photo upload, initial measurement fields.
- **API dependencies:** `POST /plants`, `POST /plants/{id}/qr-code`.
- **DB entities:** `plants`, `plant_images`, `species`.
- **AI dependencies:** None at creation (predictions begin accumulating after first history entries).
- **Validation rules:** Required species and branch; image upload validated for type/size (NFR-4.5).
- **Permissions:** `plants:write`.

### PG-22 Plant Digital Twin Detail
- **Purpose:** The aggregated single-plant record — the system's core screen (FR-5.3, US-C.3).
- **Users:** Owner, Org Admin, Branch Manager, Horticulturist (full); Sales Staff (read, e.g., from POS lookup).
- **Entry points:** PG-20, QR scan, deep-link from notifications/reports/assistant.
- **Exit points:** Tabs PG-23/24/25/26; PG-27 Transfer; PG-28 Disease Detection; PG-53 Passport; PG-39 (add to sale, if status allows).
- **Key components:** Header (identity, QR code, current status badge), photo gallery, tab navigation, quick-action buttons (log growth, log health, scan disease, transfer, mark sold/deceased).
- **API dependencies:** `GET /plants/{id}` (aggregates growth/health/env/watering/predictions summaries).
- **DB entities:** `plants`, `species`, `plant_images`, `growth_timeline`, `health_history`, `environmental_readings`, `watering_logs`, `ai_predictions`.
- **AI dependencies:** Latest predictions across all AI modules for this plant, shown inline.
- **Validation rules:** Status transitions follow the lifecycle state machine (`13-digital-twin-lifecycle.md`) — invalid transitions (e.g., Sold → In Production) are blocked.
- **Permissions:** `plants:read`; action buttons individually gated by `growth:write`, `health:write`, `plants:transfer`, `passport:generate`, `sales:write`.

### PG-23 Growth Timeline (tab)
- **Purpose:** Chronological growth measurement history (FR-6).
- **Users:** Owner, Org Admin, Branch Manager, Horticulturist.
- **Entry points:** PG-22 tab.
- **Exit points:** Stays within PG-22; "log growth" opens inline form.
- **Key components:** Growth chart (height/spread over time), measurement list, "Log Growth" quick-add form.
- **API dependencies:** `GET /plants/{id}/growth-timeline`, `POST /plants/{id}/growth-timeline`.
- **DB entities:** `growth_timeline`.
- **AI dependencies:** Growth Prediction overlay (FR-8.2) shown alongside actuals.
- **Validation rules:** Numeric measurements ≥ 0; photo optional but validated if attached.
- **Permissions:** `growth:read`, `growth:write`.

### PG-24 Health History (tab)
- **Purpose:** Chronological health observations and disease reports for this plant (FR-7).
- **Users:** Owner, Org Admin, Branch Manager, Horticulturist.
- **Entry points:** PG-22 tab.
- **Exit points:** PG-30 (disease report detail), PG-28 (new scan).
- **Key components:** Health status timeline, linked disease reports list, "Log Health Observation" form.
- **API dependencies:** `GET /plants/{id}/health-history`, `POST /plants/{id}/health-history`.
- **DB entities:** `health_history`, `disease_reports`.
- **AI dependencies:** Survival risk score (FR-8.3) shown with contributing factors.
- **Validation rules:** Required status selection; notes free-text capped at a reasonable length.
- **Permissions:** `health:read`, `health:write`.

### PG-25 Environmental & Watering (tab)
- **Purpose:** Environmental readings and watering log for this plant/zone (FR-10, FR-11).
- **Users:** Owner, Org Admin, Branch Manager, Horticulturist.
- **Entry points:** PG-22 tab.
- **Exit points:** PG-35 (log watering event modal).
- **Key components:** Environmental readings chart, watering event list, next-due indicator.
- **API dependencies:** `GET /plants/{id}/environmental-readings`, `GET /plants/{id}/watering-logs`, `POST .../watering-logs`.
- **DB entities:** `environmental_readings`, `watering_logs`.
- **AI dependencies:** Water Recommendation schedule (FR-8.4).
- **Validation rules:** Numeric readings within plausible sensor ranges; watering volume ≥ 0.
- **Permissions:** `environmental:read`/`write`, `watering:read`/`write`.

### PG-26 AI Predictions (tab)
- **Purpose:** All AI predictions ever generated for this plant, current and historical (FR-8.8).
- **Users:** Owner, Org Admin, Branch Manager, Horticulturist.
- **Entry points:** PG-22 tab.
- **Exit points:** PG-28 (trigger a new disease scan).
- **Key components:** Prediction cards per module (disease, growth, survival, water) with confidence, explanation, model version, and history toggle.
- **API dependencies:** `GET /plants/{id}/ai-predictions`.
- **DB entities:** `ai_predictions`.
- **AI dependencies:** All plant-level AI modules (FR-8.1–8.4).
- **Validation rules:** N/A (read view).
- **Permissions:** `ai_predictions:read`.

### PG-27 Transfer Plant (modal)
- **Purpose:** Move a plant to a different Branch (FR-5.5, US-C.4).
- **Users:** Owner, Org Admin, Branch Manager.
- **Entry points:** PG-22 quick action.
- **Exit points:** Closes back to PG-22 (updated branch shown).
- **Key components:** Destination branch selector, optional note.
- **API dependencies:** `POST /plants/{id}/transfer`.
- **DB entities:** `plants`, `plant_transfers` (history), `inventory` (both branches' counts if applicable).
- **AI dependencies:** None.
- **Validation rules:** Destination must be an active branch different from current; user must have `plants:write` on both source and destination branches.
- **Permissions:** `plants:transfer`.

---

## Disease & Health

### PG-28 AI Disease Detection Scan
- **Purpose:** Submit a plant photo for AI disease analysis (FR-8.1, US-E.1).
- **Users:** Owner, Org Admin, Branch Manager, Horticulturist.
- **Entry points:** PG-22 quick action, PG-24 tab.
- **Exit points:** PG-30 (if a report is drafted), back to PG-22.
- **Key components:** Camera/upload capture, in-progress state (≤5s target, NFR-1.2), result card (condition, confidence, recommended action).
- **API dependencies:** `POST /ai/disease-detection/scan`.
- **DB entities:** `plant_images`, `ai_predictions`, `disease_reports` (if auto-drafted).
- **AI dependencies:** Disease Detection CNN module (Phase 8/AI architecture).
- **Validation rules:** Image required, type/size validated (NFR-4.5); result always persisted before being shown (FR-8.7 — no un-logged AI output).
- **Permissions:** `disease:write`, `ai_predictions:run`.

### PG-29 Disease Reports List
- **Purpose:** Track all disease reports across a branch/org (FR-7.2).
- **Users:** Owner, Org Admin, Branch Manager, Horticulturist.
- **Entry points:** Sidebar (under Plants/AI Center), PG-08 dashboard task list.
- **Exit points:** PG-30.
- **Key components:** Filterable table (status: pending review, confirmed, treated, resolved; severity).
- **API dependencies:** `GET /disease-reports?branch_id=&status=`.
- **DB entities:** `disease_reports`.
- **AI dependencies:** Reports originated from AI carry a source flag.
- **Validation rules:** N/A.
- **Permissions:** `disease:read`.

### PG-30 Disease Report Detail
- **Purpose:** Review, confirm/dismiss, and track treatment of a disease report (FR-7.2, FR-7.3, US-D.4).
- **Users:** Owner, Org Admin, Branch Manager, Horticulturist.
- **Entry points:** PG-29, PG-28 (auto-drafted), notification deep-link.
- **Exit points:** PG-22 (linked plant), PG-29 (back).
- **Key components:** AI evidence panel (photo, condition, confidence), confirm/dismiss actions, treatment log form, outcome selector.
- **API dependencies:** `GET /disease-reports/{id}`, `PATCH /disease-reports/{id}`, `POST /disease-reports/{id}/treatments`.
- **DB entities:** `disease_reports`, `treatments`, `notifications` (triggered on confirm).
- **AI dependencies:** Original detection result; dismissal is logged as model feedback for future retraining.
- **Validation rules:** Outcome selection required to close a report; treatment entries require a description.
- **Permissions:** `disease:approve` to confirm/dismiss, `health:write` to log treatment.

---

## AI Predictions Center

### PG-31 AI Predictions Dashboard
- **Purpose:** Cross-plant AI overview — survival risk, growth summaries (US-E.3).
- **Users:** Owner, Org Admin, Branch Manager (full); Horticulturist (read).
- **Entry points:** Sidebar "AI Center," PG-07/08 dashboard drill-in.
- **Exit points:** PG-22 (specific plant), PG-32, PG-33.
- **Key components:** Ranked at-risk plant list with contributing factors, growth-trend summary, filter by branch/species.
- **API dependencies:** `GET /ai/predictions/survival-risk?branch_id=`, `GET /ai/predictions/growth-summary`.
- **DB entities:** `ai_predictions`, `plants`.
- **AI dependencies:** Survival Prediction (FR-8.3), Growth Prediction (FR-8.2).
- **Validation rules:** N/A (read view).
- **Permissions:** `ai_predictions:read`.

### PG-32 Revenue Forecast
- **Purpose:** Branch/org revenue projection (FR-8.5, US-E.2).
- **Users:** Owner, Org Admin (org + branch level); Branch Manager (own branch).
- **Entry points:** PG-31, sidebar AI Center.
- **Exit points:** PG-51 (export as report).
- **Key components:** Forecast chart with confidence interval, historical-vs-projected comparison, branch selector.
- **API dependencies:** `GET /ai/predictions/revenue-forecast?branch_id=`.
- **DB entities:** `ai_predictions`, `sales`.
- **AI dependencies:** Revenue Forecast module (Prophet-based time series).
- **Validation rules:** N/A (read view).
- **Permissions:** `ai_predictions:read` (branch-scoped for Branch Manager).

### PG-33 Recommendation Feed
- **Purpose:** Prioritized, explained AI action suggestions (FR-8.6, US-E.3).
- **Users:** Owner, Org Admin, Branch Manager.
- **Entry points:** PG-31, sidebar AI Center.
- **Exit points:** Deep-links into the relevant plant/inventory/task screen per recommendation.
- **Key components:** Card list (recommendation text, explanation, priority, action button), dismiss/snooze controls.
- **API dependencies:** `GET /ai/recommendations?branch_id=`, `POST /ai/recommendations/{id}/dismiss`.
- **DB entities:** `ai_recommendations`, `ai_predictions`.
- **AI dependencies:** Recommendation Engine (feature-weighted scoring + LLM narrative, FR-8.6).
- **Validation rules:** N/A.
- **Permissions:** `ai_predictions:read`.

---

## Watering

### PG-34 Watering Schedule / Tasks
- **Purpose:** Daily/upcoming watering tasks, AI-recommended (FR-11.2, US-E.4).
- **Users:** Owner, Org Admin, Branch Manager, Horticulturist.
- **Entry points:** Sidebar "Watering," PG-08 dashboard task list.
- **Exit points:** PG-35, PG-22 (specific plant).
- **Key components:** Task list grouped by zone/branch, overdue-highlighted items, "Log Watering" quick action.
- **API dependencies:** `GET /watering/tasks?branch_id=`.
- **DB entities:** `watering_logs`, `plants`, `environmental_readings`.
- **AI dependencies:** Water Recommendation module (FR-8.4).
- **Validation rules:** N/A (task list view).
- **Permissions:** `watering:read`.

### PG-35 Log Watering Event (modal)
- **Purpose:** Record a watering event (FR-11.1, US-D.5).
- **Users:** Owner, Org Admin, Branch Manager, Horticulturist.
- **Entry points:** PG-34, PG-25.
- **Exit points:** Closes back to origin screen.
- **Key components:** Plant/zone selector (pre-filled if launched from context), volume/duration field, notes.
- **API dependencies:** `POST /watering-logs`.
- **DB entities:** `watering_logs`.
- **AI dependencies:** Triggers schedule recalculation (FR-8.4).
- **Validation rules:** Target plant/zone required; volume ≥ 0.
- **Permissions:** `watering:write`.

---

## Inventory

### PG-36 Inventory List
- **Purpose:** Manage bulk stock (FR-12).
- **Users:** Owner, Org Admin, Branch Manager (full); Horticulturist, Sales Staff (read).
- **Entry points:** Sidebar "Inventory."
- **Exit points:** PG-37, PG-38.
- **Key components:** Filterable table (species/product, quantity, branch, low-stock badge), "Adjust Stock" quick action.
- **API dependencies:** `GET /inventory?branch_id=&low_stock=`.
- **DB entities:** `inventory`.
- **AI dependencies:** None directly (informs Recommendation Engine).
- **Validation rules:** N/A.
- **Permissions:** `inventory:read`.

### PG-37 Inventory Item Detail
- **Purpose:** View a single inventory line's detail and history (FR-12.4).
- **Users:** Owner, Org Admin, Branch Manager.
- **Entry points:** PG-36.
- **Exit points:** PG-38, PG-36 (back).
- **Key components:** Quantity/threshold display, adjustment history, linked purchase orders and sales.
- **API dependencies:** `GET /inventory/{id}`, `GET /inventory/{id}/history`.
- **DB entities:** `inventory`, `inventory_adjustments`, `purchase_order_items`, `sale_items`.
- **AI dependencies:** None.
- **Validation rules:** N/A (read view; edits go through PG-38).
- **Permissions:** `inventory:read`.

### PG-38 Adjust Stock (modal)
- **Purpose:** Manually adjust inventory quantity (e.g., damage, correction) (FR-12.1).
- **Users:** Owner, Org Admin, Branch Manager.
- **Entry points:** PG-36, PG-37.
- **Exit points:** Closes back to origin screen.
- **Key components:** Quantity delta field, reason selector, notes.
- **API dependencies:** `POST /inventory/{id}/adjust`.
- **DB entities:** `inventory`, `inventory_adjustments`, `audit_logs`.
- **AI dependencies:** None.
- **Validation rules:** Resulting quantity cannot go below 0; reason required.
- **Permissions:** `inventory:adjust`.

---

## Sales / POS

### PG-39 POS / New Sale
- **Purpose:** Ring up a sale (FR-13, US-F.1, US-F.2).
- **Users:** Owner, Org Admin, Branch Manager, Sales Staff.
- **Entry points:** Sidebar "Sales," dashboard quick action.
- **Exit points:** PG-41 (receipt) on completion, PG-42 (customer lookup/create), PG-46 (invoice, if wholesale).
- **Key components:** QR scan/search item entry, cart, customer attach field, discount field, payment method selector, complete-sale button.
- **API dependencies:** `POST /sales`, `GET /plants/{id}` (scan lookup), `GET /inventory/{id}` (scan lookup).
- **DB entities:** `sales`, `sale_items`, `plants`, `inventory`, `customers`.
- **AI dependencies:** None.
- **Validation rules:** Real-time availability check blocks unavailable items (FR-13.2); at least one line item required to complete.
- **Permissions:** `sales:write`.

### PG-40 Sales History
- **Purpose:** Browse past sales (FR-13, Marcus's end-of-day review).
- **Users:** Owner, Org Admin, Branch Manager (full); Sales Staff (own sales, branch-scoped).
- **Entry points:** Sidebar "Sales" → History tab.
- **Exit points:** PG-41, PG-46 (create invoice from selection).
- **Key components:** Filterable/sortable sales table, date-range summary totals.
- **API dependencies:** `GET /sales?branch_id=&date_from=&date_to=`.
- **DB entities:** `sales`, `sale_items`.
- **AI dependencies:** None directly (feeds Revenue Forecast).
- **Validation rules:** N/A.
- **Permissions:** `sales:read`.

### PG-41 Sale / Receipt Detail
- **Purpose:** View/print/email a single sale's receipt.
- **Users:** Owner, Org Admin, Branch Manager, Sales Staff.
- **Entry points:** PG-39 (on completion), PG-40.
- **Exit points:** PG-46 (generate invoice), PG-40 (back).
- **Key components:** Line-item summary, payment info, print/email actions, void action (Manager+ only).
- **API dependencies:** `GET /sales/{id}`, `POST /sales/{id}/void`, `POST /sales/{id}/receipt/email`.
- **DB entities:** `sales`, `sale_items`, `customers`.
- **AI dependencies:** None.
- **Validation rules:** Void requires reason and elevated permission; voided sales reverse inventory/plant status changes.
- **Permissions:** `sales:read`, `sales:void` (void action only).

---

## Customers

### PG-42 Customers List
- **Purpose:** Manage customer records (FR-14).
- **Users:** Owner, Org Admin, Branch Manager, Sales Staff.
- **Entry points:** Sidebar "Customers," PG-39 lookup.
- **Exit points:** PG-43.
- **Key components:** Searchable table (name, type retail/wholesale, last purchase), "Add Customer" button.
- **API dependencies:** `GET /customers?search=`.
- **DB entities:** `customers`.
- **AI dependencies:** None.
- **Validation rules:** N/A.
- **Permissions:** `customers:read`.

### PG-43 Customer Detail
- **Purpose:** View a customer's profile and purchase history (FR-14.2).
- **Users:** Owner, Org Admin, Branch Manager, Sales Staff.
- **Entry points:** PG-42, PG-39.
- **Exit points:** PG-41 (linked sales), PG-45 (linked invoices).
- **Key components:** Contact info form, classification toggle (retail/wholesale), purchase history list.
- **API dependencies:** `GET /customers/{id}`, `PATCH /customers/{id}`, `GET /customers/{id}/purchase-history`.
- **DB entities:** `customers`, `sales`, `invoices`.
- **AI dependencies:** None.
- **Validation rules:** Contact info format validation (email/phone); duplicate-customer warning on create.
- **Permissions:** `customers:read`, `customers:write`.

---

## Invoices

### PG-44 Invoices List
- **Purpose:** Track all invoices (FR-15.3).
- **Users:** Owner, Org Admin, Branch Manager, Sales Staff (create-scoped read).
- **Entry points:** Sidebar "Invoices."
- **Exit points:** PG-45, PG-46.
- **Key components:** Filterable table (status: draft/sent/paid/overdue/void), overdue highlight.
- **API dependencies:** `GET /invoices?branch_id=&status=`.
- **DB entities:** `invoices`.
- **AI dependencies:** None.
- **Validation rules:** N/A.
- **Permissions:** `invoices:read`.

### PG-45 Invoice Detail
- **Purpose:** View/manage a single invoice's status and content (FR-15.3, FR-15.4).
- **Users:** Owner, Org Admin, Branch Manager (full); Sales Staff (read/create only, no void).
- **Entry points:** PG-44, PG-41, PG-43.
- **Exit points:** PG-44 (back), PG-43 (customer).
- **Key components:** Line-item summary, terms, status timeline, mark-paid/void actions, resend action.
- **API dependencies:** `GET /invoices/{id}`, `PATCH /invoices/{id}/status`, `POST /invoices/{id}/resend`.
- **DB entities:** `invoices`, `invoice_items`, `sales`, `customers`.
- **AI dependencies:** None.
- **Validation rules:** Void requires reason (NFR-6.3); status transitions follow lifecycle (draft → sent → paid/overdue → void).
- **Permissions:** `invoices:read`, `invoices:write`, `invoices:void`.

### PG-46 Create Invoice
- **Purpose:** Generate an invoice from one or more sales (FR-15.1, US-F.4).
- **Users:** Owner, Org Admin, Branch Manager, Sales Staff (create only).
- **Entry points:** PG-40 (from selected sales), PG-41, PG-43.
- **Exit points:** PG-45 (new invoice) on success.
- **Key components:** Selected-sales summary, terms selector (net 30/60, PO reference), customer confirm, email-on-send toggle.
- **API dependencies:** `POST /invoices`.
- **DB entities:** `invoices`, `invoice_items`, `sales`, `customers`.
- **AI dependencies:** None.
- **Validation rules:** At least one sale selected; customer required; terms required if wholesale.
- **Permissions:** `invoices:write`.

---

## Suppliers & Purchasing

### PG-47 Suppliers List
- **Purpose:** Manage supplier records (FR-16.1).
- **Users:** Owner, Org Admin, Branch Manager.
- **Entry points:** Sidebar "Suppliers."
- **Exit points:** PG-48.
- **Key components:** Searchable table, "Add Supplier" button.
- **API dependencies:** `GET /suppliers`.
- **DB entities:** `suppliers`.
- **AI dependencies:** None.
- **Validation rules:** N/A.
- **Permissions:** `suppliers:read`.

### PG-48 Supplier Detail
- **Purpose:** View/edit supplier profile and order history.
- **Users:** Owner, Org Admin, Branch Manager.
- **Entry points:** PG-47.
- **Exit points:** PG-49 (filtered to this supplier), PG-47 (back).
- **Key components:** Contact/profile form, linked purchase orders list.
- **API dependencies:** `GET /suppliers/{id}`, `PATCH /suppliers/{id}`.
- **DB entities:** `suppliers`, `purchase_orders`.
- **AI dependencies:** None.
- **Validation rules:** Contact info format validation.
- **Permissions:** `suppliers:read`, `suppliers:write`.

### PG-49 Purchase Orders List
- **Purpose:** Track purchase orders (FR-16.2).
- **Users:** Owner, Org Admin, Branch Manager.
- **Entry points:** Sidebar "Suppliers" → Purchase Orders tab.
- **Exit points:** PG-50.
- **Key components:** Filterable table (status: draft/sent/partially received/received), "Create PO" button.
- **API dependencies:** `GET /purchase-orders?branch_id=&status=`.
- **DB entities:** `purchase_orders`.
- **AI dependencies:** None.
- **Validation rules:** N/A.
- **Permissions:** `purchase_orders:read`.

### PG-50 Purchase Order Detail / Create
- **Purpose:** Create/manage a PO and receive incoming stock (FR-16.2, FR-16.3).
- **Users:** Owner, Org Admin, Branch Manager.
- **Entry points:** PG-49, PG-48.
- **Exit points:** PG-36 (inventory updated on receipt), PG-49 (back).
- **Key components:** Line-item form (product/species, quantity, unit cost), supplier selector, receive-stock action (partial/full).
- **API dependencies:** `POST /purchase-orders`, `PATCH /purchase-orders/{id}`, `POST /purchase-orders/{id}/receive`.
- **DB entities:** `purchase_orders`, `purchase_order_items`, `inventory`, `suppliers`.
- **AI dependencies:** None.
- **Validation rules:** At least one line item; receive quantity cannot exceed ordered quantity; receiving updates inventory transactionally.
- **Permissions:** `purchase_orders:write`, `purchase_orders:receive`.

---

## Reports

### PG-51 Reports Hub
- **Purpose:** Entry point to all report types (FR-18).
- **Users:** Owner, Org Admin, Branch Manager.
- **Entry points:** Sidebar "Reports."
- **Exit points:** PG-52, PG-53.
- **Key components:** Report type cards (Inventory, Sales, Revenue, Plant Loss, AI Summary, Plant Passport), recent-exports list.
- **API dependencies:** `GET /reports/types`, `GET /reports/recent`.
- **DB entities:** `reports` (generated-report metadata).
- **AI dependencies:** AI Summary report type surfaces prediction-accuracy/disease-trend data (FR-18.3).
- **Validation rules:** N/A.
- **Permissions:** `reports:read`.

### PG-52 Report Export / Builder
- **Purpose:** Configure and generate a specific report export (FR-18.2).
- **Users:** Owner, Org Admin, Branch Manager.
- **Entry points:** PG-51.
- **Exit points:** Download/email result; back to PG-51.
- **Key components:** Filter form (date range, branch, category), format selector (PDF/Excel/CSV), generate button, progress state for long-running exports.
- **API dependencies:** `POST /reports/generate` (async, notifies on completion per NFR-1.2 pattern).
- **DB entities:** Varies by report type (`sales`, `inventory`, `plants`, `ai_predictions`).
- **AI dependencies:** AI Summary report only.
- **Validation rules:** Valid date range; at least one branch selected (or org-wide, Owner/Admin only).
- **Permissions:** `reports:export`.

### PG-53 Plant Passport View
- **Purpose:** Generate/view a specific plant's passport document (FR-18.1, US-G.1).
- **Users:** Owner, Org Admin, Branch Manager, Horticulturist (generate); Sales Staff (view/print at point of sale).
- **Entry points:** PG-22 quick action, QR code scan (public-safe, tokenized view for customer-facing use).
- **Exit points:** Download PDF, back to PG-22.
- **Key components:** Passport preview (species/provenance, health/treatment summary, current status, QR code), download/print/email actions.
- **API dependencies:** `GET /plants/{id}/passport`, `POST /plants/{id}/passport/generate`.
- **DB entities:** `plants`, `species`, `health_history`, `disease_reports`.
- **AI dependencies:** None (factual document; does not include speculative AI predictions).
- **Validation rules:** N/A (read/generate view).
- **Permissions:** `passport:generate` to create, `passport:read` to view (broadest access of any plant-data view, since it's customer-facing).

---

## Audit Log

### PG-54 Audit Log Viewer
- **Purpose:** Immutable activity record (FR-19, US-G.3).
- **Users:** Owner, Org Admin only.
- **Entry points:** Sidebar Settings → Audit Log.
- **Exit points:** Deep-links into referenced entities.
- **Key components:** Filterable table (actor, action, entity type, date range), entity before/after diff viewer.
- **API dependencies:** `GET /audit-logs?actor=&entity_type=&date_from=`.
- **DB entities:** `audit_logs`.
- **AI dependencies:** None.
- **Validation rules:** N/A (strictly read-only, no edit/delete path exists anywhere in the system for this entity — FR-19.3).
- **Permissions:** `audit:read`.

---

## Settings

### PG-55 Org Profile Settings
- **Purpose:** Manage org identity/branding (FR-20.1).
- **Users:** Owner, Org Admin.
- **Entry points:** Sidebar Settings.
- **Exit points:** N/A (tab within Settings).
- **Key components:** Org name/logo/contact form.
- **API dependencies:** `GET /orgs/{id}`, `PATCH /orgs/{id}`.
- **DB entities:** `nurseries`.
- **AI dependencies:** None.
- **Validation rules:** Required org name; logo upload validated (NFR-4.5).
- **Permissions:** `settings:org`.

### PG-56 Billing & Plan
- **Purpose:** Manage subscription plan and payment (FR-20.1, BRD §5).
- **Users:** Owner (full), Org Admin (read).
- **Entry points:** Sidebar Settings.
- **Exit points:** External payment provider flow (if applicable).
- **Key components:** Current plan summary, usage-against-limits meters (branches, seats, AI credits), upgrade/downgrade actions, payment method management, invoice history.
- **API dependencies:** `GET /billing/subscription`, `GET /billing/usage`, `POST /billing/change-plan`.
- **DB entities:** `subscriptions`, `usage_counters`.
- **AI dependencies:** AI credit usage meter reflects metered AI inference calls (BRD §5).
- **Validation rules:** Plan downgrade blocked if current usage (branches/seats) exceeds target plan's limits.
- **Permissions:** `settings:billing`.

### PG-57 Roles & Permissions
- **Purpose:** View system roles and manage custom roles (FR-1.5, FR-3, Growth/Enterprise tier).
- **Users:** Owner, Org Admin.
- **Entry points:** Sidebar Settings.
- **Exit points:** N/A (tab within Settings).
- **Key components:** System role list (read-only reference), custom role builder (permission checkboxes grouped by module), assigned-employees-per-role count.
- **API dependencies:** `GET /roles`, `POST /roles` (custom), `PATCH /roles/{id}`.
- **DB entities:** `roles`, `permissions`, `role_permissions`.
- **AI dependencies:** None.
- **Validation rules:** Custom role cannot exceed the permission ceiling of `org_admin`; cannot delete a role with active assignments.
- **Permissions:** `roles:manage`.

### PG-58 Notification Preferences
- **Purpose:** Configure per-user and org-default notification channels (FR-17.4).
- **Users:** All roles (own preferences); Owner/Org Admin (org defaults).
- **Entry points:** Sidebar Settings, PG-09 link.
- **Exit points:** N/A (tab within Settings).
- **Key components:** Category × channel matrix (in-app/email/SMS toggles).
- **API dependencies:** `GET /notifications/preferences`, `PATCH /notifications/preferences`.
- **DB entities:** `notification_preferences`.
- **AI dependencies:** None.
- **Validation rules:** SMS toggle only available if org has SMS enabled (FR-17.3, plan-gated).
- **Permissions:** `notifications:manage_preferences`.

### PG-59 Integrations Settings
- **Purpose:** Configure SMS/email sender and other integrations (FR-20.3).
- **Users:** Owner, Org Admin.
- **Entry points:** Sidebar Settings.
- **Exit points:** N/A (tab within Settings).
- **Key components:** SMS provider on/off + config, email sender identity, (Enterprise) API key management.
- **API dependencies:** `GET /settings/integrations`, `PATCH /settings/integrations`.
- **DB entities:** `org_settings`.
- **AI dependencies:** None.
- **Validation rules:** SMS config requires valid provider credentials before enabling; plan-gated (BRD §5).
- **Permissions:** `settings:org`.
