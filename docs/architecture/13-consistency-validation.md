# Architecture Consistency Validation

Performed before Phase 5 implementation begins, per your instruction. Each of the 10 checks was run against the actual Phase 1–4 documents (cross-referenced, not just asserted). Three real inconsistencies were found and fixed during this pass; they're detailed in §11. Everything else validated clean.

## 1. Every Functional Requirement mapped to one or more modules

Cross-checked all 20 FR groups (84 individually-numbered sub-requirements) in `docs/product/04-functional-requirements.md` against the 19 modules in `docs/architecture/02-low-level-design.md`. Confirmed 1:1 or clearer at the group level in `docs/architecture/12-final-architecture-review.md`'s traceability table. Result: **complete, no orphan FRs.**

## 2. Every User Story traceable to database entities

Checked all 20 user stories (`docs/product/06-user-stories.md`, Epics A–H) against the entity catalog (`docs/architecture/05-database-architecture.md` §2). Every story's "Acceptance" criteria references data that maps to a cataloged entity (e.g., US-C.2's QR code → `plants.qr_code_token`; US-E.3's at-risk ranking → `ai_predictions`; US-F.4's wholesale invoice → `invoices`/`invoice_items`). Result: **complete.**

## 3. Every page has supporting APIs

Checked all 59 pages' "API dependencies" column in `docs/ux/09-page-inventory.md` against the endpoint catalog in `docs/architecture/07-api-design.md` §1. Every page-level dependency resolves to a cataloged endpoint. Result: **complete** (after the fix in §11.2/11.3 below — two pages' delete actions, PG-18 Species and PG-48 Supplier, referenced a "Danger Zone"-style delete affordance implied by the design spec's confirmation-dialog rules but the endpoint didn't exist yet).

## 4. Every API maps to database tables

Checked every endpoint in `07-api-design.md` §1 against the entity catalog. Every endpoint reads or writes at least one cataloged table. No endpoint operates on an undefined table. Result: **complete.**

## 5. Every AI feature has its required data pipeline

Checked all 6 prediction modules + Assistant (FR-8/FR-9) against `docs/architecture/06-ai-architecture.md` §4 (Feature Engineering) — each module's declared feature set traces to specific source tables that exist in the entity catalog. Result: **complete.**

## 6. Every role has complete permission coverage

Checked all 6 roles (`docs/ux/07-role-permission-matrix.md`) against every module's action set. Found and fixed 2 gaps — see §11.1 and §11.3. After the fix, every module with a delete-capable UX affordance (per `docs/design/08-ux-documentation.md` §5's confirmation-dialog list: Branch, Employee, Sale/void, Invoice/void, Plant/deceased, Species, Supplier) has a corresponding permission code, and no permission code exists without a corresponding operation. Result: **complete after fix.**

## 7. Every notification has an event source

Checked all 8 trigger categories in `docs/ux/14-notification-workflow.md`'s Trigger Catalog against the LLD modules' "Notification module" dependency notes. Every trigger (disease confirmed, watering overdue, low stock, AI prediction ready, invoice overdue, employee invite, plant transferred, PO received) has an explicit producing module in `02-low-level-design.md`. Result: **complete.**

## 8. Every report has supporting database queries

Checked all report types on PG-51 (Inventory, Sales, Revenue, Plant Loss, AI Summary, Plant Passport) against `docs/ux/18-analytics-workflow.md`'s Metrics Catalog and the entity catalog. Every report type's underlying data traces to specific tables/rollups. Result: **complete.**

## 9. Every workflow has complete state transitions

Checked all state-machine workflows: Plant Digital Twin (`docs/ux/13-digital-twin-lifecycle.md`), Disease Report (drafted → confirmed/dismissed → treated → resolved), Sale (completed → voided), Invoice (draft → sent → paid/overdue → void), Purchase Order (draft → sent → partially received → received). Every state has a defined entry trigger and every non-terminal state has at least one defined exit transition (no dead-end states, no unreachable states). Result: **complete.**

## 10. Every database table belongs to a specific bounded context

Checked the full entity catalog (`05-database-architecture.md` §2) against the module list — every table's "Tenant scope" column and its owning module are unambiguous (e.g., `growth_timeline` belongs to the Growth Timeline module and nowhere else; `ai_predictions` belongs to the AI Predictions orchestration module even though six sub-modules write to it, since they share one logging contract per FR-8.7). No table is written to by more than one module's service layer except through the single designated write-path pattern already documented (e.g., only `InventoryService.apply_change()` writes to `inventory`, called by Sales/Purchasing but not written to directly by them). Result: **complete.**

## 11. Inconsistencies Found and Fixed

**11.1 — Orphan permission: `plants:delete`.** The permission matrix granted `plants:delete` to Owner/Admin/Branch Manager, but no delete operation exists anywhere in the architecture — plants are never hard-deleted; the lifecycle model (`docs/ux/13-digital-twin-lifecycle.md`) only supports a status transition to `Deceased`, which is already gated by `plants:write`. **Fix:** removed the `plants:delete` row from `docs/ux/07-role-permission-matrix.md`.

**11.2 — Missing endpoint: Species deletion.** The Database Architecture document's relationship notes stated "`species:delete` is blocked at the service layer if referenced" — implying a delete operation exists — and the UX documentation's confirmation-dialog rules (`docs/design/08-ux-documentation.md` §5) explicitly lists "deleting a Species" as a destructive action requiring confirmation, but no `DELETE /species/{id}` endpoint was ever defined in the LLD or API catalog. **Fix:** added `DELETE /species/{id}` to the Species Catalog module in `docs/architecture/02-low-level-design.md` and to the endpoint catalog in `docs/architecture/07-api-design.md`, with the referential-integrity guard (blocked if any plant references it) made explicit.

**11.3 — Missing permission + endpoint: Supplier deletion.** Same root cause as 11.2 — `docs/design/08-ux-documentation.md` §5 lists "deleting a ... Supplier" as a confirmation-gated action, but neither a `suppliers:delete` permission nor a `DELETE /suppliers/{id}` endpoint existed anywhere. **Fix:** added `suppliers:delete` to the permission matrix and `DELETE /suppliers/{id}` to the LLD Suppliers & Purchasing module and the API catalog, guarded against suppliers referenced by an existing purchase order.

## Conclusion

All 10 consistency checks pass after the three fixes above. The corrected documents (`docs/ux/07-role-permission-matrix.md`, `docs/architecture/02-low-level-design.md`, `docs/architecture/07-api-design.md`) are the current source of truth going into Phase 5 — no further architectural changes are needed before database implementation begins.
