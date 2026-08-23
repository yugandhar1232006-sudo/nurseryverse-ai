"""Integration tests for Module 6's `/api/v1/plants` routes -- exercised through the real FastAPI app against `harness`'s in-memory fakes."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.models.catalog import Species
from app.models.organization import Branch

pytestmark = pytest.mark.integration


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


async def test_requires_authentication(auth_client):
    response = await auth_client.get("/api/v1/plants")
    assert response.status_code == 401


async def test_register_plant(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read", "plants:write"])

    response = await ac.post(
        "/api/v1/plants", json={"branch_id": str(branch.id), "species_id": str(species.id), "common_label": "Fig #1"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["common_label"] == "Fig #1"
    assert body["status"] == "in_production"
    assert body["qr_code_token"].startswith("NVA-")
    assert "age_days" in body


async def test_register_plant_denied_without_branch_scope(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    other_branch = _branch(nursery_id=org_id, name="Other")
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.branches.branches[other_branch.id] = other_branch
    harness.species.species[species.id] = species
    # Role scoped only to `branch`, not `other_branch`.
    harness.grant_role(user, org_id=org_id, role_code="horticulturist", permission_codes=["plants:read", "plants:write"], branch_ids=[branch.id])

    response = await ac.post(
        "/api/v1/plants", json={"branch_id": str(other_branch.id), "species_id": str(species.id)}
    )

    assert response.status_code == 403


async def test_register_plant_denied_without_write_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=["plants:read"])

    response = await ac.post("/api/v1/plants", json={"branch_id": str(branch.id), "species_id": str(species.id)})

    assert response.status_code == 403


async def test_bulk_register_plants(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read", "plants:write"])

    response = await ac.post(
        "/api/v1/plants/bulk",
        json={"plants": [{"branch_id": str(branch.id), "species_id": str(species.id)} for _ in range(3)]},
    )

    assert response.status_code == 201
    assert len(response.json()) == 3


async def test_list_plants_scoped_to_callers_org(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read", "plants:write"])

    own = await ac.post("/api/v1/plants", json={"branch_id": str(branch.id), "species_id": str(species.id)})
    other_branch = _branch(nursery_id=other_org_id)
    other_species = _species(nursery_id=other_org_id)
    harness.branches.branches[other_branch.id] = other_branch
    harness.species.species[other_species.id] = other_species
    other_plant = await harness.plant_service.register_plant(
        nursery_id=other_org_id, branch_id=other_branch.id, species_id=other_species.id, actor_user_id=uuid.uuid4()
    )

    response = await ac.get("/api/v1/plants")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total_items"] == 1
    assert body["items"][0]["id"] == own.json()["id"]
    assert all(item["id"] != str(other_plant.id) for item in body["items"])


async def test_get_plant_rejects_cross_tenant_access(authenticated_client, harness):
    ac, user = authenticated_client
    own_org_id = uuid.uuid4()
    foreign_org_id = uuid.uuid4()
    foreign_branch = _branch(nursery_id=foreign_org_id)
    foreign_species = _species(nursery_id=foreign_org_id)
    harness.branches.branches[foreign_branch.id] = foreign_branch
    harness.species.species[foreign_species.id] = foreign_species
    foreign_plant = await harness.plant_service.register_plant(
        nursery_id=foreign_org_id, branch_id=foreign_branch.id, species_id=foreign_species.id, actor_user_id=uuid.uuid4()
    )
    harness.grant_role(user, org_id=own_org_id, role_code="owner", permission_codes=["plants:read"])

    response = await ac.get(f"/api/v1/plants/{foreign_plant.id}")

    assert response.status_code == 403
    assert harness.denials.denials[-1].reason == "cross_tenant_org"


async def test_get_plant_by_qr_token(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read"])

    response = await ac.get(f"/api/v1/plants/qr/{plant.qr_code_token}")

    assert response.status_code == 200
    assert response.json()["id"] == str(plant.id)


async def test_update_plant_profile(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read", "plants:write"])

    response = await ac.patch(f"/api/v1/plants/{plant.id}", json={"common_label": "Renamed Fig"})

    assert response.status_code == 200
    assert response.json()["common_label"] == "Renamed Fig"


async def test_status_transition_legal(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read", "plants:write"])

    response = await ac.post(f"/api/v1/plants/{plant.id}/status", json={"to_status": "ready_for_sale"})

    assert response.status_code == 200
    assert response.json()["status"] == "ready_for_sale"


async def test_status_transition_illegal_rejected(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read", "plants:write"])

    # In Production -> Sold is not a legal direct transition (must pass through Ready for Sale).
    response = await ac.post(f"/api/v1/plants/{plant.id}/status", json={"to_status": "sold"})

    assert response.status_code == 409


async def test_move_plant_requires_transfer_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=["plants:read"])

    response = await ac.post(f"/api/v1/plants/{plant.id}/move", json={"to_zone": "greenhouse-2"})

    assert response.status_code == 403


async def test_move_plant_success_and_history(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read", "plants:transfer"])

    response = await ac.post(f"/api/v1/plants/{plant.id}/move", json={"to_zone": "outdoor-A"})
    assert response.status_code == 200
    assert response.json()["zone"] == "outdoor-A"

    history = await ac.get(f"/api/v1/plants/{plant.id}/movement-history")
    assert history.status_code == 200
    assert len(history.json()) == 1


async def test_archive_plant_requires_terminal_status(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read", "plants:write"])

    response = await ac.post(f"/api/v1/plants/{plant.id}/archive", json={})

    assert response.status_code == 409


async def test_upload_and_list_images(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read", "plants:write"])

    upload = await ac.post(f"/api/v1/plants/{plant.id}/images", json={"url": "https://cdn/img.jpg"})
    assert upload.status_code == 201

    listing = await ac.get(f"/api/v1/plants/{plant.id}/images")
    assert listing.status_code == 200
    assert len(listing.json()) == 1


async def test_get_plant_timeline(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read"])

    response = await ac.get(f"/api/v1/plants/{plant.id}/timeline")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total_items"] == 1
    assert body["items"][0]["event_type"] == "plant.registered"


# -----------------------------------------------------------------------
# Plant Description, Supplier & Purchase Info Tests
# -----------------------------------------------------------------------


async def test_register_plant_with_description(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read", "plants:write"])

    response = await ac.post(
        "/api/v1/plants",
        json={
            "branch_id": str(branch.id),
            "species_id": str(species.id),
            "common_label": "Fig with description",
            "description": "Heirloom variety, slow grower",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["description"] == "Heirloom variety, slow grower"


async def test_register_plant_with_purchase_info(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read", "plants:write"])

    response = await ac.post(
        "/api/v1/plants",
        json={
            "branch_id": str(branch.id),
            "species_id": str(species.id),
            "purchase_price": 12.50,
            "purchase_date": "2026-03-15T00:00:00Z",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["purchase_price"] == 12.50
    assert body["purchase_date"] is not None


async def test_update_plant_profile_with_description(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read", "plants:write"])

    response = await ac.patch(
        f"/api/v1/plants/{plant.id}",
        json={"description": "Updated description", "purchase_price": 25.00},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["description"] == "Updated description"
    assert body["purchase_price"] == 25.00


async def test_update_plant_profile_clear_description(authenticated_client, harness):
    """Sending description=None in a PATCH means 'leave unchanged' (the standard PATCH convention).
    To clear description, the caller must send a non-None value like an empty string."""
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id,
        actor_user_id=uuid.uuid4(), description="Keep me",
    )
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read", "plants:write"])

    # Sending null means "leave unchanged" -- description should remain.
    response = await ac.patch(
        f"/api/v1/plants/{plant.id}",
        json={"common_label": "Updated"},
    )

    assert response.status_code == 200
    assert response.json()["description"] == "Keep me"

    # Sending empty string should clear it.
    response = await ac.patch(
        f"/api/v1/plants/{plant.id}",
        json={"description": ""},
    )

    assert response.status_code == 200
    assert response.json()["description"] == ""


# -----------------------------------------------------------------------
# Suppliers Endpoint Tests
# -----------------------------------------------------------------------


async def test_list_suppliers_empty(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read"])

    response = await ac.get("/api/v1/suppliers")

    assert response.status_code == 200
    assert response.json() == []


async def test_list_suppliers_returns_seeded_suppliers(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["plants:read"])

    from app.models.purchasing import Supplier
    now = datetime.now(timezone.utc)
    supplier = Supplier(
        id=uuid.uuid4(), nursery_id=org_id, branch_id=branch.id,
        name="Test Growers Inc.", email="test@growers.com",
        created_at=now, updated_at=now,
    )
    harness.suppliers.suppliers[supplier.id] = supplier

    response = await ac.get("/api/v1/suppliers")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "Test Growers Inc."
