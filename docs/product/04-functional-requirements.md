# Functional Requirements

Prioritization uses MoSCoW: **M**ust have (v1 blocking), **S**hould have (v1 target, can slip one sprint without blocking launch), **C**ould have (v1 if time allows, otherwise v1.1). Every requirement below is in scope for v1 unless marked **v1.1**. IDs are stable references used by later phases (design, architecture, test plans) — do not renumber.

## FR-1 Authentication & Access Control

| ID | Requirement | Priority |
|---|---|---|
| FR-1.1 | Users authenticate with email + password; passwords stored using a salted, adaptive hash (never reversible/plaintext) | M |
| FR-1.2 | System issues short-lived JWT access tokens and longer-lived, rotating refresh tokens | M |
| FR-1.3 | Users can request a password reset via a time-limited, single-use emailed link | M |
| FR-1.4 | System enforces RBAC on every API and UI action based on the requesting user's role and permissions | M |
| FR-1.5 | Org Admins can define custom roles composed of individual permissions, in addition to system default roles | S |
| FR-1.6 | Sessions can be revoked (logout, forced logout by admin, refresh token revocation) | M |
| FR-1.7 | Enterprise-tier orgs can configure SSO | C (v1.1) |

## FR-2 Organization & Branch Management

| ID | Requirement | Priority |
|---|---|---|
| FR-2.1 | A new customer signs up and creates exactly one Org, becoming its Owner | M |
| FR-2.2 | Org Owner/Admin can create, edit, and deactivate Branches under their Org | M |
| FR-2.3 | Each Branch has its own address, timezone, and operating settings independent of other branches | M |
| FR-2.4 | Org-level dashboard aggregates data across all active Branches | M |
| FR-2.5 | Deactivating a Branch preserves its historical data (soft delete, not destructive) | M |

## FR-3 Employee Management

| ID | Requirement | Priority |
|---|---|---|
| FR-3.1 | Admin/Manager can invite an employee by email; invite includes role assignment | M |
| FR-3.2 | Admin/Manager can assign an employee to one or more Branches | M |
| FR-3.3 | Admin/Manager can change an employee's role or deactivate their access | M |
| FR-3.4 | Deactivated employees' historical actions remain attributed to them in the audit log | M |

## FR-4 Species Catalog

| ID | Requirement | Priority |
|---|---|---|
| FR-4.1 | Admin/Manager can create and maintain species records (common name, botanical name, category, care requirements, typical growth curve, known disease susceptibilities) | M |
| FR-4.2 | Species records are shared/reusable across all Branches within an Org | M |
| FR-4.3 | Species records seed default values used by AI modules (e.g., water recommendation baselines) when plant-specific history is insufficient | S |
| FR-4.4 | Species can be searched/filtered by name, category, and care attributes | S |

## FR-5 Plant Digital Twin

| ID | Requirement | Priority |
|---|---|---|
| FR-5.1 | Staff can create an individual plant record linked to a Species, Branch, and (optionally) a specific zone/location | M |
| FR-5.2 | System generates a unique, durable identifier and scannable QR code for every plant record at creation | M |
| FR-5.3 | Plant record aggregates and displays: current status, images, growth timeline, health history, environmental exposure, watering log, and all AI predictions for that plant in one view | M |
| FR-5.4 | Plant status (e.g., in production, ready for sale, sold, deceased/written off) is tracked with timestamped transitions | M |
| FR-5.5 | Plants can be transferred between Branches with the transfer recorded in history | S |
| FR-5.6 | Bulk/non-individually-tracked stock is managed as Inventory (FR-12), not as individual Digital Twins, and the system supports both models side by side | M |

## FR-6 Growth Timeline

| ID | Requirement | Priority |
|---|---|---|
| FR-6.1 | Staff can log a growth measurement (height, spread, growth stage) against a plant, with optional photo | M |
| FR-6.2 | Growth timeline is viewable as a chronological chart and list on the plant's digital twin | M |
| FR-6.3 | Growth entries feed the AI Growth Prediction module (FR-8.2) | M |

## FR-7 Health & Disease Management

| ID | Requirement | Priority |
|---|---|---|
| FR-7.1 | Staff can log a health observation against a plant (status, notes, optional photo) | M |
| FR-7.2 | Staff can create a Disease Report manually, or the system creates one automatically from an AI Disease Detection result above a confidence threshold, pending human confirmation | M |
| FR-7.3 | Disease Reports track treatment applied and outcome (recovered, ongoing, plant lost) | M |
| FR-7.4 | Health history is viewable chronologically on the plant's digital twin | M |
| FR-7.5 | A confirmed Disease Report above a severity threshold triggers a Notification (FR-17) | M |

## FR-8 AI Predictions

| ID | Requirement | Priority |
|---|---|---|
| FR-8.1 | Staff can submit a plant photo for AI Disease Detection and receive a prediction with confidence score and identified condition(s) | M |
| FR-8.2 | System runs AI Growth Prediction against a plant's growth timeline and species baseline, producing a projected growth curve | M |
| FR-8.3 | System runs AI Survival Prediction against a plant's health/environmental history, producing a risk score and contributing factors | M |
| FR-8.4 | System runs AI Water Recommendation producing a recommended watering schedule per plant or per zone | M |
| FR-8.5 | System runs AI Revenue Forecast at the Branch and Org level, producing a projected revenue curve with a confidence interval | M |
| FR-8.6 | System runs an AI Recommendation Engine that surfaces prioritized, explained action suggestions (e.g., "these 12 plants are at elevated survival risk — inspect this week") | S |
| FR-8.7 | Every AI prediction is persisted with model version, inputs summary, confidence, and generated explanation — never shown to a user without being logged | M |
| FR-8.8 | Users can view historical AI predictions for a plant/branch, not just the latest | S |

## FR-9 AI Assistant

| ID | Requirement | Priority |
|---|---|---|
| FR-9.1 | Users can converse with an AI Assistant scoped to their Org's data | M |
| FR-9.2 | Assistant can answer questions by querying live tenant data (inventory levels, plant status, sales figures, AI prediction summaries) | M |
| FR-9.3 | Assistant can propose write actions (e.g., "create a watering task") that require explicit user confirmation before execution — never auto-executes a mutating action | M |
| FR-9.4 | Assistant conversation history is retained per user for continuity | S |

## FR-10 Environmental Readings

| ID | Requirement | Priority |
|---|---|---|
| FR-10.1 | Staff can manually log environmental readings (temperature, humidity, soil moisture, light) against a Branch, zone, or individual plant | M |
| FR-10.2 | System exposes an API endpoint for automated/third-party ingestion of environmental readings | S |
| FR-10.3 | Environmental readings feed Water Recommendation (FR-8.4) and Survival Prediction (FR-8.3) | M |

## FR-11 Watering Logs & Scheduling

| ID | Requirement | Priority |
|---|---|---|
| FR-11.1 | Staff can log a watering event against a plant or zone | M |
| FR-11.2 | System generates an AI-recommended watering schedule and surfaces "watering due" items on the relevant staff dashboard | M |
| FR-11.3 | Overdue watering beyond a configurable threshold triggers a Notification (FR-17) | M |

## FR-12 Inventory Management

| ID | Requirement | Priority |
|---|---|---|
| FR-12.1 | Staff can manage bulk stock records (species/product, quantity, unit, Branch) separate from individually tracked Digital Twin plants | M |
| FR-12.2 | Admin/Manager can set low-stock thresholds that trigger restock Notifications | M |
| FR-12.3 | Inventory quantities update automatically from Sales (FR-13) and Purchasing (FR-16) transactions | M |
| FR-12.4 | Inventory is filterable/searchable by Branch, species/category, and stock level | S |

## FR-13 Sales & POS

| ID | Requirement | Priority |
|---|---|---|
| FR-13.1 | Sales staff can create a sale transaction against Inventory stock and/or individually tracked plants | M |
| FR-13.2 | System prevents selling a plant/stock quantity that is not actually available (real-time inventory check) | M |
| FR-13.3 | Completed sale generates a receipt and updates the plant's status (if an individually tracked plant) to Sold | M |
| FR-13.4 | Sales can apply discounts and be associated with a Customer record | S |
| FR-13.5 | Scanning a plant's QR code at POS pulls up its record for fast checkout and customer-facing care/passport info | S |

## FR-14 Customer Management

| ID | Requirement | Priority |
|---|---|---|
| FR-14.1 | Staff can create and maintain Customer records (contact info, retail vs. wholesale classification) | M |
| FR-14.2 | Customer record shows purchase history across Sales and Invoices | M |

## FR-15 Invoicing

| ID | Requirement | Priority |
|---|---|---|
| FR-15.1 | Staff can generate an Invoice from one or more Sales, with wholesale/B2B terms (net terms, PO reference) where applicable | M |
| FR-15.2 | Invoices can be emailed to the Customer as a PDF | M |
| FR-15.3 | Invoice status is tracked (draft, sent, paid, overdue, void) | M |
| FR-15.4 | Overdue invoices trigger a Notification (FR-17) | S |

## FR-16 Supplier & Purchasing

| ID | Requirement | Priority |
|---|---|---|
| FR-16.1 | Staff can maintain Supplier records | M |
| FR-16.2 | Staff can create Purchase Orders against a Supplier | M |
| FR-16.3 | Receiving a Purchase Order updates Inventory quantities | M |

## FR-17 Notifications

| ID | Requirement | Priority |
|---|---|---|
| FR-17.1 | System delivers in-app notifications for: watering overdue, confirmed disease report, low stock, AI prediction ready, invoice overdue | M |
| FR-17.2 | System delivers the same notification classes via email | M |
| FR-17.3 | Org can optionally enable SMS delivery for critical notification classes (disease, watering overdue) | C |
| FR-17.4 | Users can configure their own notification preferences per channel and category | S |

## FR-18 Reports & Plant Passport

| ID | Requirement | Priority |
|---|---|---|
| FR-18.1 | System generates a Plant Passport (PDF) per plant containing species/provenance, health/treatment history summary, and current status, linked from the plant's QR code | M |
| FR-18.2 | System generates operational reports (inventory, sales, revenue, plant loss) exportable as PDF, Excel, and CSV | M |
| FR-18.3 | System generates AI summary reports (prediction accuracy over time, disease incidence trends) | S |
| FR-18.4 | Reports can be scheduled for recurring generation and email delivery | C (v1.1) |

## FR-19 Audit Log

| ID | Requirement | Priority |
|---|---|---|
| FR-19.1 | Every mutating action is recorded with actor, action, entity, before/after state, and timestamp | M |
| FR-19.2 | Org Admin can view and filter the audit log for their Org | M |
| FR-19.3 | Audit log entries are immutable (no update/delete path exists, including for Org Admins) | M |

## FR-20 Settings

| ID | Requirement | Priority |
|---|---|---|
| FR-20.1 | Org Admin can manage Org profile, branding, and billing/plan | M |
| FR-20.2 | Branch Manager can manage Branch-level operational settings (timezone, watering thresholds, low-stock thresholds) | M |
| FR-20.3 | Org Admin can configure notification and integration settings (SMS on/off, email sender identity) | S |
