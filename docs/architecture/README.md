# Phase 4 — Enterprise System Architecture

The complete technical blueprint, produced so Phase 5+ (Database, Backend, Frontend, AI, Integration, Deployment) can begin with zero ambiguity. Builds directly on Phase 1 (`../product/`), Phase 2 (`../ux/`), and Phase 3 (`../design/`) — no product, UX, or visual decision is re-litigated here, only translated into technical design.

1. [High-Level Architecture](01-high-level-architecture.md) — system architecture, frontend/backend/AI/database/infrastructure summaries, external services, cloud, deployment
2. [Low-Level Design](02-low-level-design.md) — every module: responsibilities, components, interfaces, dependencies, data flow, error handling, validation, security
3. [Backend Architecture](03-backend-architecture.md) — FastAPI structure, repository/service pattern, DI, auth, middleware, background jobs, WebSockets, versioning, logging, config, exceptions
4. [Frontend Architecture](04-frontend-architecture.md) — Next.js App Router structure, state management, React Query, forms, routing, auth flow, error boundaries, layouts, components
5. [Database Architecture](05-database-architecture.md) — full ERD, relationships, constraints, indexes, transactions, audit/backup strategy, multi-tenancy
6. [AI Architecture](06-ai-architecture.md) — AI services, model serving, inference pipeline, feature engineering, image processing, prompt orchestration, vector search, RAG, model versioning
7. [API Design](07-api-design.md) — endpoint catalog, contracts, error codes, validation, versioning, pagination, filtering, sorting
8. [Security Architecture](08-security-architecture.md) — JWT, RBAC, permission model, encryption, secrets, audit logging, rate limiting, secure uploads, OWASP
9. [Infrastructure](09-infrastructure.md) — Docker, Docker Compose, Nginx, Redis, PostgreSQL, storage, monitoring, logging, health checks
10. [DevOps](10-devops.md) — CI/CD, branching, release, rollback, backup, disaster recovery
11. [Sequence Diagrams](11-sequence-diagrams.md) — Login, Plant Registration, AI Disease Detection, Digital Twin Update, Inventory Update, Plant Sale, Notification Delivery
12. [Final Architecture Review](12-final-architecture-review.md) — every FR/NFR from the SRS traced to its architectural coverage

Status: complete, pending approval. Phase 5 (Database) begins only after this is approved.
