"""
Integration tests for Module 5's `/api/v1/plant-categories` and
`/api/v1/species` routes -- exercised through the real FastAPI app with
`authenticated_client` (tests/conftest.py) against `harness`'s in-memory
fakes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.models.catalog import PlantCategory, Species

pytestmark = pytest.mark.integration


def _category(*, code: str = "houseplant", name: str = "Houseplant") -> PlantCategory:
    return PlantCategory(id=uuid.uuid4(), code=code, name=name, description=None)


def _species(*, nursery_id: uuid.UUID, category_id: uuid.UUID, common_name: str = "Fiddle Leaf Fig", botanical_name: str = "Ficus lyrata") -> Species:
    now = datetime.now(timezone.utc)
    return Species(
        id=uuid.uuid4(), nursery_id=nursery_id, category_id=category_id,
        common_name=common_name, botanical_name=botanical_name, created_at=now, updated_at=now,
    )


async def test_requires_authentication(auth_client):
    response = await auth_client.get("/api/v1/species")
    assert response.status_code == 401


async def test_list_plant_categories(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    category = _category()
    harness.plant_categories.categories[category.id] = category
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=["species:read"])

    response = await ac.get("/api/v1/plant-categories")

    assert response.status_code == 200
    assert [c["id"] for c in response.json()] == [str(category.id)]


async def test_list_species_scoped_to_callers_org(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    category = _category()
    harness.plant_categories.categories[category.id] = category
    own_species = _species(nursery_id=org_id, category_id=category.id)
    other_species = _species(nursery_id=other_org_id, category_id=category.id)
    harness.species.species[own_species.id] = own_species
    harness.species.species[other_species.id] = other_species
    harness.grant_role(user, org_id=org_id, role_code="horticulturist", permission_codes=["species:read"])

    response = await ac.get("/api/v1/species")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total_items"] == 1
    assert body["items"][0]["id"] == str(own_species.id)


async def test_list_species_search_filter(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    category = _category()
    harness.plant_categories.categories[category.id] = category
    harness.species.species[uuid.uuid4()] = _species(nursery_id=org_id, category_id=category.id, common_name="Fiddle Leaf Fig", botanical_name="Ficus lyrata")
    harness.species.species[uuid.uuid4()] = _species(nursery_id=org_id, category_id=category.id, common_name="Snake Plant", botanical_name="Dracaena trifasciata")
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["species:read"])

    response = await ac.get("/api/v1/species", params={"search": "snake"})

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total_items"] == 1
    assert body["items"][0]["common_name"] == "Snake Plant"


async def test_create_species(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    category = _category()
    harness.plant_categories.categories[category.id] = category
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["species:read", "species:write"])

    response = await ac.post(
        "/api/v1/species",
        json={"category_id": str(category.id), "common_name": "Aloe Vera", "botanical_name": "Aloe vera"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["common_name"] == "Aloe Vera"
    assert body["nursery_id"] == str(org_id)


async def test_create_species_denied_without_write_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    category = _category()
    harness.plant_categories.categories[category.id] = category
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=["species:read"])

    response = await ac.post(
        "/api/v1/species",
        json={"category_id": str(category.id), "common_name": "Aloe Vera", "botanical_name": "Aloe vera"},
    )

    assert response.status_code == 403


async def test_get_species_rejects_cross_tenant_access(authenticated_client, harness):
    ac, user = authenticated_client
    own_org_id = uuid.uuid4()
    foreign_org_id = uuid.uuid4()
    category = _category()
    harness.plant_categories.categories[category.id] = category
    foreign_species = _species(nursery_id=foreign_org_id, category_id=category.id)
    harness.species.species[foreign_species.id] = foreign_species
    harness.grant_role(user, org_id=own_org_id, role_code="owner", permission_codes=["species:read"])

    response = await ac.get(f"/api/v1/species/{foreign_species.id}")

    assert response.status_code == 403
    assert harness.denials.denials[-1].reason == "cross_tenant_org"


async def test_update_species(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    category = _category()
    harness.plant_categories.categories[category.id] = category
    species = _species(nursery_id=org_id, category_id=category.id)
    harness.species.species[species.id] = species
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["species:read", "species:write"])

    response = await ac.patch(f"/api/v1/species/{species.id}", json={"light_requirement": "full_sun"})

    assert response.status_code == 200
    assert response.json()["light_requirement"] == "full_sun"


async def test_delete_species_success(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    category = _category()
    harness.plant_categories.categories[category.id] = category
    species = _species(nursery_id=org_id, category_id=category.id)
    harness.species.species[species.id] = species
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["species:read", "species:delete"])

    response = await ac.delete(f"/api/v1/species/{species.id}")

    assert response.status_code == 200
    get_response = await ac.get(f"/api/v1/species/{species.id}")
    assert get_response.status_code == 404


async def test_delete_species_blocked_when_referenced(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    category = _category()
    harness.plant_categories.categories[category.id] = category
    species = _species(nursery_id=org_id, category_id=category.id)
    harness.species.species[species.id] = species
    harness.species.plant_species_ids.append(species.id)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["species:read", "species:delete"])

    response = await ac.delete(f"/api/v1/species/{species.id}")

    assert response.status_code == 409
