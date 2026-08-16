"""
Phase 6 Module 7 -- Plant Digital Twin Engine.

`DigitalTwinService` is the *only* code in the entire codebase that ever
writes to `digital_twins`/`digital_twin_versions`. It has no public
"update" method any route could call -- its write surface is exactly one
method, `project(event)`, invoked exclusively by `DigitalTwinEventHandler`
(the bottom of this file) via `EventDispatcher` in reaction to a
`domain_events` row. This is what makes "No API route should modify the
Digital Twin directly" a structural fact, not a convention: there is no
other path to a write.

Snapshot shape (`digital_twins.snapshot` / `digital_twin_versions.
snapshot`) stores *latest-value summaries and counts*, not growing lists
-- see app/models/digital_twin.py's `DigitalTwin` docstring for why. Full
historical timelines are served by `get_timeline`/`get_event_history`
below, which read `digital_twin_versions`/`domain_events` directly.

    {
      "identity": {plant_id, nursery_id, species_id, variety_id,
                    qr_code_token, common_label, batch_number,
                    registered_at},
      "lifecycle_state": "in_production" | "ready_for_sale" | ...,
      "operational_status": "active" | "under_treatment" | "sold" |
                              "deceased" | "archived",
      "growth_stage": "seedling" | "growing" | "mature" | null,
      "current_location": {branch_id, zone},
      "counts": {growth, health, watering, fertilizer, environmental,
                  disease_reports, treatments, movements, images},
      "latest": {growth, health, watering, fertilizer, environmental,
                  disease, treatment} -- each null or a small dict,
      "sold_at", "deceased_at", "deceased_reason",
      "archived_at", "archived_reason",
    }

Two sections from the spec's 14-item "Include" list are deliberately
absent from every snapshot, both for the same reason Module 6's own
PlantTimelineService already gave for the identical omissions:

  - **Inventory Timeline**: `inventory_adjustments.inventory_id` FKs to
    the bulk `inventory` table (SKU-level stock), which carries no
    `plant_id` column at all -- there is no valid join from an
    individually-tracked Plant to an Inventory adjustment (see Module 6's
    own "Inventory and Plant are deliberately separate models" doc
    section). This isn't a gap to fill later; it's structurally
    inapplicable to a Plant's own Digital Twin.
  - **AI Prediction Timeline**: DONE as of Module 10 (AI Platform).
    `ai_predictions.plant_id` genuinely joins to a Plant; the full
    historical list (FR-8.8) is served live from `ai_predictions` by
    `GET /plants/{id}/ai-predictions` (app/api/routes/ai_predictions.py),
    exactly like every other historical timeline this file's own module
    docstring already described (not a growing list in the snapshot). The
    snapshot itself gained a `counts.ai_predictions` / `latest.ai_prediction`
    quick-glance summary, projected from `AIPredictionGenerated`
    (`_on_ai_prediction_generated` below) -- `AIPredictionGeneratedForBranch`
    (Revenue Forecast) is NOT projected here since its `aggregate_type` is
    "Branch", not "Plant" (see app/domain_events/events.py's own comment).

Ordering/idempotency at the projection level (belt-and-suspenders on top
of `EventDispatcher`'s own `event_dispatch_log` idempotency check -- see
that module's docstring): `project()` refuses to regress an already-
applied projection by comparing `event.sequence` against the twin's
`last_event_sequence` before doing any work.
"""
from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass
from datetime import datetime

from app.core.exceptions import ConflictError, NotFoundError
from app.db.enums import PlantStatus
from app.models.events import DomainEvent
from app.models.digital_twin import DigitalTwin, DigitalTwinVersion
from app.repositories.interfaces import (
    DigitalTwinRepository,
    DigitalTwinVersionRepository,
    DiseaseReportRepository,
    DomainEventRepository,
    EnvironmentalReadingRepository,
    FertilizerLogRepository,
    GrowthTimelineRepository,
    HealthHistoryRepository,
    PlantRepository,
    ReturnItemRepository,
    TreatmentRepository,
    WateringLogRepository,
)

# Every Module 6 event type this projector reacts to, plus one Module 8
# addition. Kept as one explicit set (not "everything published") because
# a handler must declare exactly what it's interested in -- see
# EventHandler's own docstring in app/domain_events/dispatcher.py.
#
# "plant.inventory_movement_recorded" (Module 8, Inventory & Stock
# Management) corrects this file's own prior "Inventory Timeline...
# structurally inapplicable" claim (docs/architecture/23-module7-digital-twin-engine.md,
# written before Module 8 existed): that claim was true of the bulk
# `inventory`/`stock_movements` tables, which genuinely have no `plant_id`
# join for the vast majority of rows -- but Module 8 added an *optional*
# `StockMovement.plant_id` column for the one documented case where a
# stock movement concerns a specific individually-tracked plant
# (docs/ux/16-inventory-workflow.md's "plant demoted from individual
# tracking" flow). `InventoryService` publishes this event, aggregate_type
# "Plant", only when that column is set -- never inferred automatically,
# never for ordinary bulk-SKU movements, and never a direct write into
# `digital_twins`/`digital_twin_versions` (still exclusively this
# projector's job). See docs/architecture/24-module8-inventory-management.md
# for the full reasoning.
# Module 9 (Sales, CRM, Plant Passport & QR Intelligence) additions:
# "plant.sold" / "plant.returned" / "plant.passport_generated" /
# "plant.qr_generated" are all published with aggregate_type="Plant",
# aggregate_id=<the plant's own id> (see app/domain_events/events.py) --
# exactly the same "Plant"-keyed shape every event above already has, so
# they slot into this same per-plant projector with zero change to
# `project()`'s own dispatch logic. This is what lets the module's
# "Digital Twin Integration: Sales events must update Sales Timeline,
# Ownership Timeline" requirement be satisfied by the *existing*
# `get_timeline`/`get_event_history` query methods below (a caller wanting
# "the Sales Timeline" or "the Ownership Timeline" for a plant filters
# those generic, already-paginated results by `event_type` client-side --
# exactly how "Growth Timeline"/"Health Timeline"/etc. already work; see
# this file's own module docstring on why full historical timelines are
# never separate stored lists).
#
# "invoice.payment_received" / "invoice.generated" / "refund.processed"
# are deliberately NOT in this set and never will be with the projector
# in its current, per-plant-keyed form: their `aggregate_type` is
# "Invoice"/"Refund", not "Plant" -- `aggregate_id` is an invoice/refund
# id, which `project()` uses directly as the twin's `plant_id` lookup key
# (see `project()` below). There is no plant to attribute a nursery-wide
# payment/invoice/refund event to without a Sale->SaleItem->plant_id join
# this module's event payloads don't carry, and inventing one here would
# mean guessing at exactly the kind of double-counting/faked-relationship
# bug Module 8's own docstring (this file, further down) already
# describes avoiding. "Revenue Timeline" at the *per-plant* Digital Twin
# level is therefore derived from the two events that genuinely are
# plant-scoped -- `plant.sold`'s `unit_price` and `plant.returned`'s
# associated `ReturnItem.line_refund_amount` (see `_on_plant_returned`
# below) -- while nursery-wide revenue (the module's own "Revenue
# Reports" requirement) is correctly served by
# `SalesReportingService.revenue_report` instead (app/services/
# sales_service.py), which has no per-plant scoping problem to solve.
PROJECTED_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "plant.registered",
        "plant.updated",
        "plant.status_changed",
        "plant.moved",
        "plant.image_uploaded",
        "plant.archived",
        "plant.growth_recorded",
        "plant.health_recorded",
        "plant.watering_recorded",
        "plant.fertilizer_recorded",
        "plant.environmental_recorded",
        "plant.disease_detected",
        "plant.disease_report_updated",
        "plant.treatment_applied",
        "plant.inventory_movement_recorded",
        "plant.sold",
        "plant.returned",
        "plant.passport_generated",
        "plant.qr_generated",
        # Module 10 (AI Platform): "ai.prediction_generated" (NOT
        # "ai.prediction_generated_for_branch" -- that one's aggregate_type
        # is "Branch", not "Plant", so it has no per-plant twin to project
        # into; see app/domain_events/events.py's own comment on this
        # split). Fulfills this file's own long-standing "AI Prediction
        # Timeline... once Module 10 starts writing real rows, this
        # section is already correct" note from the module docstring
        # above -- `_on_ai_prediction_generated` below is that promised
        # "no further change needed" becoming real.
        "ai.prediction_generated",
    }
)

_OPERATIONAL_STATUS_BY_LIFECYCLE = {
    PlantStatus.IN_PRODUCTION.value: "active",
    PlantStatus.READY_FOR_SALE.value: "active",
    PlantStatus.UNDER_TREATMENT.value: "under_treatment",
    PlantStatus.SOLD.value: "sold",
    PlantStatus.DECEASED.value: "deceased",
}

_EMPTY_COUNTS = {
    "growth": 0, "health": 0, "watering": 0, "fertilizer": 0, "environmental": 0,
    "disease_reports": 0, "treatments": 0, "movements": 0, "images": 0, "inventory_movements": 0,
    "plant_sold": 0, "plant_returned": 0, "passports_generated": 0, "qr_generated": 0,
    "ai_predictions": 0,
}
_EMPTY_LATEST = {
    "growth": None, "health": None, "watering": None, "fertilizer": None,
    "environmental": None, "disease": None, "treatment": None, "inventory_movement": None,
    "sale": None, "return": None, "passport": None, "qr": None,
    "ai_prediction": None,
}
_DEFAULT_OWNERSHIP = {"owner_type": "nursery", "customer_id": None, "since": None}


def _maybe_uuid(value: object) -> uuid.UUID | None:
    """
    Event payloads are JSON-safe (`DomainEventPublisher._json_safe`
    stringifies every UUID before persisting), so a payload's `branch_id`/
    `to_branch_id`/etc. always arrives here as a `str`, never a native
    `uuid.UUID` -- this is the one place that converts back for populating
    `DigitalTwin`'s typed `branch_id` column.
    """
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _as_float(value: object) -> float:
    """See app/services/inventory_service.py's identical helper — same pre-existing `Mapped[Numeric | None]` typing imprecision, same fix. Used by `_on_plant_returned` below for the enriched `line_refund_amount` read."""
    return float(value or 0)  # type: ignore[arg-type]


@dataclass(frozen=True)
class VersionComparison:
    """"Version comparison" (spec's own term) -- both full snapshots plus the flat set of top-level keys that differ between them."""

    plant_id: uuid.UUID
    version_a: int
    version_b: int
    snapshot_a: dict
    snapshot_b: dict
    changed_keys: tuple[str, ...]


class DigitalTwinService:
    def __init__(
        self,
        *,
        twin_repo: DigitalTwinRepository,
        version_repo: DigitalTwinVersionRepository,
        domain_event_repo: DomainEventRepository,
        plant_repo: PlantRepository,
        growth_repo: GrowthTimelineRepository,
        health_repo: HealthHistoryRepository,
        watering_repo: WateringLogRepository,
        fertilizer_repo: FertilizerLogRepository,
        environmental_repo: EnvironmentalReadingRepository,
        disease_repo: DiseaseReportRepository,
        treatment_repo: TreatmentRepository,
        return_item_repo: ReturnItemRepository,
    ) -> None:
        self._twins = twin_repo
        self._versions = version_repo
        self._events = domain_event_repo
        self._plants = plant_repo
        self._growth = growth_repo
        self._health = health_repo
        self._watering = watering_repo
        self._fertilizer = fertilizer_repo
        self._environmental = environmental_repo
        self._disease = disease_repo
        self._treatments = treatment_repo
        self._return_items = return_item_repo
        self._handlers = {
            "plant.updated": self._on_plant_updated,
            "plant.status_changed": self._on_plant_status_changed,
            "plant.moved": self._on_plant_moved,
            "plant.image_uploaded": self._on_plant_image_uploaded,
            "plant.archived": self._on_plant_archived,
            "plant.growth_recorded": self._on_growth_recorded,
            "plant.health_recorded": self._on_health_recorded,
            "plant.watering_recorded": self._on_watering_recorded,
            "plant.fertilizer_recorded": self._on_fertilizer_recorded,
            "plant.environmental_recorded": self._on_environmental_recorded,
            "plant.disease_detected": self._on_disease_detected,
            "plant.disease_report_updated": self._on_disease_report_updated,
            "plant.treatment_applied": self._on_treatment_applied,
            "plant.inventory_movement_recorded": self._on_inventory_movement_recorded,
            "plant.sold": self._on_plant_sold,
            "plant.returned": self._on_plant_returned,
            "plant.passport_generated": self._on_passport_generated,
            "plant.qr_generated": self._on_qr_generated,
            "ai.prediction_generated": self._on_ai_prediction_generated,
        }

    # ------------------------------------------------------------------
    # The one write path: project() -- called only by DigitalTwinEventHandler.
    # ------------------------------------------------------------------

    async def project(self, event: DomainEvent) -> int:
        """
        Apply one domain event to the plant's projection, creating it if
        this is the plant's `plant.registered` event. Returns the
        resulting version number. Idempotent: an event whose `sequence` is
        `<=` the twin's already-recorded `last_event_sequence` is treated
        as already applied and returns the current version unchanged
        without writing a new one.
        """
        plant_id = event.aggregate_id
        twin = await self._twins.get_by_plant_id(plant_id)

        if event.event_type == "plant.registered":
            if twin is not None:
                # Already projected (duplicate delivery) -- idempotent no-op.
                return twin.current_version
            return await self._create_twin(event)

        if twin is None:
            raise NotFoundError(
                f"No Digital Twin exists for plant {plant_id} -- a non-registration event "
                f"({event.event_type}) arrived before plant.registered was projected."
            )
        if twin.last_event_sequence is not None and event.sequence <= twin.last_event_sequence:
            # Already applied (or older than what's applied) -- ordering/idempotency guard.
            return twin.current_version

        handler = self._handlers.get(event.event_type)
        if handler is None:
            # Registered with the dispatcher for exactly PROJECTED_EVENT_TYPES -- unreachable in practice.
            return twin.current_version

        new_snapshot = await handler(copy.deepcopy(twin.snapshot), event)
        return await self._write_version(twin, new_snapshot, event)

    async def _create_twin(self, event: DomainEvent) -> int:
        plant = await self._plants.get_by_id(event.aggregate_id)
        payload = event.payload
        snapshot = {
            "identity": {
                "plant_id": str(event.aggregate_id),
                "nursery_id": str(event.nursery_id) if event.nursery_id else None,
                "species_id": payload.get("species_id"),
                "variety_id": str(plant.variety_id) if plant and plant.variety_id else None,
                "qr_code_token": payload.get("qr_code_token"),
                "common_label": plant.common_label if plant else None,
                "batch_number": plant.batch_number if plant else None,
                "registered_at": event.occurred_at.isoformat(),
            },
            "lifecycle_state": PlantStatus.IN_PRODUCTION.value,
            "operational_status": "active",
            "growth_stage": None,
            "current_location": {"branch_id": payload.get("branch_id"), "zone": None},
            "counts": dict(_EMPTY_COUNTS),
            "latest": dict(_EMPTY_LATEST),
            "ownership": dict(_DEFAULT_OWNERSHIP),
            "sold_at": None,
            "deceased_at": None,
            "deceased_reason": None,
            "archived_at": None,
            "archived_reason": None,
        }
        twin = DigitalTwin(
            plant_id=event.aggregate_id,
            nursery_id=event.nursery_id,
            branch_id=_maybe_uuid(payload.get("branch_id")),
            current_version=0,
            lifecycle_state=snapshot["lifecycle_state"],
            operational_status=snapshot["operational_status"],
            growth_stage=None,
            snapshot=snapshot,
        )
        twin = await self._twins.create(twin)
        return await self._write_version(twin, snapshot, event)

    async def _write_version(self, twin: DigitalTwin, snapshot: dict, event: DomainEvent) -> int:
        next_version = twin.current_version + 1
        version_row = DigitalTwinVersion(
            plant_id=twin.plant_id,
            version=next_version,
            snapshot=copy.deepcopy(snapshot),
            event_id=event.id,
            event_type=event.event_type,
            event_sequence=event.sequence,
            occurred_at=event.occurred_at,
        )
        await self._versions.add(version_row)

        twin.snapshot = snapshot
        twin.current_version = next_version
        twin.lifecycle_state = snapshot["lifecycle_state"]
        twin.operational_status = snapshot["operational_status"]
        twin.growth_stage = snapshot["growth_stage"]
        location = snapshot.get("current_location") or {}
        twin.branch_id = _maybe_uuid(location.get("branch_id"))
        twin.last_event_id = event.id
        twin.last_event_type = event.event_type
        twin.last_event_sequence = event.sequence
        twin.last_projected_at = event.occurred_at
        await self._twins.update(twin)
        return next_version

    # ------------------------------------------------------------------
    # Per-event-type snapshot transitions. Each takes the previous
    # snapshot (already deep-copied by the caller) and returns it mutated
    # -- safe because the caller owns the only reference.
    # ------------------------------------------------------------------

    async def _on_plant_updated(self, snapshot: dict, event: DomainEvent) -> dict:
        plant = await self._plants.get_by_id(event.aggregate_id)
        if plant is not None:
            snapshot["identity"]["common_label"] = plant.common_label
            snapshot["identity"]["batch_number"] = plant.batch_number
        return snapshot

    async def _on_plant_status_changed(self, snapshot: dict, event: DomainEvent) -> dict:
        to_status = event.payload["to_status"]
        snapshot["lifecycle_state"] = to_status
        if not snapshot.get("archived_at"):
            snapshot["operational_status"] = _OPERATIONAL_STATUS_BY_LIFECYCLE.get(to_status, to_status)
        if to_status == PlantStatus.SOLD.value:
            snapshot["sold_at"] = event.occurred_at.isoformat()
        if to_status == PlantStatus.DECEASED.value:
            snapshot["deceased_at"] = event.occurred_at.isoformat()
            snapshot["deceased_reason"] = event.payload.get("reason")
        return snapshot

    async def _on_plant_moved(self, snapshot: dict, event: DomainEvent) -> dict:
        snapshot["current_location"] = {
            "branch_id": event.payload.get("to_branch_id"),
            "zone": event.payload.get("to_zone"),
        }
        snapshot["counts"]["movements"] += 1
        return snapshot

    async def _on_plant_image_uploaded(self, snapshot: dict, event: DomainEvent) -> dict:
        snapshot["counts"]["images"] += 1
        return snapshot

    async def _on_plant_archived(self, snapshot: dict, event: DomainEvent) -> dict:
        # `PlantArchived` is an intentionally empty event (no payload fields
        # at all -- see its own class docstring in domain_events/events.py);
        # the reason lives on `Plant.archived_reason`, so this is an
        # enrichment read, same pattern as the growth/health/watering/
        # fertilizer/environmental handlers above.
        snapshot["archived_at"] = event.occurred_at.isoformat()
        plant = await self._plants.get_by_id(event.aggregate_id)
        snapshot["archived_reason"] = plant.archived_reason if plant else None
        snapshot["operational_status"] = "archived"
        return snapshot

    async def _on_growth_recorded(self, snapshot: dict, event: DomainEvent) -> dict:
        snapshot["counts"]["growth"] += 1
        entry_id = event.payload.get("growth_entry_id")
        entry = await self._growth.get_by_id(uuid.UUID(str(entry_id))) if entry_id else None
        if entry is not None:
            snapshot["growth_stage"] = entry.growth_stage or snapshot.get("growth_stage")
            snapshot["latest"]["growth"] = {
                "entry_id": str(entry.id),
                "height_cm": float(entry.height_cm) if entry.height_cm is not None else None,
                "growth_stage": entry.growth_stage,
                "recorded_at": entry.recorded_at.isoformat(),
            }
        return snapshot

    async def _on_health_recorded(self, snapshot: dict, event: DomainEvent) -> dict:
        snapshot["counts"]["health"] += 1
        entry_id = event.payload.get("health_entry_id")
        entry = await self._health.get_by_id(uuid.UUID(str(entry_id))) if entry_id else None
        if entry is not None:
            snapshot["latest"]["health"] = {
                "entry_id": str(entry.id),
                "status_label": entry.status_label,
                "health_score": float(entry.health_score) if entry.health_score is not None else None,
                "recorded_at": entry.recorded_at.isoformat(),
            }
        return snapshot

    async def _on_watering_recorded(self, snapshot: dict, event: DomainEvent) -> dict:
        snapshot["counts"]["watering"] += 1
        entry_id = event.payload.get("watering_log_id")
        entry = await self._watering.get_by_id(uuid.UUID(str(entry_id))) if entry_id else None
        if entry is not None:
            snapshot["latest"]["watering"] = {
                "entry_id": str(entry.id),
                "volume_ml": float(entry.volume_ml) if entry.volume_ml is not None else None,
                "method": entry.method,
                "recorded_at": entry.recorded_at.isoformat(),
            }
        return snapshot

    async def _on_fertilizer_recorded(self, snapshot: dict, event: DomainEvent) -> dict:
        snapshot["counts"]["fertilizer"] += 1
        entry_id = event.payload.get("fertilizer_log_id")
        entry = await self._fertilizer.get_by_id(uuid.UUID(str(entry_id))) if entry_id else None
        if entry is not None:
            snapshot["latest"]["fertilizer"] = {
                "entry_id": str(entry.id),
                "product_name": entry.product_name,
                "schedule": entry.schedule,
                "recorded_at": entry.recorded_at.isoformat(),
            }
        return snapshot

    async def _on_environmental_recorded(self, snapshot: dict, event: DomainEvent) -> dict:
        snapshot["counts"]["environmental"] += 1
        entry_id = event.payload.get("reading_id")
        entry = await self._environmental.get_by_id(uuid.UUID(str(entry_id))) if entry_id else None
        if entry is not None:
            snapshot["latest"]["environmental"] = {
                "entry_id": str(entry.id),
                "temperature_celsius": float(entry.temperature_celsius) if entry.temperature_celsius is not None else None,
                "humidity_percent": float(entry.humidity_percent) if entry.humidity_percent is not None else None,
                "recorded_at": entry.recorded_at.isoformat(),
            }
        return snapshot

    async def _on_disease_detected(self, snapshot: dict, event: DomainEvent) -> dict:
        snapshot["counts"]["disease_reports"] += 1
        snapshot["latest"]["disease"] = {
            "report_id": str(event.payload.get("disease_report_id")),
            "condition_name": event.payload.get("condition_name"),
            "severity": event.payload.get("severity"),
            "status": "draft",
            "detected_at": event.occurred_at.isoformat(),
        }
        return snapshot

    async def _on_disease_report_updated(self, snapshot: dict, event: DomainEvent) -> dict:
        latest = snapshot["latest"].get("disease")
        if latest is not None and latest.get("report_id") == str(event.payload.get("disease_report_id")):
            latest["status"] = event.payload.get("status")
        return snapshot

    async def _on_treatment_applied(self, snapshot: dict, event: DomainEvent) -> dict:
        snapshot["counts"]["treatments"] += 1
        snapshot["latest"]["treatment"] = {
            "treatment_id": str(event.payload.get("treatment_id")),
            "disease_report_id": str(event.payload.get("disease_report_id")),
            "outcome": event.payload.get("outcome"),
            "applied_at": event.occurred_at.isoformat(),
        }
        return snapshot

    async def _on_inventory_movement_recorded(self, snapshot: dict, event: DomainEvent) -> dict:
        """
        Module 8's one narrow coupling point -- see this file's
        `PROJECTED_EVENT_TYPES` comment and
        docs/architecture/24-module8-inventory-management.md. A thin
        event (movement id/type/quantity + which bulk inventory line);
        no enrichment read back into `app.models.inventory` is needed or
        performed here, keeping this projector's only dependencies the
        same Module 6 repositories it already had -- it does not gain an
        InventoryRepository dependency just to render this one summary.
        """
        snapshot["counts"]["inventory_movements"] += 1
        snapshot["latest"]["inventory_movement"] = {
            "movement_id": str(event.payload.get("movement_id")),
            "inventory_id": str(event.payload.get("inventory_id")),
            "movement_type": event.payload.get("movement_type"),
            "quantity": event.payload.get("quantity"),
            "recorded_at": event.occurred_at.isoformat(),
        }
        return snapshot

    # ------------------------------------------------------------------
    # Module 9 (Sales, CRM, Plant Passport & QR Intelligence) additions.
    # See this file's PROJECTED_EVENT_TYPES comment for the full
    # reasoning on scope (why Sales Timeline/Ownership Timeline/Revenue
    # Timeline are all servable from these four events and why
    # invoice/payment/refund events are not).
    # ------------------------------------------------------------------

    async def _on_plant_sold(self, snapshot: dict, event: DomainEvent) -> dict:
        """Sales Timeline + Ownership Timeline (ownership transfers nursery -> customer) + Revenue Timeline (unit_price, already on the payload -- no enrichment read needed)."""
        snapshot["counts"]["plant_sold"] += 1
        payload = event.payload
        customer_id = payload.get("customer_id")
        snapshot["latest"]["sale"] = {
            "sale_id": payload.get("sale_id"),
            "sale_item_id": payload.get("sale_item_id"),
            "customer_id": customer_id,
            "unit_price": payload.get("unit_price"),
            "sold_at": event.occurred_at.isoformat(),
        }
        snapshot["ownership"] = {
            "owner_type": "customer" if customer_id else "nursery",
            "customer_id": customer_id,
            "since": event.occurred_at.isoformat(),
        }
        return snapshot

    async def _on_plant_returned(self, snapshot: dict, event: DomainEvent) -> dict:
        """
        Sales Timeline + Ownership Timeline (ownership reverts customer ->
        nursery) + Revenue Timeline. `line_refund_amount` is not on the
        `PlantReturned` payload itself (only `return_id`/`return_item_id`/
        `condition` are -- see app/domain_events/events.py), so this is
        an enrichment read, the same pattern `_on_growth_recorded` etc.
        already use for their own payload-carries-only-an-id case.
        """
        snapshot["counts"]["plant_returned"] += 1
        payload = event.payload
        return_item_id = payload.get("return_item_id")
        refund_amount: float | None = None
        if return_item_id:
            item = await self._return_items.get_by_id(uuid.UUID(str(return_item_id)))
            if item is not None and item.line_refund_amount is not None:
                refund_amount = _as_float(item.line_refund_amount)
        snapshot["latest"]["return"] = {
            "return_id": payload.get("return_id"),
            "return_item_id": return_item_id,
            "condition": payload.get("condition"),
            "refund_amount": refund_amount,
            "returned_at": event.occurred_at.isoformat(),
        }
        snapshot["ownership"] = {"owner_type": "nursery", "customer_id": None, "since": event.occurred_at.isoformat()}
        return snapshot

    async def _on_passport_generated(self, snapshot: dict, event: DomainEvent) -> dict:
        snapshot["counts"]["passports_generated"] += 1
        snapshot["latest"]["passport"] = {
            "passport_id": str(event.payload.get("passport_id")),
            "version": event.payload.get("version"),
            "generated_at": event.occurred_at.isoformat(),
        }
        return snapshot

    async def _on_qr_generated(self, snapshot: dict, event: DomainEvent) -> dict:
        snapshot["counts"]["qr_generated"] += 1
        snapshot["latest"]["qr"] = {
            "passport_id": str(event.payload.get("passport_id")),
            "generated_at": event.occurred_at.isoformat(),
        }
        return snapshot

    async def _on_ai_prediction_generated(self, snapshot: dict, event: DomainEvent) -> dict:
        """
        Module 10 (AI Platform). A quick-glance summary only (id, type,
        model version, confidence, timestamp) -- the full historical list
        (FR-8.8) is served live from `ai_predictions` by `GET /plants/{id}/
        ai-predictions` (app/api/routes/ai_predictions.py), matching this
        file's own module docstring's "full historical timelines are
        served by get_timeline/get_event_history... not growing lists [in
        the snapshot]" rule -- this section holds only the single latest
        prediction per plant, like every other `latest.*` entry.
        """
        snapshot["counts"]["ai_predictions"] += 1
        snapshot["latest"]["ai_prediction"] = {
            "prediction_id": str(event.payload.get("prediction_id")),
            "prediction_type": event.payload.get("prediction_type"),
            "model_version": event.payload.get("model_version"),
            "confidence": event.payload.get("confidence"),
            "generated_at": event.occurred_at.isoformat(),
        }
        return snapshot

    # ------------------------------------------------------------------
    # Query APIs -- Current / Timeline / Snapshot-by-date / Version
    # history / Event history / Projection history. All read-only.
    # ------------------------------------------------------------------

    async def get_current_twin(self, plant_id: uuid.UUID) -> DigitalTwin:
        twin = await self._twins.get_by_plant_id(plant_id)
        if twin is None:
            raise NotFoundError("Digital Twin not found for this plant.")
        return twin

    async def list_twins_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        lifecycle_state: str | None = None,
        branch_id: uuid.UUID | None = None,
        sort_by: str = "updated_at",
        sort_dir: str = "desc",
    ) -> tuple[list[DigitalTwin], int]:
        if sort_by not in {"updated_at", "created_at", "lifecycle_state", "current_version"}:
            sort_by = "updated_at"
        if sort_dir not in {"asc", "desc"}:
            sort_dir = "desc"
        return await self._twins.list_for_nursery(
            nursery_id, offset=offset, limit=limit, lifecycle_state=lifecycle_state, branch_id=branch_id,
            sort_by=sort_by, sort_dir=sort_dir,
        )

    async def get_timeline(
        self, plant_id: uuid.UUID, *, offset: int = 0, limit: int = 50, sort_dir: str = "desc"
    ) -> tuple[list[DigitalTwinVersion], int]:
        """One entry per projected event -- each `DigitalTwinVersion` already carries `event_type`/`occurred_at`/`version`."""
        await self.get_current_twin(plant_id)  # 404s if the plant has no twin
        return await self._versions.list_for_plant(plant_id, offset=offset, limit=limit, sort_dir=sort_dir)

    async def get_version_history(
        self, plant_id: uuid.UUID, *, offset: int = 0, limit: int = 50, sort_dir: str = "desc"
    ) -> tuple[list[DigitalTwinVersion], int]:
        """Same underlying rows as `get_timeline` -- kept as a distinct method because the two are conceptually different queries (per the module's own API list), even though today they share one table."""
        return await self.get_timeline(plant_id, offset=offset, limit=limit, sort_dir=sort_dir)

    async def get_version(self, plant_id: uuid.UUID, version: int) -> DigitalTwinVersion:
        row = await self._versions.get_by_plant_and_version(plant_id, version)
        if row is None:
            raise NotFoundError(f"Version {version} not found for this plant.")
        return row

    async def compare_versions(self, plant_id: uuid.UUID, version_a: int, version_b: int) -> VersionComparison:
        row_a = await self.get_version(plant_id, version_a)
        row_b = await self.get_version(plant_id, version_b)
        keys = set(row_a.snapshot.keys()) | set(row_b.snapshot.keys())
        changed = tuple(sorted(k for k in keys if row_a.snapshot.get(k) != row_b.snapshot.get(k)))
        return VersionComparison(
            plant_id=plant_id, version_a=version_a, version_b=version_b,
            snapshot_a=row_a.snapshot, snapshot_b=row_b.snapshot, changed_keys=changed,
        )

    async def get_snapshot_by_date(self, plant_id: uuid.UUID, *, as_of: datetime) -> DigitalTwinVersion:
        """"Snapshot by date": the twin's state as of a point in time -- the latest version whose event occurred at or before `as_of`."""
        row = await self._versions.get_as_of(plant_id, as_of=as_of)
        if row is None:
            raise NotFoundError("No Digital Twin version exists at or before that date.")
        return row

    async def get_event_history(
        self, plant_id: uuid.UUID, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[DomainEvent], int]:
        """
        The raw `domain_events` rows for this plant (not the derived twin
        versions) -- includes full event payloads, distinct from
        `get_timeline`'s twin-snapshot-shaped entries.
        """
        await self.get_current_twin(plant_id)
        events = await self._events.list_for_aggregate(plant_id)
        events = list(reversed(events))  # newest first, matching every other list endpoint's default
        return events[offset : offset + limit], len(events)

    # ------------------------------------------------------------------
    # Event replay -- "Event replay produces identical projections".
    # ------------------------------------------------------------------

    async def compute_projection_from_events(self, plant_id: uuid.UUID) -> dict:
        """
        Pure verification replay: independently folds over *every* event
        ever recorded for this plant (read straight from `domain_events`,
        ordered by `sequence`), applying the exact same per-event-type
        transition methods `project()` uses, and returns the resulting
        snapshot -- without writing anything. Comparing this result
        against `get_current_twin(plant_id).snapshot` is the literal test
        for "event replay produces identical projections": if the
        incrementally-maintained projection and a from-scratch replay of
        the same event log ever disagree, the projector has a bug.
        """
        events = await self._events.list_for_aggregate(plant_id)
        if not events or events[0].event_type != "plant.registered":
            raise NotFoundError("No plant.registered event found for this plant -- nothing to replay.")

        registered_event = events[0]
        plant = await self._plants.get_by_id(plant_id)
        payload = registered_event.payload
        snapshot = {
            "identity": {
                "plant_id": str(plant_id),
                "nursery_id": str(registered_event.nursery_id) if registered_event.nursery_id else None,
                "species_id": payload.get("species_id"),
                "variety_id": str(plant.variety_id) if plant and plant.variety_id else None,
                "qr_code_token": payload.get("qr_code_token"),
                "common_label": plant.common_label if plant else None,
                "batch_number": plant.batch_number if plant else None,
                "registered_at": registered_event.occurred_at.isoformat(),
            },
            "lifecycle_state": PlantStatus.IN_PRODUCTION.value,
            "operational_status": "active",
            "growth_stage": None,
            "current_location": {"branch_id": payload.get("branch_id"), "zone": None},
            "counts": dict(_EMPTY_COUNTS),
            "latest": dict(_EMPTY_LATEST),
            "ownership": dict(_DEFAULT_OWNERSHIP),
            "sold_at": None,
            "deceased_at": None,
            "deceased_reason": None,
            "archived_at": None,
            "archived_reason": None,
        }
        for event in events[1:]:
            handler = self._handlers.get(event.event_type)
            if handler is not None:
                snapshot = await handler(snapshot, event)
        return snapshot

    async def verify_consistency(self, plant_id: uuid.UUID) -> tuple[bool, int, list[str]]:
        """
        Live diagnostic backing `GET /plants/{id}/digital-twin/verify`:
        compares the currently-stored projection against a from-scratch
        replay of the same plant's full event history. Returns
        `(consistent, current_version, differing_top_level_keys)`.
        """
        twin = await self.get_current_twin(plant_id)
        replayed = await self.compute_projection_from_events(plant_id)
        keys = set(twin.snapshot.keys()) | set(replayed.keys())
        differing = sorted(k for k in keys if twin.snapshot.get(k) != replayed.get(k))
        return (len(differing) == 0, twin.current_version, differing)

    async def rebuild_from_scratch(self, plant_id: uuid.UUID) -> DigitalTwin:
        """
        Recovery replay: only permitted when no twin/version rows exist
        yet for this plant (a fresh rebuild, e.g. after a disaster-
        recovery restore that lost the projection tables but kept
        `domain_events`). Projects every recorded event through the
        normal `project()` write path, in order, from scratch -- refuses
        outright if a twin already exists rather than risk duplicating or
        corrupting an in-progress projection (the `uq_digital_twins_
        plant_id` and `uq_digital_twin_versions_plant_version` constraints
        would also reject this at the database level; this check just
        gives a clear application-level error instead of a raw
        IntegrityError).
        """
        existing = await self._twins.get_by_plant_id(plant_id)
        if existing is not None:
            raise ConflictError("A Digital Twin already exists for this plant -- rebuild_from_scratch is only for a missing projection.")
        events = await self._events.list_for_aggregate(plant_id)
        if not events:
            raise NotFoundError("No events recorded for this plant.")
        for event in events:
            await self.project(event)
        return await self.get_current_twin(plant_id)


class DigitalTwinEventHandler:
    """
    The thin adapter `EventDispatcher` actually invokes -- satisfies the
    `EventHandler` Protocol (app/domain_events/dispatcher.py) by wrapping
    `DigitalTwinService.project()`. Kept separate from the service itself
    so the service's own public surface stays "a service with query
    methods and one `project()` method", not "a service that also knows
    about the dispatcher's handler-registration shape".
    """

    name = "digital_twin_projector"
    event_types = PROJECTED_EVENT_TYPES

    def __init__(self, service: DigitalTwinService) -> None:
        self._service = service

    async def handle(self, event: DomainEvent) -> int | None:
        return await self._service.project(event)
