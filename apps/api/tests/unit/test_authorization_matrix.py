"""
Authorization matrix tests (Module 3's explicit "authorization matrix
tests" requirement) — verifies AuthorizationService enforces the exact
role/permission/scope combinations defined in
docs/ux/07-role-permission-matrix.md, not a re-derivation of that table.
The legend there: F = Full (org-wide), B = Branch-scoped (assigned
branch(es) only), R = Read-only (still full access to the *permission*,
just a read-only action code), - = No access.

This intentionally re-seeds each role's permission set by hand from the
matrix document (rather than depending on migration 0002's real seed data,
which nothing in this offline sandbox can load) -- what's under test is
"does the enforcement engine honor F/B/R/- correctly", not "did the seed
script run", which the Phase 5 readiness review already covered
separately.
"""
from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.unit

# A representative slice of docs/ux/07-role-permission-matrix.md's table
# (org:read/org:write are org-scoped; branch:read/employees:read are the
# rows that distinguish F from B). role_code -> set of granted permissions.
_MATRIX: dict[str, set[str]] = {
    "owner": {"org:read", "org:write", "branch:read", "employees:read"},
    "org_admin": {"org:read", "org:write", "branch:read", "employees:read"},
    "branch_manager": {"org:read", "branch:read", "employees:read"},  # org:write is "-"
    "horticulturist": {"org:read", "branch:read"},  # employees:read is "-"
    "sales_staff": {"org:read", "branch:read"},  # employees:read is "-"
}

# Which of these roles hold a branch-scoped (not org-wide) assignment,
# per the matrix's "Scope" column.
_BRANCH_SCOPED_ROLES = {"branch_manager", "horticulturist", "sales_staff"}

_ALL_ROLES = list(_MATRIX)
_ALL_PERMISSIONS = ["org:read", "org:write", "branch:read", "employees:read"]


@pytest.mark.parametrize("role_code", _ALL_ROLES)
@pytest.mark.parametrize("permission", _ALL_PERMISSIONS)
async def test_matrix_permission_grant_matches_the_documented_role(harness, role_code, permission):
    org_id = uuid.uuid4()
    my_branch = uuid.uuid4()
    user = await harness.create_user(email=f"{role_code}-{permission.replace(':', '-')}@example.com")
    branch_ids = [my_branch] if role_code in _BRANCH_SCOPED_ROLES else None
    harness.grant_role(
        user, org_id=org_id, role_code=role_code, permission_codes=list(_MATRIX[role_code]), branch_ids=branch_ids
    )

    decision = await harness.authorization_service.authorize(
        user=user, permission=permission, target_nursery_id=org_id, target_branch_id=my_branch
    )

    expected_allowed = permission in _MATRIX[role_code]
    assert decision.allowed is expected_allowed, (
        f"role={role_code} permission={permission} expected allowed={expected_allowed}, "
        f"got {decision.allowed} ({decision.reason})"
    )


@pytest.mark.parametrize("role_code", sorted(_BRANCH_SCOPED_ROLES))
async def test_matrix_branch_scoped_roles_cannot_reach_a_foreign_branch(harness, role_code):
    org_id = uuid.uuid4()
    my_branch = uuid.uuid4()
    foreign_branch = uuid.uuid4()
    user = await harness.create_user(email=f"{role_code}-foreign-branch@example.com")
    harness.grant_role(
        user,
        org_id=org_id,
        role_code=role_code,
        permission_codes=list(_MATRIX[role_code]),
        branch_ids=[my_branch],
    )

    decision = await harness.authorization_service.authorize(
        user=user, permission="branch:read", target_nursery_id=org_id, target_branch_id=foreign_branch
    )

    assert decision.allowed is False


@pytest.mark.parametrize("role_code", ["owner", "org_admin"])
async def test_matrix_org_wide_roles_reach_every_branch(harness, role_code):
    org_id = uuid.uuid4()
    some_branch = uuid.uuid4()
    another_branch = uuid.uuid4()
    user = await harness.create_user(email=f"{role_code}-any-branch@example.com")
    harness.grant_role(user, org_id=org_id, role_code=role_code, permission_codes=list(_MATRIX[role_code]))

    for branch in (some_branch, another_branch):
        decision = await harness.authorization_service.authorize(
            user=user, permission="branch:read", target_nursery_id=org_id, target_branch_id=branch
        )
        assert decision.allowed is True
