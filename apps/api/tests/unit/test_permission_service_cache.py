"""
Unit tests for app/services/permission_service.py's Module 3 additions:
caching (resolve/hit/invalidate), the org-wide/branch-scoped
`is_org_wide()` semantics, and the multi-role-ready `resolve_all_for_user`.
Uses a bare `FakePermissionRepository` + `InMemoryCache` directly (not the
`harness` fixture) so the cache-hit/miss assertions aren't entangled with
AuthService's unrelated state.
"""
from __future__ import annotations

import uuid

import pytest

from app.core.cache import InMemoryCache
from app.models.identity import Permission, Role, RoleAssignment
from app.services.permission_service import PermissionService, ResolvedAccess
from tests.fakes.repositories import FakePermissionRepository

pytestmark = pytest.mark.unit


def _seed_role(repo: FakePermissionRepository, *, user_id, org_id, role_code, permission_codes, branch_ids=None):
    role_id = uuid.uuid4()
    permissions = [
        Permission(id=uuid.uuid4(), code=code, module=code.split(":")[0], action=code.split(":")[1], description=code)
        for code in permission_codes
    ]
    role = Role(id=role_id, nursery_id=org_id, code=role_code, name=role_code, is_system_role=True)
    role.permissions = permissions
    repo.roles[role_id] = role

    assignment = RoleAssignment(id=uuid.uuid4(), user_id=user_id, nursery_id=org_id, role_id=role_id)
    repo.role_assignments[user_id] = assignment
    if branch_ids:
        repo.branch_scopes[assignment.id] = list(branch_ids)
    return assignment


# ----------------------------------------------------------------------
# ResolvedAccess semantics
# ----------------------------------------------------------------------
def test_is_org_wide_true_when_no_branch_scopes():
    access = ResolvedAccess(org_id=uuid.uuid4(), role_id=uuid.uuid4(), role_code="owner", branch_ids=[], permissions=[])
    assert access.is_org_wide() is True


def test_is_org_wide_false_when_branch_scopes_present():
    access = ResolvedAccess(
        org_id=uuid.uuid4(), role_id=uuid.uuid4(), role_code="branch_manager", branch_ids=[uuid.uuid4()], permissions=[]
    )
    assert access.is_org_wide() is False


def test_resolved_access_round_trips_through_json():
    original = ResolvedAccess(
        org_id=uuid.uuid4(),
        role_id=uuid.uuid4(),
        role_code="branch_manager",
        branch_ids=[uuid.uuid4(), uuid.uuid4()],
        permissions=["branch:read", "plants:read"],
    )
    restored = ResolvedAccess.from_json(original.to_json())
    assert restored == original


def test_resolved_access_with_no_org_round_trips():
    original = ResolvedAccess(org_id=None, role_id=None, role_code=None, branch_ids=[], permissions=[])
    restored = ResolvedAccess.from_json(original.to_json())
    assert restored == original


# ----------------------------------------------------------------------
# Caching
# ----------------------------------------------------------------------
async def test_uncached_service_always_hits_the_repository():
    repo = FakePermissionRepository()
    user_id = uuid.uuid4()
    _seed_role(repo, user_id=user_id, org_id=uuid.uuid4(), role_code="owner", permission_codes=["org:read"])
    service = PermissionService(repo)  # no cache -- Module 2's original construction still works

    access = await service.resolve_for_user(user_id)

    assert access.permissions == ["org:read"]


async def test_cache_hit_avoids_a_second_repository_call():
    repo = FakePermissionRepository()
    user_id = uuid.uuid4()
    _seed_role(repo, user_id=user_id, org_id=uuid.uuid4(), role_code="owner", permission_codes=["org:read"])
    cache = InMemoryCache()
    service = PermissionService(repo, cache=cache)

    first = await service.resolve_for_user(user_id)
    # Mutate the repo's underlying data after the first resolution -- if
    # the second call actually hit the cache (not the repo), it must still
    # see the *original* permission set, not this new one.
    repo.role_assignments.pop(user_id)
    second = await service.resolve_for_user(user_id)

    assert second == first
    assert second.permissions == ["org:read"]


async def test_invalidate_user_forces_a_fresh_resolution():
    repo = FakePermissionRepository()
    user_id = uuid.uuid4()
    _seed_role(repo, user_id=user_id, org_id=uuid.uuid4(), role_code="owner", permission_codes=["org:read"])
    cache = InMemoryCache()
    service = PermissionService(repo, cache=cache)

    await service.resolve_for_user(user_id)  # warm the cache
    repo.role_assignments.pop(user_id)  # simulate a revoked role assignment
    await service.invalidate_user(user_id)
    after = await service.resolve_for_user(user_id)

    assert after.permissions == []
    assert after.org_id is None


async def test_user_with_no_role_assignment_resolves_to_empty_access():
    repo = FakePermissionRepository()
    service = PermissionService(repo)

    access = await service.resolve_for_user(uuid.uuid4())

    assert access.org_id is None
    assert access.permissions == []
    assert access.branch_ids == []


# ----------------------------------------------------------------------
# Multi-role future-readiness
# ----------------------------------------------------------------------
async def test_resolve_all_for_user_returns_one_entry_for_v1s_single_assignment():
    repo = FakePermissionRepository()
    user_id = uuid.uuid4()
    _seed_role(repo, user_id=user_id, org_id=uuid.uuid4(), role_code="owner", permission_codes=["org:read"])
    service = PermissionService(repo)

    results = await service.resolve_all_for_user(user_id)

    assert len(results) == 1
    assert results[0].permissions == ["org:read"]


async def test_resolve_all_for_user_returns_empty_list_for_unassigned_user():
    repo = FakePermissionRepository()
    service = PermissionService(repo)

    results = await service.resolve_all_for_user(uuid.uuid4())

    assert results == []
