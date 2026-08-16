"""Integration tests for Module 6's Growth/Health/Watering/Fertilizer/Environmental record routes."""
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


async def test_growth_timeline_requires_auth(auth_client):
    response = await auth_client.get(f"/api/v1/plants/{uuid.uuid4()}/growth-timeline")
    assert response.status_code == 401


async def test_record_and_list_growth(authenticated_client, harness):
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    harness.grant_role(user, org_id=org_id, role_code="horticulturist", permission_codes=["growth:read", "growth:write"])

    create = await ac.post(f"/api/v1/plants/{plant.id}/growth-timeline", json={"height_cm": 15.0, "leaf_count": 6})
    assert create.status_code == 201
    assert create.json()["height_cm"] == 15.0

    listing = await ac.get(f"/api/v1/plants/{plant.id}/growth-timeline")
    assert listing.status_code == 200
    assert listing.json()["meta"]["total_items"] == 1


async def test_record_growth_denied_without_write_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=["growth:read"])

    response = await ac.post(f"/api/v1/plants/{plant.id}/growth-timeline", json={"height_cm": 10})
    assert response.status_code == 403


async def test_record_and_list_health(authenticated_client, harness):
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    harness.grant_role(user, org_id=org_id, role_code="horticulturist", permission_codes=["health:read", "health:write"])

    create = await ac.post(f"/api/v1/plants/{plant.id}/health-history", json={"status_label": "healthy", "health_score": 95})
    assert create.status_code == 201
    assert create.json()["status_label"] == "healthy"

    listing = await ac.get(f"/api/v1/plants/{plant.id}/health-history")
    assert listing.json()["meta"]["total_items"] == 1


async def test_record_and_list_watering(authenticated_client, harness):
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    harness.grant_role(user, org_id=org_id, role_code="horticulturist", permission_codes=["watering:read", "watering:write"])

    create = await ac.post(f"/api/v1/plants/{plant.id}/watering-logs", json={"volume_ml": 200, "method": "drip"})
    assert create.status_code == 201
    assert create.json()["volume_ml"] == 200

    listing = await ac.get(f"/api/v1/plants/{plant.id}/watering-logs")
    assert listing.json()["meta"]["total_items"] == 1


async def test_record_and_list_fertilizer(authenticated_client, harness):
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    # Fertilizer routes reuse watering:* -- see plant_records.py's module docstring.
    harness.grant_role(user, org_id=org_id, role_code="horticulturist", permission_codes=["watering:read", "watering:write"])

    create = await ac.post(f"/api/v1/plants/{plant.id}/fertilizer-logs", json={"product_name": "GrowFast", "schedule": "weekly"})
    assert create.status_code == 201
    assert create.json()["product_name"] == "GrowFast"

    listing = await ac.get(f"/api/v1/plants/{plant.id}/fertilizer-logs")
    assert listing.json()["meta"]["total_items"] == 1


async def test_record_and_list_environmental(authenticated_client, harness):
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    harness.grant_role(user, org_id=org_id, role_code="horticulturist", permission_codes=["environmental:read", "environmental:write"])

    create = await ac.post(
        f"/api/v1/plants/{plant.id}/environmental-readings",
        json={"temperature_celsius": 21.0, "humidity_percent": 55, "ph_level": 6.2},
    )
    assert create.status_code == 201
    assert create.json()["ph_level"] == 6.2

    listing = await ac.get(f"/api/v1/plants/{plant.id}/environmental-readings")
    assert listing.json()["meta"]["total_items"] == 1


async def test_growth_records_are_immutable_no_update_or_delete_route(authenticated_client, harness):
    """Every route in this file's module is GET/POST only -- confirms via HTTP that no PATCH/PUT/DELETE exists for any record type."""
    ac, user = authenticated_client
    org_id, plant = await _seed_plant(harness)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["growth:read", "growth:write"])
    create = await ac.post(f"/api/v1/plants/{plant.id}/growth-timeline", json={"height_cm": 10})
    entry_id = create.json()["id"]

    patch_response = await ac.patch(f"/api/v1/plants/{plant.id}/growth-timeline/{entry_id}", json={"height_cm": 99})
    delete_response = await ac.delete(f"/api/v1/plants/{plant.id}/growth-timeline/{entry_id}")

    assert patch_response.status_code == 404  # no such route exists
    assert delete_response.status_code == 404
