"""
Integration tests for Module 5's `/api/v1/plant-varieties` routes --
exercised through the real FastAPI app with `authenticated_client`
(tests/conftest.py) against `harness`'s in-memory fakes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.models.catalog import PlantVariety, Species

pytestmark = pytest.mark.integration


def _species(*, nursery_id: uuid.UUID) -> Species:
    now = datetime.now(timezone.utc)
    return Species(
        id=uuid.uuid4(), nursery_id=nursery_id, category_id=uuid.uuid4(),
        common_name="Fiddle Leaf Fig", botanical_name="Ficus lyrata", created_at=now, updated_at=now,
    )


def _variety(*, nursery_id: uuid.UUID, species_id: uuid.UUID, name: str = "Bambino") -> PlantVariety:
    now = datetime.now(timezone.utc)
    return PlantVariety(
        id=uuid.uuid4(), nursery_id=nursery_id, species_id=species_id, name=name, created_at=now, updated_at=now
    )


async def test_requires_authentication(auth_client):
    response = await auth_client.get("/api/v1/plant-varieties")
    assert response.status_code == 401


async def test_list_varieties_scoped_to_callers_org(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    species = _species(nursery_id=org_id)
    harness.species.species[species.id] = species
    own_variety = _variety(nursery_id=org_id, species_id=species.id)
    other_variety = _variety(nursery_id=other_org_id, species_id=uuid.uuid4())
    harness.plant_varieties.varieties[own_variety.id] = own_variety
    harness.plant_varieties.varieties[other_variety.id] = other_variety
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["species:read"])

    response = await ac.get("/api/v1/plant-varieties")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total_items"] == 1
    assert body["items"][0]["id"] == str(own_variety.id)


async def test_list_varieties_filtered_by_species(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    species = _species(nursery_id=org_id)
    other_species = _species(nursery_id=org_id)
    harness.species.species[species.id] = species
    harness.species.species[other_species.id] = other_species
    v1 = _variety(nursery_id=org_id, species_id=species.id, name="Bambino")
    v2 = _variety(nursery_id=org_id, species_id=other_species.id, name="Laurentii")
    harness.plant_varieties.varieties[v1.id] = v1
    harness.plant_varieties.varieties[v2.id] = v2
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["species:read"])

    response = await ac.get("/api/v1/plant-varieties", params={"species_id": str(species.id)})

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total_items"] == 1
    assert body["items"][0]["name"] == "Bambino"


async def test_create_variety(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    species = _species(nursery_id=org_id)
    harness.species.species[species.id] = species
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["species:read", "species:write"])

    response = await ac.post(
        "/api/v1/plant-varieties", json={"species_id": str(species.id), "name": "Variegata"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Variegata"
    assert body["species_id"] == str(species.id)


async def test_create_variety_for_foreign_species_rejected(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    foreign_species = _species(nursery_id=uuid.uuid4())
    harness.species.species[foreign_species.id] = foreign_species
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["species:read", "species:write"])

    response = await ac.post(
        "/api/v1/plant-varieties", json={"species_id": str(foreign_species.id), "name": "Variegata"}
    )

    assert response.status_code == 422


async def test_get_variety_rejects_cross_tenant_access(authenticated_client, harness):
    ac, user = authenticated_client
    own_org_id = uuid.uuid4()
    foreign_org_id = uuid.uuid4()
    foreign_variety = _variety(nursery_id=foreign_org_id, species_id=uuid.uuid4())
    harness.plant_varieties.varieties[foreign_variety.id] = foreign_variety
    harness.grant_role(user, org_id=own_org_id, role_code="owner", permission_codes=["species:read"])

    response = await ac.get(f"/api/v1/plant-varieties/{foreign_variety.id}")

    assert response.status_code == 403
    assert harness.denials.denials[-1].reason == "cross_tenant_org"


async def test_update_variety(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    species = _species(nursery_id=org_id)
    harness.species.species[species.id] = species
    variety = _variety(nursery_id=org_id, species_id=species.id)
    harness.plant_varieties.varieties[variety.id] = variety
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["species:read", "species:write"])

    response = await ac.patch(f"/api/v1/plant-varieties/{variety.id}", json={"name": "Bambino Deluxe"})

    assert response.status_code == 200
    assert response.json()["name"] == "Bambino Deluxe"


async def test_delete_variety_success(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    species = _species(nursery_id=org_id)
    harness.species.species[species.id] = species
    variety = _variety(nursery_id=org_id, species_id=species.id)
    harness.plant_varieties.varieties[variety.id] = variety
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["species:read", "species:delete"])

    response = await ac.delete(f"/api/v1/plant-varieties/{variety.id}")

    assert response.status_code == 200
    get_response = await ac.get(f"/api/v1/plant-varieties/{variety.id}")
    assert get_response.status_code == 404


async def test_delete_variety_blocked_when_referenced(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    species = _species(nursery_id=org_id)
    harness.species.species[species.id] = species
    variety = _variety(nursery_id=org_id, species_id=species.id)
    harness.plant_varieties.varieties[variety.id] = variety
    harness.plant_varieties.plant_variety_ids.append(variety.id)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["species:read", "species:delete"])

    response = await ac.delete(f"/api/v1/plant-varieties/{variety.id}")

    assert response.status_code == 409
