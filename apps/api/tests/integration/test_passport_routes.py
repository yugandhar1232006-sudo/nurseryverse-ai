"""
Integration tests for Module 9's Plant Passport & QR Intelligence REST
API (app/api/routes/passport.py) -- internal authenticated management
routes AND the public, unauthenticated `/public/passport/{token}` /
`/public/qr/{token}` surface. The public-route tests are this module's
"Public Token Security Tests" / "QR Validation Tests": forged, tampered,
and nonexistent tokens must all be rejected identically, and no
authentication header is ever sent to those two endpoints.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.integration


def _species_and_branch(harness, *, org_id):
    from app.models.catalog import Species
    from app.models.organization import Branch

    now = datetime.now(timezone.utc)
    branch = Branch(
        id=uuid.uuid4(), nursery_id=org_id, name="Main", address_line1="123 St", city="Springfield",
        country="US", timezone="UTC", created_at=now, updated_at=now,
    )
    species = Species(
        id=uuid.uuid4(), nursery_id=org_id, category_id=uuid.uuid4(), common_name="Fig",
        botanical_name="Ficus lyrata", created_at=now, updated_at=now,
    )
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    return branch, species


# ------------------------------------------------------------------
# Internal, authenticated management routes
# ------------------------------------------------------------------


async def test_generate_passport_requires_auth(auth_client):
    response = await auth_client.post(f"/api/v1/plants/{uuid.uuid4()}/passports", json={})
    assert response.status_code == 401


async def test_generate_and_get_passport(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch, species = _species_and_branch(harness, org_id=org_id)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["passport:generate", "passport:read"])
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )

    response = await ac.post(f"/api/v1/plants/{plant.id}/passports", json={})
    assert response.status_code == 201
    passport = response.json()
    assert passport["version"] == 1
    assert passport["public_url"].endswith(passport["public_token"])
    assert "plant_id" in passport  # internal view is entitled to see this

    get_response = await ac.get(f"/api/v1/passports/{passport['id']}")
    assert get_response.status_code == 200

    list_response = await ac.get(f"/api/v1/plants/{plant.id}/passports")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


async def test_generate_passport_rejects_cross_tenant_plant(authenticated_client, harness):
    ac, user = authenticated_client
    own_org_id = uuid.uuid4()
    foreign_org_id = uuid.uuid4()
    branch, species = _species_and_branch(harness, org_id=foreign_org_id)
    foreign_plant = await harness.plant_service.register_plant(
        nursery_id=foreign_org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    harness.grant_role(user, org_id=own_org_id, role_code="owner", permission_codes=["passport:generate"])

    response = await ac.post(f"/api/v1/plants/{foreign_plant.id}/passports", json={})
    assert response.status_code == 403
    assert harness.denials.denials[-1].reason == "cross_tenant_org"


async def test_passport_report(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch, species = _species_and_branch(harness, org_id=org_id)
    harness.grant_role(
        user, org_id=org_id, role_code="owner", permission_codes=["passport:generate", "reports:read"]
    )
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    await ac.post(f"/api/v1/plants/{plant.id}/passports", json={})

    response = await ac.get("/api/v1/passports/reports/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["total_passports"] == 1
    assert body["distinct_plants_with_passport"] == 1


# ------------------------------------------------------------------
# Public, unauthenticated Plant Passport / QR Intelligence surface
# ------------------------------------------------------------------


async def test_public_passport_lookup_requires_no_authentication(authenticated_client, harness):
    """No auth header is sent at all -- proves the public route doesn't secretly require one."""
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch, species = _species_and_branch(harness, org_id=org_id)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["passport:generate"])
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    generate_response = await ac.post(f"/api/v1/plants/{plant.id}/passports", json={})
    token = generate_response.json()["public_token"]

    public_response = await ac.get(f"/api/v1/public/passport/{token}", headers={"Authorization": ""})
    assert public_response.status_code == 200
    body = public_response.json()
    assert "id" not in body
    assert "plant_id" not in body
    assert "nursery_id" not in body
    assert "branch_id" not in body
    assert body["passport_number"].startswith("NVA-PP-")


async def test_public_qr_scan_returns_all_required_sections(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch, species = _species_and_branch(harness, org_id=org_id)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["passport:generate"])
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    generate_response = await ac.post(f"/api/v1/plants/{plant.id}/passports", json={})
    token = generate_response.json()["public_token"]

    scan_response = await ac.get(f"/api/v1/public/qr/{token}")
    assert scan_response.status_code == 200
    body = scan_response.json()
    for key in (
        "passport", "care_instructions", "water_schedule", "fertilizer_schedule",
        "health_status", "growth_timeline", "ai_recommendations",
    ):
        assert key in body
    assert "nursery_id" not in body["passport"]
    assert "plant_id" not in body["passport"]


async def test_public_passport_lookup_rejects_nonexistent_token(auth_client):
    response = await auth_client.get("/api/v1/public/passport/does-not-exist")
    assert response.status_code == 404


async def test_public_passport_lookup_rejects_forged_token(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch, species = _species_and_branch(harness, org_id=org_id)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["passport:generate"])
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    generate_response = await ac.post(f"/api/v1/plants/{plant.id}/passports", json={})
    token = generate_response.json()["public_token"]

    forged = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")
    response = await ac.get(f"/api/v1/public/passport/{forged}")
    assert response.status_code == 404


async def test_public_qr_scan_rejects_tampered_token(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch, species = _species_and_branch(harness, org_id=org_id)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["passport:generate"])
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    generate_response = await ac.post(f"/api/v1/plants/{plant.id}/passports", json={})
    token = generate_response.json()["public_token"]
    mid = len(token) // 2
    swapped = "x" if token[mid] != "x" else "y"
    tampered = token[:mid] + swapped + token[mid + 1 :]

    response = await ac.get(f"/api/v1/public/qr/{tampered}")
    assert response.status_code == 404


async def test_public_endpoints_leak_no_more_detail_for_forged_vs_missing_tokens(auth_client):
    """The module's own 'no oracle' requirement: a forged-looking token and a straight-up nonexistent one must produce the identical error."""
    missing_response = await auth_client.get(f"/api/v1/public/passport/{'a' * 70}")
    nonsense_response = await auth_client.get("/api/v1/public/passport/not-base64-url-safe-at-all!!")
    assert missing_response.status_code == 404
    assert nonsense_response.status_code == 404
    assert missing_response.json()["error"] == nonsense_response.json()["error"]
