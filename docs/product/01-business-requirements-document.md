# Business Requirements Document (BRD)

**Product:** NurseryVerse AI — AI-Powered Plant Digital Twin & Nursery Intelligence Platform
**Document owner:** Product Management
**Status:** Draft v1.0 — for stakeholder approval
**Applies to:** all downstream phases (UX, design, architecture, engineering)

## 1. Executive Summary

NurseryVerse AI is a commercial multi-tenant SaaS platform for wholesale and retail plant nurseries. It gives every plant a persistent "digital twin" — a continuously updated record of its species, growth, health, environment, and sales lifecycle — and layers AI on top of that record to reduce plant loss, cut manual labor, and give owners forecasting and decision support they currently have no way to get from spreadsheets or generic inventory software.

## 2. Business Context & Problem Statement

Commercial nurseries currently run on a mix of paper logs, spreadsheets, and generic point-of-sale software that were not built for living, changing inventory. This creates five recurring, costly problems:

Plant loss from undetected disease and improper watering is a direct margin hit — by the time a visual symptom is caught during a manual walk-through, treatment is often too late and the specimen (sometimes a multi-year, high-value plant) is a write-off. Inventory counts drift from reality because plants grow, die, get moved between branches, or get sold outside the system, so owners make purchasing and pricing decisions on stale numbers. There is no standardized, exportable record of a plant's provenance and care history, which matters for wholesale buyers, landscapers, and any customer who wants proof of species authenticity and health at time of sale (a "plant passport"). Forecasting — how much water/labor is needed next week, what revenue next quarter looks like, which species are trending — is done by gut feel because the data needed to model it is scattered across disconnected tools. Multi-branch operators have no single pane of glass across locations, so branch managers and the owner are working from different, unreconciled pictures of the business.

NurseryVerse AI addresses all five by making the plant (not the SKU, not the invoice) the central object in the system, and by making AI a first-class feature rather than an add-on report.

## 3. Product Vision

Give every commercial nursery a digital twin for every plant it grows and sells — so health issues are caught before they're visible to the human eye, every plant's full history travels with it from propagation to sale, and owners run their business on forecasts instead of guesses.

## 4. Business Goals

Goal 1 — Reduce preventable plant loss. Target: 25% reduction in disease/water-related plant write-offs within the first two full growing seasons of use, measured against the nursery's pre-adoption baseline loss rate. Goal 2 — Cut manual inventory and record-keeping labor. Target: 30% reduction in staff-hours spent on manual plant counts, condition logging, and paperwork-based passport/compliance generation. Goal 3 — Improve forecasting accuracy. Target: revenue forecast within 15% of actuals at a 30-day horizon by the second quarter of use, watering/labor forecasts adopted as the default planning input by branch managers. Goal 4 — Multi-branch visibility. Target: 100% of active branches reporting into a single owner-facing dashboard with same-day data freshness. Goal 5 — Monetizable platform. Target: convert the reference client to a paying subscription and reach a repeatable, documented onboarding process that a second nursery customer can complete without custom engineering work.

## 5. Target Market & Business Model

**Primary market:** small-to-mid-size commercial nurseries (wholesale growers, retail garden centers, landscape-supply nurseries) operating 1–10 branches, with enough SKU/plant volume that manual tracking has become a bottleneck.

**Secondary market (post-v1):** botanical gardens, specialty/rare-plant collectors, agricultural extension programs — anyone managing a living plant inventory at scale.

**Pricing model:** tiered SaaS subscription, billed per organization with limits that scale price:
- **Starter** — 1 branch, up to 3 employee seats, core inventory/sales/digital twin, capped AI inference credits/month. Aimed at single-location retail nurseries.
- **Growth** — up to 5 branches, unlimited seats, full AI suite (disease detection, predictions, forecasting, assistant), priority support. Aimed at regional multi-branch operators — the primary target segment.
- **Enterprise** — unlimited branches, SSO, custom RBAC roles, dedicated model fine-tuning on the customer's own disease/species data, SLA-backed uptime, data export/API access. Aimed at large wholesale growers and franchised garden-center chains.

AI inference (disease detection scans, forecast runs, assistant conversations) is metered above plan-included allowances to keep the model-inference cost aligned with revenue as usage scales.

## 6. Stakeholders

| Stakeholder | Interest |
|---|---|
| Nursery Owner / Operator (paying customer) | ROI on plant loss reduction, revenue visibility, multi-branch control |
| Branch Manager | Day-to-day operational efficiency, staff task management |
| Horticulturist / Plant Care Staff | Accurate, low-friction health and growth logging; trustworthy AI guidance |
| Sales / POS Staff | Fast checkout, accurate inventory at point of sale |
| Wholesale / B2B Customers | Trustworthy plant passports, provenance, health guarantees |
| Engineering & Product team | Buildable, maintainable, secure platform delivered in phases |
| Compliance / Regulatory (phytosanitary bodies, where applicable) | Accurate, auditable plant health and treatment records |

## 7. Scope

**In scope for v1 (this build):** multi-tenant org/branch/employee management with RBAC; species catalog and per-plant digital twin (growth timeline, health history, environmental readings, watering logs); AI disease detection from photos; AI growth, survival, and water-recommendation predictions; AI revenue forecasting; AI recommendation engine and conversational AI assistant; inventory management; sales/POS and invoicing; customer records; supplier and purchasing records; notifications (in-app, email, and configurable SMS); PDF/Excel/CSV reporting including a printable/QR-linked Plant Passport; audit logging; org/branch settings.

**Out of scope for v1 (explicitly deferred):** public wholesale marketplace/storefront for cross-nursery buying and selling; native mobile apps (v1 ships as a responsive web app); IoT sensor hardware integration beyond a documented API for manual/third-party environmental readings; multi-language localization beyond English; payment processor integration for online storefront checkout (in-person/invoice-based sales only in v1).

## 8. Assumptions & Constraints

Assumptions: the nursery has reliable internet connectivity at each branch; staff have access to a smartphone or tablet camera for plant photo capture; the initial disease-detection model will be trained/fine-tuned on a combination of public plant-disease datasets and the customer's own labeled data, with accuracy expected to improve post-launch as more customer data is collected. Constraints: must be deployable as a self-contained Docker Compose stack for a single-customer production deployment in v1 (no dependency on a specific cloud provider being contractually locked in); must keep AI inference cost predictable via metering, since model calls are a variable cost against a fixed subscription price.

## 9. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Disease-detection model accuracy insufficient at launch (cold-start, limited labeled data) | High — undermines core value prop | Ship with confidence scores and "needs human review" states rather than binary diagnoses; collect labeled corrections from day one to retrain |
| Multi-tenant data isolation failure | Critical — cross-customer data leak | Row-level security enforced at the database layer in addition to application-layer tenant scoping (defense in depth) |
| Low staff adoption of manual logging (garbage-in/garbage-out for AI) | High — AI quality depends on data discipline | Minimize logging friction (photo-first workflows, smart defaults, mobile-first forms), make AI value visible early to build trust |
| Scope creep from "not an MVP" mandate colliding with delivery timeline | Medium | Phase-gated delivery with explicit approval checkpoints (this document is phase 1 of that process) |

## 10. Product Roadmap

**v1.0 (this engagement)** — Phases 1–10 as defined in the project charter: discovery, UX, design, architecture, database, backend, frontend, AI modules, integration/testing, deployment. Single reference customer, full feature set as scoped above.

**v1.1 (next quarter post-launch)** — model retraining pipeline using accumulated customer-labeled data; expanded report templates; SMS-based watering/health alerts at general availability (v1 ships SMS as configurable/optional).

**v2 (roadmap, not yet committed)** — native mobile app for field staff; IoT/sensor hardware integrations for automated environmental readings; multi-nursery wholesale marketplace; multi-language support; public API for third-party integrations.

## 11. Approval

This document is the baseline for Phase 2 (UX Planning). Changes to scope after this point are tracked as change requests against this BRD rather than silent scope shifts in later phases.
