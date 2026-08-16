"""
Module 6 -- Plant Timeline: a single, immutable, chronologically ordered
feed merging every one of the module's own named example events
("Plant Registered", "Plant Moved", "Image Uploaded", "Watered",
"Fertilized", "Disease Detected", "Treatment Applied", "Growth Recorded",
"Health Updated", "Transferred", "Sold", "Disposed") from their real
source-of-truth tables.

This is a *read model*, not a new source of truth: every entry below is
reconstructed from a row that already exists in an append-only table this
module already writes (GrowthTimeline, HealthHistory, WateringLog,
FertilizerLog, PlantTransfer, PlantImage, DiseaseReport, Treatment) or
from `Plant`'s own terminal-status timestamps (`sold_at`/`deceased_at`).
Nothing is written here, and nothing is duplicated: nowhere does this
service store its own copy of "what happened" -- nowhere would that copy
be able to drift from the real record it was built from, either.

Two deliberate omissions, both explained where the module's other files
already raise them:
  - "Inventory Updated" has no entries here -- Module 6 never writes to
    the separate bulk `inventory` table (see plant_service.py's own
    module docstring for why that would be architecturally wrong for an
    individually-tracked Plant).
  - Intermediate, non-terminal status changes (e.g. a Ready for Sale
    promotion/demotion that isn't itself a Disease/Treatment/Sale event)
    are not re-shown here a second time -- they are already fully
    captured, timestamped, and attributed in the Audit Log
    (`GET /api/v1/audit-log`, Module 3) and the `domain_events` outbox
    (`plant.status_changed`) every transition already writes to
    (PlantService.transition_status). Re-deriving that same history into
    a second, competing feed is exactly the "duplicate business logic"
    this module was told not to create.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.core.exceptions import NotFoundError
from app.repositories.interfaces import (
    DiseaseReportRepository,
    EnvironmentalReadingRepository,
    FertilizerLogRepository,
    GrowthTimelineRepository,
    HealthHistoryRepository,
    PlantImageRepository,
    PlantRepository,
    PlantTransferRepository,
    TreatmentRepository,
    WateringLogRepository,
)


@dataclass(frozen=True)
class PlantTimelineEntry:
    """One immutable Timeline row -- never persisted as its own table, always reconstructed from its real source row."""

    event_type: str
    occurred_at: datetime
    summary: str
    source_id: uuid.UUID
    actor_user_id: uuid.UUID | None = None


class PlantTimelineService:
    def __init__(
        self,
        *,
        plant_repo: PlantRepository,
        transfer_repo: PlantTransferRepository,
        image_repo: PlantImageRepository,
        growth_repo: GrowthTimelineRepository,
        health_repo: HealthHistoryRepository,
        watering_repo: WateringLogRepository,
        fertilizer_repo: FertilizerLogRepository,
        disease_repo: DiseaseReportRepository,
        treatment_repo: TreatmentRepository,
        environmental_repo: EnvironmentalReadingRepository | None = None,
    ) -> None:
        self._plants = plant_repo
        self._transfers = transfer_repo
        self._images = image_repo
        self._growth = growth_repo
        self._health = health_repo
        self._watering = watering_repo
        self._fertilizer = fertilizer_repo
        self._disease = disease_repo
        self._treatments = treatment_repo
        self._environmental = environmental_repo  # accepted, not used -- see module docstring's "deliberate omissions"

    async def get_timeline(self, plant_id: uuid.UUID, *, offset: int = 0, limit: int = 50) -> tuple[list[PlantTimelineEntry], int]:
        plant = await self._plants.get_by_id(plant_id)
        if plant is None:
            raise NotFoundError("Plant not found.")

        entries: list[PlantTimelineEntry] = [
            PlantTimelineEntry(
                event_type="plant.registered",
                occurred_at=plant.created_at,
                summary=f"Plant registered ({plant.qr_code_token})",
                source_id=plant.id,
                actor_user_id=plant.registered_by_user_id,
            )
        ]

        for transfer in await self._transfers.list_for_plant(plant_id):
            event_type = "plant.transferred" if transfer.from_branch_id != transfer.to_branch_id else "plant.moved"
            summary = (
                f"Moved from branch {transfer.from_branch_id} to {transfer.to_branch_id}"
                if event_type == "plant.transferred"
                else f"Moved zone '{transfer.from_zone}' -> '{transfer.to_zone}'"
            )
            entries.append(
                PlantTimelineEntry(
                    event_type=event_type, occurred_at=transfer.transferred_at, summary=summary,
                    source_id=transfer.id, actor_user_id=transfer.transferred_by_user_id,
                )
            )

        for image in await self._images.list_for_plant(plant_id):
            entries.append(
                PlantTimelineEntry(
                    event_type="plant.image_uploaded", occurred_at=image.captured_at,
                    summary=image.caption or "Image uploaded", source_id=image.id,
                    actor_user_id=image.uploaded_by_user_id,
                )
            )

        growth_rows, _ = await self._growth.list_for_plant(plant_id, offset=0, limit=10_000)
        for growth_entry in growth_rows:
            entries.append(
                PlantTimelineEntry(
                    event_type="plant.growth_recorded", occurred_at=growth_entry.recorded_at,
                    summary=f"Growth recorded (height={growth_entry.height_cm} cm)", source_id=growth_entry.id,
                    actor_user_id=growth_entry.recorded_by_user_id,
                )
            )

        health_rows, _ = await self._health.list_for_plant(plant_id, offset=0, limit=10_000)
        for health_entry in health_rows:
            entries.append(
                PlantTimelineEntry(
                    event_type="plant.health_updated", occurred_at=health_entry.recorded_at,
                    summary=f"Health updated: {health_entry.status_label}", source_id=health_entry.id,
                    actor_user_id=health_entry.recorded_by_user_id,
                )
            )

        watering_rows, _ = await self._watering.list_for_plant(plant_id, offset=0, limit=10_000)
        for watering_entry in watering_rows:
            entries.append(
                PlantTimelineEntry(
                    event_type="plant.watered", occurred_at=watering_entry.recorded_at,
                    summary=f"Watered ({watering_entry.volume_ml} ml)" if watering_entry.volume_ml else "Watered",
                    source_id=watering_entry.id, actor_user_id=watering_entry.recorded_by_user_id,
                )
            )

        fertilizer_rows, _ = await self._fertilizer.list_for_plant(plant_id, offset=0, limit=10_000)
        for fertilizer_entry in fertilizer_rows:
            entries.append(
                PlantTimelineEntry(
                    event_type="plant.fertilized", occurred_at=fertilizer_entry.recorded_at,
                    summary=f"Fertilized with {fertilizer_entry.product_name}", source_id=fertilizer_entry.id,
                    actor_user_id=fertilizer_entry.recorded_by_user_id,
                )
            )

        for report in await self._disease.list_for_plant(plant_id):
            entries.append(
                PlantTimelineEntry(
                    event_type="plant.disease_detected", occurred_at=report.created_at,
                    summary=f"Disease detected: {report.condition_name} ({report.severity.value})",
                    source_id=report.id, actor_user_id=report.confirmed_by_user_id,
                )
            )
            for treatment in await self._treatments.list_for_disease_report(report.id):
                entries.append(
                    PlantTimelineEntry(
                        event_type="plant.treatment_applied", occurred_at=treatment.applied_at,
                        summary=f"Treatment applied: {treatment.description} (outcome={treatment.outcome.value})",
                        source_id=treatment.id, actor_user_id=treatment.applied_by_user_id,
                    )
                )

        if plant.sold_at is not None:
            entries.append(
                PlantTimelineEntry(
                    event_type="plant.sold", occurred_at=plant.sold_at, summary="Plant sold", source_id=plant.id,
                )
            )
        if plant.deceased_at is not None:
            entries.append(
                PlantTimelineEntry(
                    event_type="plant.disposed", occurred_at=plant.deceased_at,
                    summary=f"Plant disposed: {plant.deceased_reason or 'no reason given'}", source_id=plant.id,
                )
            )

        entries.sort(key=lambda e: e.occurred_at, reverse=True)
        total = len(entries)
        return entries[offset : offset + limit], total
