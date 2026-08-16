"""Unit tests for Module 6's DiseaseReportService/TreatmentService -- confirm/dismiss/treat, and the Plant status transitions they trigger."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.core.exceptions import ConflictError, ValidationError
from app.db.enums import DiseaseReportSeverity, DiseaseReportStatus, PlantStatus, TreatmentOutcome
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


async def test_create_report_draft(harness, plant):
    report = await harness.disease_report_service.create_report(
        plant_id=plant.id, condition_name="Powdery mildew", severity=DiseaseReportSeverity.MEDIUM, actor_user_id=uuid.uuid4(),
    )
    assert report.status == DiseaseReportStatus.DRAFT
    assert harness.domain_events.events[-1].event_type == "plant.disease_detected"


async def test_create_report_blank_condition_rejected(harness, plant):
    with pytest.raises(ValidationError):
        await harness.disease_report_service.create_report(
            plant_id=plant.id, condition_name=" ", severity=DiseaseReportSeverity.LOW, actor_user_id=uuid.uuid4()
        )


async def test_confirm_report_medium_severity_moves_plant_to_under_treatment(harness, plant):
    report = await harness.disease_report_service.create_report(
        plant_id=plant.id, condition_name="Root rot", severity=DiseaseReportSeverity.HIGH, actor_user_id=uuid.uuid4(),
    )
    confirmed = await harness.disease_report_service.confirm_report(report_id=report.id, actor_user_id=uuid.uuid4())

    assert confirmed.status == DiseaseReportStatus.CONFIRMED
    updated_plant = await harness.plant_service.get_plant(plant.id)
    assert updated_plant.status == PlantStatus.UNDER_TREATMENT


async def test_confirm_report_low_severity_does_not_force_under_treatment(harness, plant):
    report = await harness.disease_report_service.create_report(
        plant_id=plant.id, condition_name="Minor leaf spot", severity=DiseaseReportSeverity.LOW, actor_user_id=uuid.uuid4(),
    )
    await harness.disease_report_service.confirm_report(report_id=report.id, actor_user_id=uuid.uuid4())

    updated_plant = await harness.plant_service.get_plant(plant.id)
    assert updated_plant.status == PlantStatus.IN_PRODUCTION


async def test_confirm_already_confirmed_report_rejected(harness, plant):
    report = await harness.disease_report_service.create_report(
        plant_id=plant.id, condition_name="Root rot", severity=DiseaseReportSeverity.HIGH, actor_user_id=uuid.uuid4(),
    )
    await harness.disease_report_service.confirm_report(report_id=report.id, actor_user_id=uuid.uuid4())
    with pytest.raises(ConflictError):
        await harness.disease_report_service.confirm_report(report_id=report.id, actor_user_id=uuid.uuid4())


async def test_dismiss_report_requires_reason(harness, plant):
    report = await harness.disease_report_service.create_report(
        plant_id=plant.id, condition_name="False alarm", severity=DiseaseReportSeverity.LOW, actor_user_id=uuid.uuid4(),
    )
    with pytest.raises(ValidationError):
        await harness.disease_report_service.dismiss_report(report_id=report.id, actor_user_id=uuid.uuid4(), dismissed_reason="")


async def test_dismiss_report_success(harness, plant):
    report = await harness.disease_report_service.create_report(
        plant_id=plant.id, condition_name="False alarm", severity=DiseaseReportSeverity.LOW, actor_user_id=uuid.uuid4(),
    )
    dismissed = await harness.disease_report_service.dismiss_report(
        report_id=report.id, actor_user_id=uuid.uuid4(), dismissed_reason="Not actually a disease"
    )
    assert dismissed.status == DiseaseReportStatus.DISMISSED
    assert dismissed.dismissed_reason == "Not actually a disease"


async def test_apply_treatment_ongoing_does_not_close_report(harness, plant):
    report = await harness.disease_report_service.create_report(
        plant_id=plant.id, condition_name="Root rot", severity=DiseaseReportSeverity.HIGH, actor_user_id=uuid.uuid4(),
    )
    await harness.disease_report_service.confirm_report(report_id=report.id, actor_user_id=uuid.uuid4())

    treatment = await harness.treatment_service.apply_treatment(
        disease_report_id=report.id, description="Applied fungicide", outcome=TreatmentOutcome.ONGOING, actor_user_id=uuid.uuid4(),
    )
    assert treatment.outcome == TreatmentOutcome.ONGOING
    refreshed_report = await harness.disease_report_service.get_report(report.id)
    assert refreshed_report.status == DiseaseReportStatus.TREATED
    updated_plant = await harness.plant_service.get_plant(plant.id)
    assert updated_plant.status == PlantStatus.UNDER_TREATMENT


async def test_apply_treatment_recovered_resolves_report_and_returns_plant_to_production(harness, plant):
    report = await harness.disease_report_service.create_report(
        plant_id=plant.id, condition_name="Root rot", severity=DiseaseReportSeverity.HIGH, actor_user_id=uuid.uuid4(),
    )
    await harness.disease_report_service.confirm_report(report_id=report.id, actor_user_id=uuid.uuid4())

    await harness.treatment_service.apply_treatment(
        disease_report_id=report.id, description="Fungicide worked", outcome=TreatmentOutcome.RECOVERED, actor_user_id=uuid.uuid4(),
    )
    refreshed_report = await harness.disease_report_service.get_report(report.id)
    assert refreshed_report.status == DiseaseReportStatus.RESOLVED
    updated_plant = await harness.plant_service.get_plant(plant.id)
    assert updated_plant.status == PlantStatus.IN_PRODUCTION


async def test_apply_treatment_plant_lost_resolves_report_and_marks_plant_deceased(harness, plant):
    report = await harness.disease_report_service.create_report(
        plant_id=plant.id, condition_name="Root rot", severity=DiseaseReportSeverity.CRITICAL, actor_user_id=uuid.uuid4(),
    )
    await harness.disease_report_service.confirm_report(report_id=report.id, actor_user_id=uuid.uuid4())

    await harness.treatment_service.apply_treatment(
        disease_report_id=report.id, description="Beyond saving", outcome=TreatmentOutcome.PLANT_LOST, actor_user_id=uuid.uuid4(),
    )
    updated_plant = await harness.plant_service.get_plant(plant.id)
    assert updated_plant.status == PlantStatus.DECEASED
    assert updated_plant.deceased_reason is not None


async def test_apply_treatment_against_resolved_report_rejected(harness, plant):
    report = await harness.disease_report_service.create_report(
        plant_id=plant.id, condition_name="Root rot", severity=DiseaseReportSeverity.HIGH, actor_user_id=uuid.uuid4(),
    )
    await harness.disease_report_service.confirm_report(report_id=report.id, actor_user_id=uuid.uuid4())
    await harness.treatment_service.apply_treatment(
        disease_report_id=report.id, description="Fungicide worked", outcome=TreatmentOutcome.RECOVERED, actor_user_id=uuid.uuid4(),
    )
    with pytest.raises(ConflictError):
        await harness.treatment_service.apply_treatment(
            disease_report_id=report.id, description="Too late", outcome=TreatmentOutcome.ONGOING, actor_user_id=uuid.uuid4(),
        )


async def test_list_for_plant_returns_disease_history(harness, plant):
    await harness.disease_report_service.create_report(
        plant_id=plant.id, condition_name="Root rot", severity=DiseaseReportSeverity.LOW, actor_user_id=uuid.uuid4(),
    )
    await harness.disease_report_service.create_report(
        plant_id=plant.id, condition_name="Aphids", severity=DiseaseReportSeverity.MEDIUM, actor_user_id=uuid.uuid4(),
    )
    reports = await harness.disease_report_service.list_for_plant(plant.id)
    assert len(reports) == 2
