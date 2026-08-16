# Non-Functional Requirements

Each NFR is written to be testable — Phase 9 (Integration & Testing) verifies against these directly.

## NFR-1 Performance

- NFR-1.1 — 95th percentile API response time under 300ms for standard CRUD read endpoints under normal load (excludes AI inference endpoints).
- NFR-1.2 — Synchronous AI inference endpoints (single-image disease detection, single water recommendation) return within 5 seconds at the 95th percentile; longer-running inference (batch forecasts) runs asynchronously and notifies on completion rather than blocking the request.
- NFR-1.3 — Dashboard initial load (authenticated, cached data) renders primary content within 2 seconds on a standard broadband connection.
- NFR-1.4 — Realtime updates (notifications, live dashboard figures) propagate to connected clients within 2 seconds of the triggering event.

## NFR-2 Scalability

- NFR-2.1 — System supports at least 50 concurrent Orgs and 500 concurrent active users at v1 launch scale without architectural rework, with a documented path to horizontal scaling of the API and worker tiers.
- NFR-2.2 — Database schema and query patterns are designed so a single Org's data volume (tens of thousands of plant records) does not degrade query performance for other tenants (tenant-scoped indexing).
- NFR-2.3 — Background job workers (AI inference, report generation, notification delivery) scale horizontally by adding worker processes without code changes.

## NFR-3 Availability & Reliability

- NFR-3.1 — Target 99.5% uptime for the production deployment (excludes scheduled maintenance windows communicated in advance).
- NFR-3.2 — System performs automated daily database backups with a documented, tested restore procedure.
- NFR-3.3 — A failure in an AI module (e.g., inference service unavailable) degrades gracefully — the rest of the platform remains usable, and the affected feature shows a clear "unavailable, retry" state rather than failing the whole request/page.
- NFR-3.4 — Health check endpoints (liveness/readiness) are exposed for all services and wired into deployment orchestration.

## NFR-4 Security

- NFR-4.1 — All client-server traffic is encrypted in transit (HTTPS/WSS only, no unencrypted fallback).
- NFR-4.2 — Passwords are hashed with a modern adaptive algorithm (e.g., bcrypt/argon2); plaintext passwords are never logged or stored.
- NFR-4.3 — Tenant data isolation is enforced at both the application layer (tenant-scoping middleware) and the database layer (row-level security policies) as defense in depth.
- NFR-4.4 — All user input is validated and sanitized server-side regardless of client-side validation; the system is protected against SQL injection, XSS, and CSRF by construction (parameterized queries via ORM, output encoding, CSRF tokens on state-changing form submissions where applicable).
- NFR-4.5 — File uploads (plant images) are validated for type/size and scanned before being served back to other users.
- NFR-4.6 — Every authentication and authorization failure is logged; repeated failures trigger rate limiting/lockout.
- NFR-4.7 — Secrets (API keys, DB credentials, JWT signing keys) are never committed to source control and are injected via environment configuration.
- NFR-4.8 — A security review (Phase 9) is completed before production deployment, covering the OWASP Top 10 at minimum.

## NFR-5 Compliance & Data Governance

- NFR-5.1 — Customer Org data (plants, records, reports) is exportable in full on request, supporting data portability and contract termination.
- NFR-5.2 — Personally identifiable customer/employee data is limited to what's functionally necessary (contact info for Customers/Employees) and is deletable/anonymizable on a documented request process.
- NFR-5.3 — Audit log retention is a minimum of 12 months, immutable, and independently queryable from operational data.

## NFR-6 Usability

- NFR-6.1 — Core field workflows (photo capture for disease detection, watering log entry) are completable in 3 taps/clicks or fewer from the relevant dashboard.
- NFR-6.2 — The system provides clear, non-technical error messages to end users; technical detail is logged, not surfaced.
- NFR-6.3 — Destructive or hard-to-reverse actions (deactivating a branch, voiding an invoice, marking a plant deceased) require explicit confirmation.

## NFR-7 Accessibility

- NFR-7.1 — Frontend targets WCAG 2.1 AA: sufficient color contrast (including in the health-status color palette, which must not rely on color alone — paired with icon/label), full keyboard navigability, semantic HTML/ARIA labeling on interactive components.
- NFR-7.2 — All charts and status indicators have a non-color-dependent way to convey meaning (labels, icons, patterns).

## NFR-8 Maintainability

- NFR-8.1 — Backend follows Clean Architecture layering (api → services → repositories → models) with enforced import boundaries, per the Enterprise System Architecture document.
- NFR-8.2 — Frontend follows feature-based architecture with no cross-feature internal imports.
- NFR-8.3 — Minimum automated test coverage thresholds are defined and enforced in CI before Phase 10 deployment (detailed in Phase 9).
- NFR-8.4 — All configuration is externalized (environment variables); no hardcoded values in business logic.

## NFR-9 Portability

- NFR-9.1 — The entire stack is deployable via Docker Compose without a hard dependency on a single cloud provider's proprietary services (Cloudinary and the LLM provider are external SaaS dependencies by design, not infrastructure lock-in).

## NFR-10 Observability

- NFR-10.1 — All services emit structured logs correlated by request ID.
- NFR-10.2 — Application errors are captured by an error-tracking service with alerting.
- NFR-10.3 — Key business and system metrics (AI inference latency/error rate, job queue depth, per-tenant usage against plan limits) are observable by the platform operations team (persona: Alex, System Administrator).
