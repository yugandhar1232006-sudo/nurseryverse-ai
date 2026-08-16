# Low-Level Design (LLD)

Every backend module, specified to the level Phase 6 (Backend implementation) builds directly against. Modules correspond 1:1 to `docs/ux/06-module-dependency-diagram.md` and the FR groups in `docs/product/04-functional-requirements.md`. Each module is a Python package `app/services/<module>/` (service layer) with a matching `app/repositories/<module>_repository.py` and `app/api/v1/endpoints/<module>.py`, per the Backend Architecture folder structure (`03-backend-architecture.md`).

## Module: Auth & RBAC

- **Responsibilities:** authentication (login, token issuance/refresh/revocation), password reset, invite acceptance, permission resolution.
- **Internal components:** `AuthService` (login, token lifecycle), `PasswordResetService`, `InviteService`, `PermissionResolver` (builds the effective permission set for a request from role + custom-role assignments).
- **Public interfaces:** `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/password-reset/request`, `POST /auth/password-reset/confirm`, `POST /auth/invite/accept`; internal `require_permission()` FastAPI dependency consumed by every other module.
- **Dependencies:** `users`, `roles`, `permissions`, `role_permissions` tables; Redis (refresh-token revocation list, rate limiting).
- **Data flow:** credentials → `AuthService.authenticate()` → password hash verify → issue JWT pair → refresh token hashed and stored; every subsequent request → `PermissionResolver` populates request-scoped user/org/branch/permission context consumed by the tenant-scoping middleware.
- **Error handling:** generic "invalid credentials" for any auth failure (no user enumeration, NFR-4.6); typed `AuthenticationError`/`AuthorizationError` domain exceptions mapped to 401/403 by the global exception handler.
- **Validation:** password strength policy (min length/complexity) enforced server-side regardless of client validation; email format/uniqueness.
- **Security:** bcrypt/argon2 password hashing (NFR-4.2); RS256 JWT (asymmetric — API can verify without holding the signing key, relevant if the signing responsibility is ever split out); refresh tokens rotated on use and revocable; failed-login rate limiting (NFR-4.6).

## Module: Organization & Branch

- **Responsibilities:** org/branch CRUD, branch settings, org-branch hierarchy enforcement.
- **Internal components:** `OrgService`, `BranchService`.
- **Public interfaces:** `POST/GET/PATCH /orgs/{id}`, `GET/POST /branches`, `GET/PATCH/DELETE /branches/{id}`.
- **Dependencies:** `nurseries`, `branches` tables; Employees module (branch deactivation checks for assigned staff).
- **Data flow:** branch creation validates against the org's plan branch-limit (reads `subscriptions`) before insert.
- **Error handling:** `PlanLimitExceededError` (typed, distinct from generic validation errors per UX spec) on branch-limit breach.
- **Validation:** required name/address; valid IANA timezone string.
- **Security:** `branch:write`/`branch:delete` permission-gated; branch deactivation is a soft delete (`status` field), never a hard delete (preserves historical data per FR-2.5).

## Module: Employees

- **Responsibilities:** staff invite, role/branch assignment, deactivation.
- **Internal components:** `EmployeeService`, `InviteService` (shared with Auth module).
- **Public interfaces:** `GET /employees`, `POST /employees/invite`, `GET/PATCH /employees/{id}`, `POST /employees/{id}/deactivate`.
- **Dependencies:** `employees`, `users`, `role_assignments`, `invites` tables; Auth module (session revocation on deactivation).
- **Data flow:** invite created → email dispatched (Notification module) → invite accepted → `users` + `employees` + `role_assignments` rows created transactionally.
- **Error handling:** blocks deactivating the sole remaining Owner/Admin (`LastAdminError`).
- **Validation:** role assignable is capped at the inviter's own permission ceiling; seat-limit enforced against plan (`subscriptions`).
- **Security:** deactivation immediately revokes all active refresh tokens for that user (FR-3.3/1.6).

## Module: Species Catalog

- **Responsibilities:** species reference data CRUD.
- **Internal components:** `SpeciesService`.
- **Public interfaces:** `GET /species`, `POST /species`, `GET/PATCH /species/{id}`, `DELETE /species/{id}` (blocked with a `409 conflict` if any plant references it — service-layer referential check ahead of the DB's `ON DELETE RESTRICT` backstop).
- **Dependencies:** `species` table; consumed by Plants, AI Predictions modules.
- **Data flow:** read-heavy, org-wide (not branch-scoped); cached in Redis with a short TTL given low write frequency and high read frequency (dashboard/form lookups).
- **Error handling:** standard validation error envelope.
- **Validation:** unique botanical name per org; numeric care-range fields min ≤ max.
- **Security:** `species:write` permission-gated; `species:read` broadly available (all roles).

## Module: Plants (Digital Twin)

- **Responsibilities:** plant lifecycle (create, status transitions, transfer), aggregation of sub-record summaries for the Twin detail view.
- **Internal components:** `PlantService` (lifecycle state machine per `docs/ux/13-digital-twin-lifecycle.md`), `PlantAggregationService` (assembles the PG-22 overview payload), `QRCodeService`.
- **Public interfaces:** `GET /plants`, `POST /plants`, `GET /plants/{id}`, `PATCH /plants/{id}/status`, `POST /plants/{id}/transfer`, `POST /plants/{id}/qr-code`.
- **Dependencies:** `plants`, `plant_images`, `species`, `branches` tables; reads from Growth/Health/Environmental/Watering/AI Predictions modules for aggregation.
- **Data flow:** status transitions validated against the state machine (illegal transitions rejected before write); transfer is a single transaction updating `plants.branch_id` + inserting a `plant_transfers` history row.
- **Error handling:** `InvalidStatusTransitionError` (typed, maps to 409 Conflict — the resource state doesn't allow this operation, distinct from a validation error).
- **Validation:** species and branch required at creation; transfer destination must be active and different from current.
- **Security:** `plants:write`/`plants:transfer` permission-gated, branch-scoped (`B`) per the permission matrix.

## Module: Growth Timeline

- **Responsibilities:** append-only growth measurement logging.
- **Internal components:** `GrowthService`.
- **Public interfaces:** `GET /plants/{id}/growth-timeline`, `POST /plants/{id}/growth-timeline`.
- **Dependencies:** `growth_timeline` table; feeds AI Growth Prediction.
- **Data flow:** log entry insert triggers an async event that may re-trigger Growth Prediction (per `docs/ux/12-ai-workflow-diagrams.md` §2's "new growth entry logged" trigger).
- **Error handling:** standard validation envelope.
- **Validation:** numeric measurements ≥ 0.
- **Security:** `growth:write` permission-gated, branch-scoped; entries are immutable once created (append-only, no PATCH/DELETE endpoint exists).

## Module: Health & Disease

- **Responsibilities:** health observation logging, disease report lifecycle (draft → confirmed/dismissed → treated → resolved).
- **Internal components:** `HealthService` (observations), `DiseaseReportService` (lifecycle + treatment tracking).
- **Public interfaces:** `GET/POST /plants/{id}/health-history`, `GET /disease-reports`, `GET /disease-reports/{id}`, `PATCH /disease-reports/{id}`, `POST /disease-reports/{id}/treatments`.
- **Dependencies:** `health_history`, `disease_reports`, `treatments` tables; AI Predictions module (auto-draft creation per FR-7.2); Notification module (confirmed-report trigger).
- **Data flow:** AI disease detection above threshold → `DiseaseReportService.create_draft()` → human confirms/dismisses → confirm triggers Notification event → treatment logged → outcome closes the report, feeding back into AI Survival Prediction training data.
- **Error handling:** `ReportAlreadyClosedError` if a treatment/outcome is submitted against a resolved report.
- **Validation:** outcome selection required to close; treatment description required.
- **Security:** `disease:approve` (confirm/dismiss) is a distinct, narrower permission than `disease:write` (log observation) — see permission matrix.

## Module: AI Predictions (orchestration layer)

- **Responsibilities:** orchestrates the six prediction modules (§ full detail in `06-ai-architecture.md`), enforces the universal logging contract (FR-8.7).
- **Internal components:** `PredictionOrchestrator` (routes to the correct model module, enforces persist-before-return), per-module inference classes under `app/ai/`.
- **Public interfaces:** `POST /ai/disease-detection/scan`, `GET /plants/{id}/ai-predictions`, `GET /ai/predictions/survival-risk`, `GET /ai/predictions/revenue-forecast`, `GET /ai/recommendations`.
- **Dependencies:** every Digital Twin sub-record module (input features); `ai_predictions`, `ai_recommendations` tables; Cloudinary (image input); Celery (async modules).
- **Data flow:** see `06-ai-architecture.md` §4 (Inference Pipeline) — identical pattern across modules: gather features → infer → persist → conditionally trigger downstream (Disease Reports, Notifications, Recommendation Engine).
- **Error handling:** `ModelUnavailableError` (typed) → surfaced as the module-specific graceful-degradation message (NFR-3.3), never a bare 500.
- **Validation:** image inputs validated (type/size) before inference is attempted.
- **Security:** predictions are always tenant-scoped (a model never receives cross-tenant training/inference context at request time); `ai_predictions:run` permission-gated for on-demand triggers.

## Module: AI Assistant

- **Responsibilities:** conversational interface, tool-calling into other modules' service layer, proposed-write confirmation gate.
- **Internal components:** `AssistantOrchestrator` (LLM call + tool-calling loop), `AssistantToolRegistry` (maps callable tools to existing service methods — never bespoke assistant-only logic), `AssistantConversationService`.
- **Public interfaces:** `POST /ai/assistant/message`, `POST /ai/assistant/actions/{id}/confirm`, `GET /ai/assistant/conversations/{id}`.
- **Dependencies:** every module's service layer (read tools); Anthropic Claude API; `ai_assistant_conversations`, `ai_assistant_messages` tables.
- **Data flow:** message → intent resolution → read tool-calls execute directly; write tool-calls produce a proposal persisted with `status=pending_confirmation` → user confirms → the **same service method** the native page would call is invoked (per `docs/ux/12-ai-workflow-diagrams.md` §7's guarantee).
- **Error handling:** LLM API failure surfaces as an inline chat error with retry, never blocks the rest of the app.
- **Validation:** every proposed write re-validates through its target service's normal validation path — no assistant-specific validation bypass exists.
- **Security:** `ai_assistant:use`/`ai_assistant:confirm_write` permission-gated; the tool registry only exposes tools the requesting user's role could already call directly — enforced by passing the user's actual permission context into every tool invocation, not a privileged "assistant service account."

## Module: Environmental Readings

- **Responsibilities:** environmental data ingestion (manual + API).
- **Internal components:** `EnvironmentalService`.
- **Public interfaces:** `GET/POST /plants/{id}/environmental-readings`, `POST /environmental-readings/ingest` (third-party API path, FR-10.2).
- **Dependencies:** `environmental_readings` table; feeds Water Recommendation, Survival Prediction.
- **Data flow:** ingest endpoint is API-key-authenticated (distinct from user JWT auth) for third-party sensor integrations.
- **Error handling:** standard validation envelope; ingest endpoint returns partial-success detail for batch payloads.
- **Validation:** readings within plausible sensor ranges (reject obviously erroneous values, e.g., negative humidity).
- **Security:** ingest API keys are per-org, scoped, revocable, rate-limited independently from user-session rate limits.

## Module: Watering

- **Responsibilities:** watering event logging, AI-driven schedule generation, overdue detection.
- **Internal components:** `WateringService`, `WateringScheduleService`.
- **Public interfaces:** `GET /watering/tasks`, `POST /watering-logs`.
- **Dependencies:** `watering_logs` table; AI Water Recommendation module; Notification module (overdue trigger).
- **Data flow:** scheduled Celery Beat job recalculates due-dates; a log event resets the relevant plant/zone's due-date.
- **Error handling:** standard validation envelope.
- **Validation:** target plant/zone required; volume ≥ 0.
- **Security:** `watering:write` permission-gated, branch-scoped.

## Module: Inventory

- **Responsibilities:** bulk stock quantity management, threshold-based alerting.
- **Internal components:** `InventoryService`, `StockAdjustmentService`.
- **Public interfaces:** `GET /inventory`, `GET /inventory/{id}`, `POST /inventory/{id}/adjust`.
- **Dependencies:** `inventory`, `inventory_adjustments` tables; consumed transactionally by Sales and Purchasing modules.
- **Data flow:** every quantity change (sale, adjustment, PO receipt) is a single DB transaction (per `docs/ux/16-inventory-workflow.md`'s consistency guarantee) — enforced via `InventoryService.apply_change()` being the sole write path other modules call, never direct row updates from Sales/Purchasing.
- **Error handling:** `InsufficientStockError` (typed, 409) blocks over-selling/over-decrementing.
- **Validation:** adjustment reason required; resulting quantity cannot go below 0.
- **Security:** `inventory:adjust` permission-gated, branch-scoped.

## Module: Sales / POS

- **Responsibilities:** sale transaction creation, availability enforcement, void handling.
- **Internal components:** `SalesService`, `AvailabilityChecker`.
- **Public interfaces:** `POST /sales`, `GET /sales`, `GET /sales/{id}`, `POST /sales/{id}/void`, `POST /sales/{id}/receipt/email`.
- **Dependencies:** `sales`, `sale_items` tables; Plants module (status update), Inventory module (`apply_change`), Customers module.
- **Data flow:** `SalesService.create_sale()` opens a single DB transaction spanning `sales`/`sale_items` insert + `plants.status` update and/or `InventoryService.apply_change()` — all-or-nothing (per `docs/ux/11-data-flow-diagrams.md` §2).
- **Error handling:** `ItemUnavailableError` (typed, 409) blocks the specific line item, not the whole request until resolved by the client.
- **Validation:** at least one line item; availability re-checked at commit time (not just at add-to-cart time) to close the race-condition window.
- **Security:** `sales:write`/`sales:void` permission-gated, branch-scoped; void requires a reason and is itself a transactional reversal.

## Module: Customers

- **Responsibilities:** customer record CRUD, purchase-history aggregation.
- **Internal components:** `CustomerService`.
- **Public interfaces:** `GET /customers`, `POST /customers`, `GET/PATCH /customers/{id}`, `GET /customers/{id}/purchase-history`.
- **Dependencies:** `customers` table; read by Sales, Invoicing.
- **Data flow:** duplicate-detection on create (fuzzy match via `pg_trgm`) surfaces a non-blocking suggestion, never auto-merges.
- **Error handling:** standard validation envelope.
- **Validation:** contact info format (email/phone).
- **Security:** `customers:write` permission-gated, branch-scoped.

## Module: Invoicing

- **Responsibilities:** invoice generation from sales, status lifecycle, overdue detection.
- **Internal components:** `InvoiceService`, `InvoiceLifecycleService` (status transitions).
- **Public interfaces:** `POST /invoices`, `GET /invoices`, `GET /invoices/{id}`, `PATCH /invoices/{id}/status`, `POST /invoices/{id}/resend`.
- **Dependencies:** `invoices`, `invoice_items` tables; Sales, Customers modules; Reports module (PDF generation); Notification module (overdue trigger).
- **Data flow:** scheduled Celery Beat job scans `invoices` for past-due unpaid records and transitions status + triggers notification.
- **Error handling:** `InvalidStatusTransitionError` reused from the same pattern as Plants' lifecycle.
- **Validation:** at least one sale; customer required; terms required for wholesale.
- **Security:** `invoices:void` is a narrower permission than `invoices:write` (create), per the matrix.

## Module: Suppliers & Purchasing

- **Responsibilities:** supplier records, purchase order lifecycle, stock receiving.
- **Internal components:** `SupplierService`, `PurchaseOrderService`.
- **Public interfaces:** `GET/POST /suppliers`, `GET/PATCH /suppliers/{id}`, `DELETE /suppliers/{id}` (blocked if referenced by any purchase order), `GET/POST /purchase-orders`, `PATCH /purchase-orders/{id}`, `POST /purchase-orders/{id}/receive`.
- **Dependencies:** `suppliers`, `purchase_orders`, `purchase_order_items` tables; Inventory module (`apply_change` on receipt).
- **Data flow:** receiving is transactional — PO line-item received-quantity update + Inventory quantity increase happen together or not at all.
- **Error handling:** `OverReceiptError` if received quantity would exceed ordered quantity.
- **Validation:** at least one line item on PO creation.
- **Security:** `purchase_orders:receive` permission-gated, branch-scoped.

## Module: Notifications

- **Responsibilities:** trigger catalog, recipient resolution, multi-channel dispatch, preference enforcement.
- **Internal components:** `NotificationService` (creates the notification record + resolves recipients), `NotificationDispatcher` (Celery task, channel fan-out per `docs/ux/14-notification-workflow.md`).
- **Public interfaces:** `GET /notifications`, `PATCH /notifications/{id}/read`, `GET/PATCH /notifications/preferences`.
- **Dependencies:** `notifications`, `notification_preferences` tables; every other module emits trigger events consumed here; Email/SMS provider adapters; Redis pub/sub (WebSocket fan-out).
- **Data flow:** domain event → `NotificationService.create()` (always, regardless of channel preference — in-app record exists first) → enqueue `NotificationDispatcher` → per-recipient preference check → channel dispatch.
- **Error handling:** a failed email/SMS dispatch does not fail the in-app notification (already persisted); dispatch failures are logged and retried with backoff (Celery retry policy), not silently dropped.
- **Validation:** category/channel combinations validated against what the org's plan allows (SMS gating).
- **Security:** recipient resolution never notifies a user outside their branch/permission scope (restated from the workflow doc).

## Module: Reports & Plant Passport

- **Responsibilities:** report generation (PDF/Excel/CSV), Plant Passport generation and tokenized public access.
- **Internal components:** `ReportGenerationService` (Celery-backed, per report type), `PassportService` (includes the public-token issuance path).
- **Public interfaces:** `POST /reports/generate`, `GET /reports/recent`, `GET /plants/{id}/passport`, `POST /plants/{id}/passport/generate`, `GET /passport/public/{token}` (unauthenticated).
- **Dependencies:** varies by report type (reads across most modules); `reports`, `passports` tables; Cloudinary (document storage).
- **Data flow:** async generation (`11-data-flow-diagrams.md` §5 pattern) for all report types; Passport generation additionally issues a signed, time-scoped public token distinct from the plant's internal ID.
- **Error handling:** generation failures surface via the notification/WebSocket completion channel, not a blocking request.
- **Validation:** valid date range; at least one branch (or org-wide, Owner/Admin only).
- **Security:** `GET /passport/public/{token}` is the **one deliberate unauthenticated, tenant-safe exception** to the system's blanket auth requirement (per `docs/ux/15-plant-passport-workflow.md`) — it returns only the factual passport content (no AI predictions, no internal cost data), token is signed and time-scoped, and the endpoint is rate-limited independently to prevent token brute-forcing.

## Module: Audit Log

- **Responsibilities:** immutable activity recording, org-scoped querying.
- **Internal components:** `AuditLogService` (write path, invoked by every other service's mutating operations via a shared decorator/hook, not called ad hoc); no update/delete method exists anywhere in this module.
- **Public interfaces:** `GET /audit-logs` (read only — no write endpoint is ever exposed; writes happen exclusively as a side effect of other modules' mutations).
- **Dependencies:** `audit_logs` table; every other module is a producer.
- **Data flow:** every service-layer mutation passes through a common `@audited` decorator (or equivalent DI-based interceptor) capturing actor, action, entity, before/after diff — this is enforced structurally (a mutation that bypasses this path is treated as a code-review defect, not an acceptable variance).
- **Error handling:** an audit-write failure fails the enclosing transaction (an action that can't be audited does not happen) — audit logging is not best-effort.
- **Validation:** N/A (system-generated only).
- **Security:** `audit:read` restricted to Owner/Org Admin only; the table has no application-level or database-level update/delete grant for any role (FR-19.3 enforced at the database permission level, not just the API layer).

## Module: Settings

- **Responsibilities:** org profile, billing/plan, custom roles, notification/integration settings.
- **Internal components:** `OrgSettingsService`, `BillingService`, `RoleManagementService`.
- **Public interfaces:** `GET/PATCH /orgs/{id}` (profile), `GET /billing/subscription`, `GET /billing/usage`, `POST /billing/change-plan`, `GET/POST/PATCH /roles`, `GET/PATCH /settings/integrations`.
- **Dependencies:** `nurseries`, `subscriptions`, `usage_counters`, `roles`, `permissions`, `role_permissions`, `org_settings` tables.
- **Data flow:** plan downgrade validates current usage against target-plan limits before allowing the change (reads `usage_counters`).
- **Error handling:** `PlanDowngradeBlockedError` (typed, explanatory, not a generic validation error).
- **Validation:** custom role permission ceiling cannot exceed `org_admin` (enforced server-side, not just hidden in the UI).
- **Security:** `settings:billing` (plan/payment changes) is Owner-only, distinct from `settings:org` (profile), per the permission matrix's finer-grained split.
