"""
Unit tests for Module 7's `DigitalTwinService` -- the event-driven
projector. Exercises the service directly (not through HTTP), the same
split every prior module's unit test files use.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.db.enums import DiseaseReportSeverity, PlantStatus, TreatmentOutcome
from app.models.catalog import Species
from app.models.organization import Branch

pytestmark = pytest.mark.unit


def _branch(*, nursery_id: uuid.UUID, name: str = "Main") -> Branch:
    now = datetime.now(timezone.utc)
    return Branch(
        id=uuid.uuid4(), nursery_id=nursery_id, name=name, address_line1="123 St", city="Springfield",
        country="US", timezone="UTC", created_at=now, updated_at=now,
    )


def _species(*, nursery_id: uuid.UUID) -> Species:
    now = datetime.now(timezone.utc)
    return Species(
        id=uuid.uuid4(), nursery_id=nursery_id, category_id=uuid.uuid4(), common_name="Fig", botanical_name="Ficus lyrata",
        created_at=now, updated_at=now,
    )


async def _register_plant(harness, *, org_id=None, branch=None, species=None):
    org_id = org_id or uuid.uuid4()
    branch = branch or _branch(nursery_id=org_id)
    species = species or _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    return org_id, branch, species, plant


async def test_registration_creates_twin_at_version_one(harness):
    _, branch, species, plant = await _register_plant(harness)

    twin = await harness.digital_twin_service.get_current_twin(plant.id)

    assert twin.current_version == 1
    assert twin.lifecycle_state == PlantStatus.IN_PRODUCTION.value
    assert twin.operational_status == "active"
    assert twin.plant_id == plant.id
    assert twin.snapshot["identity"]["qr_code_token"] == plant.qr_code_token
    assert twin.snapshot["counts"] == {
        "growth": 0, "health": 0, "watering": 0, "fertilizer": 0, "environmental": 0,
        "disease_reports": 0, "treatments": 0, "movements": 0, "images": 0, "inventory_movements": 0,
        # Module 9 additions -- see digital_twin_service.py's PROJECTED_EVENT_TYPES comment.
        "plant_sold": 0, "plant_returned": 0, "passports_generated": 0, "qr_generated": 0,
        # Module 10 addition (AI Platform) -- see digital_twin_service.py's PROJECTED_EVENT_TYPES comment.
        "ai_predictions": 0,
    }
    assert twin.snapshot["ownership"] == {"owner_type": "nursery", "customer_id": None, "since": None}
    versions, total = await harness.digital_twin_versions.list_for_plant(plant.id, offset=0, limit=10)
    assert total == 1
    assert versions[0].event_type == "plant.registered"


async def test_get_current_twin_not_found_for_unknown_plant(harness):
    with pytest.raises(NotFoundError):
        await harness.digital_twin_service.get_current_twin(uuid.uuid4())


async def test_project_non_registration_event_before_registration_raises(harness):
    from app.domain_events.events import GrowthRecorded

    org_id, branch, species, plant = await _register_plant(harness)
    # Simulate a genuinely-unregistered plant id by constructing a bare event row directly.
    fake_event = await harness.domain_events.add(
        _make_row(GrowthRecorded(aggregate_id=uuid.uuid4(), nursery_id=org_id, actor_user_id=None, growth_entry_id=uuid.uuid4(), height_cm=1.0))
    )
    with pytest.raises(NotFoundError):
        await harness.digital_twin_service.project(fake_event)


def _make_row(event):
    from app.models.events import DomainEvent as DomainEventRow

    from app.domain_events.publisher import _json_safe

    return DomainEventRow(
        event_type=event.event_type, aggregate_type=event.aggregate_type, aggregate_id=event.aggregate_id,
        nursery_id=event.nursery_id, actor_user_id=event.actor_user_id, payload=_json_safe(event.payload()),
        occurred_at=datetime.now(timezone.utc),
    )


async def test_growth_recorded_updates_snapshot_growth_stage_and_latest(harness):
    _, branch, species, plant = await _register_plant(harness)

    await harness.growth_service.record_growth(
        plant_id=plant.id, actor_user_id=uuid.uuid4(), height_cm=12.5, growth_stage="seedling"
    )

    twin = await harness.digital_twin_service.get_current_twin(plant.id)
    assert twin.current_version == 2
    assert twin.growth_stage == "seedling"
    assert twin.snapshot["counts"]["growth"] == 1
    assert twin.snapshot["latest"]["growth"]["height_cm"] == 12.5


async def test_health_recorded_updates_latest_health(harness):
    _, branch, species, plant = await _register_plant(harness)

    await harness.health_service.record_health(plant_id=plant.id, actor_user_id=uuid.uuid4(), status_label="healthy", health_score=91)

    twin = await harness.digital_twin_service.get_current_twin(plant.id)
    assert twin.snapshot["counts"]["health"] == 1
    assert twin.snapshot["latest"]["health"]["status_label"] == "healthy"
    assert twin.snapshot["latest"]["health"]["health_score"] == 91.0


async def test_watering_recorded_updates_latest_watering(harness):
    _, branch, species, plant = await _register_plant(harness)

    await harness.watering_service.record_watering(plant_id=plant.id, actor_user_id=uuid.uuid4(), volume_ml=150, method="drip")

    twin = await harness.digital_twin_service.get_current_twin(plant.id)
    assert twin.snapshot["counts"]["watering"] == 1
    assert twin.snapshot["latest"]["watering"]["volume_ml"] == 150.0
    assert twin.snapshot["latest"]["watering"]["method"] == "drip"


async def test_fertilizer_recorded_updates_latest_fertilizer(harness):
    _, branch, species, plant = await _register_plant(harness)

    await harness.fertilizer_service.record_fertilizer(plant_id=plant.id, actor_user_id=uuid.uuid4(), product_name="GrowFast", schedule="weekly")

    twin = await harness.digital_twin_service.get_current_twin(plant.id)
    assert twin.snapshot["counts"]["fertilizer"] == 1
    assert twin.snapshot["latest"]["fertilizer"]["product_name"] == "GrowFast"


async def test_environmental_recorded_updates_latest_environmental(harness):
    _, branch, species, plant = await _register_plant(harness)

    await harness.environmental_service.record_reading(
        plant_id=plant.id, actor_user_id=uuid.uuid4(), temperature_celsius=21.0, humidity_percent=55
    )

    twin = await harness.digital_twin_service.get_current_twin(plant.id)
    assert twin.snapshot["counts"]["environmental"] == 1
    assert twin.snapshot["latest"]["environmental"]["temperature_celsius"] == 21.0


async def test_plant_moved_updates_location_and_movement_count(harness):
    org_id, branch, species, plant = await _register_plant(harness)
    downtown = _branch(nursery_id=org_id, name="Downtown")
    harness.branches.branches[downtown.id] = downtown

    await harness.plant_service.move_plant(plant_id=plant.id, actor_user_id=uuid.uuid4(), to_branch_id=downtown.id, to_zone=None, note=None)

    twin = await harness.digital_twin_service.get_current_twin(plant.id)
    assert twin.branch_id == downtown.id
    assert twin.snapshot["counts"]["movements"] == 1
    assert twin.snapshot["current_location"]["branch_id"] == str(downtown.id)


async def test_status_changed_to_sold_sets_sold_fields(harness):
    _, branch, species, plant = await _register_plant(harness)
    await harness.plant_service.transition_status(plant_id=plant.id, to_status=PlantStatus.READY_FOR_SALE, actor_user_id=uuid.uuid4())

    await harness.plant_service.transition_status(plant_id=plant.id, to_status=PlantStatus.SOLD, actor_user_id=uuid.uuid4())

    twin = await harness.digital_twin_service.get_current_twin(plant.id)
    assert twin.lifecycle_state == PlantStatus.SOLD.value
    assert twin.operational_status == "sold"
    assert twin.snapshot["sold_at"] is not None


async def test_status_changed_to_deceased_sets_deceased_fields(harness):
    _, branch, species, plant = await _register_plant(harness)

    await harness.plant_service.transition_status(
        plant_id=plant.id, to_status=PlantStatus.DECEASED, actor_user_id=uuid.uuid4(), reason="Frost damage"
    )

    twin = await harness.digital_twin_service.get_current_twin(plant.id)
    assert twin.lifecycle_state == PlantStatus.DECEASED.value
    assert twin.operational_status == "deceased"
    assert twin.snapshot["deceased_reason"] == "Frost damage"


async def test_plant_archived_sets_archived_fields_and_operational_status(harness):
    _, branch, species, plant = await _register_plant(harness)
    await harness.plant_service.transition_status(plant_id=plant.id, to_status=PlantStatus.DECEASED, actor_user_id=uuid.uuid4(), reason="Lost")

    await harness.plant_service.archive_plant(plant_id=plant.id, actor_user_id=uuid.uuid4(), reason="Season complete")

    twin = await harness.digital_twin_service.get_current_twin(plant.id)
    assert twin.operational_status == "archived"
    assert twin.snapshot["archived_at"] is not None
    assert twin.snapshot["archived_reason"] == "Season complete"


async def test_disease_detected_then_confirmed_updates_latest_disease_status(harness):
    _, branch, species, plant = await _register_plant(harness)

    report = await harness.disease_report_service.create_report(
        plant_id=plant.id, condition_name="Root rot", severity=DiseaseReportSeverity.HIGH, actor_user_id=uuid.uuid4()
    )
    twin_after_detect = await harness.digital_twin_service.get_current_twin(plant.id)
    assert twin_after_detect.snapshot["counts"]["disease_reports"] == 1
    assert twin_after_detect.snapshot["latest"]["disease"]["status"] == "draft"

    await harness.disease_report_service.confirm_report(report_id=report.id, actor_user_id=uuid.uuid4())

    twin_after_confirm = await harness.digital_twin_service.get_current_twin(plant.id)
    assert twin_after_confirm.snapshot["latest"]["disease"]["status"] == "confirmed"
    assert twin_after_confirm.lifecycle_state == PlantStatus.UNDER_TREATMENT.value


async def test_treatment_applied_updates_latest_treatment_and_count(harness):
    _, branch, species, plant = await _register_plant(harness)
    report = await harness.disease_report_service.create_report(
        plant_id=plant.id, condition_name="Root rot", severity=DiseaseReportSeverity.HIGH, actor_user_id=uuid.uuid4()
    )
    await harness.disease_report_service.confirm_report(report_id=report.id, actor_user_id=uuid.uuid4())

    await harness.treatment_service.apply_treatment(
        disease_report_id=report.id, actor_user_id=uuid.uuid4(), description="Fungicide", outcome=TreatmentOutcome.RECOVERED
    )

    twin = await harness.digital_twin_service.get_current_twin(plant.id)
    assert twin.snapshot["counts"]["treatments"] == 1
    assert twin.snapshot["latest"]["treatment"]["outcome"] == TreatmentOutcome.RECOVERED.value
    assert twin.lifecycle_state == PlantStatus.IN_PRODUCTION.value


# ---------------------------------------------------------------------------
# Idempotency / ordering
# ---------------------------------------------------------------------------


async def test_duplicate_dispatch_of_the_same_event_is_idempotent(harness):
    _, branch, species, plant = await _register_plant(harness)
    twin_before = await harness.digital_twin_service.get_current_twin(plant.id)
    assert twin_before.current_version == 1

    registered_event = harness.domain_events.events[0]
    await harness.event_dispatcher.dispatch(registered_event)  # dispatch the exact same row a second time

    twin_after = await harness.digital_twin_service.get_current_twin(plant.id)
    assert twin_after.current_version == 1
    versions, total = await harness.digital_twin_versions.list_for_plant(plant.id, offset=0, limit=10)
    assert total == 1  # no duplicate version was written


async def test_project_ignores_an_already_applied_event(harness):
    """Ordering guard: calling `project()` again for an event whose sequence is <= the twin's last applied sequence is a no-op."""
    _, branch, species, plant = await _register_plant(harness)
    registered_event = harness.domain_events.events[0]

    result = await harness.digital_twin_service.project(registered_event)

    assert result == 1  # unchanged, not re-projected


async def test_dispatch_log_records_every_successful_projection(harness):
    _, branch, species, plant = await _register_plant(harness)
    await harness.growth_service.record_growth(plant_id=plant.id, actor_user_id=uuid.uuid4(), height_cm=5.0)

    for event in harness.domain_events.events:
        log_row = await harness.event_dispatch_log.get(event.id, "digital_twin_projector")
        assert log_row is not None
        assert log_row.status.value == "succeeded"


# ---------------------------------------------------------------------------
# Query APIs
# ---------------------------------------------------------------------------


async def test_get_version_returns_specific_version(harness):
    _, branch, species, plant = await _register_plant(harness)
    await harness.growth_service.record_growth(plant_id=plant.id, actor_user_id=uuid.uuid4(), height_cm=5.0)

    v1 = await harness.digital_twin_service.get_version(plant.id, 1)
    v2 = await harness.digital_twin_service.get_version(plant.id, 2)

    assert v1.event_type == "plant.registered"
    assert v2.event_type == "plant.growth_recorded"


async def test_get_version_not_found_raises(harness):
    _, branch, species, plant = await _register_plant(harness)
    with pytest.raises(NotFoundError):
        await harness.digital_twin_service.get_version(plant.id, 99)


async def test_compare_versions_reports_changed_keys(harness):
    _, branch, species, plant = await _register_plant(harness)
    await harness.growth_service.record_growth(plant_id=plant.id, actor_user_id=uuid.uuid4(), height_cm=5.0, growth_stage="seedling")

    comparison = await harness.digital_twin_service.compare_versions(plant.id, 1, 2)

    assert comparison.version_a == 1
    assert comparison.version_b == 2
    assert "counts" in comparison.changed_keys
    assert "growth_stage" in comparison.changed_keys


async def test_get_snapshot_by_date_returns_the_version_as_of_that_time(harness):
    _, branch, species, plant = await _register_plant(harness)
    v1 = await harness.digital_twin_service.get_version(plant.id, 1)
    await harness.growth_service.record_growth(plant_id=plant.id, actor_user_id=uuid.uuid4(), height_cm=5.0)

    snapshot = await harness.digital_twin_service.get_snapshot_by_date(plant.id, as_of=v1.occurred_at)

    assert snapshot.version == 1


async def test_get_snapshot_by_date_raises_when_before_any_version(harness):
    _, branch, species, plant = await _register_plant(harness)
    too_early = datetime(2000, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(NotFoundError):
        await harness.digital_twin_service.get_snapshot_by_date(plant.id, as_of=too_early)


async def test_get_event_history_returns_raw_events_newest_first(harness):
    _, branch, species, plant = await _register_plant(harness)
    await harness.growth_service.record_growth(plant_id=plant.id, actor_user_id=uuid.uuid4(), height_cm=5.0)

    events, total = await harness.digital_twin_service.get_event_history(plant.id, offset=0, limit=10)

    assert total == 2
    assert events[0].event_type == "plant.growth_recorded"
    assert events[1].event_type == "plant.registered"
    assert "height_cm" in events[0].payload


async def test_get_timeline_pagination(harness):
    _, branch, species, plant = await _register_plant(harness)
    for i in range(3):
        await harness.watering_service.record_watering(plant_id=plant.id, actor_user_id=uuid.uuid4(), volume_ml=100 + i)

    page1, total = await harness.digital_twin_service.get_timeline(plant.id, offset=0, limit=2)
    assert total == 4  # registered + 3 waterings
    assert len(page1) == 2


async def test_list_twins_for_nursery_filters_and_paginates(harness):
    org_id, branch, species, plant_a = await _register_plant(harness)
    _, _, _, plant_b = await _register_plant(harness, org_id=org_id, branch=branch, species=species)
    await harness.plant_service.transition_status(plant_id=plant_a.id, to_status=PlantStatus.READY_FOR_SALE, actor_user_id=uuid.uuid4())

    all_twins, total = await harness.digital_twin_service.list_twins_for_nursery(org_id, offset=0, limit=10)
    assert total == 2

    ready_only, ready_total = await harness.digital_twin_service.list_twins_for_nursery(
        org_id, offset=0, limit=10, lifecycle_state=PlantStatus.READY_FOR_SALE.value
    )
    assert ready_total == 1
    assert ready_only[0].plant_id == plant_a.id


# ---------------------------------------------------------------------------
# Replay / consistency
# ---------------------------------------------------------------------------


async def test_compute_projection_from_events_matches_live_projection(harness):
    org_id, branch, species, plant = await _register_plant(harness)
    downtown = _branch(nursery_id=org_id, name="Downtown")
    harness.branches.branches[downtown.id] = downtown
    await harness.growth_service.record_growth(plant_id=plant.id, actor_user_id=uuid.uuid4(), height_cm=10.0, growth_stage="growing")
    await harness.watering_service.record_watering(plant_id=plant.id, actor_user_id=uuid.uuid4(), volume_ml=200)
    await harness.plant_service.move_plant(plant_id=plant.id, actor_user_id=uuid.uuid4(), to_branch_id=downtown.id, to_zone=None, note=None)
    await harness.plant_service.transition_status(plant_id=plant.id, to_status=PlantStatus.READY_FOR_SALE, actor_user_id=uuid.uuid4())

    live_twin = await harness.digital_twin_service.get_current_twin(plant.id)
    replayed_snapshot = await harness.digital_twin_service.compute_projection_from_events(plant.id)

    assert replayed_snapshot == live_twin.snapshot


async def test_verify_consistency_reports_consistent_for_a_healthy_twin(harness):
    _, branch, species, plant = await _register_plant(harness)
    await harness.growth_service.record_growth(plant_id=plant.id, actor_user_id=uuid.uuid4(), height_cm=5.0)

    consistent, version, differing = await harness.digital_twin_service.verify_consistency(plant.id)

    assert consistent is True
    assert version == 2
    assert differing == []


async def test_rebuild_from_scratch_rejected_when_twin_already_exists(harness):
    _, branch, species, plant = await _register_plant(harness)

    with pytest.raises(ConflictError):
        await harness.digital_twin_service.rebuild_from_scratch(plant.id)


async def test_rebuild_from_scratch_recovers_a_lost_projection(harness):
    """Simulates disaster recovery: the projection tables are lost but `domain_events` survives."""
    _, branch, species, plant = await _register_plant(harness)
    await harness.growth_service.record_growth(plant_id=plant.id, actor_user_id=uuid.uuid4(), height_cm=8.0, growth_stage="growing")
    original_twin = await harness.digital_twin_service.get_current_twin(plant.id)

    # Simulate loss of the projection (never done by any real code path -- domain_events itself is untouched).
    harness.digital_twins.twins.clear()
    harness.digital_twins._by_plant.clear()
    harness.digital_twin_versions.versions.clear()

    rebuilt_twin = await harness.digital_twin_service.rebuild_from_scratch(plant.id)

    assert rebuilt_twin.current_version == original_twin.current_version
    assert rebuilt_twin.snapshot == original_twin.snapshot


async def test_rebuild_from_scratch_raises_when_no_events_exist(harness):
    with pytest.raises(NotFoundError):
        await harness.digital_twin_service.rebuild_from_scratch(uuid.uuid4())


# ---------------------------------------------------------------------------
# Structural immutability guarantee
# ---------------------------------------------------------------------------


def test_digital_twin_version_repository_fake_has_no_mutation_methods(harness):
    """
    "No historical record may be overwritten": the version repository's
    own surface (Protocol in interfaces.py, mirrored here by the fake)
    literally has no `update`/`delete` method to call -- this is checked
    structurally, the same technique test_plant_timeline_service.py
    already used for the Module 6 Timeline's own immutability claim.
    """
    assert not hasattr(harness.digital_twin_versions, "update")
    assert not hasattr(harness.digital_twin_versions, "delete")


# ---------------------------------------------------------------------------
# Coverage-closing: remaining branches
# ---------------------------------------------------------------------------


async def test_maybe_uuid_handles_none_and_native_uuid():
    from app.services.digital_twin_service import _maybe_uuid

    assert _maybe_uuid(None) is None
    native = uuid.uuid4()
    assert _maybe_uuid(native) is native  # already a uuid.UUID -- returned as-is, not re-parsed


async def test_project_ignores_a_stale_non_registration_event(harness):
    """Ordering guard for a real (non-registration) event type -- distinct from the plant.registered idempotency branch."""
    _, branch, species, plant = await _register_plant(harness)
    await harness.growth_service.record_growth(plant_id=plant.id, actor_user_id=uuid.uuid4(), height_cm=5.0)
    growth_event = harness.domain_events.events[-1]
    assert growth_event.event_type == "plant.growth_recorded"

    result = await harness.digital_twin_service.project(growth_event)  # already applied once by the dispatcher

    assert result == 2  # unchanged -- no new version written
    _, total = await harness.digital_twin_versions.list_for_plant(plant.id, offset=0, limit=10)
    assert total == 2


async def test_project_with_unmapped_event_type_is_a_safe_no_op(harness):
    """Defensive fallback: `project()` is only ever called by the dispatcher for `PROJECTED_EVENT_TYPES`, but a direct call with an unmapped type must not crash."""
    from app.domain_events.events import PlantUpdated

    _, branch, species, plant = await _register_plant(harness)
    bogus_event = _make_row(PlantUpdated(aggregate_id=plant.id, nursery_id=None, actor_user_id=None, changed_fields=()))
    bogus_event.event_type = "plant.some_future_event_type"
    bogus_event.sequence = 999

    result = await harness.digital_twin_service.project(bogus_event)

    assert result == 1  # unchanged


async def test_list_twins_for_nursery_rejects_invalid_sort_params(harness):
    org_id, branch, species, plant = await _register_plant(harness)

    twins, total = await harness.digital_twin_service.list_twins_for_nursery(
        org_id, offset=0, limit=10, sort_by="'; DROP TABLE", sort_dir="sideways"
    )

    assert total == 1  # falls back to the defaults rather than erroring


async def test_compute_projection_from_events_raises_when_no_events(harness):
    with pytest.raises(NotFoundError):
        await harness.digital_twin_service.compute_projection_from_events(uuid.uuid4())


def test_digital_twin_service_has_exactly_one_public_write_entrypoint(harness):
    """
    `project()` is the only method that can create a new version from a
    live event; `rebuild_from_scratch` is the sole, explicitly-guarded
    recovery path (refuses if a twin already exists -- see its own test
    above). No other public method on the service ever calls
    `_write_version`.
    """
    import inspect

    from app.services.digital_twin_service import DigitalTwinService

    write_methods = {"project", "rebuild_from_scratch"}
    public_methods = {
        name for name, _ in inspect.getmembers(DigitalTwinService, predicate=inspect.isfunction)
        if not name.startswith("_")
    }
    query_methods = public_methods - write_methods
    for name in query_methods:
        source = inspect.getsource(getattr(DigitalTwinService, name))
        assert "_write_version" not in source, f"{name} unexpectedly writes a version"
