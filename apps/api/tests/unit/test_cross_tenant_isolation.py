"""
Cross-tenant isolation tests (Module 3's explicit requirement: "cross-
tenant access must be impossible"). Two independent nurseries, each with
their own Owner, verifying neither can reach the other's org or branch
data through AuthorizationService -- the application-layer half of
isolation (the database-layer half is RLS, migrations/versions/
0003_row_level_security.py, validated separately in the Phase 5 readiness
review since it requires a live Postgres this sandbox doesn't have).
"""
from __future__ import annotations

import uuid

import pytest

from app.db.enums import AuthorizationDenialReason

pytestmark = pytest.mark.unit


async def test_owner_of_org_a_cannot_read_org_b(harness):
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    owner_a = await harness.create_user(email="owner-a@example.com")
    harness.grant_role(owner_a, org_id=org_a, role_code="owner", permission_codes=["org:read"])

    decision = await harness.authorization_service.authorize(
        user=owner_a, permission="org:read", target_nursery_id=org_b
    )

    assert decision.allowed is False
    assert decision.reason == AuthorizationDenialReason.CROSS_TENANT_ORG


async def test_owner_of_org_a_cannot_read_a_branch_belonging_to_org_b(harness):
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    branch_in_b = uuid.uuid4()
    owner_a = await harness.create_user(email="owner-a-branch@example.com")
    harness.grant_role(owner_a, org_id=org_a, role_code="owner", permission_codes=["branch:read"])

    decision = await harness.authorization_service.authorize(
        user=owner_a, permission="branch:read", target_nursery_id=org_b, target_branch_id=branch_in_b
    )

    # Org mismatch is caught before branch is even considered.
    assert decision.allowed is False
    assert decision.reason == AuthorizationDenialReason.CROSS_TENANT_ORG


async def test_two_orgs_full_permission_sets_never_leak_into_each_other(harness):
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    owner_a = await harness.create_user(email="owner-a-leak@example.com")
    owner_b = await harness.create_user(email="owner-b-leak@example.com")
    harness.grant_role(owner_a, org_id=org_a, role_code="owner", permission_codes=["org:read", "org:write"])
    harness.grant_role(owner_b, org_id=org_b, role_code="owner", permission_codes=["org:read", "org:write"])

    access_a = await harness.permission_service.resolve_for_user(owner_a.id)
    access_b = await harness.permission_service.resolve_for_user(owner_b.id)

    assert access_a.org_id == org_a
    assert access_b.org_id == org_b
    assert access_a.org_id != access_b.org_id
    # Same permission codes granted, but under distinct, non-transferable org contexts.
    assert access_a.permissions == access_b.permissions == ["org:read", "org:write"]


async def test_branch_manager_of_org_a_branch_cannot_reach_org_bs_matching_branch_id(harness):
    """
    Even in the pathological case of two orgs' branches colliding on a
    UUID (astronomically unlikely in practice, but the check order must
    not accidentally rely on that): org must match before branch is ever
    compared.
    """
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    shared_branch_id = uuid.uuid4()
    manager_a = await harness.create_user(email="manager-a@example.com")
    harness.grant_role(
        manager_a,
        org_id=org_a,
        role_code="branch_manager",
        permission_codes=["branch:read"],
        branch_ids=[shared_branch_id],
    )

    decision = await harness.authorization_service.authorize(
        user=manager_a,
        permission="branch:read",
        target_nursery_id=org_b,  # wrong org, even though the branch id "matches"
        target_branch_id=shared_branch_id,
    )

    assert decision.allowed is False
    assert decision.reason == AuthorizationDenialReason.CROSS_TENANT_ORG


async def test_denials_from_two_different_orgs_are_each_correctly_attributed(harness):
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    owner_a = await harness.create_user(email="owner-a-attrib@example.com")
    owner_b = await harness.create_user(email="owner-b-attrib@example.com")
    harness.grant_role(owner_a, org_id=org_a, role_code="owner", permission_codes=["org:read"])
    harness.grant_role(owner_b, org_id=org_b, role_code="owner", permission_codes=["org:read"])

    await harness.authorization_service.authorize(user=owner_a, permission="org:read", target_nursery_id=org_b)
    await harness.authorization_service.authorize(user=owner_b, permission="org:read", target_nursery_id=org_a)

    assert len(harness.denials.denials) == 2
    denial_by_user = {d.user_id: d for d in harness.denials.denials}
    assert denial_by_user[owner_a.id].reason == AuthorizationDenialReason.CROSS_TENANT_ORG
    assert denial_by_user[owner_b.id].reason == AuthorizationDenialReason.CROSS_TENANT_ORG
