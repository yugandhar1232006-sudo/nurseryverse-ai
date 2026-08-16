"""
Integration tests for Module 4's `/api/v1/employees` routes -- invite,
list, get/update, transfer-branches, deactivate -- exercised through the
real FastAPI app with `authenticated_client` (tests/conftest.py) against
`harness`'s in-memory fakes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.db.enums import BranchStatus, EmployeeStatus
from app.models.organization import Branch, Employee

pytestmark = pytest.mark.integration


def _employee(*, nursery_id: uuid.UUID, user_id: uuid.UUID, status: EmployeeStatus = EmployeeStatus.ACTIVE) -> Employee:
    now = datetime.now(timezone.utc)
    return Employee(
        id=uuid.uuid4(), nursery_id=nursery_id, user_id=user_id, status=status, created_at=now, updated_at=now
    )


async def test_requires_authentication(auth_client):
    response = await auth_client.get("/api/v1/employees")
    assert response.status_code == 401


async def test_list_employees_scoped_to_callers_org(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    own_employee = _employee(nursery_id=org_id, user_id=uuid.uuid4())
    other_employee = _employee(nursery_id=other_org_id, user_id=uuid.uuid4())
    harness.employees.employees[own_employee.id] = own_employee
    harness.employees.employees[other_employee.id] = other_employee
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["employees:read"])

    response = await ac.get("/api/v1/employees")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total_items"] == 1
    assert body["items"][0]["id"] == str(own_employee.id)


async def test_list_employees_denied_without_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=["sales:read"])

    response = await ac.get("/api/v1/employees")

    assert response.status_code == 403


async def test_invite_employee(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.seed_system_role("horticulturist", ["plants:read"])
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["employees:read", "employees:write"])

    response = await ac.post(
        "/api/v1/employees/invite",
        json={"email": "newhire@example.com", "role_code": "horticulturist", "branch_ids": []},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "newhire@example.com"
    assert len(harness.email_sender.sent) == 1


async def test_invite_employee_denied_without_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.seed_system_role("horticulturist", ["plants:read"])
    harness.grant_role(user, org_id=org_id, role_code="horticulturist", permission_codes=["plants:read"])

    response = await ac.post(
        "/api/v1/employees/invite",
        json={"email": "newhire@example.com", "role_code": "horticulturist", "branch_ids": []},
    )

    assert response.status_code == 403


async def test_invite_unknown_role_returns_422(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["employees:read", "employees:write"])

    response = await ac.post(
        "/api/v1/employees/invite",
        json={"email": "newhire@example.com", "role_code": "not_a_real_role", "branch_ids": []},
    )

    assert response.status_code == 422


async def test_get_employee_rejects_cross_tenant_access(authenticated_client, harness):
    ac, user = authenticated_client
    own_org_id = uuid.uuid4()
    foreign_org_id = uuid.uuid4()
    foreign_employee = _employee(nursery_id=foreign_org_id, user_id=uuid.uuid4())
    harness.employees.employees[foreign_employee.id] = foreign_employee
    harness.grant_role(user, org_id=own_org_id, role_code="owner", permission_codes=["employees:read"])

    response = await ac.get(f"/api/v1/employees/{foreign_employee.id}")

    assert response.status_code == 403
    assert harness.denials.denials[-1].reason == "cross_tenant_org"


async def test_update_employee_profile(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    employee = _employee(nursery_id=org_id, user_id=uuid.uuid4())
    harness.employees.employees[employee.id] = employee
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["employees:read", "employees:write"])

    response = await ac.patch(f"/api/v1/employees/{employee.id}", json={"department": "Horticulture", "position": "Lead"})

    assert response.status_code == 200
    body = response.json()
    assert body["department"] == "Horticulture"
    assert body["position"] == "Lead"


async def test_transfer_branches(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    target_user_id = uuid.uuid4()
    employee = _employee(nursery_id=org_id, user_id=target_user_id)
    harness.employees.employees[employee.id] = employee

    role = harness.seed_system_role("branch_manager", ["branch:read"])
    harness.permissions.role_assignments[target_user_id] = type(
        "Assignment", (), {"id": uuid.uuid4(), "user_id": target_user_id, "nursery_id": org_id, "role_id": role.id}
    )()

    new_branch_id = uuid.uuid4()
    harness.branches.branches[new_branch_id] = Branch(
        id=new_branch_id, nursery_id=org_id, name="B2", address_line1="x", city="y", country="US",
        timezone="America/Chicago", status=BranchStatus.ACTIVE,
    )

    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["employees:read", "employees:write"])

    response = await ac.post(
        f"/api/v1/employees/{employee.id}/transfer-branches", json={"branch_ids": [str(new_branch_id)]}
    )

    assert response.status_code == 200
    access = await harness.permission_service.resolve_for_user(target_user_id)
    assert access.branch_ids == [new_branch_id]


async def test_deactivate_employee(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    target_user_id = uuid.uuid4()
    employee = _employee(nursery_id=org_id, user_id=target_user_id)
    harness.employees.employees[employee.id] = employee

    role = harness.seed_system_role("sales_staff", ["sales:read"])
    harness.permissions.role_assignments[target_user_id] = type(
        "Assignment", (), {"id": uuid.uuid4(), "user_id": target_user_id, "nursery_id": org_id, "role_id": role.id}
    )()

    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["employees:read", "employees:delete"])

    response = await ac.post(f"/api/v1/employees/{employee.id}/deactivate", json={"reason": "resigned"})

    assert response.status_code == 200
    assert response.json()["status"] == "deactivated"

    access = await harness.permission_service.resolve_for_user(target_user_id)
    assert access.org_id is None


async def test_deactivate_employee_denied_without_delete_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    employee = _employee(nursery_id=org_id, user_id=uuid.uuid4())
    harness.employees.employees[employee.id] = employee
    harness.grant_role(user, org_id=org_id, role_code="branch_manager", permission_codes=["employees:read", "employees:write"])

    response = await ac.post(f"/api/v1/employees/{employee.id}/deactivate", json={})

    assert response.status_code == 403
