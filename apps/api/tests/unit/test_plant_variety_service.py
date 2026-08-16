"""Module 5 unit tests: PlantVarietyService against in-memory fakes."""
from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain_events import DomainEventPublisher
from app.models.catalog import Species
from app.services.plant_variety_service import PlantVarietyService
from tests.fakes.repositories import FakeAuditLogRepository, FakeDomainEventRepository, FakePlantVarietyRepository, FakeSpeciesRepository


@pytest.fixture
def nursery_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def species_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def variety_service(nursery_id: uuid.UUID, species_id: uuid.UUID) -> PlantVarietyService:
    species_repo = FakeSpeciesRepository()
    species_repo.species[species_id] = Species(
        id=species_id,
        nursery_id=nursery_id,
        category_id=uuid.uuid4(),
        common_name="Fiddle Leaf Fig",
        botanical_name="Ficus lyrata",
    )
    varieties = FakePlantVarietyRepository()
    audit = FakeAuditLogRepository()
    events = DomainEventPublisher(FakeDomainEventRepository())
    return PlantVarietyService(variety_repo=varieties, species_repo=species_repo, audit_repo=audit, event_publisher=events)


class TestCreateVariety:
    async def test_creates_variety(self, variety_service: PlantVarietyService, nursery_id: uuid.UUID, species_id: uuid.UUID) -> None:
        variety = await variety_service.create_variety(
            nursery_id=nursery_id, species_id=species_id, name="Bambino", actor_user_id=uuid.uuid4()
        )
        assert variety.id is not None
        assert variety.name == "Bambino"
        assert variety.species_id == species_id

    async def test_species_outside_org_rejected(self, variety_service: PlantVarietyService, nursery_id: uuid.UUID) -> None:
        with pytest.raises(ValidationError):
            await variety_service.create_variety(
                nursery_id=nursery_id, species_id=uuid.uuid4(), name="Bambino", actor_user_id=uuid.uuid4()
            )

    async def test_duplicate_name_for_species_conflicts(
        self, variety_service: PlantVarietyService, nursery_id: uuid.UUID, species_id: uuid.UUID
    ) -> None:
        await variety_service.create_variety(
            nursery_id=nursery_id, species_id=species_id, name="Bambino", actor_user_id=uuid.uuid4()
        )
        with pytest.raises(ConflictError):
            await variety_service.create_variety(
                nursery_id=nursery_id, species_id=species_id, name="Bambino", actor_user_id=uuid.uuid4()
            )

    async def test_blank_name_rejected(self, variety_service: PlantVarietyService, nursery_id: uuid.UUID, species_id: uuid.UUID) -> None:
        with pytest.raises(ValidationError):
            await variety_service.create_variety(
                nursery_id=nursery_id, species_id=species_id, name="   ", actor_user_id=uuid.uuid4()
            )


class TestGetVariety:
    async def test_not_found_raises(self, variety_service: PlantVarietyService) -> None:
        with pytest.raises(NotFoundError):
            await variety_service.get_variety(uuid.uuid4())


class TestListVarieties:
    async def test_filters_by_species(
        self, variety_service: PlantVarietyService, nursery_id: uuid.UUID, species_id: uuid.UUID
    ) -> None:
        other_species_id = uuid.uuid4()
        variety_service._species.species[other_species_id] = Species(  # type: ignore[attr-defined]
            id=other_species_id, nursery_id=nursery_id, category_id=uuid.uuid4(),
            common_name="Snake Plant", botanical_name="Dracaena trifasciata",
        )
        await variety_service.create_variety(nursery_id=nursery_id, species_id=species_id, name="Bambino", actor_user_id=uuid.uuid4())
        await variety_service.create_variety(nursery_id=nursery_id, species_id=other_species_id, name="Laurentii", actor_user_id=uuid.uuid4())

        rows, total = await variety_service.list_varieties(nursery_id=nursery_id, offset=0, limit=20, species_id=species_id)
        assert total == 1
        assert rows[0].name == "Bambino"

    async def test_no_species_filter_lists_whole_org(
        self, variety_service: PlantVarietyService, nursery_id: uuid.UUID, species_id: uuid.UUID
    ) -> None:
        await variety_service.create_variety(nursery_id=nursery_id, species_id=species_id, name="Bambino", actor_user_id=uuid.uuid4())
        await variety_service.create_variety(nursery_id=nursery_id, species_id=species_id, name="Variegata", actor_user_id=uuid.uuid4())
        rows, total = await variety_service.list_varieties(nursery_id=nursery_id, offset=0, limit=20)
        assert total == 2


class TestUpdateVariety:
    async def test_updates_name(self, variety_service: PlantVarietyService, nursery_id: uuid.UUID, species_id: uuid.UUID) -> None:
        variety = await variety_service.create_variety(nursery_id=nursery_id, species_id=species_id, name="Bambino", actor_user_id=uuid.uuid4())
        updated = await variety_service.update_variety(variety_id=variety.id, actor_user_id=uuid.uuid4(), name="Bambino Deluxe")
        assert updated.name == "Bambino Deluxe"

    async def test_rename_to_existing_name_conflicts(
        self, variety_service: PlantVarietyService, nursery_id: uuid.UUID, species_id: uuid.UUID
    ) -> None:
        await variety_service.create_variety(nursery_id=nursery_id, species_id=species_id, name="Bambino", actor_user_id=uuid.uuid4())
        other = await variety_service.create_variety(nursery_id=nursery_id, species_id=species_id, name="Variegata", actor_user_id=uuid.uuid4())
        with pytest.raises(ConflictError):
            await variety_service.update_variety(variety_id=other.id, actor_user_id=uuid.uuid4(), name="Bambino")

    async def test_noop_update_skips_audit(self, variety_service: PlantVarietyService, nursery_id: uuid.UUID, species_id: uuid.UUID) -> None:
        variety = await variety_service.create_variety(nursery_id=nursery_id, species_id=species_id, name="Bambino", actor_user_id=uuid.uuid4())
        before = len(variety_service._audit.rows)  # type: ignore[attr-defined]
        await variety_service.update_variety(variety_id=variety.id, actor_user_id=uuid.uuid4())
        assert len(variety_service._audit.rows) == before  # type: ignore[attr-defined]


class TestDeleteVariety:
    async def test_deletes_unreferenced_variety(
        self, variety_service: PlantVarietyService, nursery_id: uuid.UUID, species_id: uuid.UUID
    ) -> None:
        variety = await variety_service.create_variety(nursery_id=nursery_id, species_id=species_id, name="Bambino", actor_user_id=uuid.uuid4())
        await variety_service.delete_variety(variety_id=variety.id, actor_user_id=uuid.uuid4())
        with pytest.raises(NotFoundError):
            await variety_service.get_variety(variety.id)

    async def test_blocked_when_referenced_by_a_plant(
        self, variety_service: PlantVarietyService, nursery_id: uuid.UUID, species_id: uuid.UUID
    ) -> None:
        variety = await variety_service.create_variety(nursery_id=nursery_id, species_id=species_id, name="Bambino", actor_user_id=uuid.uuid4())
        variety_service._varieties.plant_variety_ids.append(variety.id)  # type: ignore[attr-defined]
        with pytest.raises(ConflictError):
            await variety_service.delete_variety(variety_id=variety.id, actor_user_id=uuid.uuid4())
