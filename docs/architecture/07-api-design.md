# API Design

REST + WebSocket, versioned at `/api/v1`. This consolidates every API dependency named per-page in `docs/ux/09-page-inventory.md` into one authoritative endpoint catalog with system-wide contract conventions.

## 1. Endpoint Catalog

| Resource | Endpoints |
|---|---|
| Auth | `POST /auth/signup`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/password-reset/request`, `POST /auth/password-reset/confirm`, `POST /auth/invite/accept` |
| Orgs | `GET/PATCH /orgs/{id}`, `GET /orgs/{id}/dashboard-summary` |
| Branches | `GET/POST /branches`, `GET/PATCH/DELETE /branches/{id}`, `GET /branches/{id}/dashboard-summary` |
| Employees | `GET /employees`, `POST /employees/invite`, `GET/PATCH /employees/{id}`, `POST /employees/{id}/deactivate` |
| Roles | `GET/POST /roles`, `PATCH/DELETE /roles/{id}` |
| Species | `GET/POST /species`, `GET/PATCH /species/{id}`, `DELETE /species/{id}` |
| Plants | `GET/POST /plants`, `GET /plants/{id}`, `PATCH /plants/{id}/status`, `POST /plants/{id}/transfer`, `POST /plants/{id}/qr-code` |
| Growth Timeline | `GET/POST /plants/{id}/growth-timeline` |
| Health History | `GET/POST /plants/{id}/health-history` |
| Disease Reports | `GET /disease-reports`, `GET/PATCH /disease-reports/{id}`, `POST /disease-reports/{id}/treatments` |
| Environmental | `GET/POST /plants/{id}/environmental-readings`, `POST /environmental-readings/ingest` (API-key auth) |
| Watering | `GET /watering/tasks`, `POST /watering-logs` |
| AI — Disease | `POST /ai/disease-detection/scan` |
| AI — Predictions | `GET /plants/{id}/ai-predictions`, `GET /ai/predictions/survival-risk`, `GET /ai/predictions/growth-summary`, `GET /ai/predictions/revenue-forecast` |
| AI — Recommendations | `GET /ai/recommendations`, `POST /ai/recommendations/{id}/dismiss` |
| AI — Assistant | `POST /ai/assistant/message`, `POST /ai/assistant/actions/{id}/confirm`, `GET /ai/assistant/conversations/{id}` |
| Inventory | `GET /inventory`, `GET /inventory/{id}`, `GET /inventory/{id}/history`, `POST /inventory/{id}/adjust` |
| Sales | `POST /sales`, `GET /sales`, `GET /sales/{id}`, `POST /sales/{id}/void`, `POST /sales/{id}/receipt/email` |
| Customers | `GET/POST /customers`, `GET/PATCH /customers/{id}`, `GET /customers/{id}/purchase-history` |
| Invoices | `POST /invoices`, `GET /invoices`, `GET /invoices/{id}`, `PATCH /invoices/{id}/status`, `POST /invoices/{id}/resend` |
| Suppliers | `GET/POST /suppliers`, `GET/PATCH /suppliers/{id}`, `DELETE /suppliers/{id}` |
| Purchase Orders | `GET/POST /purchase-orders`, `PATCH /purchase-orders/{id}`, `POST /purchase-orders/{id}/receive` |
| Notifications | `GET /notifications`, `PATCH /notifications/{id}/read`, `GET/PATCH /notifications/preferences` |
| Reports | `GET /reports/types`, `GET /reports/recent`, `POST /reports/generate` |
| Passport | `GET /plants/{id}/passport`, `POST /plants/{id}/passport/generate`, `GET /passport/public/{token}` (unauthenticated) |
| Audit Log | `GET /audit-logs` |
| Billing | `GET /billing/subscription`, `GET /billing/usage`, `POST /billing/change-plan` |
| Settings | `GET/PATCH /settings/integrations` |
| Realtime | `POST /ws/ticket`, `WSS /ws/{channel}` |
| System | `GET /healthz`, `GET /readyz` |

## 2. Request/Response Contract Conventions

**Envelope:** successful responses return the resource/collection directly (no unnecessary `{data: ...}` wrapper for single resources); paginated collections use `{items: [...], pagination: {cursor/offset, total, has_more}}`. **Timestamps:** ISO 8601, UTC, always — client localizes for display. **IDs:** UUID strings. **Partial updates:** `PATCH` accepts only the fields being changed (not a full-resource replace) and uses standard JSON body, not JSON Patch — simpler client code, sufficient for this API's mutation patterns. **Idempotency:** mutating endpoints that could plausibly be retried by a flaky client (`POST /sales`, `POST /invoices`) accept an optional `Idempotency-Key` header; a repeated key within a 24-hour window returns the original result rather than creating a duplicate.

## 3. Error Codes

Standard envelope on every error response: `{code, message, details, request_id}`. `code` is a stable machine-readable string (not just the HTTP status), enabling frontend logic to branch on specific errors without string-matching `message`.

| HTTP status | `code` examples | Meaning |
|---|---|---|
| 400 | `validation_error` | Request failed schema/field validation |
| 401 | `authentication_required`, `invalid_credentials`, `token_expired` | Auth failure |
| 403 | `permission_denied`, `plan_feature_unavailable` | Authorization failure |
| 404 | `not_found` | Resource doesn't exist or isn't visible to this tenant |
| 409 | `invalid_status_transition`, `insufficient_stock`, `item_unavailable`, `already_exists` | State conflict |
| 422 | `plan_limit_exceeded` | Valid request, blocked by business/plan rule |
| 429 | `rate_limited` | Too many requests |
| 500 | `internal_error` | Unhandled server error (no internal detail in `details`) |
| 503 | `ai_module_unavailable`, `external_service_unavailable` | Graceful-degradation case (NFR-3.3) |

`details` carries structured, field-level validation errors (`{field: "email", issue: "already_registered"}`) where applicable — enough for the frontend to attach the error to the correct form field per `docs/design/07-ui-state-documentation.md` §6, without the frontend having to parse a human-readable message.

## 4. Validation Rules

Every request body is validated against a Pydantic v2 schema before reaching the service layer (`03-backend-architecture.md` §14) — no endpoint accepts or partially trusts an unvalidated payload. Validation is layered: (1) schema-level (types, required fields, format — email/UUID/enum), (2) domain-level (business rules — e.g., `end_date >= start_date`, resolved in the service layer since it may require a DB lookup), (3) database-level (constraints as the final backstop, per `05-database-architecture.md` §4). A validation failure at any layer returns the same `400 validation_error` envelope shape regardless of which layer caught it — the client doesn't need to know which layer failed.

## 5. Versioning Strategy

URL-path versioning (`/api/v1/...`), restated from `03-backend-architecture.md` §11. Breaking changes ship as a new version prefix (`/api/v2/...`) mounted alongside `/api/v1`, never as an in-place breaking change to an existing version. Non-breaking changes (new optional fields, new endpoints) ship within the existing version. A version is deprecated with advance notice (minimum one release cycle) before removal, communicated via a `Deprecation` response header on the outgoing version once a successor exists.

## 6. Pagination

Two conventions, applied per `docs/ux/08-information-architecture.md`/`docs/design/08-ux-documentation.md` §10: **offset-based** (`?page=1&page_size=25`) for standard bounded lists (Employees, Species, Customers, Suppliers) where jumping to an arbitrary page is a real use case; **cursor-based** (`?cursor=<opaque>&limit=25`) for high-volume/high-write-rate lists (Sales History, Audit Log, Plants at scale) where offset pagination would risk skipped/duplicated rows under concurrent writes. Every list endpoint's pagination style is fixed and documented per-endpoint (not client-selectable) to keep the contract predictable.

## 7. Filtering

Query-parameter convention: `?filter[field]=value` for exact-match filters, `?filter[field][gte]=`/`[lte]=` for range filters (dates, numeric), repeated params for multi-select (`?filter[status]=sold&filter[status]=deceased` = OR within that field, per `docs/design/08-ux-documentation.md` §8's AND-across/OR-within rule). Every filterable field is explicitly enumerated in that endpoint's schema (no arbitrary field filtering against the ORM layer, which would risk exposing internal column names or enabling inefficient unindexed queries).

## 8. Sorting

`?sort=field` (ascending) / `?sort=-field` (descending), single-field only in v1 (per `docs/design/08-ux-documentation.md` §9's deliberate no-multi-column-sort decision). Each endpoint documents its default sort and its allowed sort fields (a subset of filterable fields, restricted to indexed columns per `05-database-architecture.md` §5 to keep sorted queries performant at scale).
