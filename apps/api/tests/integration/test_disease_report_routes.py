"""Integration tests for Module 6's `/disease-reports` routes -- create, confirm, dismiss, treatments."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.db.enums import DiseaseReportSeverity
from app.models.catalog import Species
from app.models.organization import Branch

pytestmark = pytest.mark.integration


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


async def _seed_plant(harness):
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    return org_id, plant


async def test_create_disease_report(authenticated_client, harness):
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    harness.grant_role(user, org_id=org_id, role_code="horticulturist", permission_codes=["disease:read", "disease:write"])

    response = await ac.post(
        f"/api/v1/plants/{plant.id}/disease-reports", json={"condition_name": "Root rot", "severity": "high"}
    )

    assert response.status_code == 201
    assert response.json()["status"] == "draft"


async def test_confirm_requires_approve_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    harness.grant_role(user, org_id=org_id, role_code="horticulturist", permission_codes=["disease:read", "disease:write"])
    create = await ac.post(f"/api/v1/plants/{plant.id}/disease-reports", json={"condition_name": "Root rot", "severity": "high"})
    report_id = create.json()["id"]

    response = await ac.post(f"/api/v1/disease-reports/{report_id}/confirm")

    assert response.status_code == 403


async def test_confirm_report_transitions_plant_to_under_treatment(authenticated_client, harness):
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    harness.grant_role(
        user, org_id=org_id, role_code="branch_manager",
        permission_codes=["disease:read", "disease:write", "disease:approve", "plants:read"],
    )
    create = await ac.post(f"/api/v1/plants/{plant.id}/disease-reports", json={"condition_name": "Root rot", "severity": "high"})
    report_id = create.json()["id"]

    response = await ac.post(f"/api/v1/disease-reports/{report_id}/confirm")

    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"
    plant_response = await ac.get(f"/api/v1/plants/{plant.id}")
    assert plant_response.json()["status"] == "under_treatment"


async def test_dismiss_report(authenticated_client, harness):
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    harness.grant_role(
        user, org_id=org_id, role_code="branch_manager",
        permission_codes=["disease:read", "disease:write", "disease:approve"],
    )
    create = await ac.post(f"/api/v1/plants/{plant.id}/disease-reports", json={"condition_name": "False alarm", "severity": "low"})
    report_id = create.json()["id"]

    response = await ac.post(f"/api/v1/disease-reports/{report_id}/dismiss", json={"dismissed_reason": "Not real"})

    assert response.status_code == 200
    assert response.json()["status"] == "dismissed"


async def test_apply_treatment_recovered_closes_report(authenticated_client, harness):
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    harness.grant_role(
        user, org_id=org_id, role_code="branch_manager",
        permission_codes=["disease:read", "disease:write", "disease:approve"],
    )
    create = await ac.post(f"/api/v1/plants/{plant.id}/disease-reports", json={"condition_name": "Root rot", "severity": "high"})
    report_id = create.json()["id"]
    await ac.post(f"/api/v1/disease-reports/{report_id}/confirm")

    response = await ac.post(
        f"/api/v1/disease-reports/{report_id}/treatments", json={"description": "Fungicide", "outcome": "recovered"}
    )

    assert response.status_code == 201
    assert response.json()["outcome"] == "recovered"
    report_response = await ac.get(f"/api/v1/disease-reports/{report_id}")
    assert report_response.json()["status"] == "resolved"


async def test_list_disease_reports_scoped_to_org(authenticated_client, harness):
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    other_org_id = uuid.uuid4()
    other_branch = _branch(nursery_id=other_org_id)
    other_species = _species(nursery_id=other_org_id)
    harness.branches.branches[other_branch.id] = other_branch
    harness.species.species[other_species.id] = other_species
    other_plant = await harness.plant_service.register_plant(
        nursery_id=other_org_id, branch_id=other_branch.id, species_id=other_species.id, actor_user_id=uuid.uuid4()
    )
    await harness.disease_report_service.create_report(
        plant_id=plant.id, condition_name="Own report", severity=DiseaseReportSeverity.LOW, actor_user_id=uuid.uuid4()
    )
    await harness.disease_report_service.create_report(
        plant_id=other_plant.id, condition_name="Other org report", severity=DiseaseReportSeverity.LOW, actor_user_id=uuid.uuid4()
    )
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["disease:read"])

    response = await ac.get("/api/v1/disease-reports")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total_items"] == 1
    assert body["items"][0]["condition_name"] == "Own report"


async def test_get_disease_report_cross_tenant_rejected(authenticated_client, harness):
    ac, user = authenticated_client
    own_org_id = uuid.uuid4()
    foreign_org_id, foreign_plant = await _seed_plant(harness)
    report = await harness.disease_report_service.create_report(
        plant_id=foreign_plant.id, condition_name="Foreign", severity=DiseaseReportSeverity.LOW, actor_user_id=uuid.uuid4()
    )
    harness.grant_role(user, org_id=own_org_id, role_code="owner", permission_codes=["disease:read"])

    response = await ac.get(f"/api/v1/disease-reports/{report.id}")

    assert response.status_code == 403
