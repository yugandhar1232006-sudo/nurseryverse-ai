"""Module 5 unit tests: SpeciesService (Species Catalog, FR-4) against in-memory fakes."""
from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain_events import DomainEventPublisher
from app.models.catalog import PlantCategory
from app.services.species_service import SpeciesService
from tests.fakes.repositories import FakeAuditLogRepository, FakeDomainEventRepository, FakePlantCategoryRepository, FakeSpeciesRepository


@pytest.fixture
def category_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def nursery_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def species_service(category_id: uuid.UUID) -> SpeciesService:
    categories = FakePlantCategoryRepository()
    categories.categories[category_id] = PlantCategory(
        id=category_id, code="houseplant", name="Houseplant", description="Indoor foliage"
    )
    species = FakeSpeciesRepository()
    audit = FakeAuditLogRepository()
    events = DomainEventPublisher(FakeDomainEventRepository())
    return SpeciesService(species_repo=species, category_repo=categories, audit_repo=audit, event_publisher=events)


VALID_KWARGS = dict(common_name="Fiddle Leaf Fig", botanical_name="Ficus lyrata")


class TestListCategories:
    async def test_lists_seeded_categories(self, species_service: SpeciesService, category_id: uuid.UUID) -> None:
        categories = await species_service.list_categories()
        assert [c.id for c in categories] == [category_id]


class TestCreateSpecies:
    async def test_creates_species(self, species_service: SpeciesService, nursery_id: uuid.UUID, category_id: uuid.UUID) -> None:
        species = await species_service.create_species(
            nursery_id=nursery_id, category_id=category_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS
        )
        assert species.id is not None
        assert species.common_name == "Fiddle Leaf Fig"
        assert species.botanical_name == "Ficus lyrata"

    async def test_unknown_category_rejected(self, species_service: SpeciesService, nursery_id: uuid.UUID) -> None:
        with pytest.raises(ValidationError):
            await species_service.create_species(
                nursery_id=nursery_id, category_id=uuid.uuid4(), actor_user_id=uuid.uuid4(), **VALID_KWARGS
            )

    async def test_duplicate_botanical_name_conflicts(
        self, species_service: SpeciesService, nursery_id: uuid.UUID, category_id: uuid.UUID
    ) -> None:
        await species_service.create_species(
            nursery_id=nursery_id, category_id=category_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS
        )
        with pytest.raises(ConflictError):
            await species_service.create_species(
                nursery_id=nursery_id, category_id=category_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS
            )

    async def test_blank_common_name_rejected(
        self, species_service: SpeciesService, nursery_id: uuid.UUID, category_id: uuid.UUID
    ) -> None:
        with pytest.raises(ValidationError):
            await species_service.create_species(
                nursery_id=nursery_id, category_id=category_id, actor_user_id=uuid.uuid4(),
                common_name="   ", botanical_name="Ficus lyrata",
            )

    async def test_temperature_min_greater_than_max_rejected(
        self, species_service: SpeciesService, nursery_id: uuid.UUID, category_id: uuid.UUID
    ) -> None:
        with pytest.raises(ValidationError):
            await species_service.create_species(
                nursery_id=nursery_id, category_id=category_id, actor_user_id=uuid.uuid4(),
                temperature_min_celsius=25.0, temperature_max_celsius=10.0, **VALID_KWARGS,
            )

    async def test_invalid_growth_curve_rejected(
        self, species_service: SpeciesService, nursery_id: uuid.UUID, category_id: uuid.UUID
    ) -> None:
        with pytest.raises(ValidationError):
            await species_service.create_species(
                nursery_id=nursery_id, category_id=category_id, actor_user_id=uuid.uuid4(),
                growth_curve_baseline=[{"days_since_planting": -5, "expected_height_cm": 10.0}], **VALID_KWARGS,
            )

    async def test_invalid_disease_susceptibility_rejected(
        self, species_service: SpeciesService, nursery_id: uuid.UUID, category_id: uuid.UUID
    ) -> None:
        with pytest.raises(ValidationError):
            await species_service.create_species(
                nursery_id=nursery_id, category_id=category_id, actor_user_id=uuid.uuid4(),
                disease_susceptibility=["root_rot", ""], **VALID_KWARGS,
            )

    async def test_valid_full_payload_persisted(
        self, species_service: SpeciesService, nursery_id: uuid.UUID, category_id: uuid.UUID
    ) -> None:
        species = await species_service.create_species(
            nursery_id=nursery_id,
            category_id=category_id,
            actor_user_id=uuid.uuid4(),
            light_requirement="bright_indirect",
            water_baseline_ml_per_week=500,
            soil_type="well_draining",
            temperature_min_celsius=15.0,
            temperature_max_celsius=27.0,
            growth_curve_baseline=[{"days_since_planting": 30, "expected_height_cm": 20.5}],
            disease_susceptibility=["root_rot", "powdery_mildew"],
            **VALID_KWARGS,
        )
        assert species.light_requirement == "bright_indirect"
        assert species.growth_curve_baseline == [{"days_since_planting": 30, "expected_height_cm": 20.5}]
        assert species.disease_susceptibility == ["root_rot", "powdery_mildew"]


class TestGetSpecies:
    async def test_not_found_raises(self, species_service: SpeciesService) -> None:
        with pytest.raises(NotFoundError):
            await species_service.get_species(uuid.uuid4())


class TestListSpecies:
    async def test_search_filters_by_name(
        self, species_service: SpeciesService, nursery_id: uuid.UUID, category_id: uuid.UUID
    ) -> None:
        await species_service.create_species(
            nursery_id=nursery_id, category_id=category_id, actor_user_id=uuid.uuid4(),
            common_name="Fiddle Leaf Fig", botanical_name="Ficus lyrata",
        )
        await species_service.create_species(
            nursery_id=nursery_id, category_id=category_id, actor_user_id=uuid.uuid4(),
            common_name="Snake Plant", botanical_name="Dracaena trifasciata",
        )
        rows, total = await species_service.list_species(nursery_id=nursery_id, offset=0, limit=20, search="fiddle")
        assert total == 1
        assert rows[0].common_name == "Fiddle Leaf Fig"

    async def test_category_filter(
        self, species_service: SpeciesService, nursery_id: uuid.UUID, category_id: uuid.UUID
    ) -> None:
        other_category_id = uuid.uuid4()
        species_service._categories.categories[other_category_id] = PlantCategory(  # type: ignore[attr-defined]
            id=other_category_id, code="succulent", name="Succulent", description=None
        )
        await species_service.create_species(
            nursery_id=nursery_id, category_id=category_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS
        )
        await species_service.create_species(
            nursery_id=nursery_id, category_id=other_category_id, actor_user_id=uuid.uuid4(),
            common_name="Aloe", botanical_name="Aloe vera",
        )
        rows, total = await species_service.list_species(
            nursery_id=nursery_id, offset=0, limit=20, category_id=category_id
        )
        assert total == 1
        assert rows[0].botanical_name == "Ficus lyrata"


class TestUpdateSpecies:
    async def test_updates_changed_fields(
        self, species_service: SpeciesService, nursery_id: uuid.UUID, category_id: uuid.UUID
    ) -> None:
        species = await species_service.create_species(
            nursery_id=nursery_id, category_id=category_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS
        )
        updated = await species_service.update_species(
            species_id=species.id, actor_user_id=uuid.uuid4(), light_requirement="full_sun"
        )
        assert updated.light_requirement == "full_sun"
        assert updated.common_name == VALID_KWARGS["common_name"]

    async def test_updates_every_field(
        self, species_service: SpeciesService, nursery_id: uuid.UUID, category_id: uuid.UUID
    ) -> None:
        other_category_id = uuid.uuid4()
        species_service._categories.categories[other_category_id] = PlantCategory(  # type: ignore[attr-defined]
            id=other_category_id, code="succulent", name="Succulent", description=None
        )
        species = await species_service.create_species(
            nursery_id=nursery_id,
            category_id=category_id,
            actor_user_id=uuid.uuid4(),
            temperature_min_celsius=10.0,
            temperature_max_celsius=20.0,
            **VALID_KWARGS,
        )
        updated = await species_service.update_species(
            species_id=species.id,
            actor_user_id=uuid.uuid4(),
            category_id=other_category_id,
            common_name="Renamed Common",
            botanical_name="Renamed botanica",
            light_requirement="low_light",
            water_baseline_ml_per_week=250,
            soil_type="cactus_mix",
            temperature_min_celsius=5.0,
            temperature_max_celsius=30.0,
            growth_curve_baseline=[{"days_since_planting": 10, "expected_height_cm": 5.0}],
            disease_susceptibility=["spider_mites"],
        )
        assert updated.category_id == other_category_id
        assert updated.common_name == "Renamed Common"
        assert updated.botanical_name == "Renamed botanica"
        assert updated.light_requirement == "low_light"
        assert updated.water_baseline_ml_per_week == 250
        assert updated.soil_type == "cactus_mix"
        assert float(updated.temperature_min_celsius) == 5.0
        assert float(updated.temperature_max_celsius) == 30.0
        assert updated.growth_curve_baseline == [{"days_since_planting": 10, "expected_height_cm": 5.0}]
        assert updated.disease_susceptibility == ["spider_mites"]

    async def test_update_only_max_temperature_still_validates_range(
        self, species_service: SpeciesService, nursery_id: uuid.UUID, category_id: uuid.UUID
    ) -> None:
        species = await species_service.create_species(
            nursery_id=nursery_id, category_id=category_id, actor_user_id=uuid.uuid4(),
            temperature_min_celsius=10.0, temperature_max_celsius=20.0, **VALID_KWARGS,
        )
        with pytest.raises(ValidationError):
            await species_service.update_species(
                species_id=species.id, actor_user_id=uuid.uuid4(), temperature_max_celsius=1.0
            )

    async def test_blank_botanical_name_on_update_rejected(
        self, species_service: SpeciesService, nursery_id: uuid.UUID, category_id: uuid.UUID
    ) -> None:
        species = await species_service.create_species(
            nursery_id=nursery_id, category_id=category_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS
        )
        with pytest.raises(ValidationError):
            await species_service.update_species(species_id=species.id, actor_user_id=uuid.uuid4(), botanical_name="   ")

    async def test_rename_botanical_name_to_existing_conflicts(
        self, species_service: SpeciesService, nursery_id: uuid.UUID, category_id: uuid.UUID
    ) -> None:
        await species_service.create_species(
            nursery_id=nursery_id, category_id=category_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS
        )
        other = await species_service.create_species(
            nursery_id=nursery_id, category_id=category_id, actor_user_id=uuid.uuid4(),
            common_name="Snake Plant", botanical_name="Dracaena trifasciata",
        )
        with pytest.raises(ConflictError):
            await species_service.update_species(
                species_id=other.id, actor_user_id=uuid.uuid4(), botanical_name=VALID_KWARGS["botanical_name"]
            )

    async def test_noop_update_skips_audit(
        self, species_service: SpeciesService, nursery_id: uuid.UUID, category_id: uuid.UUID
    ) -> None:
        species = await species_service.create_species(
            nursery_id=nursery_id, category_id=category_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS
        )
        before = len(species_service._audit.rows)  # type: ignore[attr-defined]
        await species_service.update_species(species_id=species.id, actor_user_id=uuid.uuid4())
        assert len(species_service._audit.rows) == before  # type: ignore[attr-defined]

    async def test_unknown_category_on_update_rejected(
        self, species_service: SpeciesService, nursery_id: uuid.UUID, category_id: uuid.UUID
    ) -> None:
        species = await species_service.create_species(
            nursery_id=nursery_id, category_id=category_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS
        )
        with pytest.raises(ValidationError):
            await species_service.update_species(species_id=species.id, actor_user_id=uuid.uuid4(), category_id=uuid.uuid4())

    async def test_temperature_range_revalidated_on_partial_update(
        self, species_service: SpeciesService, nursery_id: uuid.UUID, category_id: uuid.UUID
    ) -> None:
        species = await species_service.create_species(
            nursery_id=nursery_id, category_id=category_id, actor_user_id=uuid.uuid4(),
            temperature_min_celsius=10.0, temperature_max_celsius=20.0, **VALID_KWARGS,
        )
        with pytest.raises(ValidationError):
            await species_service.update_species(
                species_id=species.id, actor_user_id=uuid.uuid4(), temperature_max_celsius=5.0
            )


class TestDeleteSpecies:
    async def test_deletes_unreferenced_species(
        self, species_service: SpeciesService, nursery_id: uuid.UUID, category_id: uuid.UUID
    ) -> None:
        species = await species_service.create_species(
            nursery_id=nursery_id, category_id=category_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS
        )
        await species_service.delete_species(species_id=species.id, actor_user_id=uuid.uuid4())
        with pytest.raises(NotFoundError):
            await species_service.get_species(species.id)

    async def test_blocked_when_referenced_by_a_plant(
        self, species_service: SpeciesService, nursery_id: uuid.UUID, category_id: uuid.UUID
    ) -> None:
        species = await species_service.create_species(
            nursery_id=nursery_id, category_id=category_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS
        )
        species_service._species.plant_species_ids.append(species.id)  # type: ignore[attr-defined]
        with pytest.raises(ConflictError):
            await species_service.delete_species(species_id=species.id, actor_user_id=uuid.uuid4())
        # still there -- the block actually prevented the delete
        assert await species_service.get_species(species.id) is not None
