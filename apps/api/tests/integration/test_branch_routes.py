"""
Integration tests for Module 4's `/api/v1/branches` routes -- the worked
example of the fetch-then-authorize pattern for a flat resource with no
`nursery_id` in its path (see app/api/routes/branches.py's module
docstring). Exercised through the real FastAPI app with
`authenticated_client` (tests/conftest.py) against `harness`'s in-memory
fakes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.db.enums import BranchStatus, NurseryStatus
from app.models.organization import Branch, Nursery

pytestmark = pytest.mark.integration


def _branch(*, nursery_id: uuid.UUID, name: str = "Main Branch", status: BranchStatus = BranchStatus.ACTIVE) -> Branch:
    now = datetime.now(timezone.utc)
    return Branch(
        id=uuid.uuid4(),
        nursery_id=nursery_id,
        name=name,
        address_line1="1 Main St",
        city="Austin",
        country="US",
        timezone="America/Chicago",
        status=status,
        created_at=now,
        updated_at=now,
    )


async def test_requires_authentication(auth_client):
    response = await auth_client.get("/api/v1/branches")
    assert response.status_code == 401


async def test_list_branches_scoped_to_callers_org(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    own_branch = _branch(nursery_id=org_id)
    other_branch = _branch(nursery_id=other_org_id)
    harness.branches.branches[own_branch.id] = own_branch
    harness.branches.branches[other_branch.id] = other_branch
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["branch:read"])

    response = await ac.get("/api/v1/branches")

    assert response.status_code == 200
    ids = {b["id"] for b in response.json()}
    assert ids == {str(own_branch.id)}


async def test_list_branches_denied_without_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=["sales:read"])

    response = await ac.get("/api/v1/branches")

    assert response.status_code == 403


async def test_create_branch_in_callers_org(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["branch:read", "branch:write"])
    harness.nurseries.nurseries[org_id] = Nursery(id=org_id, name="N", contact_email="n@x.com", status=NurseryStatus.ACTIVE)

    response = await ac.post(
        "/api/v1/branches",
        json={
            "name": "New Branch",
            "address_line1": "42 Elm St",
            "city": "Houston",
            "country": "US",
            "timezone": "America/Chicago",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "New Branch"
    assert body["nursery_id"] == str(org_id)


async def test_get_branch_rejects_cross_tenant_access(authenticated_client, harness):
    ac, user = authenticated_client
    own_org_id = uuid.uuid4()
    foreign_org_id = uuid.uuid4()
    foreign_branch = _branch(nursery_id=foreign_org_id)
    harness.branches.branches[foreign_branch.id] = foreign_branch
    harness.grant_role(user, org_id=own_org_id, role_code="owner", permission_codes=["branch:read"])

    response = await ac.get(f"/api/v1/branches/{foreign_branch.id}")

    assert response.status_code == 403
    assert harness.denials.denials[-1].reason == "cross_tenant_org"


async def test_get_branch_not_found(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["branch:read"])

    response = await ac.get(f"/api/v1/branches/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_branch_manager_can_read_own_branch(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.grant_role(
        user, org_id=org_id, role_code="branch_manager", permission_codes=["branch:read"], branch_ids=[branch.id]
    )

    response = await ac.get(f"/api/v1/branches/{branch.id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(branch.id)


async def test_update_branch(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["branch:read", "branch:write"])

    response = await ac.patch(f"/api/v1/branches/{branch.id}", json={"city": "Round Rock"})

    assert response.status_code == 200
    assert response.json()["city"] == "Round Rock"


async def test_update_branch_denied_for_horticulturist(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.grant_role(
        user, org_id=org_id, role_code="horticulturist", permission_codes=["branch:read"], branch_ids=[branch.id]
    )

    response = await ac.patch(f"/api/v1/branches/{branch.id}", json={"city": "Round Rock"})

    assert response.status_code == 403


async def test_archive_branch(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["branch:read", "branch:delete"])

    response = await ac.delete(f"/api/v1/branches/{branch.id}")

    assert response.status_code == 200
    assert response.json()["status"] == "inactive"


async def test_archive_branch_denied_without_delete_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.grant_role(user, org_id=org_id, role_code="branch_manager", permission_codes=["branch:read", "branch:write"])

    response = await ac.delete(f"/api/v1/branches/{branch.id}")

    assert response.status_code == 403
