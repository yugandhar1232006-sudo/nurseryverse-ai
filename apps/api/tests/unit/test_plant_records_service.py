"""Unit tests for Module 6's five append-only record services: Growth, Health, Watering, Fertilizer, Environmental."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.models.catalog import Species
from app.models.organization import Branch

pytestmark = pytest.mark.unit


def _branch(*, nursery_id: uuid.UUID) -> Branch:
    now = datetime.now(timezone.utc)
    return Branch(
        id=uuid.uuid4(), nursery_id=nursery_id, name="Main", address_line1="123 St", city="Springfield",
        country="US", timezone="UTC", created_at=now, updated_at=now,
    )


def _species(*, nursery_id: uuid.UUID) -> Species:
    now = datetime.now(timezone.utc)
    return Species(
        id=uuid.uuid4(), nursery_id=nursery_id, category_id=uuid.uuid4(), common_name="Fig", botanical_name="Ficus lyrata",
        created_at=now, updated_at=now,
    )


@pytest.fixture
async def plant(harness):
    nursery_id = uuid.uuid4()
    branch = _branch(nursery_id=nursery_id)
    species = _species(nursery_id=nursery_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    return await harness.plant_service.register_plant(
        nursery_id=nursery_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )


# ==============================================================================
# Growth
# ==============================================================================


async def test_record_growth_success(harness, plant):
    entry = await harness.growth_service.record_growth(
        plant_id=plant.id, actor_user_id=uuid.uuid4(), height_cm=12.5, leaf_count=4, flower_count=0,
        fruit_count=0, growth_stage="seedling", photo_urls=["https://cdn/1.jpg", "https://cdn/2.jpg"],
    )
    assert entry.height_cm == 12.5
    assert entry.photo_url == "https://cdn/1.jpg"
    assert entry.photo_urls == ["https://cdn/1.jpg", "https://cdn/2.jpg"]
    assert harness.domain_events.events[-1].event_type == "plant.growth_recorded"


async def test_record_growth_negative_height_rejected(harness, plant):
    with pytest.raises(ValidationError):
        await harness.growth_service.record_growth(plant_id=plant.id, actor_user_id=uuid.uuid4(), height_cm=-1)


async def test_record_growth_unknown_plant_rejected(harness):
    with pytest.raises(NotFoundError):
        await harness.growth_service.record_growth(plant_id=uuid.uuid4(), actor_user_id=uuid.uuid4(), height_cm=5)


async def test_list_growth_paginates(harness, plant):
    for i in range(3):
        await harness.growth_service.record_growth(plant_id=plant.id, actor_user_id=uuid.uuid4(), height_cm=float(i))
    rows, total = await harness.growth_service.list_growth(plant.id, offset=0, limit=2)
    assert total == 3
    assert len(rows) == 2


# ==============================================================================
# Health
# ==============================================================================


async def test_record_health_success(harness, plant):
    entry = await harness.health_service.record_health(
        plant_id=plant.id, status_label="healthy", actor_user_id=uuid.uuid4(), health_score=92.5, is_ai_observation=True,
    )
    assert entry.status_label == "healthy"
    assert entry.health_score == 92.5
    assert entry.is_ai_observation is True
    assert harness.domain_events.events[-1].event_type == "plant.health_recorded"


async def test_record_health_blank_status_label_rejected(harness, plant):
    with pytest.raises(ValidationError):
        await harness.health_service.record_health(plant_id=plant.id, status_label="  ", actor_user_id=uuid.uuid4())


async def test_record_health_score_out_of_range_rejected(harness, plant):
    with pytest.raises(ValidationError):
        await harness.health_service.record_health(plant_id=plant.id, status_label="healthy", actor_user_id=uuid.uuid4(), health_score=150)


# ==============================================================================
# Watering
# ==============================================================================


async def test_record_watering_success(harness, plant):
    entry = await harness.watering_service.record_watering(plant_id=plant.id, actor_user_id=uuid.uuid4(), volume_ml=250, method="drip")
    assert entry.volume_ml == 250
    assert entry.method == "drip"
    assert entry.branch_id == plant.branch_id
    assert harness.domain_events.events[-1].event_type == "plant.watering_recorded"


async def test_record_watering_negative_volume_rejected(harness, plant):
    with pytest.raises(ValidationError):
        await harness.watering_service.record_watering(plant_id=plant.id, actor_user_id=uuid.uuid4(), volume_ml=-10)


# ==============================================================================
# Fertilizer
# ==============================================================================


async def test_record_fertilizer_success(harness, plant):
    next_app = datetime.now(timezone.utc)
    entry = await harness.fertilizer_service.record_fertilizer(
        plant_id=plant.id, product_name="GrowFast 10-10-10", actor_user_id=uuid.uuid4(), quantity_ml=50,
        method="soil_drench", schedule="weekly", next_application_date=next_app,
    )
    assert entry.product_name == "GrowFast 10-10-10"
    assert entry.schedule == "weekly"
    assert entry.next_application_date == next_app
    assert harness.domain_events.events[-1].event_type == "plant.fertilizer_recorded"


async def test_record_fertilizer_blank_product_name_rejected(harness, plant):
    with pytest.raises(ValidationError):
        await harness.fertilizer_service.record_fertilizer(plant_id=plant.id, product_name="  ", actor_user_id=uuid.uuid4())


# ==============================================================================
# Environmental
# ==============================================================================


async def test_record_environmental_success(harness, plant):
    entry = await harness.environmental_service.record_reading(
        plant_id=plant.id, actor_user_id=uuid.uuid4(), temperature_celsius=22.5, humidity_percent=55,
        soil_moisture_percent=40, ph_level=6.5, weather_snapshot={"condition": "sunny"},
    )
    assert entry.temperature_celsius == 22.5
    assert entry.ph_level == 6.5
    assert entry.weather_snapshot == {"condition": "sunny"}
    assert harness.domain_events.events[-1].event_type == "plant.environmental_recorded"


async def test_record_environmental_humidity_out_of_range_rejected(harness, plant):
    with pytest.raises(ValidationError):
        await harness.environmental_service.record_reading(plant_id=plant.id, actor_user_id=uuid.uuid4(), humidity_percent=150)


async def test_record_environmental_ph_out_of_range_rejected(harness, plant):
    with pytest.raises(ValidationError):
        await harness.environmental_service.record_reading(plant_id=plant.id, actor_user_id=uuid.uuid4(), ph_level=15)
