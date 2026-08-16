"""Unit tests for Module 6's PlantService -- registration, QR generation, profile, movement, status state machine, archive."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.enums import BranchStatus, DiseaseReportSeverity, DiseaseReportStatus, PlantStatus, TreatmentOutcome
from app.models.catalog import PlantVariety, Species
from app.models.disease import DiseaseReport, Treatment
from app.models.organization import Branch
from app.models.purchasing import Supplier

pytestmark = pytest.mark.unit


def _branch(*, nursery_id: uuid.UUID, name: str = "Main", status: BranchStatus = BranchStatus.ACTIVE) -> Branch:
    now = datetime.now(timezone.utc)
    return Branch(
        id=uuid.uuid4(), nursery_id=nursery_id, name=name, address_line1="123 Greenhouse Rd", city="Springfield",
        country="US", timezone="UTC", status=status, created_at=now, updated_at=now,
    )


def _species(*, nursery_id: uuid.UUID, common_name: str = "Fiddle Leaf Fig", botanical_name: str = "Ficus lyrata") -> Species:
    now = datetime.now(timezone.utc)
    return Species(
        id=uuid.uuid4(), nursery_id=nursery_id, category_id=uuid.uuid4(), common_name=common_name,
        botanical_name=botanical_name, created_at=now, updated_at=now,
    )


def _variety(*, nursery_id: uuid.UUID, species_id: uuid.UUID, name: str = "Bambino") -> PlantVariety:
    now = datetime.now(timezone.utc)
    return PlantVariety(id=uuid.uuid4(), nursery_id=nursery_id, species_id=species_id, name=name, created_at=now, updated_at=now)


def _supplier(*, nursery_id: uuid.UUID, branch_id: uuid.UUID, name: str = "Acme Growers") -> Supplier:
    now = datetime.now(timezone.utc)
    return Supplier(id=uuid.uuid4(), nursery_id=nursery_id, branch_id=branch_id, name=name, created_at=now, updated_at=now)


@pytest.fixture
def scene(harness):
    """A ready-to-register scene: one org, one branch, one species."""
    nursery_id = uuid.uuid4()
    branch = _branch(nursery_id=nursery_id)
    species = _species(nursery_id=nursery_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    return nursery_id, branch, species


async def _register(harness, nursery_id, branch_id, species_id, actor_user_id=None, **kwargs):
    return await harness.plant_service.register_plant(
        nursery_id=nursery_id, branch_id=branch_id, species_id=species_id,
        actor_user_id=actor_user_id or uuid.uuid4(), **kwargs,
    )


# ==============================================================================
# Registration
# ==============================================================================


async def test_register_plant_success(harness, scene):
    nursery_id, branch, species = scene
    actor = uuid.uuid4()

    plant = await _register(harness, nursery_id, branch.id, species.id, actor_user_id=actor, common_label="Fig #1")

    assert plant.status == PlantStatus.IN_PRODUCTION
    assert plant.qr_code_token.startswith("NVA-")
    assert plant.registered_by_user_id == actor
    assert plant.nursery_id == nursery_id
    assert plant.branch_id == branch.id
    assert plant.species_id == species.id
    assert plant.common_label == "Fig #1"
    assert harness.domain_events.events[-1].event_type == "plant.registered"
    assert harness.audit_logs.rows[-1].action == "plant.registered"


async def test_register_plant_unknown_branch_rejected(harness, scene):
    nursery_id, _branch, species = scene
    with pytest.raises(ValidationError):
        await _register(harness, nursery_id, uuid.uuid4(), species.id)


async def test_register_plant_foreign_branch_rejected(harness, scene):
    nursery_id, _own_branch, species = scene
    foreign_branch = _branch(nursery_id=uuid.uuid4())
    harness.branches.branches[foreign_branch.id] = foreign_branch
    with pytest.raises(ValidationError):
        await _register(harness, nursery_id, foreign_branch.id, species.id)


async def test_register_plant_unknown_species_rejected(harness, scene):
    nursery_id, branch, _species = scene
    with pytest.raises(ValidationError):
        await _register(harness, nursery_id, branch.id, uuid.uuid4())


async def test_register_plant_variety_wrong_species_rejected(harness, scene):
    nursery_id, branch, species = scene
    other_species = _species(nursery_id=nursery_id, botanical_name="Aloe vera")
    harness.species.species[other_species.id] = other_species
    wrong_variety = _variety(nursery_id=nursery_id, species_id=other_species.id)
    harness.plant_varieties.varieties[wrong_variety.id] = wrong_variety

    with pytest.raises(ValidationError):
        await _register(harness, nursery_id, branch.id, species.id, variety_id=wrong_variety.id)


async def test_register_plant_with_matching_variety_succeeds(harness, scene):
    nursery_id, branch, species = scene
    variety = _variety(nursery_id=nursery_id, species_id=species.id)
    harness.plant_varieties.varieties[variety.id] = variety

    plant = await _register(harness, nursery_id, branch.id, species.id, variety_id=variety.id)
    assert plant.variety_id == variety.id


async def test_register_plant_unknown_supplier_rejected(harness, scene):
    nursery_id, branch, species = scene
    with pytest.raises(ValidationError):
        await _register(harness, nursery_id, branch.id, species.id, supplier_id=uuid.uuid4())


async def test_register_plant_with_valid_supplier_succeeds(harness, scene):
    nursery_id, branch, species = scene
    supplier = _supplier(nursery_id=nursery_id, branch_id=branch.id)
    harness.suppliers.suppliers[supplier.id] = supplier

    plant = await _register(
        harness, nursery_id, branch.id, species.id, supplier_id=supplier.id,
        purchase_price=12.5, batch_number="BATCH-42",
    )
    assert plant.supplier_id == supplier.id
    assert plant.purchase_price == 12.5
    assert plant.batch_number == "BATCH-42"


async def test_register_plant_negative_purchase_price_rejected(harness, scene):
    nursery_id, branch, species = scene
    with pytest.raises(ValidationError):
        await _register(harness, nursery_id, branch.id, species.id, purchase_price=-1)


async def test_register_plant_negative_price_rejected(harness, scene):
    nursery_id, branch, species = scene
    with pytest.raises(ValidationError):
        await _register(harness, nursery_id, branch.id, species.id, price=-5)


async def test_qr_tokens_are_unique_across_registrations(harness, scene):
    nursery_id, branch, species = scene
    tokens = set()
    for _ in range(25):
        plant = await _register(harness, nursery_id, branch.id, species.id)
        tokens.add(plant.qr_code_token)
    assert len(tokens) == 25


async def test_get_by_qr_token_success(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)
    found = await harness.plant_service.get_by_qr_token(plant.qr_code_token)
    assert found.id == plant.id


async def test_get_by_qr_token_not_found(harness):
    with pytest.raises(NotFoundError):
        await harness.plant_service.get_by_qr_token("NVA-DOES-NOT-EXIST")


# ==============================================================================
# Bulk registration
# ==============================================================================


async def test_bulk_register_plants_success(harness, scene):
    nursery_id, branch, species = scene
    items = [{"branch_id": branch.id, "species_id": species.id, "common_label": f"Plant {i}"} for i in range(5)]

    plants = await harness.plant_service.bulk_register_plants(nursery_id=nursery_id, actor_user_id=uuid.uuid4(), items=items)

    assert len(plants) == 5
    assert len({p.qr_code_token for p in plants}) == 5


async def test_bulk_register_plants_empty_list_rejected(harness):
    with pytest.raises(ValidationError):
        await harness.plant_service.bulk_register_plants(nursery_id=uuid.uuid4(), actor_user_id=uuid.uuid4(), items=[])


async def test_bulk_register_plants_stops_on_first_invalid_item(harness, scene):
    nursery_id, branch, species = scene
    items = [
        {"branch_id": branch.id, "species_id": species.id},
        {"branch_id": uuid.uuid4(), "species_id": species.id},  # invalid branch
    ]
    with pytest.raises(ValidationError):
        await harness.plant_service.bulk_register_plants(nursery_id=nursery_id, actor_user_id=uuid.uuid4(), items=items)


# ==============================================================================
# Profile / list
# ==============================================================================


async def test_get_plant_not_found(harness):
    with pytest.raises(NotFoundError):
        await harness.plant_service.get_plant(uuid.uuid4())


async def test_update_plant_profile_changes_fields(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)

    updated = await harness.plant_service.update_plant_profile(
        plant_id=plant.id, actor_user_id=uuid.uuid4(), common_label="Renamed", batch_number="B-99",
    )
    assert updated.common_label == "Renamed"
    assert updated.batch_number == "B-99"
    assert harness.audit_logs.rows[-1].action == "plant.updated"


async def test_update_plant_profile_noop_skips_audit(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id, common_label="Same")
    audit_count_before = len(harness.audit_logs.rows)

    await harness.plant_service.update_plant_profile(plant_id=plant.id, actor_user_id=uuid.uuid4(), common_label="Same")

    assert len(harness.audit_logs.rows) == audit_count_before


async def test_update_plant_profile_updates_every_field(harness, scene):
    nursery_id, branch, species = scene
    variety = _variety(nursery_id=nursery_id, species_id=species.id)
    harness.plant_varieties.varieties[variety.id] = variety
    supplier = _supplier(nursery_id=nursery_id, branch_id=branch.id)
    harness.suppliers.suppliers[supplier.id] = supplier
    plant = await _register(harness, nursery_id, branch.id, species.id)
    purchase_date = datetime.now(timezone.utc)

    updated = await harness.plant_service.update_plant_profile(
        plant_id=plant.id, actor_user_id=uuid.uuid4(), variety_id=variety.id, supplier_id=supplier.id,
        purchase_price=25.0, purchase_date=purchase_date, price=49.99,
    )

    assert updated.variety_id == variety.id
    assert updated.supplier_id == supplier.id
    assert updated.purchase_price == 25.0
    assert updated.purchase_date == purchase_date
    assert updated.price == 49.99


async def test_update_plant_profile_unknown_supplier_rejected(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)
    with pytest.raises(ValidationError):
        await harness.plant_service.update_plant_profile(plant_id=plant.id, actor_user_id=uuid.uuid4(), supplier_id=uuid.uuid4())


async def test_update_plant_profile_negative_purchase_price_rejected(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)
    with pytest.raises(ValidationError):
        await harness.plant_service.update_plant_profile(plant_id=plant.id, actor_user_id=uuid.uuid4(), purchase_price=-1)


async def test_update_plant_profile_negative_price_rejected(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)
    with pytest.raises(ValidationError):
        await harness.plant_service.update_plant_profile(plant_id=plant.id, actor_user_id=uuid.uuid4(), price=-1)


async def test_list_plants_invalid_sort_dir_rejected(harness, scene):
    nursery_id, _branch, _species = scene
    with pytest.raises(ValidationError):
        await harness.plant_service.list_plants(nursery_id=nursery_id, offset=0, limit=50, sort_dir="sideways")


async def test_update_plant_profile_variety_must_match_species(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)
    other_species = _species(nursery_id=nursery_id, botanical_name="Aloe vera")
    harness.species.species[other_species.id] = other_species
    wrong_variety = _variety(nursery_id=nursery_id, species_id=other_species.id)
    harness.plant_varieties.varieties[wrong_variety.id] = wrong_variety

    with pytest.raises(ValidationError):
        await harness.plant_service.update_plant_profile(plant_id=plant.id, actor_user_id=uuid.uuid4(), variety_id=wrong_variety.id)


async def test_list_plants_filters_by_branch_and_species(harness, scene):
    nursery_id, branch, species = scene
    other_branch = _branch(nursery_id=nursery_id, name="North")
    harness.branches.branches[other_branch.id] = other_branch
    p1 = await _register(harness, nursery_id, branch.id, species.id)
    await _register(harness, nursery_id, other_branch.id, species.id)

    rows, total = await harness.plant_service.list_plants(nursery_id=nursery_id, offset=0, limit=50, branch_id=branch.id)
    assert total == 1
    assert rows[0].id == p1.id


async def test_list_plants_search_matches_common_label(harness, scene):
    nursery_id, branch, species = scene
    await _register(harness, nursery_id, branch.id, species.id, common_label="Sunny Fig")
    await _register(harness, nursery_id, branch.id, species.id, common_label="Shady Fern")

    rows, total = await harness.plant_service.list_plants(nursery_id=nursery_id, offset=0, limit=50, search="sunny")
    assert total == 1
    assert rows[0].common_label == "Sunny Fig"


async def test_list_plants_invalid_sort_by_rejected(harness, scene):
    nursery_id, _branch, _species = scene
    with pytest.raises(ValidationError):
        await harness.plant_service.list_plants(nursery_id=nursery_id, offset=0, limit=50, sort_by="not_a_field")


# ==============================================================================
# Movement
# ==============================================================================


async def test_move_plant_branch_transfer(harness, scene):
    nursery_id, branch, species = scene
    dest = _branch(nursery_id=nursery_id, name="Downtown")
    harness.branches.branches[dest.id] = dest
    plant = await _register(harness, nursery_id, branch.id, species.id)

    moved = await harness.plant_service.move_plant(plant_id=plant.id, actor_user_id=uuid.uuid4(), to_branch_id=dest.id)

    assert moved.branch_id == dest.id
    history = await harness.plant_service.list_movement_history(plant.id)
    assert len(history) == 1
    assert history[0].from_branch_id == branch.id
    assert history[0].to_branch_id == dest.id
    assert harness.domain_events.events[-1].event_type == "plant.moved"


async def test_move_plant_zone_only(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id, zone="greenhouse-1")

    moved = await harness.plant_service.move_plant(plant_id=plant.id, actor_user_id=uuid.uuid4(), to_zone="outdoor-A")

    assert moved.branch_id == branch.id
    assert moved.zone == "outdoor-A"
    history = await harness.plant_service.list_movement_history(plant.id)
    assert history[0].from_zone == "greenhouse-1"
    assert history[0].to_zone == "outdoor-A"


async def test_move_plant_no_change_rejected(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id, zone="A1")
    with pytest.raises(ValidationError):
        await harness.plant_service.move_plant(plant_id=plant.id, actor_user_id=uuid.uuid4(), to_zone="A1")


async def test_move_plant_unknown_destination_branch_rejected(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)
    with pytest.raises(ValidationError):
        await harness.plant_service.move_plant(plant_id=plant.id, actor_user_id=uuid.uuid4(), to_branch_id=uuid.uuid4())


# ==============================================================================
# Status state machine
# ==============================================================================


async def test_promote_to_ready_for_sale_succeeds(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)

    updated = await harness.plant_service.transition_status(
        plant_id=plant.id, to_status=PlantStatus.READY_FOR_SALE, actor_user_id=uuid.uuid4()
    )
    assert updated.status == PlantStatus.READY_FOR_SALE


async def test_promote_to_ready_for_sale_blocked_by_open_disease_report(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)
    report = DiseaseReport(
        id=uuid.uuid4(), plant_id=plant.id, condition_name="Root rot", status=DiseaseReportStatus.DRAFT,
        severity=DiseaseReportSeverity.LOW, is_ai_sourced=False, created_at=datetime.now(timezone.utc),
    )
    harness.disease_reports.reports[report.id] = report

    with pytest.raises(ConflictError):
        await harness.plant_service.transition_status(
            plant_id=plant.id, to_status=PlantStatus.READY_FOR_SALE, actor_user_id=uuid.uuid4()
        )


async def test_demote_ready_for_sale_to_in_production(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)
    await harness.plant_service.transition_status(plant_id=plant.id, to_status=PlantStatus.READY_FOR_SALE, actor_user_id=uuid.uuid4())

    updated = await harness.plant_service.transition_status(plant_id=plant.id, to_status=PlantStatus.IN_PRODUCTION, actor_user_id=uuid.uuid4())
    assert updated.status == PlantStatus.IN_PRODUCTION


async def test_under_treatment_requires_confirmed_disease_report(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)
    with pytest.raises(ConflictError):
        await harness.plant_service.transition_status(plant_id=plant.id, to_status=PlantStatus.UNDER_TREATMENT, actor_user_id=uuid.uuid4())


async def test_under_treatment_with_confirmed_report_succeeds(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)
    report = DiseaseReport(
        id=uuid.uuid4(), plant_id=plant.id, condition_name="Aphids", status=DiseaseReportStatus.CONFIRMED,
        severity=DiseaseReportSeverity.HIGH, is_ai_sourced=False, created_at=datetime.now(timezone.utc),
    )
    harness.disease_reports.reports[report.id] = report

    updated = await harness.plant_service.transition_status(plant_id=plant.id, to_status=PlantStatus.UNDER_TREATMENT, actor_user_id=uuid.uuid4())
    assert updated.status == PlantStatus.UNDER_TREATMENT


async def test_under_treatment_to_in_production_requires_resolved_recovered(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)
    report = DiseaseReport(
        id=uuid.uuid4(), plant_id=plant.id, condition_name="Aphids", status=DiseaseReportStatus.CONFIRMED,
        severity=DiseaseReportSeverity.HIGH, is_ai_sourced=False, created_at=datetime.now(timezone.utc),
    )
    harness.disease_reports.reports[report.id] = report
    await harness.plant_service.transition_status(plant_id=plant.id, to_status=PlantStatus.UNDER_TREATMENT, actor_user_id=uuid.uuid4())

    with pytest.raises(ConflictError):
        await harness.plant_service.transition_status(plant_id=plant.id, to_status=PlantStatus.IN_PRODUCTION, actor_user_id=uuid.uuid4())


async def test_under_treatment_to_in_production_succeeds_after_recovered_resolution(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)
    report = DiseaseReport(
        id=uuid.uuid4(), plant_id=plant.id, condition_name="Aphids", status=DiseaseReportStatus.CONFIRMED,
        severity=DiseaseReportSeverity.HIGH, is_ai_sourced=False, created_at=datetime.now(timezone.utc),
    )
    harness.disease_reports.reports[report.id] = report
    await harness.plant_service.transition_status(plant_id=plant.id, to_status=PlantStatus.UNDER_TREATMENT, actor_user_id=uuid.uuid4())
    report.status = DiseaseReportStatus.RESOLVED
    treatment = Treatment(
        id=uuid.uuid4(), disease_report_id=report.id, description="Neem oil", outcome=TreatmentOutcome.RECOVERED,
        applied_by_user_id=uuid.uuid4(), applied_at=datetime.now(timezone.utc),
    )
    harness.treatments.treatments[treatment.id] = treatment

    updated = await harness.plant_service.transition_status(plant_id=plant.id, to_status=PlantStatus.IN_PRODUCTION, actor_user_id=uuid.uuid4())
    assert updated.status == PlantStatus.IN_PRODUCTION


async def test_ready_for_sale_to_sold_sets_sold_at(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)
    await harness.plant_service.transition_status(plant_id=plant.id, to_status=PlantStatus.READY_FOR_SALE, actor_user_id=uuid.uuid4())

    updated = await harness.plant_service.transition_status(plant_id=plant.id, to_status=PlantStatus.SOLD, actor_user_id=uuid.uuid4())
    assert updated.status == PlantStatus.SOLD
    assert updated.sold_at is not None


async def test_direct_writeoff_to_deceased_requires_reason(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)
    with pytest.raises(ValidationError):
        await harness.plant_service.transition_status(plant_id=plant.id, to_status=PlantStatus.DECEASED, actor_user_id=uuid.uuid4())


async def test_direct_writeoff_to_deceased_with_reason_succeeds(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)
    updated = await harness.plant_service.transition_status(
        plant_id=plant.id, to_status=PlantStatus.DECEASED, actor_user_id=uuid.uuid4(), reason="Frost damage"
    )
    assert updated.status == PlantStatus.DECEASED
    assert updated.deceased_at is not None
    assert updated.deceased_reason == "Frost damage"


async def test_illegal_transition_from_terminal_status_rejected(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)
    await harness.plant_service.transition_status(
        plant_id=plant.id, to_status=PlantStatus.DECEASED, actor_user_id=uuid.uuid4(), reason="Lost"
    )
    with pytest.raises(ConflictError):
        await harness.plant_service.transition_status(plant_id=plant.id, to_status=PlantStatus.IN_PRODUCTION, actor_user_id=uuid.uuid4())


async def test_transition_to_same_status_rejected(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)
    with pytest.raises(ConflictError):
        await harness.plant_service.transition_status(plant_id=plant.id, to_status=PlantStatus.IN_PRODUCTION, actor_user_id=uuid.uuid4())


# ==============================================================================
# Archive
# ==============================================================================


async def test_archive_requires_terminal_status(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)
    with pytest.raises(ConflictError):
        await harness.plant_service.archive_plant(plant_id=plant.id, actor_user_id=uuid.uuid4())


async def test_archive_succeeds_when_sold(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)
    await harness.plant_service.transition_status(plant_id=plant.id, to_status=PlantStatus.READY_FOR_SALE, actor_user_id=uuid.uuid4())
    await harness.plant_service.transition_status(plant_id=plant.id, to_status=PlantStatus.SOLD, actor_user_id=uuid.uuid4())

    archived = await harness.plant_service.archive_plant(plant_id=plant.id, actor_user_id=uuid.uuid4(), reason="End of season")
    assert archived.archived_at is not None
    assert archived.archived_reason == "End of season"


async def test_archive_already_archived_rejected(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)
    await harness.plant_service.transition_status(plant_id=plant.id, to_status=PlantStatus.READY_FOR_SALE, actor_user_id=uuid.uuid4())
    await harness.plant_service.transition_status(plant_id=plant.id, to_status=PlantStatus.SOLD, actor_user_id=uuid.uuid4())
    await harness.plant_service.archive_plant(plant_id=plant.id, actor_user_id=uuid.uuid4())

    with pytest.raises(ConflictError):
        await harness.plant_service.archive_plant(plant_id=plant.id, actor_user_id=uuid.uuid4())


# ==============================================================================
# Images
# ==============================================================================


async def test_upload_image_success(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)

    image = await harness.plant_service.upload_image(plant_id=plant.id, url="https://cdn/img.jpg", actor_user_id=uuid.uuid4(), caption="Day 1")
    assert image.url == "https://cdn/img.jpg"
    images = await harness.plant_service.list_images(plant.id)
    assert len(images) == 1


async def test_upload_image_blank_url_rejected(harness, scene):
    nursery_id, branch, species = scene
    plant = await _register(harness, nursery_id, branch.id, species.id)
    with pytest.raises(ValidationError):
        await harness.plant_service.upload_image(plant_id=plant.id, url="  ", actor_user_id=uuid.uuid4())
