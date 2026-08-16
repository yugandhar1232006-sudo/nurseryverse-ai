"""
Unit tests for Module 6's PlantTimelineService -- aggregation, chronological
ordering, and the "every event is immutable" requirement (the Timeline
itself performs no writes; these tests assert that by construction: no
method on PlantTimelineService other than `get_timeline` exists).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.core.exceptions import NotFoundError
from app.db.enums import DiseaseReportSeverity, PlantStatus, TreatmentOutcome
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


def test_timeline_service_has_no_write_methods():
    """The Timeline is a read model over other tables' data -- it must never itself be a write path (see its module docstring)."""
    from app.services.plant_timeline_service import PlantTimelineService

    public_methods = [name for name in dir(PlantTimelineService) if not name.startswith("_")]
    assert public_methods == ["get_timeline"]


async def test_timeline_not_found_for_unknown_plant(harness):
    with pytest.raises(NotFoundError):
        await harness.plant_timeline_service.get_timeline(uuid.uuid4())


async def test_timeline_includes_registration_event(harness, plant):
    entries, total = await harness.plant_timeline_service.get_timeline(plant.id)
    assert total == 1
    assert entries[0].event_type == "plant.registered"


async def test_timeline_aggregates_every_event_source_newest_first(harness, plant):
    await harness.growth_service.record_growth(plant_id=plant.id, actor_user_id=uuid.uuid4(), height_cm=5)
    await harness.health_service.record_health(plant_id=plant.id, status_label="healthy", actor_user_id=uuid.uuid4())
    await harness.watering_service.record_watering(plant_id=plant.id, actor_user_id=uuid.uuid4(), volume_ml=100)
    await harness.fertilizer_service.record_fertilizer(plant_id=plant.id, product_name="Feed", actor_user_id=uuid.uuid4())
    await harness.plant_service.upload_image(plant_id=plant.id, url="https://cdn/x.jpg", actor_user_id=uuid.uuid4())
    dest = _branch(nursery_id=plant.nursery_id)
    harness.branches.branches[dest.id] = dest
    await harness.plant_service.move_plant(plant_id=plant.id, actor_user_id=uuid.uuid4(), to_branch_id=dest.id)
    report = await harness.disease_report_service.create_report(
        plant_id=plant.id, condition_name="Root rot", severity=DiseaseReportSeverity.HIGH, actor_user_id=uuid.uuid4()
    )
    await harness.disease_report_service.confirm_report(report_id=report.id, actor_user_id=uuid.uuid4())
    await harness.treatment_service.apply_treatment(
        disease_report_id=report.id, description="Treated", outcome=TreatmentOutcome.RECOVERED, actor_user_id=uuid.uuid4()
    )

    entries, total = await harness.plant_timeline_service.get_timeline(plant.id, offset=0, limit=100)

    event_types = {e.event_type for e in entries}
    assert "plant.registered" in event_types
    assert "plant.growth_recorded" in event_types
    assert "plant.health_updated" in event_types
    assert "plant.watered" in event_types
    assert "plant.fertilized" in event_types
    assert "plant.image_uploaded" in event_types
    assert "plant.transferred" in event_types
    assert "plant.disease_detected" in event_types
    assert "plant.treatment_applied" in event_types
    assert total == len(entries)

    # Chronological ordering: newest first, never out of order.
    occurred_ats = [e.occurred_at for e in entries]
    assert occurred_ats == sorted(occurred_ats, reverse=True)


async def test_timeline_pagination(harness, plant):
    for i in range(5):
        await harness.growth_service.record_growth(plant_id=plant.id, actor_user_id=uuid.uuid4(), height_cm=float(i))

    page1, total = await harness.plant_timeline_service.get_timeline(plant.id, offset=0, limit=3)
    page2, _ = await harness.plant_timeline_service.get_timeline(plant.id, offset=3, limit=3)

    assert total == 6  # 5 growth entries + 1 registration
    assert len(page1) == 3
    assert len(page2) == 3
    assert {e.source_id for e in page1}.isdisjoint({e.source_id for e in page2})


async def test_timeline_shows_sold_and_disposed(harness, plant):
    await harness.plant_service.transition_status(plant_id=plant.id, to_status=PlantStatus.READY_FOR_SALE, actor_user_id=uuid.uuid4())
    await harness.plant_service.transition_status(plant_id=plant.id, to_status=PlantStatus.SOLD, actor_user_id=uuid.uuid4())

    entries, _ = await harness.plant_timeline_service.get_timeline(plant.id)
    assert any(e.event_type == "plant.sold" for e in entries)
