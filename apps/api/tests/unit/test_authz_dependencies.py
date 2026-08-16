"""
Unit tests for Module 3's FastAPI dependency factories
(app/api/deps.py's `require_permission`/`require_org_match`/
`require_branch_match`/`require_ownership_or_permission`). These are the
"Authorization Middleware" requirement's concrete implementation: route
protection, resource-level authorization, organization isolation, and
branch isolation, respectively.

Called directly (not through a real FastAPI route) with a minimal
duck-typed `_FakeRequest` standing in for Starlette's `Request` -- the
dependency bodies only ever read `.path_params`, `.headers.get(...)`,
`.client`, and `.state.request_id`, none of which requires the real
Starlette object. `get_current_user`/`get_authorization_service` are
supplied directly as arguments rather than resolved through FastAPI's DI
container, which is exactly how FastAPI itself calls a dependency once its
sub-dependencies are resolved -- this is testing the same code path a real
request runs, just without the ASGI machinery around it (that machinery,
and that these functions are wired to real routes correctly, is what
tests/integration/test_audit_routes.py additionally covers for
`require_permission`).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import pytest

from app.api.deps import (
    require_branch_match,
    require_ownership_or_permission,
    require_org_match,
    require_permission,
)
from app.core.exceptions import PermissionDeniedError

pytestmark = pytest.mark.unit


@dataclass
class _FakeState:
    request_id: str | None = "req-dep-test"


@dataclass
class _FakeRequest:
    path_params: dict = field(default_factory=dict)
    headers: dict = field(default_factory=dict)
    client = None
    state: _FakeState = field(default_factory=_FakeState)

    def __post_init__(self) -> None:
        # Starlette's Request.headers supports .get(...) case-insensitively;
        # a plain dict with lowercase keys is enough for what deps.py reads.
        class _Headers(dict):
            def get(self, key, default=None):  # noqa: D102
                return super().get(key.lower(), default)

        self.headers = _Headers(self.headers)


# ----------------------------------------------------------------------
# require_permission
# ----------------------------------------------------------------------
async def test_require_permission_allows_when_granted(harness):
    org_id = uuid.uuid4()
    user = await harness.create_user(email="dep-perm-allow@example.com")
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["audit:read"])
    dependency = require_permission("audit:read")

    decision = await dependency(request=_FakeRequest(), user=user, authz=harness.authorization_service)

    assert decision.allowed is True


async def test_require_permission_raises_permission_denied_when_missing(harness):
    user = await harness.create_user(email="dep-perm-deny@example.com")
    dependency = require_permission("audit:read")

    with pytest.raises(PermissionDeniedError):
        await dependency(request=_FakeRequest(), user=user, authz=harness.authorization_service)

    assert harness.denials.denials  # the FastAPI-facing wrapper still records the denial


# ----------------------------------------------------------------------
# require_org_match
# ----------------------------------------------------------------------
async def test_require_org_match_allows_when_path_org_matches_caller_org(harness):
    org_id = uuid.uuid4()
    user = await harness.create_user(email="dep-org-allow@example.com")
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["org:read"])
    dependency = require_org_match("org:read")
    request = _FakeRequest(path_params={"nursery_id": str(org_id)})

    decision = await dependency(request=request, user=user, authz=harness.authorization_service)

    assert decision.allowed is True


async def test_require_org_match_denies_when_path_org_is_a_different_tenant(harness):
    org_id, other_org_id = uuid.uuid4(), uuid.uuid4()
    user = await harness.create_user(email="dep-org-deny@example.com")
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["org:read"])
    dependency = require_org_match("org:read")
    request = _FakeRequest(path_params={"nursery_id": str(other_org_id)})

    with pytest.raises(PermissionDeniedError):
        await dependency(request=request, user=user, authz=harness.authorization_service)


async def test_require_org_match_supports_a_renamed_path_param(harness):
    org_id = uuid.uuid4()
    user = await harness.create_user(email="dep-org-renamed@example.com")
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["org:read"])
    dependency = require_org_match("org:read", nursery_id_param="org_id")
    request = _FakeRequest(path_params={"org_id": str(org_id)})

    decision = await dependency(request=request, user=user, authz=harness.authorization_service)

    assert decision.allowed is True


# ----------------------------------------------------------------------
# require_branch_match
# ----------------------------------------------------------------------
async def test_require_branch_match_allows_for_the_assigned_branch(harness):
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    user = await harness.create_user(email="dep-branch-allow@example.com")
    harness.grant_role(
        user, org_id=org_id, role_code="branch_manager", permission_codes=["branch:read"], branch_ids=[branch_id]
    )
    dependency = require_branch_match("branch:read")
    request = _FakeRequest(path_params={"nursery_id": str(org_id), "branch_id": str(branch_id)})

    decision = await dependency(request=request, user=user, authz=harness.authorization_service)

    assert decision.allowed is True


async def test_require_branch_match_denies_for_a_foreign_branch(harness):
    org_id = uuid.uuid4()
    my_branch, foreign_branch = uuid.uuid4(), uuid.uuid4()
    user = await harness.create_user(email="dep-branch-deny@example.com")
    harness.grant_role(
        user, org_id=org_id, role_code="branch_manager", permission_codes=["branch:read"], branch_ids=[my_branch]
    )
    dependency = require_branch_match("branch:read")
    request = _FakeRequest(path_params={"nursery_id": str(org_id), "branch_id": str(foreign_branch)})

    with pytest.raises(PermissionDeniedError):
        await dependency(request=request, user=user, authz=harness.authorization_service)


# ----------------------------------------------------------------------
# require_ownership_or_permission
# ----------------------------------------------------------------------
async def test_require_ownership_or_permission_allows_via_resolved_owner(harness):
    org_id = uuid.uuid4()
    user = await harness.create_user(email="dep-own-allow@example.com")
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=["orders:read_own"])

    async def resolve_owner_id(_request):
        return user.id  # simulates a repository lookup confirming the caller owns the resource

    dependency = require_ownership_or_permission("orders:read", resolve_owner_id=resolve_owner_id)

    decision = await dependency(request=_FakeRequest(), user=user, authz=harness.authorization_service)

    assert decision.allowed is True


async def test_require_ownership_or_permission_denies_when_neither_owner_nor_permitted(harness):
    org_id = uuid.uuid4()
    user = await harness.create_user(email="dep-own-deny@example.com")
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=["orders:read_own"])

    async def resolve_owner_id(_request):
        return uuid.uuid4()  # someone else's resource

    dependency = require_ownership_or_permission("orders:read", resolve_owner_id=resolve_owner_id)

    with pytest.raises(PermissionDeniedError):
        await dependency(request=_FakeRequest(), user=user, authz=harness.authorization_service)
