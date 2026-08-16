"""
Unit tests for app/api/deps.py's `get_tenant_context` and `get_scoped_db`
-- the two dependencies that resolve a request's org/branch scope and
wire it into Postgres's `app.current_org_id` RLS session variable
(migrations/versions/0003_row_level_security.py). `get_scoped_db` is
exercised here with a minimal fake `AsyncSession` (records what it was
asked to `execute`, doesn't touch a real database) so the "org id present
-> issues set_config" / "org id absent -> issues nothing" branches are
both covered without needing the live Postgres this sandbox doesn't have.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import pytest

from app.api.deps import TenantContext, get_scoped_db, get_tenant_context
from app.core.context import current_branch_ids_var, current_org_id_var, current_user_id_var

pytestmark = pytest.mark.unit


@dataclass
class _FakeSession:
    executed: list[tuple] = field(default_factory=list)

    async def execute(self, statement, params=None):
        self.executed.append((str(statement), params))
        return None


async def test_get_tenant_context_resolves_access_and_populates_contextvars(harness):
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    user = await harness.create_user(email="tenant-ctx@example.com")
    harness.grant_role(
        user, org_id=org_id, role_code="branch_manager", permission_codes=["branch:read"], branch_ids=[branch_id]
    )

    tenant = await get_tenant_context(user=user, permission_service=harness.permission_service)

    assert isinstance(tenant, TenantContext)
    assert tenant.org_id == org_id
    assert tenant.branch_ids == (branch_id,)
    assert tenant.role_code == "branch_manager"
    assert tenant.permissions == ("branch:read",)
    assert tenant.is_org_wide() is False
    assert current_user_id_var.get() == user.id
    assert current_org_id_var.get() == org_id
    assert current_branch_ids_var.get() == (branch_id,)


async def test_get_tenant_context_for_org_wide_role(harness):
    org_id = uuid.uuid4()
    user = await harness.create_user(email="tenant-ctx-orgwide@example.com")
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["org:read"])

    tenant = await get_tenant_context(user=user, permission_service=harness.permission_service)

    assert tenant.is_org_wide() is True
    assert tenant.branch_ids == ()


async def test_get_scoped_db_issues_set_config_when_org_id_present():
    session = _FakeSession()
    tenant = TenantContext(org_id=uuid.uuid4(), branch_ids=(), role_code="owner", permissions=("org:read",))

    agen = get_scoped_db(db=session, tenant=tenant)
    yielded = await agen.__anext__()

    assert yielded is session
    assert len(session.executed) == 1
    statement, params = session.executed[0]
    assert "set_config" in statement
    assert params == {"val": str(tenant.org_id)}
    await agen.aclose()


async def test_get_scoped_db_issues_nothing_when_org_id_is_none():
    session = _FakeSession()
    tenant = TenantContext(org_id=None, branch_ids=(), role_code=None, permissions=())

    agen = get_scoped_db(db=session, tenant=tenant)
    yielded = await agen.__anext__()

    assert yielded is session
    assert session.executed == []
    await agen.aclose()
