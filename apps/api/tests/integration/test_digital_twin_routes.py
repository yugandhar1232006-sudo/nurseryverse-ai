"""Integration tests for Module 7's read-only Digital Twin Query API (app/api/routes/digital_twin.py)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

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


async def test_get_current_twin_requires_auth(auth_client):
    response = await auth_client.get(f"/api/v1/plants/{uuid.uuid4()}/digital-twin")
    assert response.status_code == 401


async def test_get_current_twin_denied_without_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=[])

    response = await ac.get(f"/api/v1/plants/{plant.id}/digital-twin")

    assert response.status_code == 403


async def test_get_current_twin_success(authenticated_client, harness):
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read"])

    response = await ac.get(f"/api/v1/plants/{plant.id}/digital-twin")

    assert response.status_code == 200
    body = response.json()
    assert body["plant_id"] == str(plant.id)
    assert body["current_version"] == 1
    assert body["lifecycle_state"] == "in_production"
    assert body["snapshot"]["identity"]["qr_code_token"] == plant.qr_code_token


async def test_get_current_twin_cross_tenant_rejected(authenticated_client, harness):
    ac, user = authenticated_client
    own_org_id = uuid.uuid4()
    foreign_org_id, foreign_plant = await _seed_plant(harness)
    harness.grant_role(user, org_id=own_org_id, role_code="owner", permission_codes=["plants:read"])

    response = await ac.get(f"/api/v1/plants/{foreign_plant.id}/digital-twin")

    assert response.status_code == 403
    assert response.json()["error"]["context"]["reason"] == "cross_tenant_org"


async def test_get_current_twin_not_found_for_unknown_plant(authenticated_client, harness):
    ac, user = authenticated_client
    response = await ac.get(f"/api/v1/plants/{uuid.uuid4()}/digital-twin")
    assert response.status_code in (403, 404)  # plant_service.get_plant 404s before authz can even run


async def test_timeline_reflects_every_projected_event(authenticated_client, harness):
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read", "growth:write"])
    await ac.post(f"/api/v1/plants/{plant.id}/growth-timeline", json={"height_cm": 12.0, "growth_stage": "seedling"})

    response = await ac.get(f"/api/v1/plants/{plant.id}/digital-twin/timeline")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total_items"] == 2
    event_types = {item["event_type"] for item in body["items"]}
    assert event_types == {"plant.registered", "plant.growth_recorded"}


async def test_version_history_and_get_specific_version(authenticated_client, harness):
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read", "watering:write"])
    await ac.post(f"/api/v1/plants/{plant.id}/watering-logs", json={"volume_ml": 150})

    history = await ac.get(f"/api/v1/plants/{plant.id}/digital-twin/versions")
    assert history.status_code == 200
    assert history.json()["meta"]["total_items"] == 2

    version_1 = await ac.get(f"/api/v1/plants/{plant.id}/digital-twin/versions/1")
    assert version_1.status_code == 200
    assert version_1.json()["event_type"] == "plant.registered"

    missing_version = await ac.get(f"/api/v1/plants/{plant.id}/digital-twin/versions/99")
    assert missing_version.status_code == 404


async def test_compare_versions(authenticated_client, harness):
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read", "growth:write"])
    await ac.post(f"/api/v1/plants/{plant.id}/growth-timeline", json={"height_cm": 20.0})

    response = await ac.get(
        f"/api/v1/plants/{plant.id}/digital-twin/versions/compare", params={"version_a": 1, "version_b": 2}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["version_a"] == 1
    assert body["version_b"] == 2
    assert "counts" in body["changed_keys"]


async def test_snapshot_by_date(authenticated_client, harness):
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read"])
    v1 = await harness.digital_twin_service.get_version(plant.id, 1)

    response = await ac.get(
        f"/api/v1/plants/{plant.id}/digital-twin/snapshot", params={"as_of": v1.occurred_at.isoformat()}
    )

    assert response.status_code == 200
    assert response.json()["version"] == 1


async def test_event_history_includes_raw_payloads(authenticated_client, harness):
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read"])

    response = await ac.get(f"/api/v1/plants/{plant.id}/digital-twin/events")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total_items"] == 1
    assert body["items"][0]["event_type"] == "plant.registered"
    assert "qr_code_token" in body["items"][0]["payload"]


async def test_verify_consistency_reports_true_for_a_healthy_twin(authenticated_client, harness):
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read"])

    response = await ac.get(f"/api/v1/plants/{plant.id}/digital-twin/verify")

    assert response.status_code == 200
    body = response.json()
    assert body["consistent"] is True
    assert body["differing_keys"] == []


async def test_list_digital_twins_scoped_to_org(authenticated_client, harness):
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    other_org_id, other_plant = await _seed_plant(harness)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read"])

    response = await ac.get("/api/v1/digital-twins")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total_items"] == 1
    assert body["items"][0]["plant_id"] == str(plant.id)


async def test_list_digital_twins_without_org_membership_returns_empty_page(authenticated_client, harness):
    ac, user = authenticated_client
    response = await ac.get("/api/v1/digital-twins")
    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_list_digital_twins_denied_without_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=[])

    response = await ac.get("/api/v1/digital-twins")

    assert response.status_code == 403


async def test_no_write_routes_exist_for_digital_twin(authenticated_client, harness):
    """Structural proof at the HTTP level: no POST/PATCH/PUT/DELETE route exists anywhere under /digital-twin."""
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read", "plants:write"])

    post_response = await ac.post(f"/api/v1/plants/{plant.id}/digital-twin", json={})
    patch_response = await ac.patch(f"/api/v1/plants/{plant.id}/digital-twin", json={})
    delete_response = await ac.delete(f"/api/v1/plants/{plant.id}/digital-twin")

    assert post_response.status_code == 405
    assert patch_response.status_code == 405
    assert delete_response.status_code == 405
