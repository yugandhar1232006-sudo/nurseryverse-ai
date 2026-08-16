"""
Module 6 -- the five append-only Digital Twin record types: Growth,
Health, Watering, Fertilizer, Environmental. Each is its own real table
with its own real domain columns (app/models/digital_twin_records.py),
but every one of the five services below shares an identical shape:
validate non-negative measurements, fetch the parent Plant (tenant scope
+ existence), insert the immutable row, audit-log it, publish one domain
event. Five near-identical service classes were kept deliberately
separate (not folded into one generic `RecordService[T]`) because each
validates genuinely different fields -- collapsing them into one generic
class would trade five short, obviously-correct methods for one harder-
to-read parametrized one, which is not what "don't create duplicate
business logic" is asking for here (there's no duplicated *business
rule*, only a duplicated *shape*).

No update/delete method exists anywhere in this file -- these are
immutable once created, per the LLD's "Module: Growth Timeline"
("entries are immutable once created (append-only, no PATCH/DELETE
endpoint exists)"), a rule this module's own Timeline requirement
depends on ("Every event must be immutable").
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.exceptions import NotFoundError, ValidationError
from app.domain_events import (
    DomainEventPublisher,
    EnvironmentalRecorded,
    FertilizerRecorded,
    GrowthRecorded,
    HealthRecorded,
    WateringRecorded,
)
from app.models.digital_twin_records import EnvironmentalReading, FertilizerLog, GrowthTimeline, HealthHistory, WateringLog
from app.models.platform import AuditLog
from app.repositories.interfaces import (
    AuditLogRepository,
    EnvironmentalReadingRepository,
    FertilizerLogRepository,
    GrowthTimelineRepository,
    HealthHistoryRepository,
    PlantRepository,
    WateringLogRepository,
)


def _require_non_negative(value: float | int | None, field_name: str) -> None:
    if value is not None and value < 0:
        raise ValidationError(f"{field_name} cannot be negative.")


class GrowthService:
    def __init__(
        self,
        *,
        growth_repo: GrowthTimelineRepository,
        plant_repo: PlantRepository,
        audit_repo: AuditLogRepository,
        event_publisher: DomainEventPublisher,
    ) -> None:
        self._growth = growth_repo
        self._plants = plant_repo
        self._audit = audit_repo
        self._events = event_publisher

    async def record_growth(
        self,
        *,
        plant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        height_cm: float | None = None,
        spread_cm: float | None = None,
        leaf_count: int | None = None,
        flower_count: int | None = None,
        fruit_count: int | None = None,
        growth_stage: str | None = None,
        notes: str | None = None,
        photo_urls: list[str] | None = None,
        measured_at: datetime | None = None,
        request_id: str | None = None,
    ) -> GrowthTimeline:
        _require_non_negative(height_cm, "height_cm")
        _require_non_negative(spread_cm, "spread_cm")
        _require_non_negative(leaf_count, "leaf_count")
        _require_non_negative(flower_count, "flower_count")
        _require_non_negative(fruit_count, "fruit_count")

        plant = await self._plants.get_by_id(plant_id)
        if plant is None:
            raise NotFoundError("Plant not found.")

        entry = GrowthTimeline(
            plant_id=plant_id,
            height_cm=height_cm,
            spread_cm=spread_cm,
            leaf_count=leaf_count,
            flower_count=flower_count,
            fruit_count=fruit_count,
            growth_stage=growth_stage,
            photo_url=(photo_urls[0] if photo_urls else None),
            photo_urls=photo_urls,
            notes=notes,
            recorded_by_user_id=actor_user_id,
            recorded_at=measured_at or datetime.now(timezone.utc),
        )
        await self._growth.add(entry)

        await self._log_audit(
            nursery_id=plant.nursery_id, actor_user_id=actor_user_id, action="plant.growth_recorded",
            entity_id=plant_id, diff={"after": {"growth_entry_id": str(entry.id), "height_cm": height_cm}},
            request_id=request_id,
        )
        await self._events.publish(
            GrowthRecorded(
                aggregate_id=plant_id, nursery_id=plant.nursery_id, actor_user_id=actor_user_id,
                growth_entry_id=entry.id, height_cm=height_cm,
            ),
            request_id=request_id,
        )
        return entry

    async def list_growth(self, plant_id: uuid.UUID, *, offset: int, limit: int) -> tuple[list[GrowthTimeline], int]:
        return await self._growth.list_for_plant(plant_id, offset=offset, limit=limit)

    async def _log_audit(self, **kwargs) -> None:
        await _log_audit(self._audit, entity_type="Plant", **kwargs)


class HealthService:
    def __init__(
        self,
        *,
        health_repo: HealthHistoryRepository,
        plant_repo: PlantRepository,
        audit_repo: AuditLogRepository,
        event_publisher: DomainEventPublisher,
    ) -> None:
        self._health = health_repo
        self._plants = plant_repo
        self._audit = audit_repo
        self._events = event_publisher

    async def record_health(
        self,
        *,
        plant_id: uuid.UUID,
        status_label: str,
        actor_user_id: uuid.UUID,
        health_score: float | None = None,
        notes: str | None = None,
        photo_url: str | None = None,
        is_ai_observation: bool = False,
        observed_at: datetime | None = None,
        request_id: str | None = None,
    ) -> HealthHistory:
        if not status_label or not status_label.strip():
            raise ValidationError("status_label is required (e.g. 'healthy', 'stressed', 'recovering').")
        if health_score is not None and not (0 <= health_score <= 100):
            raise ValidationError("health_score must be between 0 and 100.")

        plant = await self._plants.get_by_id(plant_id)
        if plant is None:
            raise NotFoundError("Plant not found.")

        entry = HealthHistory(
            plant_id=plant_id,
            status_label=status_label.strip(),
            health_score=health_score,
            notes=notes,
            photo_url=photo_url,
            is_ai_observation=is_ai_observation,
            recorded_by_user_id=actor_user_id,
            recorded_at=observed_at or datetime.now(timezone.utc),
        )
        await self._health.add(entry)

        await _log_audit(
            self._audit, nursery_id=plant.nursery_id, actor_user_id=actor_user_id, action="plant.health_recorded",
            entity_type="Plant", entity_id=plant_id,
            diff={"after": {"health_entry_id": str(entry.id), "status_label": entry.status_label}},
            request_id=request_id,
        )
        await self._events.publish(
            HealthRecorded(
                aggregate_id=plant_id, nursery_id=plant.nursery_id, actor_user_id=actor_user_id,
                health_entry_id=entry.id, status_label=entry.status_label,
            ),
            request_id=request_id,
        )
        return entry

    async def list_health(self, plant_id: uuid.UUID, *, offset: int, limit: int) -> tuple[list[HealthHistory], int]:
        return await self._health.list_for_plant(plant_id, offset=offset, limit=limit)


class WateringService:
    def __init__(
        self,
        *,
        watering_repo: WateringLogRepository,
        plant_repo: PlantRepository,
        audit_repo: AuditLogRepository,
        event_publisher: DomainEventPublisher,
    ) -> None:
        self._watering = watering_repo
        self._plants = plant_repo
        self._audit = audit_repo
        self._events = event_publisher

    async def record_watering(
        self,
        *,
        plant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        volume_ml: float | None = None,
        method: str | None = None,
        notes: str | None = None,
        watered_at: datetime | None = None,
        request_id: str | None = None,
    ) -> WateringLog:
        _require_non_negative(volume_ml, "volume_ml")
        plant = await self._plants.get_by_id(plant_id)
        if plant is None:
            raise NotFoundError("Plant not found.")

        entry = WateringLog(
            branch_id=plant.branch_id, plant_id=plant_id, zone=plant.zone, volume_ml=volume_ml, method=method,
            notes=notes, recorded_by_user_id=actor_user_id, recorded_at=watered_at or datetime.now(timezone.utc),
        )
        await self._watering.add(entry)

        await _log_audit(
            self._audit, nursery_id=plant.nursery_id, actor_user_id=actor_user_id, action="plant.watering_recorded",
            entity_type="Plant", entity_id=plant_id, diff={"after": {"watering_log_id": str(entry.id)}},
            request_id=request_id,
        )
        await self._events.publish(
            WateringRecorded(
                aggregate_id=plant_id, nursery_id=plant.nursery_id, actor_user_id=actor_user_id,
                watering_log_id=entry.id,
            ),
            request_id=request_id,
        )
        return entry

    async def list_watering(self, plant_id: uuid.UUID, *, offset: int, limit: int) -> tuple[list[WateringLog], int]:
        return await self._watering.list_for_plant(plant_id, offset=offset, limit=limit)


class FertilizerService:
    def __init__(
        self,
        *,
        fertilizer_repo: FertilizerLogRepository,
        plant_repo: PlantRepository,
        audit_repo: AuditLogRepository,
        event_publisher: DomainEventPublisher,
    ) -> None:
        self._fertilizer = fertilizer_repo
        self._plants = plant_repo
        self._audit = audit_repo
        self._events = event_publisher

    async def record_fertilizer(
        self,
        *,
        plant_id: uuid.UUID,
        product_name: str,
        actor_user_id: uuid.UUID,
        quantity_ml: float | None = None,
        npk_ratio: str | None = None,
        method: str | None = None,
        schedule: str | None = None,
        next_application_date: datetime | None = None,
        notes: str | None = None,
        applied_at: datetime | None = None,
        request_id: str | None = None,
    ) -> FertilizerLog:
        if not product_name or not product_name.strip():
            raise ValidationError("product_name is required.")
        _require_non_negative(quantity_ml, "quantity_ml")

        plant = await self._plants.get_by_id(plant_id)
        if plant is None:
            raise NotFoundError("Plant not found.")

        entry = FertilizerLog(
            branch_id=plant.branch_id, plant_id=plant_id, zone=plant.zone, product_name=product_name.strip(),
            quantity_ml=quantity_ml, npk_ratio=npk_ratio, method=method, schedule=schedule,
            next_application_date=next_application_date, notes=notes, recorded_by_user_id=actor_user_id,
            recorded_at=applied_at or datetime.now(timezone.utc),
        )
        await self._fertilizer.add(entry)

        await _log_audit(
            self._audit, nursery_id=plant.nursery_id, actor_user_id=actor_user_id, action="plant.fertilizer_recorded",
            entity_type="Plant", entity_id=plant_id, diff={"after": {"fertilizer_log_id": str(entry.id)}},
            request_id=request_id,
        )
        await self._events.publish(
            FertilizerRecorded(
                aggregate_id=plant_id, nursery_id=plant.nursery_id, actor_user_id=actor_user_id,
                fertilizer_log_id=entry.id,
            ),
            request_id=request_id,
        )
        return entry

    async def list_fertilizer(self, plant_id: uuid.UUID, *, offset: int, limit: int) -> tuple[list[FertilizerLog], int]:
        return await self._fertilizer.list_for_plant(plant_id, offset=offset, limit=limit)


class EnvironmentalService:
    def __init__(
        self,
        *,
        environmental_repo: EnvironmentalReadingRepository,
        plant_repo: PlantRepository,
        audit_repo: AuditLogRepository,
        event_publisher: DomainEventPublisher,
    ) -> None:
        self._environmental = environmental_repo
        self._plants = plant_repo
        self._audit = audit_repo
        self._events = event_publisher

    async def record_reading(
        self,
        *,
        plant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        temperature_celsius: float | None = None,
        humidity_percent: float | None = None,
        soil_moisture_percent: float | None = None,
        light_lux: float | None = None,
        ph_level: float | None = None,
        weather_snapshot: dict | None = None,
        source: str = "manual",
        recorded_at: datetime | None = None,
        request_id: str | None = None,
    ) -> EnvironmentalReading:
        if humidity_percent is not None and not (0 <= humidity_percent <= 100):
            raise ValidationError("humidity_percent must be between 0 and 100.")
        if soil_moisture_percent is not None and not (0 <= soil_moisture_percent <= 100):
            raise ValidationError("soil_moisture_percent must be between 0 and 100.")
        if ph_level is not None and not (0 <= ph_level <= 14):
            raise ValidationError("ph_level must be between 0 and 14.")
        _require_non_negative(light_lux, "light_lux")

        plant = await self._plants.get_by_id(plant_id)
        if plant is None:
            raise NotFoundError("Plant not found.")

        entry = EnvironmentalReading(
            branch_id=plant.branch_id, plant_id=plant_id, zone=plant.zone,
            temperature_celsius=temperature_celsius, humidity_percent=humidity_percent,
            soil_moisture_percent=soil_moisture_percent, light_lux=light_lux, ph_level=ph_level,
            weather_snapshot=weather_snapshot, source=source, recorded_at=recorded_at or datetime.now(timezone.utc),
        )
        await self._environmental.add(entry)

        await _log_audit(
            self._audit, nursery_id=plant.nursery_id, actor_user_id=actor_user_id,
            action="plant.environmental_recorded", entity_type="Plant", entity_id=plant_id,
            diff={"after": {"reading_id": str(entry.id)}}, request_id=request_id,
        )
        await self._events.publish(
            EnvironmentalRecorded(
                aggregate_id=plant_id, nursery_id=plant.nursery_id, actor_user_id=actor_user_id,
                reading_id=entry.id,
            ),
            request_id=request_id,
        )
        return entry

    async def list_readings(
        self, plant_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[EnvironmentalReading], int]:
        return await self._environmental.list_for_plant(plant_id, offset=offset, limit=limit)


async def _log_audit(
    audit_repo: AuditLogRepository,
    *,
    nursery_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    diff: dict,
    request_id: str | None,
) -> None:
    """Shared by all five services above -- the exact same audit-row shape every other module's service already writes."""
    await audit_repo.log(
        AuditLog(
            nursery_id=nursery_id, actor_user_id=actor_user_id, action=action, entity_type=entity_type,
            entity_id=entity_id, diff=diff, request_id=request_id, created_at=datetime.now(timezone.utc),
        )
    )
