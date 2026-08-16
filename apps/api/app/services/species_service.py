"""
Module 5 (Species Catalog) — species reference data CRUD (FR-4).

Same layering discipline as every prior module's services: takes only
repository Protocols (app/repositories/interfaces.py) and pure data, no
FastAPI/SQLAlchemy-session concerns. Authorization is not checked here —
by the time this runs, the route's `require_permission` dependency
(app/api/deps.py) has already verified the caller may perform this
action.

Species is per-Org (`nursery_id`), *not* branch-scoped (FR-4.2: "shared/
reusable across all Branches within an Org") — every method below takes
`nursery_id`, never `branch_id`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain_events import DomainEventPublisher, SpeciesCreated, SpeciesDeleted, SpeciesUpdated
from app.models.catalog import PlantCategory, Species
from app.models.platform import AuditLog
from app.repositories.interfaces import AuditLogRepository, PlantCategoryRepository, SpeciesRepository
from app.services.validation import validate_disease_susceptibility, validate_growth_curve_baseline


class SpeciesService:
    def __init__(
        self,
        *,
        species_repo: SpeciesRepository,
        category_repo: PlantCategoryRepository,
        audit_repo: AuditLogRepository,
        event_publisher: DomainEventPublisher,
    ) -> None:
        self._species = species_repo
        self._categories = category_repo
        self._audit = audit_repo
        self._events = event_publisher

    # ------------------------------------------------------------------
    # Plant categories (read-only reference data)
    # ------------------------------------------------------------------
    async def list_categories(self) -> list[PlantCategory]:
        return await self._categories.list_all()

    # ------------------------------------------------------------------
    # Species lifecycle
    # ------------------------------------------------------------------
    async def create_species(
        self,
        *,
        nursery_id: uuid.UUID,
        category_id: uuid.UUID,
        common_name: str,
        botanical_name: str,
        actor_user_id: uuid.UUID,
        light_requirement: str | None = None,
        water_baseline_ml_per_week: int | None = None,
        soil_type: str | None = None,
        temperature_min_celsius: float | None = None,
        temperature_max_celsius: float | None = None,
        growth_curve_baseline: list | None = None,
        disease_susceptibility: list | None = None,
        request_id: str | None = None,
    ) -> Species:
        category = await self._categories.get_by_id(category_id)
        if category is None:
            raise ValidationError(f"'{category_id}' is not a recognized plant category.")

        normalized_common = common_name.strip()
        normalized_botanical = botanical_name.strip()
        if not normalized_common or not normalized_botanical:
            raise ValidationError("common_name and botanical_name cannot be blank.")
        if await self._species.get_by_botanical_name(nursery_id, normalized_botanical) is not None:
            raise ConflictError(f"A species with botanical name '{normalized_botanical}' already exists in this organization.")

        _validate_temperature_range(temperature_min_celsius, temperature_max_celsius)
        validated_growth_curve = validate_growth_curve_baseline(growth_curve_baseline)
        validated_disease_susceptibility = validate_disease_susceptibility(disease_susceptibility)

        species = Species(
            nursery_id=nursery_id,
            category_id=category_id,
            common_name=normalized_common,
            botanical_name=normalized_botanical,
            light_requirement=light_requirement,
            water_baseline_ml_per_week=water_baseline_ml_per_week,
            soil_type=soil_type,
            temperature_min_celsius=temperature_min_celsius,
            temperature_max_celsius=temperature_max_celsius,
            growth_curve_baseline=validated_growth_curve,
            disease_susceptibility=validated_disease_susceptibility,
        )
        await self._species.add(species)

        await self._log_audit(
            nursery_id=nursery_id,
            actor_user_id=actor_user_id,
            action="species.created",
            entity_id=species.id,
            diff={"after": {"common_name": species.common_name, "botanical_name": species.botanical_name}},
            request_id=request_id,
        )
        await self._events.publish(
            SpeciesCreated(
                aggregate_id=species.id,
                nursery_id=nursery_id,
                actor_user_id=actor_user_id,
                common_name=species.common_name,
                botanical_name=species.botanical_name,
            ),
            request_id=request_id,
        )
        return species

    async def get_species(self, species_id: uuid.UUID) -> Species:
        species = await self._species.get_by_id(species_id)
        if species is None:
            raise NotFoundError("Species not found.")
        return species

    async def list_species(
        self,
        *,
        nursery_id: uuid.UUID,
        offset: int,
        limit: int,
        search: str | None = None,
        category_id: uuid.UUID | None = None,
        light_requirement: str | None = None,
    ) -> tuple[list[Species], int]:
        return await self._species.list_for_nursery(
            nursery_id,
            offset=offset,
            limit=limit,
            search=search,
            category_id=category_id,
            light_requirement=light_requirement,
        )

    async def update_species(
        self,
        *,
        species_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        category_id: uuid.UUID | None = None,
        common_name: str | None = None,
        botanical_name: str | None = None,
        light_requirement: str | None = None,
        water_baseline_ml_per_week: int | None = None,
        soil_type: str | None = None,
        temperature_min_celsius: float | None = None,
        temperature_max_celsius: float | None = None,
        growth_curve_baseline: list | None = None,
        disease_susceptibility: list | None = None,
        request_id: str | None = None,
    ) -> Species:
        """
        Same "`None` means leave this field unchanged" convention Module 4's
        `update_nursery`/`update_branch` use throughout this codebase --
        including for Species' own nullable fields (`light_requirement`,
        `soil_type`, the temperature bounds, the two JSON fields): a PATCH
        can set a new value but not explicitly clear one back to null. If a
        future requirement needs "clear this field", it gets a dedicated
        sentinel or endpoint rather than overloading `None` here, the same
        tradeoff Module 4 already made and documented for Branch's
        nullable contact fields.
        """
        species = await self.get_species(species_id)
        before = _snapshot(species)
        changed: list[str] = []

        if category_id is not None and category_id != species.category_id:
            category = await self._categories.get_by_id(category_id)
            if category is None:
                raise ValidationError(f"'{category_id}' is not a recognized plant category.")
            species.category_id = category_id
            changed.append("category_id")
        if common_name is not None:
            normalized = common_name.strip()
            if not normalized:
                raise ValidationError("common_name cannot be blank.")
            if normalized != species.common_name:
                species.common_name = normalized
                changed.append("common_name")
        if botanical_name is not None:
            normalized = botanical_name.strip()
            if not normalized:
                raise ValidationError("botanical_name cannot be blank.")
            if normalized != species.botanical_name:
                existing = await self._species.get_by_botanical_name(species.nursery_id, normalized)
                if existing is not None and existing.id != species.id:
                    raise ConflictError(f"A species with botanical name '{normalized}' already exists in this organization.")
                species.botanical_name = normalized
                changed.append("botanical_name")
        if light_requirement is not None and light_requirement != species.light_requirement:
            species.light_requirement = light_requirement
            changed.append("light_requirement")
        if water_baseline_ml_per_week is not None and water_baseline_ml_per_week != species.water_baseline_ml_per_week:
            species.water_baseline_ml_per_week = water_baseline_ml_per_week
            changed.append("water_baseline_ml_per_week")
        if soil_type is not None and soil_type != species.soil_type:
            species.soil_type = soil_type
            changed.append("soil_type")

        if temperature_min_celsius is not None or temperature_max_celsius is not None:
            new_min = temperature_min_celsius if temperature_min_celsius is not None else species.temperature_min_celsius
            new_max = temperature_max_celsius if temperature_max_celsius is not None else species.temperature_max_celsius
            _validate_temperature_range(new_min, new_max)
            if temperature_min_celsius is not None and new_min != species.temperature_min_celsius:
                species.temperature_min_celsius = new_min
                changed.append("temperature_min_celsius")
            if temperature_max_celsius is not None and new_max != species.temperature_max_celsius:
                species.temperature_max_celsius = new_max
                changed.append("temperature_max_celsius")

        if growth_curve_baseline is not None:
            validated = validate_growth_curve_baseline(growth_curve_baseline)
            if validated != species.growth_curve_baseline:
                species.growth_curve_baseline = validated
                changed.append("growth_curve_baseline")
        if disease_susceptibility is not None:
            validated = validate_disease_susceptibility(disease_susceptibility)
            if validated != species.disease_susceptibility:
                species.disease_susceptibility = validated
                changed.append("disease_susceptibility")

        if not changed:
            return species

        await self._log_audit(
            nursery_id=species.nursery_id,
            actor_user_id=actor_user_id,
            action="species.updated",
            entity_id=species.id,
            diff={"before": before, "after": _snapshot(species)},
            request_id=request_id,
        )
        await self._events.publish(
            SpeciesUpdated(
                aggregate_id=species.id,
                nursery_id=species.nursery_id,
                actor_user_id=actor_user_id,
                changed_fields=tuple(changed),
            ),
            request_id=request_id,
        )
        return species

    async def delete_species(
        self, *, species_id: uuid.UUID, actor_user_id: uuid.UUID, request_id: str | None = None
    ) -> None:
        species = await self.get_species(species_id)
        referencing = await self._species.count_plants_referencing(species_id)
        if referencing > 0:
            raise ConflictError(
                f"Cannot delete this species: {referencing} plant record(s) still reference it. "
                "Reassign or remove those plants first."
            )

        await self._species.delete(species)
        await self._log_audit(
            nursery_id=species.nursery_id,
            actor_user_id=actor_user_id,
            action="species.deleted",
            entity_id=species.id,
            diff={"before": {"common_name": species.common_name, "botanical_name": species.botanical_name}},
            request_id=request_id,
        )
        await self._events.publish(
            SpeciesDeleted(
                aggregate_id=species.id,
                nursery_id=species.nursery_id,
                actor_user_id=actor_user_id,
                botanical_name=species.botanical_name,
            ),
            request_id=request_id,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    async def _log_audit(
        self,
        *,
        nursery_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        action: str,
        entity_id: uuid.UUID,
        diff: dict,
        request_id: str | None,
    ) -> None:
        await self._audit.log(
            AuditLog(
                nursery_id=nursery_id,
                actor_user_id=actor_user_id,
                action=action,
                entity_type="Species",
                entity_id=entity_id,
                diff=diff,
                request_id=request_id,
                created_at=datetime.now(timezone.utc),
            )
        )


def _validate_temperature_range(min_c: float | None, max_c: float | None) -> None:
    if min_c is not None and max_c is not None and min_c > max_c:
        raise ValidationError("temperature_min_celsius must be <= temperature_max_celsius.")


def _snapshot(species: Species) -> dict:
    return {
        "category_id": str(species.category_id),
        "common_name": species.common_name,
        "botanical_name": species.botanical_name,
        "light_requirement": species.light_requirement,
        "water_baseline_ml_per_week": species.water_baseline_ml_per_week,
        "soil_type": species.soil_type,
        "temperature_min_celsius": float(species.temperature_min_celsius) if species.temperature_min_celsius is not None else None,
        "temperature_max_celsius": float(species.temperature_max_celsius) if species.temperature_max_celsius is not None else None,
        "growth_curve_baseline": species.growth_curve_baseline,
        "disease_susceptibility": species.disease_susceptibility,
    }
