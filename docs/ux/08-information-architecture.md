# Information Architecture

## 1. Organizing Principle

The system is organized around one central object — **the Plant** (as an individual Digital Twin) or **the Inventory line** (as bulk stock) — with every other entity existing either upstream (defines/classifies a plant: Species, Branch) or downstream (records something that happened to or because of a plant: Growth, Health, AI Predictions, Sales) of it. This mirrors BRD §2: "the plant, not the SKU, not the invoice, is the central object." Navigation, the page inventory, and the database schema (Phase 5) all derive from this same hierarchy so a user's mental model stays consistent from dashboard to detail screen to underlying record.

## 2. Content Hierarchy

```
Org (tenant boundary)
└── Branch (physical location, operational boundary for most roles)
    ├── Employees (who works here)
    ├── Species Catalog (org-wide, referenced by branch-level plants)
    ├── Plants (Digital Twin — the core object)
    │   ├── Growth Timeline (time-series, append-only)
    │   ├── Health History (time-series, append-only)
    │   ├── Disease Reports (event records, has lifecycle: open → treated → resolved)
    │   ├── Environmental Readings (time-series, append-only)
    │   ├── Watering Logs (time-series, append-only)
    │   └── AI Predictions (system-generated, append-only, versioned by model)
    ├── Inventory (bulk stock, parallel to individual Plants)
    ├── Sales (transactional, references Plants and/or Inventory)
    │   └── Invoices (financial document, references one or more Sales)
    ├── Customers (referenced by Sales/Invoices)
    ├── Suppliers (referenced by Purchase Orders)
    │   └── Purchase Orders (referenced by Inventory receiving)
    └── Notifications (system-generated, references any of the above as trigger source)

Org-wide, not branch-scoped:
├── Reports (can aggregate across branches for Owner/Admin)
├── Audit Log (org-wide activity)
└── Settings (org profile, billing, roles — branch settings nested under Branch)
```

## 3. Classification Rules

**Tenant boundary (Org):** nothing crosses it — this is the hard isolation line enforced at both application and database layers (NFR-4.3). All information architecture below this line exists only within one Org's context.

**Branch as the operational boundary:** most roles (Manager, Horticulturist, Sales Staff) never need to think above the Branch level — the IA is deliberately branch-first for navigation even though data is stored org-wide, so their daily mental model matches their daily scope. Only Owner/Admin routinely cross branch boundaries (hence the branch switcher rather than a branch-per-URL-root pattern).

**Append-only vs. mutable-lifecycle records:** Growth, Health, Environmental, and Watering records are append-only history — once logged, they are never edited, only superseded by a new entry (this matches NFR-4 audit expectations and keeps the "digital twin" narrative honest: it is a history, not a mutable snapshot). Disease Reports, Sales, Invoices, and Purchase Orders have an explicit status lifecycle (see workflow diagrams later in this document) — these are the records users actively move forward, not just log.

**Species vs. Plant:** Species is a *reference/classification* entity (like a taxonomy), Plant is an *instance*. This split exists so care-requirement knowledge is maintained once per species and inherited by every plant of that species, rather than duplicated per plant (FR-4.2).

**AI Predictions as annotations, not primary records:** predictions are always attached to (and displayed within) the entity they're about (a Plant, a Branch's revenue) rather than existing as a standalone top-level section a user browses independently — this is why "AI Predictions" appears both as a Plant tab (PG-26) and as an aggregated cross-plant dashboard (PG-31), rather than one or the other.

## 4. Naming Conventions

User-facing labels favor plain nursery-industry language over generic SaaS terms: "Plant Digital Twin" not "Asset Record," "Watering Log" not "Activity Log," "Plant Passport" not "Export Document." Internal/technical naming (API resources, DB tables — Phase 4/5) may differ from UI labels where the technical term is more precise (e.g., DB table `disease_reports` vs. UI section "Health & Disease").

## 5. Search & Findability

Global search (per `04-navigation-architecture.md`) indexes: Plant (by ID, species, common name), Species (by name), Customer (by name/contact), Inventory (by name/SKU), Invoice (by number). Disease Reports, Growth entries, and other history records are not globally searched directly — they're found by drilling into their parent Plant, consistent with the append-only-history classification above (history is browsed in context, not searched in isolation).

## 6. Metadata Standards

Every top-level entity (Branch, Plant, Inventory item, Customer, Supplier, Invoice) carries: `created_at`, `created_by`, `updated_at`, `updated_by`, and a `status` field where the entity has a lifecycle. This consistency is what makes a single Audit Log format (FR-19.1) possible across otherwise-different entity types.
