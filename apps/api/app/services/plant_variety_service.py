"""
Module 5 (Species Catalog) — PlantVariety (cultivar) management, nested
under a Species (e.g. Species "Ficus lyrata" -> Variety "Bambino").

Same per-Org, not branch-scoped, "None means leave unchanged" conventions
as `app/services/species_service.py` -- see that module's docstrings for
the full rationale, not repeated here.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain_events import DomainEventPublisher, PlantVarietyCreated, PlantVarietyDeleted, PlantVarietyUpdated
from app.models.catalog import PlantVariety
from app.models.platform import AuditLog
from app.repositories.interfaces import AuditLogRepository, PlantVarietyRepository, SpeciesRepository


class PlantVarietyService:
    def __init__(
        self,
        *,
        variety_repo: PlantVarietyRepository,
        species_repo: SpeciesRepository,
        audit_repo: AuditLogRepository,
        event_publisher: DomainEventPublisher,
    ) -> None:
        self._varieties = variety_repo
        self._species = species_repo
        self._audit = audit_repo
        self._events = event_publisher

    async def create_variety(
        self,
        *,
        nursery_id: uuid.UUID,
        species_id: uuid.UUID,
        name: str,
        actor_user_id: uuid.UUID,
        description: str | None = None,
        request_id: str | None = None,
    ) -> PlantVariety:
        species = await self._species.get_by_id(species_id)
        if species is None or species.nursery_id != nursery_id:
            raise ValidationError(f"Species {species_id} does not belong to this organization.")

        normalized_name = name.strip()
        if not normalized_name:
            raise ValidationError("name cannot be blank.")
        if await self._varieties.get_by_name(species_id, normalized_name) is not None:
            raise ConflictError(f"A variety named '{normalized_name}' already exists for this species.")

        variety = PlantVariety(
            nursery_id=nursery_id, species_id=species_id, name=normalized_name, description=description
        )
        await self._varieties.add(variety)

        await self._log_audit(
            nursery_id=nursery_id,
            actor_user_id=actor_user_id,
            action="plant_variety.created",
            entity_id=variety.id,
            diff={"after": {"name": variety.name, "species_id": str(species_id)}},
            request_id=request_id,
        )
        await self._events.publish(
            PlantVarietyCreated(
                aggregate_id=variety.id,
                nursery_id=nursery_id,
                actor_user_id=actor_user_id,
                species_id=species_id,
                name=variety.name,
            ),
            request_id=request_id,
        )
        return variety

    async def get_variety(self, variety_id: uuid.UUID) -> PlantVariety:
        variety = await self._varieties.get_by_id(variety_id)
        if variety is None:
            raise NotFoundError("Plant variety not found.")
        return variety

    async def list_varieties(
        self,
        *,
        nursery_id: uuid.UUID,
        offset: int,
        limit: int,
        species_id: uuid.UUID | None = None,
    ) -> tuple[list[PlantVariety], int]:
        if species_id is not None:
            return await self._varieties.list_for_species(species_id, offset=offset, limit=limit)
        return await self._varieties.list_for_nursery(nursery_id, offset=offset, limit=limit)

    async def update_variety(
        self,
        *,
        variety_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        name: str | None = None,
        description: str | None = None,
        request_id: str | None = None,
    ) -> PlantVariety:
        variety = await self.get_variety(variety_id)
        before = {"name": variety.name, "description": variety.description}
        changed: list[str] = []

        if name is not None:
            normalized = name.strip()
            if not normalized:
                raise ValidationError("name cannot be blank.")
            if normalized != variety.name:
                existing = await self._varieties.get_by_name(variety.species_id, normalized)
                if existing is not None and existing.id != variety.id:
                    raise ConflictError(f"A variety named '{normalized}' already exists for this species.")
                variety.name = normalized
                changed.append("name")
        if description is not None and description != variety.description:
            variety.description = description
            changed.append("description")

        if not changed:
            return variety

        await self._log_audit(
            nursery_id=variety.nursery_id,
            actor_user_id=actor_user_id,
            action="plant_variety.updated",
            entity_id=variety.id,
            diff={"before": before, "after": {"name": variety.name, "description": variety.description}},
            request_id=request_id,
        )
        await self._events.publish(
            PlantVarietyUpdated(
                aggregate_id=variety.id,
                nursery_id=variety.nursery_id,
                actor_user_id=actor_user_id,
                changed_fields=tuple(changed),
            ),
            request_id=request_id,
        )
        return variety

    async def delete_variety(
        self, *, variety_id: uuid.UUID, actor_user_id: uuid.UUID, request_id: str | None = None
    ) -> None:
        variety = await self.get_variety(variety_id)
        referencing = await self._varieties.count_plants_referencing(variety_id)
        if referencing > 0:
            raise ConflictError(
                f"Cannot delete this variety: {referencing} plant record(s) still reference it. "
                "Reassign or remove those plants first."
            )

        await self._varieties.delete(variety)
        await self._log_audit(
            nursery_id=variety.nursery_id,
            actor_user_id=actor_user_id,
            action="plant_variety.deleted",
            entity_id=variety.id,
            diff={"before": {"name": variety.name, "species_id": str(variety.species_id)}},
            request_id=request_id,
        )
        await self._events.publish(
            PlantVarietyDeleted(
                aggregate_id=variety.id,
                nursery_id=variety.nursery_id,
                actor_user_id=actor_user_id,
                species_id=variety.species_id,
                name=variety.name,
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
                entity_type="PlantVariety",
                entity_id=entity_id,
                diff=diff,
                request_id=request_id,
                created_at=datetime.now(timezone.utc),
            )
        )
