"""
Unit tests for app/services/authorization_service.py — the core of
Module 3. Covers every item in the module's own validation checklist:
every permission resolves correctly, cross-tenant org/branch access is
blocked, ownership fallback works, account-inactive is denied, and every
denial is persisted with User ID/Permission/Resource/Request ID/IP/
Timestamp/Reason (the module's explicit auditing requirement).
"""
from __future__ import annotations

import uuid

import pytest

from app.db.enums import AuthorizationDenialReason
from app.services.authorization_service import RequestContext

pytestmark = pytest.mark.unit

_CTX = RequestContext(request_id="req-123", ip_address="203.0.113.7")


# ----------------------------------------------------------------------
# Basic allow / deny on permission membership
# ----------------------------------------------------------------------
async def test_allowed_when_role_grants_the_permission(harness):
    org_id = uuid.uuid4()
    user = await harness.create_user()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["audit:read"])

    decision = await harness.authorization_service.authorize(user=user, permission="audit:read", context=_CTX)

    assert decision.allowed is True
    assert decision.reason is None
    assert "grants" in decision.explanation
    assert harness.denials.denials == []


async def test_denied_when_role_lacks_the_permission(harness):
    org_id = uuid.uuid4()
    user = await harness.create_user()
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=["plants:read"])

    decision = await harness.authorization_service.authorize(user=user, permission="audit:read", context=_CTX)

    assert decision.allowed is False
    assert decision.reason == AuthorizationDenialReason.MISSING_PERMISSION


async def test_denied_when_user_has_no_role_assignment_at_all(harness):
    # A brand-new user with no RoleAssignment yet -- default-deny, not a crash.
    user = await harness.create_user()

    decision = await harness.authorization_service.authorize(user=user, permission="audit:read", context=_CTX)

    assert decision.allowed is False
    assert decision.reason == AuthorizationDenialReason.MISSING_PERMISSION


# ----------------------------------------------------------------------
# Account state
# ----------------------------------------------------------------------
async def test_denied_when_account_is_inactive(harness):
    org_id = uuid.uuid4()
    user = await harness.create_user(is_active=False)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["audit:read"])

    decision = await harness.authorization_service.authorize(user=user, permission="audit:read", context=_CTX)

    assert decision.allowed is False
    assert decision.reason == AuthorizationDenialReason.ACCOUNT_INACTIVE


# ----------------------------------------------------------------------
# Cross-tenant: organization
# ----------------------------------------------------------------------
async def test_denied_when_target_org_does_not_match_caller_org(harness):
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    user = await harness.create_user()
    harness.grant_role(user, org_id=org_a, role_code="owner", permission_codes=["org:read"])

    decision = await harness.authorization_service.authorize(
        user=user, permission="org:read", target_nursery_id=org_b, context=_CTX
    )

    assert decision.allowed is False
    assert decision.reason == AuthorizationDenialReason.CROSS_TENANT_ORG


async def test_allowed_when_target_org_matches_caller_org(harness):
    org_a = uuid.uuid4()
    user = await harness.create_user()
    harness.grant_role(user, org_id=org_a, role_code="owner", permission_codes=["org:read"])

    decision = await harness.authorization_service.authorize(
        user=user, permission="org:read", target_nursery_id=org_a, context=_CTX
    )

    assert decision.allowed is True


async def test_denied_with_no_org_context_when_org_scope_is_required(harness):
    org_b = uuid.uuid4()
    user = await harness.create_user()  # no role assignment -> no org

    decision = await harness.authorization_service.authorize(
        user=user, permission="org:read", target_nursery_id=org_b, context=_CTX
    )

    assert decision.allowed is False
    assert decision.reason == AuthorizationDenialReason.NO_ORG_CONTEXT


# ----------------------------------------------------------------------
# Cross-tenant: branch
# ----------------------------------------------------------------------
async def test_org_wide_role_bypasses_branch_check(harness):
    org_id = uuid.uuid4()
    other_branch = uuid.uuid4()
    user = await harness.create_user()
    # Owner: org-wide, no branch_scopes rows at all.
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["branch:read"])

    decision = await harness.authorization_service.authorize(
        user=user,
        permission="branch:read",
        target_nursery_id=org_id,
        target_branch_id=other_branch,
        context=_CTX,
    )

    assert decision.allowed is True


async def test_branch_scoped_role_denied_for_a_branch_outside_its_scope(harness):
    org_id = uuid.uuid4()
    my_branch = uuid.uuid4()
    other_branch = uuid.uuid4()
    user = await harness.create_user()
    harness.grant_role(
        user,
        org_id=org_id,
        role_code="branch_manager",
        permission_codes=["branch:read"],
        branch_ids=[my_branch],
    )

    decision = await harness.authorization_service.authorize(
        user=user,
        permission="branch:read",
        target_nursery_id=org_id,
        target_branch_id=other_branch,
        context=_CTX,
    )

    assert decision.allowed is False
    assert decision.reason == AuthorizationDenialReason.CROSS_TENANT_BRANCH


async def test_branch_scoped_role_allowed_for_its_own_branch(harness):
    org_id = uuid.uuid4()
    my_branch = uuid.uuid4()
    user = await harness.create_user()
    harness.grant_role(
        user,
        org_id=org_id,
        role_code="branch_manager",
        permission_codes=["branch:read"],
        branch_ids=[my_branch],
    )

    decision = await harness.authorization_service.authorize(
        user=user,
        permission="branch:read",
        target_nursery_id=org_id,
        target_branch_id=my_branch,
        context=_CTX,
    )

    assert decision.allowed is True


# ----------------------------------------------------------------------
# Ownership fallback
# ----------------------------------------------------------------------
async def test_ownership_grants_access_without_the_blanket_permission(harness):
    org_id = uuid.uuid4()
    user = await harness.create_user()
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=["orders:read_own"])

    decision = await harness.authorization_service.authorize(
        user=user,
        permission="orders:read",  # caller does NOT hold this exact permission
        resource_owner_user_id=user.id,  # but they own the resource
        context=_CTX,
    )

    assert decision.allowed is True
    assert "ownership" in decision.explanation


async def test_denied_when_not_owner_and_lacks_permission(harness):
    org_id = uuid.uuid4()
    user = await harness.create_user()
    other_user_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=["orders:read_own"])

    decision = await harness.authorization_service.authorize(
        user=user,
        permission="orders:read",
        resource_owner_user_id=other_user_id,
        context=_CTX,
    )

    assert decision.allowed is False
    assert decision.reason == AuthorizationDenialReason.NOT_OWNER


# ----------------------------------------------------------------------
# Denial audit trail — "every authorization failure must generate:
# User ID, Permission, Resource, Request ID, IP, Timestamp, Reason."
# ----------------------------------------------------------------------
async def test_denial_is_persisted_with_full_context(harness):
    org_id = uuid.uuid4()
    resource_id = uuid.uuid4()
    user = await harness.create_user()
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=["plants:read"])

    await harness.authorization_service.authorize(
        user=user,
        permission="audit:read",
        resource_type="audit_log",
        resource_id=resource_id,
        context=_CTX,
    )

    assert len(harness.denials.denials) == 1
    denial = harness.denials.denials[0]
    assert denial.user_id == user.id
    assert denial.permission_code == "audit:read"
    assert denial.resource_type == "audit_log"
    assert denial.resource_id == resource_id
    assert denial.reason == AuthorizationDenialReason.MISSING_PERMISSION
    assert denial.request_id == "req-123"
    assert denial.ip_address == "203.0.113.7"
    assert denial.explanation  # human-readable, non-empty -- "explainable"


async def test_persist_denial_false_skips_the_audit_write(harness):
    user = await harness.create_user()

    await harness.authorization_service.authorize(
        user=user, permission="audit:read", context=_CTX, persist_denial=False
    )

    assert harness.denials.denials == []


async def test_allowed_decision_never_writes_a_denial(harness):
    org_id = uuid.uuid4()
    user = await harness.create_user()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["audit:read"])

    await harness.authorization_service.authorize(user=user, permission="audit:read", context=_CTX)

    assert harness.denials.denials == []
