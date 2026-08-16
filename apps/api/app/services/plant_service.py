"""
Module 6 (Plant Lifecycle Management) -- `PlantService`: Plant
Registration (incl. bulk registration + QR generation), Plant Profile,
Plant Movement, and the `PlantStatus` state machine
(docs/ux/13-digital-twin-lifecycle.md). Growth/Health/Watering/
Fertilizer/Environmental append-only logs live in
plant_records_service.py; Disease/Treatment lifecycle lives in
disease_service.py; the cross-source Timeline lives in
plant_timeline_service.py -- kept out of this file so it doesn't grow into
a god-service, per the module's own "keep services testable" instruction.

"Initial Digital Twin creation" (the module's own registration
requirement): there is no separate `digital_twins` table anywhere in the
schema -- `Plant` *is* the Digital Twin root entity
(app/models/plants.py's own docstring, and the LLD's "Module: Plants
(Digital Twin)"). Registering a Plant row IS creating its Digital Twin;
the two are the same INSERT, automatically, every time -- there is no
separate step that could be skipped.

"Initial inventory assignment" (the same requirement): per
docs/ux/16-inventory-workflow.md's own "Relationship to the Digital
Twin" section, bulk `inventory` rows and individually-tracked `Plant`
rows are *deliberately separate, non-overlapping* models -- "a nursery is
not required to individually track every plant to use the system," and
the only documented flow between them is a rare one-way demotion
(Plant -> bulk inventory), never the reverse. Writing an Inventory/
StockMovement row on every individual Plant registration would
double-count the same physical plant in both models, which is exactly
what that architecture document rules out (and exactly what Module 8,
built afterward, confirms by never subscribing to Plant lifecycle
events -- see docs/architecture/24-module8-inventory-management.md).
"Initial inventory assignment"
for an individually-tracked Plant is therefore satisfied by the fields
registration already sets -- `branch_id` (which stock location it
belongs to) and `status` (whether it currently counts as available/in-
production stock) -- not a write to the separate bulk `inventory` table.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.enums import DiseaseReportStatus, PlantStatus, TreatmentOutcome
from app.domain_events import (
    DomainEventPublisher,
    PlantArchived,
    PlantImageUploaded,
    PlantMoved,
    PlantRegistered,
    PlantStatusChanged,
    PlantUpdated,
)
from app.models.plants import Plant, PlantImage, PlantTransfer
from app.models.platform import AuditLog
from app.repositories.interfaces import (
    AuditLogRepository,
    BranchRepository,
    DiseaseReportRepository,
    PlantImageRepository,
    PlantRepository,
    PlantTransferRepository,
    PlantVarietyRepository,
    SpeciesRepository,
    SupplierRepository,
    TreatmentRepository,
)
from app.services.qr_code_service import QRCodeService

# The full state machine from docs/ux/13-digital-twin-lifecycle.md's
# Transition Rules table -- illegal transitions are rejected here, before
# they ever reach a write, per that doc's own "illegal transitions are
# blocked at the service layer, not just hidden in the UI."
_TRANSITIONS: dict[PlantStatus, set[PlantStatus]] = {
    PlantStatus.IN_PRODUCTION: {PlantStatus.READY_FOR_SALE, PlantStatus.UNDER_TREATMENT, PlantStatus.DECEASED},
    PlantStatus.READY_FOR_SALE: {
        PlantStatus.IN_PRODUCTION,
        PlantStatus.UNDER_TREATMENT,
        PlantStatus.DECEASED,
        PlantStatus.SOLD,
    },
    PlantStatus.UNDER_TREATMENT: {PlantStatus.IN_PRODUCTION, PlantStatus.DECEASED},
    PlantStatus.SOLD: set(),  # terminal -- historical record, per the lifecycle doc
    PlantStatus.DECEASED: set(),  # terminal -- historical record, per the lifecycle doc
}

_OPEN_DISEASE_STATUSES = {DiseaseReportStatus.DRAFT, DiseaseReportStatus.CONFIRMED, DiseaseReportStatus.TREATED}
_CONFIRMED_DISEASE_STATUSES = {DiseaseReportStatus.CONFIRMED, DiseaseReportStatus.TREATED}


class PlantService:
    def __init__(
        self,
        *,
        plant_repo: PlantRepository,
        image_repo: PlantImageRepository,
        transfer_repo: PlantTransferRepository,
        species_repo: SpeciesRepository,
        variety_repo: PlantVarietyRepository,
        branch_repo: BranchRepository,
        supplier_repo: SupplierRepository,
        disease_repo: DiseaseReportRepository,
        treatment_repo: TreatmentRepository,
        qr_service: QRCodeService,
        audit_repo: AuditLogRepository,
        event_publisher: DomainEventPublisher,
    ) -> None:
        self._plants = plant_repo
        self._images = image_repo
        self._transfers = transfer_repo
        self._species = species_repo
        self._varieties = variety_repo
        self._branches = branch_repo
        self._suppliers = supplier_repo
        self._disease_reports = disease_repo
        self._treatments = treatment_repo
        self._qr = qr_service
        self._audit = audit_repo
        self._events = event_publisher

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    async def register_plant(
        self,
        *,
        nursery_id: uuid.UUID,
        branch_id: uuid.UUID,
        species_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        variety_id: uuid.UUID | None = None,
        common_label: str | None = None,
        zone: str | None = None,
        batch_number: str | None = None,
        supplier_id: uuid.UUID | None = None,
        purchase_price: float | None = None,
        purchase_date: datetime | None = None,
        price: float | None = None,
        planted_at: datetime | None = None,
        request_id: str | None = None,
    ) -> Plant:
        """
        Register new plant (FR-5): validates species/branch/variety/
        supplier all belong to this org, generates a guaranteed-unique QR
        token, and defaults `status=IN_PRODUCTION` -- the lifecycle doc's
        own "[*] -> In Production: Plant created" transition, requiring
        nothing more than species+branch, which this signature already
        makes mandatory.
        """
        branch = await self._branches.get_by_id(branch_id)
        if branch is None or branch.nursery_id != nursery_id:
            raise ValidationError(f"'{branch_id}' is not a recognized branch in this organization.")

        species = await self._species.get_by_id(species_id)
        if species is None or species.nursery_id != nursery_id:
            raise ValidationError(f"'{species_id}' is not a recognized species in this organization.")

        if variety_id is not None:
            # Variety must belong to the species it's attached to -- same
            # cross-reference check Module 5's PlantVarietyService already
            # applies at variety-creation time; re-checked here since a
            # caller could otherwise pair a valid variety with the wrong
            # species at registration time.
            variety = await self._varieties.get_by_id(variety_id)
            if variety is None or variety.species_id != species_id:
                raise ValidationError(f"'{variety_id}' is not a recognized variety of species '{species_id}'.")

        if supplier_id is not None:
            supplier = await self._suppliers.get_by_id(supplier_id)
            if supplier is None or supplier.nursery_id != nursery_id:
                raise ValidationError(f"'{supplier_id}' is not a recognized supplier in this organization.")

        if purchase_price is not None and purchase_price < 0:
            raise ValidationError("purchase_price cannot be negative.")
        if price is not None and price < 0:
            raise ValidationError("price cannot be negative.")

        qr_code_token = await self._qr.generate_unique_token()

        plant = Plant(
            nursery_id=nursery_id,
            branch_id=branch_id,
            species_id=species_id,
            variety_id=variety_id,
            common_label=common_label,
            zone=zone,
            status=PlantStatus.IN_PRODUCTION,
            qr_code_token=qr_code_token,
            price=price,
            planted_at=planted_at or datetime.now(timezone.utc),
            batch_number=batch_number,
            supplier_id=supplier_id,
            purchase_price=purchase_price,
            purchase_date=purchase_date,
            registered_by_user_id=actor_user_id,
        )
        await self._plants.add(plant)

        await self._log_audit(
            nursery_id=nursery_id,
            actor_user_id=actor_user_id,
            action="plant.registered",
            entity_id=plant.id,
            diff={"after": {"species_id": str(species_id), "branch_id": str(branch_id), "qr_code_token": qr_code_token}},
            request_id=request_id,
        )
        await self._events.publish(
            PlantRegistered(
                aggregate_id=plant.id,
                nursery_id=nursery_id,
                actor_user_id=actor_user_id,
                branch_id=branch_id,
                species_id=species_id,
                qr_code_token=qr_code_token,
            ),
            request_id=request_id,
        )
        return plant

    async def bulk_register_plants(
        self,
        *,
        nursery_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        items: list[dict],
        request_id: str | None = None,
    ) -> list[Plant]:
        """
        Bulk registration: each item is the same field set as
        `register_plant` (minus `nursery_id`/`actor_user_id`, supplied
        once for the whole batch). All-or-nothing -- a single invalid item
        raises before any row is committed, the same transactional
        guarantee every other bulk-ish operation in this codebase gives
        (there is no documented partial-success contract for Plant
        registration, unlike the Environmental ingest endpoint's own
        explicitly-different partial-success design).
        """
        if not items:
            raise ValidationError("At least one plant is required for bulk registration.")
        registered: list[Plant] = []
        for item in items:
            plant = await self.register_plant(
                nursery_id=nursery_id, actor_user_id=actor_user_id, request_id=request_id, **item
            )
            registered.append(plant)
        return registered

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------
    async def get_plant(self, plant_id: uuid.UUID) -> Plant:
        plant = await self._plants.get_by_id(plant_id)
        if plant is None:
            raise NotFoundError("Plant not found.")
        return plant

    async def get_by_qr_token(self, qr_code_token: str) -> Plant:
        plant = await self._plants.get_by_qr_token(qr_code_token)
        if plant is None:
            raise NotFoundError("No plant matches this QR code.")
        return plant

    async def list_plants(
        self,
        *,
        nursery_id: uuid.UUID,
        offset: int,
        limit: int,
        branch_id: uuid.UUID | None = None,
        species_id: uuid.UUID | None = None,
        status: PlantStatus | None = None,
        zone: str | None = None,
        batch_number: str | None = None,
        search: str | None = None,
        include_archived: bool = False,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> tuple[list[Plant], int]:
        if sort_by not in {"created_at", "planted_at", "status", "common_label"}:
            raise ValidationError(f"'{sort_by}' is not a sortable field.")
        if sort_dir not in {"asc", "desc"}:
            raise ValidationError("sort_dir must be 'asc' or 'desc'.")
        return await self._plants.list_for_nursery(
            nursery_id,
            offset=offset,
            limit=limit,
            branch_id=branch_id,
            species_id=species_id,
            status=status,
            zone=zone,
            batch_number=batch_number,
            search=search,
            include_archived=include_archived,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )

    async def update_plant_profile(
        self,
        *,
        plant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        common_label: str | None = None,
        variety_id: uuid.UUID | None = None,
        batch_number: str | None = None,
        supplier_id: uuid.UUID | None = None,
        purchase_price: float | None = None,
        purchase_date: datetime | None = None,
        price: float | None = None,
        request_id: str | None = None,
    ) -> Plant:
        """Same "`None` means leave unchanged" convention every prior module's own PATCH-style update method uses (Module 4/5)."""
        plant = await self.get_plant(plant_id)
        changed: list[str] = []

        if common_label is not None and common_label != plant.common_label:
            plant.common_label = common_label
            changed.append("common_label")
        if variety_id is not None and variety_id != plant.variety_id:
            variety = await self._varieties.get_by_id(variety_id)
            if variety is None or variety.species_id != plant.species_id:
                raise ValidationError(f"'{variety_id}' is not a recognized variety of this plant's species.")
            plant.variety_id = variety_id
            changed.append("variety_id")
        if batch_number is not None and batch_number != plant.batch_number:
            plant.batch_number = batch_number
            changed.append("batch_number")
        if supplier_id is not None and supplier_id != plant.supplier_id:
            supplier = await self._suppliers.get_by_id(supplier_id)
            if supplier is None or supplier.nursery_id != plant.nursery_id:
                raise ValidationError(f"'{supplier_id}' is not a recognized supplier in this organization.")
            plant.supplier_id = supplier_id
            changed.append("supplier_id")
        if purchase_price is not None and purchase_price != plant.purchase_price:
            if purchase_price < 0:
                raise ValidationError("purchase_price cannot be negative.")
            plant.purchase_price = purchase_price
            changed.append("purchase_price")
        if purchase_date is not None and purchase_date != plant.purchase_date:
            plant.purchase_date = purchase_date
            changed.append("purchase_date")
        if price is not None and price != plant.price:
            if price < 0:
                raise ValidationError("price cannot be negative.")
            plant.price = price
            changed.append("price")

        if not changed:
            return plant

        await self._log_audit(
            nursery_id=plant.nursery_id,
            actor_user_id=actor_user_id,
            action="plant.updated",
            entity_id=plant.id,
            diff={"changed_fields": changed},
            request_id=request_id,
        )
        await self._events.publish(
            PlantUpdated(
                aggregate_id=plant.id, nursery_id=plant.nursery_id, actor_user_id=actor_user_id,
                changed_fields=tuple(changed),
            ),
            request_id=request_id,
        )
        return plant

    async def upload_image(
        self,
        *,
        plant_id: uuid.UUID,
        url: str,
        actor_user_id: uuid.UUID,
        thumbnail_url: str | None = None,
        caption: str | None = None,
        request_id: str | None = None,
    ) -> PlantImage:
        plant = await self.get_plant(plant_id)
        if not url.strip():
            raise ValidationError("url is required.")

        image = PlantImage(
            plant_id=plant.id, url=url, thumbnail_url=thumbnail_url, caption=caption,
            uploaded_by_user_id=actor_user_id, captured_at=datetime.now(timezone.utc),
        )
        await self._images.add(image)

        await self._log_audit(
            nursery_id=plant.nursery_id, actor_user_id=actor_user_id, action="plant.image_uploaded",
            entity_id=plant.id, diff={"after": {"image_id": str(image.id)}}, request_id=request_id,
        )
        await self._events.publish(
            PlantImageUploaded(
                aggregate_id=plant.id, nursery_id=plant.nursery_id, actor_user_id=actor_user_id, image_id=image.id
            ),
            request_id=request_id,
        )
        return image

    async def list_images(self, plant_id: uuid.UUID) -> list[PlantImage]:
        await self.get_plant(plant_id)
        return await self._images.list_for_plant(plant_id)

    # ------------------------------------------------------------------
    # Movement (branch transfer, zone/greenhouse/outdoor movement)
    # ------------------------------------------------------------------
    async def move_plant(
        self,
        *,
        plant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        to_branch_id: uuid.UUID | None = None,
        to_zone: str | None = None,
        note: str | None = None,
        request_id: str | None = None,
    ) -> Plant:
        """
        Covers every kind of Plant Movement: pass `to_branch_id` for a
        branch transfer, `to_zone` for a zone/greenhouse/outdoor move
        (any free-text zone label -- "greenhouse-2"/"outdoor-A" are just
        zone values, not separate concepts), or both at once. At least
        one of the two must actually change something, otherwise there is
        no movement to record.
        """
        plant = await self.get_plant(plant_id)
        from_branch_id = plant.branch_id
        from_zone = plant.zone

        target_branch_id = to_branch_id if to_branch_id is not None else from_branch_id
        target_zone = to_zone if to_zone is not None else from_zone

        if target_branch_id == from_branch_id and target_zone == from_zone:
            raise ValidationError("Destination must differ from the plant's current branch and/or zone.")

        if to_branch_id is not None and to_branch_id != from_branch_id:
            branch = await self._branches.get_by_id(to_branch_id)
            if branch is None or branch.nursery_id != plant.nursery_id:
                raise ValidationError(f"'{to_branch_id}' is not a recognized branch in this organization.")

        transfer = PlantTransfer(
            nursery_id=plant.nursery_id,
            plant_id=plant.id,
            from_branch_id=from_branch_id,
            to_branch_id=target_branch_id,
            from_zone=from_zone,
            to_zone=target_zone,
            note=note,
            transferred_by_user_id=actor_user_id,
            transferred_at=datetime.now(timezone.utc),
        )
        await self._transfers.add(transfer)

        plant.branch_id = target_branch_id
        plant.zone = target_zone

        await self._log_audit(
            nursery_id=plant.nursery_id, actor_user_id=actor_user_id, action="plant.moved", entity_id=plant.id,
            diff={
                "before": {"branch_id": str(from_branch_id), "zone": from_zone},
                "after": {"branch_id": str(target_branch_id), "zone": target_zone},
            },
            request_id=request_id,
        )
        await self._events.publish(
            PlantMoved(
                aggregate_id=plant.id, nursery_id=plant.nursery_id, actor_user_id=actor_user_id,
                from_branch_id=from_branch_id, to_branch_id=target_branch_id,
                from_zone=from_zone, to_zone=target_zone,
            ),
            request_id=request_id,
        )
        return plant

    async def list_movement_history(self, plant_id: uuid.UUID) -> list[PlantTransfer]:
        await self.get_plant(plant_id)
        return await self._transfers.list_for_plant(plant_id)

    # ------------------------------------------------------------------
    # Status state machine (docs/ux/13-digital-twin-lifecycle.md)
    # ------------------------------------------------------------------
    async def transition_status(
        self,
        *,
        plant_id: uuid.UUID,
        to_status: PlantStatus,
        actor_user_id: uuid.UUID,
        reason: str | None = None,
        request_id: str | None = None,
    ) -> Plant:
        plant = await self.get_plant(plant_id)
        from_status = plant.status

        if from_status == to_status:
            raise ConflictError(f"Plant is already '{to_status.value}'.")

        allowed = _TRANSITIONS.get(from_status, set())
        if to_status not in allowed:
            raise ConflictError(
                f"Cannot transition a plant from '{from_status.value}' to '{to_status.value}'."
            )

        await self._check_transition_guard(plant, from_status=from_status, to_status=to_status, reason=reason)

        plant.status = to_status
        now = datetime.now(timezone.utc)
        if to_status == PlantStatus.SOLD:
            plant.sold_at = now
        if to_status == PlantStatus.DECEASED:
            plant.deceased_at = now
            plant.deceased_reason = reason

        await self._log_audit(
            nursery_id=plant.nursery_id, actor_user_id=actor_user_id, action="plant.status_changed",
            entity_id=plant.id,
            diff={"before": {"status": from_status.value}, "after": {"status": to_status.value}, "reason": reason},
            request_id=request_id,
        )
        await self._events.publish(
            PlantStatusChanged(
                aggregate_id=plant.id, nursery_id=plant.nursery_id, actor_user_id=actor_user_id,
                from_status=from_status.value, to_status=to_status.value, reason=reason,
            ),
            request_id=request_id,
        )
        return plant

    async def _check_transition_guard(
        self, plant: Plant, *, from_status: PlantStatus, to_status: PlantStatus, reason: str | None
    ) -> None:
        if to_status == PlantStatus.READY_FOR_SALE:
            open_count = sum(
                1
                for r in await self._disease_reports.list_for_plant(plant.id)
                if r.status in _OPEN_DISEASE_STATUSES
            )
            if open_count > 0:
                raise ConflictError("Cannot promote to Ready for Sale while an open disease report exists.")

        if to_status == PlantStatus.UNDER_TREATMENT:
            confirmed = [
                r for r in await self._disease_reports.list_for_plant(plant.id) if r.status in _CONFIRMED_DISEASE_STATUSES
            ]
            if not confirmed:
                raise ConflictError("Under Treatment requires a confirmed disease report for this plant.")

        if from_status == PlantStatus.UNDER_TREATMENT and to_status in (
            PlantStatus.IN_PRODUCTION,
            PlantStatus.DECEASED,
        ):
            expected_outcome = (
                TreatmentOutcome.RECOVERED if to_status == PlantStatus.IN_PRODUCTION else TreatmentOutcome.PLANT_LOST
            )
            if not await self._has_resolved_treatment_with_outcome(plant.id, expected_outcome):
                raise ConflictError(
                    f"Leaving Under Treatment for '{to_status.value}' requires a disease report resolved with "
                    f"treatment outcome '{expected_outcome.value}'."
                )

        if to_status == PlantStatus.DECEASED and from_status != PlantStatus.UNDER_TREATMENT:
            if not reason or not reason.strip():
                raise ValidationError("A reason is required to write off a plant as deceased.")

    async def _has_resolved_treatment_with_outcome(self, plant_id: uuid.UUID, outcome: TreatmentOutcome) -> bool:
        for report in await self._disease_reports.list_for_plant(plant_id):
            if report.status != DiseaseReportStatus.RESOLVED:
                continue
            treatments = await self._treatments.list_for_disease_report(report.id)
            if treatments and treatments[-1].outcome == outcome:
                return True
        return False

    # ------------------------------------------------------------------
    # Archive (administrative, not a business-status transition -- see module docstring)
    # ------------------------------------------------------------------
    async def archive_plant(
        self, *, plant_id: uuid.UUID, actor_user_id: uuid.UUID, reason: str | None = None, request_id: str | None = None
    ) -> Plant:
        plant = await self.get_plant(plant_id)
        if plant.archived_at is not None:
            raise ConflictError("This plant is already archived.")
        if plant.status not in (PlantStatus.SOLD, PlantStatus.DECEASED):
            raise ConflictError(
                "Only a plant in a terminal status (Sold or Deceased) can be archived. "
                "Write it off or complete its sale first."
            )

        plant.archived_at = datetime.now(timezone.utc)
        plant.archived_reason = reason

        await self._log_audit(
            nursery_id=plant.nursery_id, actor_user_id=actor_user_id, action="plant.archived", entity_id=plant.id,
            diff={"after": {"archived": True, "reason": reason}}, request_id=request_id,
        )
        await self._events.publish(
            PlantArchived(aggregate_id=plant.id, nursery_id=plant.nursery_id, actor_user_id=actor_user_id),
            request_id=request_id,
        )
        return plant

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    async def _log_audit(
        self, *, nursery_id: uuid.UUID, actor_user_id: uuid.UUID, action: str, entity_id: uuid.UUID,
        diff: dict, request_id: str | None,
    ) -> None:
        await self._audit.log(
            AuditLog(
                nursery_id=nursery_id, actor_user_id=actor_user_id, action=action, entity_type="Plant",
                entity_id=entity_id, diff=diff, request_id=request_id, created_at=datetime.now(timezone.utc),
            )
        )
