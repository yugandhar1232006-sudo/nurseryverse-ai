"""
Integration tests for Module 4's `/api/v1/orgs` routes -- exercised through
the real FastAPI app with `authenticated_client`/`auth_client`
(tests/conftest.py), which override the Module 2-4 service dependencies to
run against `harness`'s in-memory fakes. No live database required.
"""
from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


async def test_requires_authentication(auth_client):
    response = await auth_client.post("/api/v1/orgs", json={"name": "Acme", "contact_email": "a@acme.com"})
    assert response.status_code == 401


async def test_create_org_makes_caller_the_owner(authenticated_client, harness):
    ac, user = authenticated_client
    harness.seed_system_role("owner", ["org:read", "org:write", "org:delete"])

    response = await ac.post(
        "/api/v1/orgs", json={"name": "Green Thumb Nursery", "contact_email": "owner@greenthumb.com"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Green Thumb Nursery"
    assert body["status"] == "active"

    access = await harness.permission_service.resolve_for_user(user.id)
    assert access.org_id == uuid.UUID(body["id"])
    assert access.role_code == "owner"


async def test_create_org_rejects_caller_who_already_belongs_to_one(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["org:read"])

    response = await ac.post("/api/v1/orgs", json={"name": "Second Org", "contact_email": "x@x.com"})

    assert response.status_code == 409


async def test_get_org_requires_org_read_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.nurseries.nurseries[org_id] = _nursery(org_id)
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=["sales:read"])

    response = await ac.get(f"/api/v1/orgs/{org_id}")

    assert response.status_code == 403


async def test_get_org_rejects_cross_tenant_access(authenticated_client, harness):
    ac, user = authenticated_client
    own_org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    harness.nurseries.nurseries[other_org_id] = _nursery(other_org_id)
    harness.grant_role(user, org_id=own_org_id, role_code="owner", permission_codes=["org:read"])

    response = await ac.get(f"/api/v1/orgs/{other_org_id}")

    assert response.status_code == 403
    assert harness.denials.denials[-1].reason == "cross_tenant_org"


async def test_owner_can_read_and_update_their_own_org(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.nurseries.nurseries[org_id] = _nursery(org_id, name="Old Name")
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["org:read", "org:write"])

    get_response = await ac.get(f"/api/v1/orgs/{org_id}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Old Name"

    patch_response = await ac.patch(f"/api/v1/orgs/{org_id}", json={"name": "New Name"})
    assert patch_response.status_code == 200
    assert patch_response.json()["name"] == "New Name"


async def test_org_admin_cannot_archive_only_owner_can(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.nurseries.nurseries[org_id] = _nursery(org_id)
    harness.grant_role(user, org_id=org_id, role_code="org_admin", permission_codes=["org:read", "org:write"])

    response = await ac.post(f"/api/v1/orgs/{org_id}/archive")

    assert response.status_code == 403


async def test_owner_can_archive_org(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.nurseries.nurseries[org_id] = _nursery(org_id)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["org:read", "org:delete"])

    response = await ac.post(f"/api/v1/orgs/{org_id}/archive")

    assert response.status_code == 200
    assert response.json()["status"] == "archived"


async def test_org_settings_round_trip(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.nurseries.nurseries[org_id] = _nursery(org_id)
    harness.nurseries.settings[org_id] = _settings(org_id)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["org:read", "org:write"])

    get_response = await ac.get(f"/api/v1/orgs/{org_id}/settings")
    assert get_response.status_code == 200
    assert get_response.json()["default_currency"] == "INR"

    patch_response = await ac.patch(f"/api/v1/orgs/{org_id}/settings", json={"currency": "EUR"})
    assert patch_response.status_code == 200
    assert patch_response.json()["default_currency"] == "EUR"


async def test_transfer_ownership_requires_org_delete_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="org_admin", permission_codes=["org:write"])  # no org:delete

    response = await ac.post(
        f"/api/v1/orgs/{org_id}/transfer-ownership", json={"new_owner_user_id": str(uuid.uuid4())}
    )

    assert response.status_code == 403


async def test_owner_can_transfer_ownership_to_an_existing_employee(authenticated_client, harness):
    ac, current_owner = authenticated_client
    org_id = uuid.uuid4()
    owner_role = harness.seed_system_role("owner", ["org:read", "org:delete"])
    admin_role = harness.seed_system_role("org_admin", ["org:read"])
    harness.grant_role(current_owner, org_id=org_id, role_code="owner", permission_codes=["org:read", "org:delete"])
    # Re-key the assignment onto the seeded owner role id so
    # EmployeeService.transfer_ownership's role-code check finds it.
    harness.permissions.role_assignments[current_owner.id].role_id = owner_role.id

    new_owner = await harness.create_user(email="successor@example.com")
    new_assignment = harness.grant_role(new_owner, org_id=org_id, role_code="org_admin", permission_codes=["org:read"])
    new_assignment.role_id = admin_role.id

    response = await ac.post(
        f"/api/v1/orgs/{org_id}/transfer-ownership", json={"new_owner_user_id": str(new_owner.id)}
    )

    assert response.status_code == 204
    assert harness.permissions.role_assignments[new_owner.id].role_id == owner_role.id
    assert harness.permissions.role_assignments[current_owner.id].role_id == admin_role.id


def _nursery(org_id: uuid.UUID, *, name: str = "Test Nursery"):
    from datetime import datetime, timezone

    from app.db.enums import NurseryStatus
    from app.models.organization import Nursery

    now = datetime.now(timezone.utc)
    # Pre-seeded directly into the fake's dict (not via `.add()`), so
    # `created_at`/`updated_at` (server-generated in production -- see
    # `_backfill_timestamps`'s docstring in tests/fakes/repositories.py)
    # are set explicitly here rather than relying on that backfill.
    return Nursery(
        id=org_id, name=name, contact_email="n@example.com", status=NurseryStatus.ACTIVE,
        created_at=now, updated_at=now,
    )


def _settings(org_id: uuid.UUID):
    from app.models.platform import OrgSettings

    return OrgSettings(
        id=uuid.uuid4(), nursery_id=org_id, default_currency="INR", default_timezone="UTC", sms_enabled=False
    )
