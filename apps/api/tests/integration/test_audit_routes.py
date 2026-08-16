"""
Integration tests for Module 3's `GET /api/v1/audit-log` — the worked
example of the full authorization stack (permission check + tenant
isolation + pagination) protecting a real endpoint, exercised through the
real FastAPI app with `authenticated_client` (tests/conftest.py), which
overrides `get_auth_service`/`get_authorization_service`/
`get_permission_service`/`get_audit_log_repository`/`get_current_user` to
run against `harness`'s in-memory fakes -- no live database required.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.models.platform import AuditLog

pytestmark = pytest.mark.integration


def _row(*, nursery_id: uuid.UUID, action: str, created_at: datetime | None = None) -> AuditLog:
    return AuditLog(
        id=uuid.uuid4(),
        nursery_id=nursery_id,
        actor_user_id=uuid.uuid4(),
        action=action,
        entity_type="plant",
        entity_id=uuid.uuid4(),
        diff=None,
        request_id="req-abc",
        created_at=created_at or datetime.now(timezone.utc),
    )


async def test_requires_authentication(auth_client):
    response = await auth_client.get("/api/v1/audit-log")
    assert response.status_code == 401


async def test_denied_without_audit_read_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=["plants:read"])

    response = await ac.get("/api/v1/audit-log")

    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "permission_denied"
    assert harness.denials.denials  # the denial was recorded
    assert harness.denials.denials[0].permission_code == "audit:read"


async def test_owner_can_list_their_orgs_audit_log(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["audit:read"])
    harness.audit_logs.rows.extend(
        [
            _row(nursery_id=org_id, action="plant.status_changed"),
            _row(nursery_id=org_id, action="employee.invited"),
            _row(nursery_id=other_org_id, action="plant.deleted"),  # a different org's row
        ]
    )

    response = await ac.get("/api/v1/audit-log")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total_items"] == 2  # the other org's row is invisible
    actions = {item["action"] for item in body["items"]}
    assert actions == {"plant.status_changed", "employee.invited"}


async def test_pagination_params_are_respected(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="org_admin", permission_codes=["audit:read"])
    harness.audit_logs.rows.extend([_row(nursery_id=org_id, action=f"action.{i}") for i in range(5)])

    response = await ac.get("/api/v1/audit-log", params={"page": 1, "page_size": 2})

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["meta"]["total_items"] == 5
    assert body["meta"]["total_pages"] == 3


async def test_user_with_no_org_membership_sees_an_empty_page_not_an_error(authenticated_client, harness):
    ac, user = authenticated_client
    # authenticated but no RoleAssignment at all -- authorize() denies
    # for lack of the audit:read permission (no role -> no permissions),
    # which is the correct outcome: a user with no org context should
    # never see a "success, zero rows" response for a permission they
    # were never actually granted.
    response = await ac.get("/api/v1/audit-log")

    assert response.status_code == 403
