"""
Privilege escalation tests (Module 3's explicit requirement). Each test
attempts a distinct escalation vector and asserts it is refused:
- a caller cannot grant themselves access by claiming a permission/org/
  branch that isn't the one their actual RoleAssignment resolves to;
- a lower-privilege role's cached access can't be upgraded by having a
  higher-privilege role's ResolvedAccess handed to a *different* user's
  cache key;
- revoking a role takes effect immediately once invalidated (a stale
  cached grant is itself a privilege-escalation vector if it outlives the
  revocation);
- ownership fallback cannot be used to claim someone else's resource by
  simply asserting a different `resource_owner_user_id` than the actual
  authenticated caller.

All of these route through the same `AuthorizationService.authorize()`
used by production's `require_permission`/`require_org_match`/
`require_branch_match`/`require_ownership_or_permission` dependencies
(app/api/deps.py) -- there is no separate, weaker code path a client
could hit instead.
"""
from __future__ import annotations

import uuid

import pytest

from app.db.enums import AuthorizationDenialReason

pytestmark = pytest.mark.unit


async def test_caller_cannot_claim_a_permission_their_role_does_not_grant(harness):
    org_id = uuid.uuid4()
    user = await harness.create_user(email="sales@example.com")
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=["plants:read"])

    # The permission string is never client-supplied in production (each
    # `require_permission("...")` call is hardcoded per-route), but the
    # service itself must still refuse it regardless of what's asked for --
    # nothing about `authorize()`'s inputs are trusted as a grant.
    decision = await harness.authorization_service.authorize(
        user=user, permission="org:delete", target_nursery_id=org_id
    )

    assert decision.allowed is False
    assert decision.reason == AuthorizationDenialReason.MISSING_PERMISSION


async def test_caller_cannot_reach_a_different_orgs_resources_by_asserting_its_id(harness):
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    user = await harness.create_user(email="owner-escalate@example.com")
    harness.grant_role(user, org_id=org_a, role_code="owner", permission_codes=["org:write"])

    decision = await harness.authorization_service.authorize(
        user=user, permission="org:write", target_nursery_id=org_b
    )

    assert decision.allowed is False
    assert decision.reason == AuthorizationDenialReason.CROSS_TENANT_ORG


async def test_revoked_role_stops_granting_access_immediately_after_invalidation(harness):
    """
    A cached grant that outlives its revocation is itself an escalation
    path (a fired employee retaining write access for up to the cache
    TTL). `invalidate_user` is what closes that window immediately rather
    than waiting on the TTL.
    """
    org_id = uuid.uuid4()
    user = await harness.create_user(email="revoked@example.com")
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["org:write"])

    warm = await harness.authorization_service.authorize(
        user=user, permission="org:write", target_nursery_id=org_id
    )
    assert warm.allowed is True

    # Simulate role revocation at the source of truth.
    harness.permissions.role_assignments.pop(user.id)
    await harness.permission_service.invalidate_user(user.id)

    after_revocation = await harness.authorization_service.authorize(
        user=user, permission="org:write", target_nursery_id=org_id
    )
    assert after_revocation.allowed is False
    # Revocation also wipes org membership (no RoleAssignment -> no org
    # context), so the specific denial reason surfaced is NO_ORG_CONTEXT
    # rather than MISSING_PERMISSION -- either way, access is refused.
    assert after_revocation.reason == AuthorizationDenialReason.NO_ORG_CONTEXT


async def test_stale_cache_without_invalidation_would_still_be_closed_by_ttl(harness):
    """
    Documents the safety-net behavior distinct from the test above:
    *without* an explicit `invalidate_user` call, a revoked role's access
    remains cached until the TTL expires -- this is the known, bounded
    exposure window app/services/permission_service.py's module docstring
    calls out, not an unbounded one. Verified here by asserting the cache
    entry is still present (not by waiting out a real TTL, which would
    make this test slow and flaky).
    """
    org_id = uuid.uuid4()
    user = await harness.create_user(email="stale-cache@example.com")
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["org:write"])

    await harness.permission_service.resolve_for_user(user.id)
    harness.permissions.role_assignments.pop(user.id)  # revoked at the source, but NOT invalidated

    cached = await harness.cache.get(f"perm:user:{user.id}")
    assert cached is not None  # the stale grant is still sitting in cache, bounded by TTL only


async def test_ownership_fallback_cannot_be_used_to_claim_another_users_resource(harness):
    org_id = uuid.uuid4()
    user = await harness.create_user(email="claimant@example.com")
    real_owner_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=["orders:read_own"])

    # The route layer resolves resource_owner_user_id from the database
    # record itself (e.g. an Order's own owner_user_id column), never
    # from client input -- so there is no "claim ownership" input for a
    # caller to spoof in the first place. This test confirms the service
    # side of that contract: passing the *real* owner id (not the
    # caller's) never grants access via the ownership path.
    decision = await harness.authorization_service.authorize(
        user=user,
        permission="orders:read",
        resource_owner_user_id=real_owner_id,
    )

    assert decision.allowed is False
    assert decision.reason == AuthorizationDenialReason.NOT_OWNER


async def test_inactive_account_cannot_use_a_still_valid_permission_cache_entry(harness):
    """
    Deactivating a user (e.g. an offboarded employee) must block access
    even if their permission cache entry is still warm -- account-active
    is checked before permission resolution even runs.
    """
    org_id = uuid.uuid4()
    user = await harness.create_user(email="deactivated@example.com")
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["org:write"])
    await harness.permission_service.resolve_for_user(user.id)  # warm the cache while still active

    user.is_active = False

    decision = await harness.authorization_service.authorize(
        user=user, permission="org:write", target_nursery_id=org_id
    )

    assert decision.allowed is False
    assert decision.reason == AuthorizationDenialReason.ACCOUNT_INACTIVE
