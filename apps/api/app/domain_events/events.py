"""
Module 4's required domain event types: NurseryCreated, NurseryUpdated,
BranchCreated, BranchUpdated, EmployeeInvited, EmployeeActivated,
EmployeeTransferred, EmployeeRemoved -- plus NurseryArchived/BranchArchived
(the natural "archive" counterpart the spec's own "Archive Nursery"/
"Archive Branch" operations need an event for, even though the module's
event list didn't spell those two out by name).

Every event is a frozen dataclass carrying only domain facts -- no
`occurred_at`/`request_id` (envelope metadata the publisher adds at
persist time, not part of "what happened"), no repository or session
access. `event_type`/`aggregate_type` are `ClassVar`s (not per-instance
fields), so they're fixed per event *class*, not something a caller could
accidentally set inconsistently per instance.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from typing import ClassVar


@dataclass(frozen=True)
class BaseDomainEvent:
    """
    Every event's common envelope: which aggregate it's about, which
    tenant it belongs to (nullable only in principle -- every Module 4
    event populates it, since Nursery is this module's own tenant root),
    and who caused it (nullable for system-initiated events, e.g. an
    invite auto-expiring).
    """

    event_type: ClassVar[str]
    aggregate_type: ClassVar[str]

    aggregate_id: uuid.UUID
    nursery_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None

    def payload(self) -> dict:
        """Event-specific fields only -- the envelope fields are stored in their own DB columns, not duplicated into the JSON payload."""
        data = asdict(self)
        for key in ("aggregate_id", "nursery_id", "actor_user_id"):
            data.pop(key, None)
        return data


@dataclass(frozen=True)
class NurseryCreated(BaseDomainEvent):
    event_type: ClassVar[str] = "nursery.created"
    aggregate_type: ClassVar[str] = "Nursery"

    name: str
    contact_email: str


@dataclass(frozen=True)
class NurseryUpdated(BaseDomainEvent):
    event_type: ClassVar[str] = "nursery.updated"
    aggregate_type: ClassVar[str] = "Nursery"

    changed_fields: tuple[str, ...]


@dataclass(frozen=True)
class NurseryArchived(BaseDomainEvent):
    event_type: ClassVar[str] = "nursery.archived"
    aggregate_type: ClassVar[str] = "Nursery"


@dataclass(frozen=True)
class BranchCreated(BaseDomainEvent):
    event_type: ClassVar[str] = "branch.created"
    aggregate_type: ClassVar[str] = "Branch"

    name: str
    branch_id: uuid.UUID


@dataclass(frozen=True)
class BranchUpdated(BaseDomainEvent):
    event_type: ClassVar[str] = "branch.updated"
    aggregate_type: ClassVar[str] = "Branch"

    branch_id: uuid.UUID
    changed_fields: tuple[str, ...]


@dataclass(frozen=True)
class BranchArchived(BaseDomainEvent):
    event_type: ClassVar[str] = "branch.archived"
    aggregate_type: ClassVar[str] = "Branch"

    branch_id: uuid.UUID


@dataclass(frozen=True)
class EmployeeInvited(BaseDomainEvent):
    event_type: ClassVar[str] = "employee.invited"
    aggregate_type: ClassVar[str] = "Employee"

    email: str
    role_code: str
    branch_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True)
class EmployeeActivated(BaseDomainEvent):
    """Emitted when an invited employee accepts and their Employee row transitions INVITED -> ACTIVE."""

    event_type: ClassVar[str] = "employee.activated"
    aggregate_type: ClassVar[str] = "Employee"

    employee_id: uuid.UUID
    role_code: str


@dataclass(frozen=True)
class EmployeeTransferred(BaseDomainEvent):
    event_type: ClassVar[str] = "employee.transferred"
    aggregate_type: ClassVar[str] = "Employee"

    employee_id: uuid.UUID
    from_branch_ids: tuple[uuid.UUID, ...]
    to_branch_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True)
class EmployeeRemoved(BaseDomainEvent):
    event_type: ClassVar[str] = "employee.removed"
    aggregate_type: ClassVar[str] = "Employee"

    employee_id: uuid.UUID
    reason: str | None = None


# --------------------------------------------------------------------------
# Module 5 (Species Catalog) — SpeciesCreated/Updated/Deleted,
# PlantVarietyCreated/Updated/Deleted. `PlantCategory`/`Unit` are global
# system-metadata reference tables (seeded once, migration 0002 — never
# mutated through the API), so they get no domain events of their own; only
# the per-Org catalog data an Org actually maintains (Species, PlantVariety)
# does.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SpeciesCreated(BaseDomainEvent):
    event_type: ClassVar[str] = "species.created"
    aggregate_type: ClassVar[str] = "Species"

    common_name: str
    botanical_name: str


@dataclass(frozen=True)
class SpeciesUpdated(BaseDomainEvent):
    event_type: ClassVar[str] = "species.updated"
    aggregate_type: ClassVar[str] = "Species"

    changed_fields: tuple[str, ...]


@dataclass(frozen=True)
class SpeciesDeleted(BaseDomainEvent):
    event_type: ClassVar[str] = "species.deleted"
    aggregate_type: ClassVar[str] = "Species"

    botanical_name: str


@dataclass(frozen=True)
class PlantVarietyCreated(BaseDomainEvent):
    event_type: ClassVar[str] = "plant_variety.created"
    aggregate_type: ClassVar[str] = "PlantVariety"

    species_id: uuid.UUID
    name: str


@dataclass(frozen=True)
class PlantVarietyUpdated(BaseDomainEvent):
    event_type: ClassVar[str] = "plant_variety.updated"
    aggregate_type: ClassVar[str] = "PlantVariety"

    changed_fields: tuple[str, ...]


@dataclass(frozen=True)
class PlantVarietyDeleted(BaseDomainEvent):
    event_type: ClassVar[str] = "plant_variety.deleted"
    aggregate_type: ClassVar[str] = "PlantVariety"

    species_id: uuid.UUID
    name: str


# --------------------------------------------------------------------------
# Module 6 (Plant Lifecycle Management) — one event per Plant Timeline
# entry the module's spec names by example ("Plant Registered", "Plant
# Moved", "Image Uploaded", "Watered", "Fertilized", "Disease Detected",
# "Treatment Applied", "Growth Recorded", "Health Updated", "Transferred",
# "Sold", "Disposed"). "Inventory Updated" is intentionally NOT duplicated
# here: `StockMovement` (app/models/inventory.py, Module 8) is the
# Inventory module's own append-only ledger and already carries a full
# audit trail. Module 6 does NOT read or write `inventory`/
# `stock_movements` at all -- individually-tracked Plants and bulk
# Inventory are deliberately separate, non-overlapping bounded contexts
# (docs/ux/16-inventory-workflow.md "Relationship to the Digital Twin");
# an earlier draft of Module 6 briefly wired a write path that bumped bulk
# `inventory.quantity` on every Plant registration and was removed once
# this would have double-counted a plant that's both individually tracked
# AND rolled into bulk stock. Module 8 does not subscribe to Plant
# lifecycle events for the same reason, in the other direction — see
# docs/architecture/24-module8-inventory-management.md. "Sold"/"Disposed"
# are not separate event classes either -- they are `PlantStatusChanged`
# with `to_status="sold"`/`"deceased"`, exactly the mapping documented in
# migration 0010 and docs/architecture/22-module6-plant-lifecycle.md; a
# separate PlantSold/PlantDisposed event class would duplicate the same
# fact PlantStatusChanged already states, which is the "no duplicate
# business logic" instruction this module was explicitly given.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PlantRegistered(BaseDomainEvent):
    event_type: ClassVar[str] = "plant.registered"
    aggregate_type: ClassVar[str] = "Plant"

    branch_id: uuid.UUID
    species_id: uuid.UUID
    qr_code_token: str


@dataclass(frozen=True)
class PlantUpdated(BaseDomainEvent):
    event_type: ClassVar[str] = "plant.updated"
    aggregate_type: ClassVar[str] = "Plant"

    changed_fields: tuple[str, ...]


@dataclass(frozen=True)
class PlantStatusChanged(BaseDomainEvent):
    """Also how "Sold" and "Disposed" (Deceased) show up on the Timeline -- see module docstring above."""

    event_type: ClassVar[str] = "plant.status_changed"
    aggregate_type: ClassVar[str] = "Plant"

    from_status: str
    to_status: str
    reason: str | None = None


@dataclass(frozen=True)
class PlantMoved(BaseDomainEvent):
    """Covers every kind of Plant Movement (branch transfer, zone/greenhouse/outdoor move) -- see plant_transfers' migration 0010 docstring."""

    event_type: ClassVar[str] = "plant.moved"
    aggregate_type: ClassVar[str] = "Plant"

    from_branch_id: uuid.UUID
    to_branch_id: uuid.UUID
    from_zone: str | None = None
    to_zone: str | None = None


@dataclass(frozen=True)
class PlantImageUploaded(BaseDomainEvent):
    event_type: ClassVar[str] = "plant.image_uploaded"
    aggregate_type: ClassVar[str] = "Plant"

    image_id: uuid.UUID


@dataclass(frozen=True)
class PlantArchived(BaseDomainEvent):
    """
    Administrative visibility-only action (never a business-status value --
    see migration 0010's docstring): hides a terminal-status (Sold/
    Deceased) Plant from default active listings while its full Digital
    Twin history remains queryable forever, mirroring Module 4's
    NurseryArchived/BranchArchived.
    """

    event_type: ClassVar[str] = "plant.archived"
    aggregate_type: ClassVar[str] = "Plant"


@dataclass(frozen=True)
class GrowthRecorded(BaseDomainEvent):
    event_type: ClassVar[str] = "plant.growth_recorded"
    aggregate_type: ClassVar[str] = "Plant"

    growth_entry_id: uuid.UUID
    height_cm: float | None = None


@dataclass(frozen=True)
class HealthRecorded(BaseDomainEvent):
    event_type: ClassVar[str] = "plant.health_recorded"
    aggregate_type: ClassVar[str] = "Plant"

    health_entry_id: uuid.UUID
    status_label: str = ""


@dataclass(frozen=True)
class WateringRecorded(BaseDomainEvent):
    event_type: ClassVar[str] = "plant.watering_recorded"
    aggregate_type: ClassVar[str] = "Plant"

    watering_log_id: uuid.UUID


@dataclass(frozen=True)
class FertilizerRecorded(BaseDomainEvent):
    event_type: ClassVar[str] = "plant.fertilizer_recorded"
    aggregate_type: ClassVar[str] = "Plant"

    fertilizer_log_id: uuid.UUID


@dataclass(frozen=True)
class EnvironmentalRecorded(BaseDomainEvent):
    event_type: ClassVar[str] = "plant.environmental_recorded"
    aggregate_type: ClassVar[str] = "Plant"

    reading_id: uuid.UUID


@dataclass(frozen=True)
class DiseaseDetected(BaseDomainEvent):
    """Fired on DiseaseReport creation, whether manually logged or (in a later module) AI-sourced."""

    event_type: ClassVar[str] = "plant.disease_detected"
    aggregate_type: ClassVar[str] = "Plant"

    disease_report_id: uuid.UUID
    condition_name: str
    severity: str


@dataclass(frozen=True)
class DiseaseReportUpdated(BaseDomainEvent):
    event_type: ClassVar[str] = "plant.disease_report_updated"
    aggregate_type: ClassVar[str] = "Plant"

    disease_report_id: uuid.UUID
    status: str


@dataclass(frozen=True)
class TreatmentApplied(BaseDomainEvent):
    event_type: ClassVar[str] = "plant.treatment_applied"
    aggregate_type: ClassVar[str] = "Plant"

    disease_report_id: uuid.UUID
    treatment_id: uuid.UUID
    outcome: str


# --------------------------------------------------------------------------
# Module 8 (Inventory & Stock Management) — the Inventory bounded context's
# own event vocabulary. `aggregate_type == "Inventory"`, `aggregate_id ==
# inventory.id` for every event below except `InventoryLocationCreated`
# (aggregate_type="InventoryLocation") and `InventoryMovementRecorded`
# (deliberately "Plant" -- see below).
#
# The prompt's own ARCHITECTURE section lists `PlantRegistered`,
# `PlantTransferred`, `PlantSold`, `PlantDisposed`, `PlantArchived` as
# example events Inventory "reacts to." Inventory does NOT subscribe to
# any of these -- no handler in this module is registered against them
# with the dispatcher. Doing so would mean bulk `inventory.quantity`
# incrementing/decrementing every time an *individually-tracked* Plant is
# registered/transferred/sold/disposed, which is exactly the double-
# counting bug Module 6 introduced and then removed (see plant_service.py's
# "Initial inventory assignment" docstring) and exactly what the very next
# sentence of this module's own prompt rules out: "Do not duplicate plant
# data. Inventory is a separate bounded context." The prompt's Plant*
# examples are read as illustrative real-world triggers for *this
# module's own* `StockReceived`/`StockSold`/etc. vocabulary (e.g. a
# purchase order arriving is the real-world event that becomes
# `StockReceived`), not as a literal subscription list.
#
# `StockReceived`/`StockTransferred`/`StockReserved`/`StockReleased`/
# `StockAdjusted`/`StockDisposed`/`StockDamaged`/`StockSold` are Inventory's
# own outbound facts -- other modules (Analytics in Module 12, and this
# module's own projection refresh) subscribe to THESE, the direction the
# spec's "these events must update: Inventory projections, Digital Twin
# timelines, and Analytics" sentence actually describes. The prompt's own
# "InventoryAdjustment" example event maps onto `StockAdjusted` (same
# "map spec vocabulary onto one real event" consolidation Module 6 already
# established for Sold/Disposed -> PlantStatusChanged) rather than minting
# a second, redundant event class for the same fact.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class InventoryLocationCreated(BaseDomainEvent):
    event_type: ClassVar[str] = "inventory_location.created"
    aggregate_type: ClassVar[str] = "InventoryLocation"

    branch_id: uuid.UUID
    location_type: str
    name: str
    parent_location_id: uuid.UUID | None = None


@dataclass(frozen=True)
class StockReceived(BaseDomainEvent):
    """Receiving workflow -- a purchase-order receipt or manual initial stock entry."""

    event_type: ClassVar[str] = "inventory.stock_received"
    aggregate_type: ClassVar[str] = "Inventory"

    movement_id: uuid.UUID
    quantity: int
    quantity_after: int
    to_location_id: uuid.UUID | None = None
    reference_purchase_order_id: uuid.UUID | None = None


@dataclass(frozen=True)
class StockTransferred(BaseDomainEvent):
    """
    Covers both same-branch location moves (destination_inventory_id is
    None -- one inventory row, location_id updated in place) and
    cross-branch transfers (destination_inventory_id set -- two
    StockMovement rows sharing transfer_group_id, one per branch's
    inventory row; this event is published once per affected inventory
    row, so a cross-branch transfer produces two of these).
    """

    event_type: ClassVar[str] = "inventory.stock_transferred"
    aggregate_type: ClassVar[str] = "Inventory"

    movement_id: uuid.UUID
    quantity: int
    transfer_group_id: uuid.UUID
    from_location_id: uuid.UUID | None = None
    to_location_id: uuid.UUID | None = None
    destination_inventory_id: uuid.UUID | None = None


@dataclass(frozen=True)
class StockReserved(BaseDomainEvent):
    event_type: ClassVar[str] = "inventory.stock_reserved"
    aggregate_type: ClassVar[str] = "Inventory"

    reservation_id: uuid.UUID
    quantity: int
    reference_type: str | None = None
    reference_id: uuid.UUID | None = None


@dataclass(frozen=True)
class StockReleased(BaseDomainEvent):
    event_type: ClassVar[str] = "inventory.stock_released"
    aggregate_type: ClassVar[str] = "Inventory"

    reservation_id: uuid.UUID
    quantity: int


@dataclass(frozen=True)
class StockAdjusted(BaseDomainEvent):
    """Manual correction (stocktake, count correction, internal use, other) -- the prompt's "InventoryAdjustment" example."""

    event_type: ClassVar[str] = "inventory.stock_adjusted"
    aggregate_type: ClassVar[str] = "Inventory"

    movement_id: uuid.UUID
    quantity_delta: int
    quantity_after: int
    reason: str


@dataclass(frozen=True)
class StockDisposed(BaseDomainEvent):
    """Waste — stock permanently removed (spoilage, expiry, disposal of previously-damaged stock)."""

    event_type: ClassVar[str] = "inventory.stock_disposed"
    aggregate_type: ClassVar[str] = "Inventory"

    movement_id: uuid.UUID
    quantity: int
    reason: str | None = None


@dataclass(frozen=True)
class StockDamaged(BaseDomainEvent):
    """Stock marked damaged -- still physically on hand, no longer available/sellable."""

    event_type: ClassVar[str] = "inventory.stock_damaged"
    aggregate_type: ClassVar[str] = "Inventory"

    movement_id: uuid.UUID
    quantity: int
    note: str | None = None


@dataclass(frozen=True)
class StockSold(BaseDomainEvent):
    event_type: ClassVar[str] = "inventory.stock_sold"
    aggregate_type: ClassVar[str] = "Inventory"

    movement_id: uuid.UUID
    quantity: int
    reservation_id: uuid.UUID | None = None
    reference_sale_id: uuid.UUID | None = None


@dataclass(frozen=True)
class InventoryArchived(BaseDomainEvent):
    event_type: ClassVar[str] = "inventory.archived"
    aggregate_type: ClassVar[str] = "Inventory"

    reason: str | None = None


@dataclass(frozen=True)
class InventoryMovementRecorded(BaseDomainEvent):
    """
    The ONE, narrow, deliberate coupling point between Inventory and the
    Digital Twin (Module 7). `aggregate_type` is "Plant" (not "Inventory")
    and `aggregate_id` is the plant's id, not the inventory line's --
    published only when a StockMovement carries a non-null `plant_id`
    (the rare "plant demoted from individual tracking into bulk stock"
    case docs/ux/16-inventory-workflow.md's own flowchart already
    documents). Routed through the exact same domain-events outbox and
    dispatcher every other Plant event uses, so the existing Module 7
    `DigitalTwinEventHandler` picks it up with no new plumbing beyond
    adding this event_type to `PROJECTED_EVENT_TYPES` and one handler
    method. The vast majority of stock movements never emit this event.
    """

    event_type: ClassVar[str] = "plant.inventory_movement_recorded"
    aggregate_type: ClassVar[str] = "Plant"

    movement_id: uuid.UUID
    inventory_id: uuid.UUID
    movement_type: str
    quantity: int


# --------------------------------------------------------------------------
# Module 9 (Sales, CRM, Plant Passport & QR Intelligence) — Sales' own event
# vocabulary. Sales is its own bounded context: it never writes to `plants`
# or `inventory`/`stock_movements` directly. Stock holds are taken through
# Module 8's real `InventoryService.reserve_stock()`/`release_reservation()`
# (which already publish their own `StockReserved`/`StockReleased`,
# above) -- `ReservationCreated`/`ReservationReleased` below are Sales' own,
# narrower facts ("this Sales Order's hold was created/released"),
# published immediately alongside the InventoryService call, not a
# duplicate of Inventory's own event: two bounded contexts legitimately
# narrating the same real-world moment from their own vantage point is
# normal in an event-driven design, the same way `plant.moved` and a
# `branch.updated`-adjacent fact could both exist without one being
# redundant.
#
# `PlantSold`/`PlantReturned` are `aggregate_type="Plant"` (not "Sale" or
# "SalesOrder"), riding the Plant's own event stream so the Digital Twin
# projector picks them up with no new plumbing beyond adding the event
# type to `PROJECTED_EVENT_TYPES` -- the identical pattern Module 8
# established for `InventoryMovementRecorded`. Deliberately, `SalesService`
# does NOT call `PlantService` (directly or via any handler) to flip
# `Plant.status` to SOLD -- doing so would be exactly the "couple Sales
# directly to Plant Lifecycle" this module's own ARCHITECTURE PRINCIPLES
# section forbids, and no other bounded context in this codebase writes
# into another context's transactional write-side tables in reaction to an
# event (every existing event-driven reaction -- Module 7's Digital Twin
# projector -- only ever writes its OWN derived read projection, never
# back into the origin context). `Plant.status` transitioning to SOLD
# remains PlantService's own state machine, reachable through Module 6's
# existing `PATCH /plants/{id}/status` -- see
# docs/architecture/25-module9-sales-crm-passport.md for the full
# reasoning and the disclosed tradeoff this implies.
#
# `PassportGenerated`/`QRGenerated` are also `aggregate_type="Plant"` for
# the same reason. Their payloads deliberately omit the passport's raw
# `public_token` -- domain_events rows are an internal audit trail read by
# authorized nursery staff through normal tenant-scoped tooling, a
# different (broader) audience than the one deliberately unauthenticated
# public passport endpoint; the token itself is never persisted anywhere
# an internal viewer could read it back out.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CustomerCreated(BaseDomainEvent):
    event_type: ClassVar[str] = "customer.created"
    aggregate_type: ClassVar[str] = "Customer"

    branch_id: uuid.UUID
    name: str


@dataclass(frozen=True)
class CustomerUpdated(BaseDomainEvent):
    event_type: ClassVar[str] = "customer.updated"
    aggregate_type: ClassVar[str] = "Customer"

    changed_fields: tuple[str, ...]


@dataclass(frozen=True)
class QuotationCreated(BaseDomainEvent):
    event_type: ClassVar[str] = "quotation.created"
    aggregate_type: ClassVar[str] = "Quotation"

    branch_id: uuid.UUID
    customer_id: uuid.UUID
    total_amount: str


@dataclass(frozen=True)
class QuotationStatusChanged(BaseDomainEvent):
    event_type: ClassVar[str] = "quotation.status_changed"
    aggregate_type: ClassVar[str] = "Quotation"

    from_status: str
    to_status: str


@dataclass(frozen=True)
class OrderCreated(BaseDomainEvent):
    """A SalesOrder was created (walk-up cart or converted from a Quotation)."""

    event_type: ClassVar[str] = "sales_order.created"
    aggregate_type: ClassVar[str] = "SalesOrder"

    branch_id: uuid.UUID
    customer_id: uuid.UUID
    quotation_id: uuid.UUID | None = None


@dataclass(frozen=True)
class OrderStatusChanged(BaseDomainEvent):
    event_type: ClassVar[str] = "sales_order.status_changed"
    aggregate_type: ClassVar[str] = "SalesOrder"

    from_status: str
    to_status: str


@dataclass(frozen=True)
class ReservationCreated(BaseDomainEvent):
    """Sales' own narration of a stock hold taken for an Order -- see module docstring above."""

    event_type: ClassVar[str] = "sales_order.reservation_created"
    aggregate_type: ClassVar[str] = "SalesOrder"

    order_item_id: uuid.UUID
    inventory_reservation_id: uuid.UUID
    quantity: int


@dataclass(frozen=True)
class ReservationReleased(BaseDomainEvent):
    event_type: ClassVar[str] = "sales_order.reservation_released"
    aggregate_type: ClassVar[str] = "SalesOrder"

    order_item_id: uuid.UUID
    inventory_reservation_id: uuid.UUID


@dataclass(frozen=True)
class InvoiceGenerated(BaseDomainEvent):
    event_type: ClassVar[str] = "invoice.generated"
    aggregate_type: ClassVar[str] = "Invoice"

    branch_id: uuid.UUID
    customer_id: uuid.UUID
    total_amount: str
    sale_id: uuid.UUID | None = None


@dataclass(frozen=True)
class PaymentReceived(BaseDomainEvent):
    event_type: ClassVar[str] = "invoice.payment_received"
    aggregate_type: ClassVar[str] = "Invoice"

    payment_id: uuid.UUID
    amount: str
    method: str
    invoice_fully_paid: bool = False


@dataclass(frozen=True)
class PlantSold(BaseDomainEvent):
    """
    Fired once per individually-tracked plant sold as a Sale line item.
    `aggregate_type="Plant"` -- see the module docstring above for why
    this does NOT also flip `Plant.status`.
    """

    event_type: ClassVar[str] = "plant.sold"
    aggregate_type: ClassVar[str] = "Plant"

    sale_id: uuid.UUID
    sale_item_id: uuid.UUID
    customer_id: uuid.UUID | None
    unit_price: str


@dataclass(frozen=True)
class PlantReturned(BaseDomainEvent):
    event_type: ClassVar[str] = "plant.returned"
    aggregate_type: ClassVar[str] = "Plant"

    return_id: uuid.UUID
    return_item_id: uuid.UUID
    condition: str


@dataclass(frozen=True)
class RefundProcessed(BaseDomainEvent):
    event_type: ClassVar[str] = "refund.processed"
    aggregate_type: ClassVar[str] = "Refund"

    amount: str
    method: str
    return_id: uuid.UUID | None = None
    invoice_id: uuid.UUID | None = None
    sale_id: uuid.UUID | None = None


@dataclass(frozen=True)
class PassportGenerated(BaseDomainEvent):
    """`public_token` deliberately omitted from the payload -- see module docstring above."""

    event_type: ClassVar[str] = "plant.passport_generated"
    aggregate_type: ClassVar[str] = "Plant"

    passport_id: uuid.UUID
    version: int


@dataclass(frozen=True)
class QRGenerated(BaseDomainEvent):
    event_type: ClassVar[str] = "plant.qr_generated"
    aggregate_type: ClassVar[str] = "Plant"

    passport_id: uuid.UUID


# ==============================================================================
# Phase 6 Module 10 (AI Platform)
# ==============================================================================
#
# Two AIPrediction* events, not one, for the same reason Module 8's
# `InventoryMovementRecorded` only fires for the plant-linked case rather
# than trying to force one event class to cover two different aggregate
# scopes: `AIPrediction.plant_id` is nullable (Phase 5 schema) -- Disease
# Detection/Growth/Survival/Water Recommendation always populate it (they
# are inherently about one plant), Revenue Forecast never does (it is
# branch/org-level, per FR-8.5). `aggregate_type` is a per-class `ClassVar`,
# so a single event class cannot carry two different aggregate scopes;
# `AIPredictionGenerated` (aggregate_type="Plant") is what reaches the
# per-plant Digital Twin projector -- see app/services/digital_twin_service.py's
# long-standing "AI Prediction Timeline... once Module 10 starts writing
# real rows, this section is already correct" note, now made true.
# `AIPredictionGeneratedForBranch` (aggregate_type="Branch") is Revenue
# Forecast's own event; nothing before this module has a per-branch
# Digital-Twin-shaped projection to feed, so it is published for the same
# reasons every other event in this codebase is (audit trail, outbox
# durability, future consumers) without a projector needing to exist yet --
# identical position Module 6's `PlantArchived` was in before Module 7
# existed to consume it.
@dataclass(frozen=True)
class AIPredictionGenerated(BaseDomainEvent):
    """One of Disease Detection/Growth/Survival/Water Recommendation ran for a specific plant. `aggregate_id` is the `plant_id`."""

    event_type: ClassVar[str] = "ai.prediction_generated"
    aggregate_type: ClassVar[str] = "Plant"

    prediction_id: uuid.UUID
    prediction_type: str
    model_version: str
    confidence: str | None = None


@dataclass(frozen=True)
class AIPredictionGeneratedForBranch(BaseDomainEvent):
    """Revenue Forecast (or any future branch/org-level prediction type) ran. `aggregate_id` is the `branch_id`."""

    event_type: ClassVar[str] = "ai.prediction_generated_for_branch"
    aggregate_type: ClassVar[str] = "Branch"

    prediction_id: uuid.UUID
    prediction_type: str
    model_version: str
    confidence: str | None = None


@dataclass(frozen=True)
class AIRecommendationGenerated(BaseDomainEvent):
    """The Recommendation Engine produced one prioritized, explained action suggestion (FR-8.6). `aggregate_id` is the `branch_id`."""

    event_type: ClassVar[str] = "ai.recommendation_generated"
    aggregate_type: ClassVar[str] = "Branch"

    recommendation_id: uuid.UUID
    priority: str
    source_prediction_id: uuid.UUID | None = None


@dataclass(frozen=True)
class AIRecommendationDismissed(BaseDomainEvent):
    event_type: ClassVar[str] = "ai.recommendation_dismissed"
    aggregate_type: ClassVar[str] = "Branch"

    recommendation_id: uuid.UUID


@dataclass(frozen=True)
class AIRecommendationActedUpon(BaseDomainEvent):
    event_type: ClassVar[str] = "ai.recommendation_acted_upon"
    aggregate_type: ClassVar[str] = "Branch"

    recommendation_id: uuid.UUID


@dataclass(frozen=True)
class AssistantConversationStarted(BaseDomainEvent):
    """FR-9.4. `aggregate_id` is the conversation's own id, matching the SalesOrder/Quotation precedent of a fresh aggregate owning its own event stream."""

    event_type: ClassVar[str] = "ai_assistant.conversation_started"
    aggregate_type: ClassVar[str] = "AIAssistantConversation"

    user_id: uuid.UUID


@dataclass(frozen=True)
class AssistantMessageSent(BaseDomainEvent):
    """
    Fired once per message, `role` distinguishing "user" from "assistant".
    Token/cost fields mirror migration 0015's `ai_assistant_messages`
    columns -- null for `role="user"`, populated for `role="assistant"`.
    """

    event_type: ClassVar[str] = "ai_assistant.message_sent"
    aggregate_type: ClassVar[str] = "AIAssistantConversation"

    message_id: uuid.UUID
    role: str
    model_name: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: str | None = None


@dataclass(frozen=True)
class AssistantActionProposed(BaseDomainEvent):
    """
    FR-9.3's mandatory confirmation gate: the assistant proposed a write
    but did NOT execute it. `tool_name` is one of `AssistantToolRegistry`'s
    registered write tools (e.g. `propose_watering_log`); `tool_arguments`
    is the exact argument set that will be re-validated and passed to the
    real service method if/when a human confirms -- never executed from
    this event alone.
    """

    event_type: ClassVar[str] = "ai_assistant.action_proposed"
    aggregate_type: ClassVar[str] = "AIAssistantConversation"

    message_id: uuid.UUID
    tool_name: str
    tool_arguments: dict


@dataclass(frozen=True)
class AssistantActionConfirmed(BaseDomainEvent):
    """
    The human confirmed a previously proposed action, and the underlying
    write went through the *same* service method the native page would
    have called (never assistant-only logic) -- `result_summary` is a
    short, human-readable description of what happened (e.g. "Watering
    log recorded for Ficus lyrata #A102"), not the raw service response.
    """

    event_type: ClassVar[str] = "ai_assistant.action_confirmed"
    aggregate_type: ClassVar[str] = "AIAssistantConversation"

    message_id: uuid.UUID
    tool_name: str
    result_summary: str


@dataclass(frozen=True)
class AssistantActionCancelled(BaseDomainEvent):
    event_type: ClassVar[str] = "ai_assistant.action_cancelled"
    aggregate_type: ClassVar[str] = "AIAssistantConversation"

    message_id: uuid.UUID
    tool_name: str


# ==============================================================================
# Knowledge Articles (RAG Ingestion Pipeline)
# ==============================================================================


@dataclass(frozen=True)
class KnowledgeArticleCreated(BaseDomainEvent):
    """Fired when a knowledge article is ingested into the RAG knowledge base."""

    event_type: ClassVar[str] = "knowledge_article.created"
    aggregate_type: ClassVar[str] = "KnowledgeBaseChunk"

    source_ref: str
    title: str
    chunk_count: int


@dataclass(frozen=True)
class KnowledgeArticleUpdated(BaseDomainEvent):
    """Fired when a knowledge article is re-ingested (old chunks replaced)."""

    event_type: ClassVar[str] = "knowledge_article.updated"
    aggregate_type: ClassVar[str] = "KnowledgeBaseChunk"

    source_ref: str
    title: str
    chunk_count: int


@dataclass(frozen=True)
class KnowledgeArticleDeleted(BaseDomainEvent):
    """Fired when a knowledge article's chunks are removed from the RAG store."""

    event_type: ClassVar[str] = "knowledge_article.deleted"
    aggregate_type: ClassVar[str] = "KnowledgeBaseChunk"

    source_ref: str
    deleted_chunk_count: int


# ==============================================================================
# Phase 6 Module 11 (Notifications) — this module's OWN new event vocabulary.
# Thirteen of its sixteen required notification categories are driven by
# events every prior module already publishes (EmployeeInvited,
# PlantRegistered, PlantStatusChanged, DiseaseDetected, PlantSold,
# StockReserved, StockTransferred, InvoiceGenerated, PaymentReceived,
# AIRecommendationGenerated, and a live-Inventory-row threshold check
# reacting to any stock-decreasing event for Low Stock) -- see
# docs/architecture/27-module11-notifications.md for the full category ->
# event mapping. Only four genuinely new events were needed, all below.
#
# `PasswordResetRequested`/`EmailVerificationRequested` are DELIBERATELY
# token-free: `DomainEventPublisher.publish()` persists every event's full
# `payload()` to the `domain_events` audit table (see that class's own
# docstring) — putting a raw, still-valid password-reset/email-verification
# token in a payload would mean it sits in plaintext in a permanent audit
# log, a real security regression versus today's design (the token is
# hashed before being stored in its own single-purpose token table, and the
# raw value only ever exists transiently in memory and in the one email
# sent to the user). These two events exist for observability (an org's
# security-event visibility) and to make "Password Reset"/"Email
# Verification" real, testable notification categories, exactly as this
# module's own spec requires -- but `AuthService` continues to send the
# actual token-bearing email itself, synchronously, immediately after
# publishing the event, through this module's own `EmailProvider`
# interface (not the old ad-hoc `EmailSender` Protocol, now merged into
# it) rather than through the async per-recipient-preference notification
# pipeline: a password reset link must not be delayed, digested, or
# suppressed by a user's "email notifications off" preference. This is
# the one narrow, disclosed exception to this module's own "no business
# module sends notifications directly" rule, and it is a security
# necessity, not a convenience shortcut — restated in
# docs/architecture/27-module11-notifications.md.
@dataclass(frozen=True)
class PasswordResetRequested(BaseDomainEvent):
    event_type: ClassVar[str] = "auth.password_reset_requested"
    aggregate_type: ClassVar[str] = "User"

    requested_ip: str | None = None


@dataclass(frozen=True)
class EmailVerificationRequested(BaseDomainEvent):
    event_type: ClassVar[str] = "auth.email_verification_requested"
    aggregate_type: ClassVar[str] = "User"


@dataclass(frozen=True)
class SystemAlertRaised(BaseDomainEvent):
    """
    An Org Admin/Owner broadcasting an operational alert to their own
    org's staff (`POST /notifications/system-alerts`) -- e.g. "Irrigation
    system offline at Riverside Branch". `aggregate_id` is a fresh id for
    this alert (no pre-existing aggregate an alert is "about"), matching
    `AssistantConversationStarted`'s own "a fresh aggregate owning its own
    event stream" precedent.
    """

    event_type: ClassVar[str] = "notification.system_alert_raised"
    aggregate_type: ClassVar[str] = "SystemAlert"

    title: str
    message: str
    severity: str


@dataclass(frozen=True)
class ReservationExpiringSoon(BaseDomainEvent):
    """
    Published by `NotificationService.check_expiring_reservations()`, an
    on-demand scan (no Celery/scheduled-job infrastructure exists anywhere
    in this codebase through Module 10 -- see that method's own docstring)
    over `StockReservation` rows whose `expires_at` falls within a
    configurable horizon. `aggregate_id` is the `inventory_id` (matching
    every other Inventory-scoped Module 8 event's own convention).
    """

    event_type: ClassVar[str] = "inventory.reservation_expiring_soon"
    aggregate_type: ClassVar[str] = "Inventory"

    reservation_id: uuid.UUID
    expires_at: str
    minutes_remaining: int


# --------------------------------------------------------------------------
# Phase 6 Module 12 — Reports & Analytics
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ReportGenerated(BaseDomainEvent):
    """
    Published by `ReportGenerationService` once a background report-build
    task finishes successfully. Two independent subscribers react to
    this, neither aware of the other (the same "one event, multiple
    independent subscribers" shape `PlantStatusChanged` already
    demonstrates for Digital Twin + Notifications): `AnalyticsEventHandler`
    treats it as a no-op (a report isn't a rollup input), and
    `NotificationEventHandler` (Module 11) notifies the requesting user
    their report is ready -- `aggregate_id` is the `Report.id`.
    """

    event_type: ClassVar[str] = "report.generated"
    aggregate_type: ClassVar[str] = "Report"

    report_type: str
    format: str
    file_url: str


@dataclass(frozen=True)
class ReportFailed(BaseDomainEvent):
    """Published when the background report-build task raises. Notifies the requester rather than leaving a silently-`FAILED` row nobody is told about."""

    event_type: ClassVar[str] = "report.failed"
    aggregate_type: ClassVar[str] = "Report"

    report_type: str
    error_message: str
