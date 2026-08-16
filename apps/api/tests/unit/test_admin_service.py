"""
Phase 6 Module 13 (Administration & System Management) unit tests --
`app/services/admin_service.py`'s eight services, exercised directly
against `harness` (the same shared in-memory-fake harness every prior
module's unit tests use; see tests/conftest.py), with a deliberate
security-first emphasis since this module IS the authorization/audit
control surface:

  * RoleAdminService  -- role/permission catalog, the "owner role is
    untouchable" invariant, cross-tenant role-assignment rejection,
    unknown-role-code validation, permission cache invalidation.
  * UserAdminService  -- cross-tenant 403 (never 404, never leaks
    existence), the "owner account cannot be administered by another
    user" invariant, account activation/lock/unlock, session
    management, password reset / email verification delegation.
  * FeatureFlagService -- fail-safe resolution (missing key -> False,
    never raises), three-tier upsert, branch-without-org validation.
  * SystemConfigService -- category/value_type validation, before/after
    audit diff, "no secret exposure" (nothing here ever handles a
    credential value).
  * AuditAdminService -- org-scoped search delegation, the one
    deliberately cross-tenant `platform_security_events` method.
  * HealthCheckService -- every field boolean/label only; database/cache
    checks fail closed (return False) rather than raising or leaking a
    stack trace.
  * AIAdminService -- read-only model-status/usage/failures/knowledge-
    base visibility; no write path exists (Section 10's "no arbitrary
    model configuration changes" requirement).
  * DataManagementService -- retention visibility only, no deletion path.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.db.enums import EmployeeStatus, SecurityEventType
from app.models.auth import RefreshToken
from app.models.organization import Employee

pytestmark = pytest.mark.unit


def _employee(*, nursery_id: uuid.UUID, user_id: uuid.UUID, status: EmployeeStatus = EmployeeStatus.ACTIVE) -> Employee:
    return Employee(id=uuid.uuid4(), nursery_id=nursery_id, user_id=user_id, status=status)


# ==========================================================================
# RoleAdminService (Section 1)
# ==========================================================================


async def test_list_roles_returns_system_roles_and_this_orgs_own_roles(harness):
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    harness.seed_system_role("owner", ["employees:read"])
    user = await harness.create_user(email="a@example.com")
    other_user = await harness.create_user(email="b@example.com")
    harness.grant_role(user, org_id=org_id, role_code="manager", permission_codes=["employees:read"])
    harness.grant_role(other_user, org_id=other_org_id, role_code="manager", permission_codes=["employees:read"])

    roles = await harness.role_admin_service.list_roles(nursery_id=org_id)
    codes = {(r.nursery_id, r.code) for r in roles}
    assert (None, "owner") in codes
    assert (org_id, "manager") in codes
    assert (other_org_id, "manager") not in codes


async def test_list_permissions_deduplicates_by_code(harness):
    harness.seed_system_role("owner", ["employees:read", "employees:write"])
    harness.seed_system_role("org_admin", ["employees:read"])
    permissions = await harness.role_admin_service.list_permissions()
    codes = [p.code for p in permissions]
    assert codes.count("employees:read") == 1
    assert "employees:write" in codes


async def test_get_role_permissions_lists_codes_for_one_role(harness):
    role = harness.seed_system_role("branch_manager", ["employees:read", "audit:read"])
    pairs = await harness.role_admin_service.get_role_permissions(role.id)
    assert {code for code, _scope in pairs} == {"employees:read", "audit:read"}


async def test_get_effective_permissions_delegates_to_permission_service(harness):
    org_id = uuid.uuid4()
    user = await harness.create_user()
    harness.grant_role(user, org_id=org_id, role_code="staff", permission_codes=["employees:read"])

    access = await harness.role_admin_service.get_effective_permissions(user.id)
    assert access.org_id == org_id
    assert access.role_code == "staff"
    assert "employees:read" in access.permissions


async def test_change_user_role_updates_assignment_invalidates_cache_and_audits(harness):
    org_id = uuid.uuid4()
    actor = await harness.create_user(email="actor@example.com")
    target = await harness.create_user(email="target@example.com")
    harness.grant_role(target, org_id=org_id, role_code="staff", permission_codes=["employees:read"])
    manager_role = harness.seed_system_role("manager", ["employees:read", "employees:write"])

    # Warm the permission cache for the target with the OLD role, then
    # confirm the change actually invalidates it -- a stale cache entry
    # here would be a silent privilege-escalation-persistence bug.
    before = await harness.permission_service.resolve_for_user(target.id)
    assert before.role_code == "staff"

    assignment = await harness.role_admin_service.change_user_role(
        actor_user_id=actor.id, nursery_id=org_id, target_user_id=target.id,
        new_role_code="manager", request_id="req-1",
    )
    assert assignment.role_id == manager_role.id

    after = await harness.permission_service.resolve_for_user(target.id)
    assert after.role_code == "manager"
    assert "employees:write" in after.permissions

    entry = harness.audit_logs.rows[-1]
    assert entry.action == "admin.role_assignment_changed"
    assert entry.nursery_id == org_id
    assert entry.diff["before"]["role_code"] == "staff"
    assert entry.diff["after"]["role_code"] == "manager"


async def test_change_user_role_rejects_target_with_no_assignment_in_this_org(harness):
    org_id = uuid.uuid4()
    actor = await harness.create_user(email="actor2@example.com")
    target = await harness.create_user(email="target2@example.com")
    harness.grant_role(target, org_id=uuid.uuid4(), role_code="staff", permission_codes=[])
    harness.seed_system_role("manager", ["employees:read"])

    with pytest.raises(PermissionDeniedError):
        await harness.role_admin_service.change_user_role(
            actor_user_id=actor.id, nursery_id=org_id, target_user_id=target.id, new_role_code="manager",
        )


async def test_change_user_role_rejects_target_with_no_assignment_at_all(harness):
    org_id = uuid.uuid4()
    actor = await harness.create_user(email="actor3@example.com")
    target = await harness.create_user(email="target3@example.com")
    harness.seed_system_role("manager", ["employees:read"])

    with pytest.raises(PermissionDeniedError):
        await harness.role_admin_service.change_user_role(
            actor_user_id=actor.id, nursery_id=org_id, target_user_id=target.id, new_role_code="manager",
        )


async def test_change_user_role_refuses_when_current_role_is_owner(harness):
    org_id = uuid.uuid4()
    actor = await harness.create_user(email="actor4@example.com")
    owner = await harness.create_user(email="owner@example.com")
    harness.grant_role(owner, org_id=org_id, role_code="owner", permission_codes=["employees:read"])
    harness.seed_system_role("manager", ["employees:read"])

    with pytest.raises(ValidationError):
        await harness.role_admin_service.change_user_role(
            actor_user_id=actor.id, nursery_id=org_id, target_user_id=owner.id, new_role_code="manager",
        )


async def test_change_user_role_refuses_to_grant_owner(harness):
    org_id = uuid.uuid4()
    actor = await harness.create_user(email="actor5@example.com")
    target = await harness.create_user(email="target5@example.com")
    harness.grant_role(target, org_id=org_id, role_code="staff", permission_codes=[])

    with pytest.raises(ValidationError):
        await harness.role_admin_service.change_user_role(
            actor_user_id=actor.id, nursery_id=org_id, target_user_id=target.id, new_role_code="owner",
        )


async def test_change_user_role_rejects_unknown_role_code(harness):
    org_id = uuid.uuid4()
    actor = await harness.create_user(email="actor6@example.com")
    target = await harness.create_user(email="target6@example.com")
    harness.grant_role(target, org_id=org_id, role_code="staff", permission_codes=[])

    with pytest.raises(ValidationError):
        await harness.role_admin_service.change_user_role(
            actor_user_id=actor.id, nursery_id=org_id, target_user_id=target.id, new_role_code="not-a-real-role",
        )


# ==========================================================================
# UserAdminService (Section 2)
# ==========================================================================


async def test_search_users_returns_only_this_orgs_employees(harness):
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    u1 = await harness.create_user(email="u1@example.com")
    u2 = await harness.create_user(email="u2@example.com")
    await harness.employees.add(_employee(nursery_id=org_id, user_id=u1.id))
    await harness.employees.add(_employee(nursery_id=other_org_id, user_id=u2.id))

    rows, total = await harness.user_admin_service.search_users(nursery_id=org_id, offset=0, limit=50)
    assert total == 1
    assert rows[0][1].id == u1.id


async def test_get_user_detail_cross_tenant_is_403_not_404(harness):
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    user = await harness.create_user(email="cross@example.com")
    await harness.employees.add(_employee(nursery_id=other_org_id, user_id=user.id))

    with pytest.raises(PermissionDeniedError):
        await harness.user_admin_service.get_user_detail(nursery_id=org_id, target_user_id=user.id)


async def test_get_user_detail_unknown_user_still_403_within_own_org_scope(harness):
    org_id = uuid.uuid4()
    with pytest.raises(PermissionDeniedError):
        await harness.user_admin_service.get_user_detail(nursery_id=org_id, target_user_id=uuid.uuid4())


async def test_set_account_active_deactivate_logs_security_event_and_audit(harness):
    org_id = uuid.uuid4()
    actor = await harness.create_user(email="admin1@example.com")
    target = await harness.create_user(email="staffmember@example.com", is_active=True)
    await harness.employees.add(_employee(nursery_id=org_id, user_id=target.id))

    updated = await harness.user_admin_service.set_account_active(
        actor_user_id=actor.id, nursery_id=org_id, target_user_id=target.id, is_active=False, request_id="r1",
    )
    assert updated.is_active is False
    assert harness.security_events.events[-1].event_type == SecurityEventType.ACCOUNT_DEACTIVATED_BY_ADMIN
    assert harness.audit_logs.rows[-1].action == "admin.user.account_active_changed"


async def test_set_account_active_refuses_to_touch_the_owners_account(harness):
    org_id = uuid.uuid4()
    actor = await harness.create_user(email="admin2@example.com")
    owner_user = await harness.create_user(email="owner2@example.com")
    await harness.employees.add(_employee(nursery_id=org_id, user_id=owner_user.id))
    harness.grant_role(owner_user, org_id=org_id, role_code="owner", permission_codes=[])

    with pytest.raises(PermissionDeniedError):
        await harness.user_admin_service.set_account_active(
            actor_user_id=actor.id, nursery_id=org_id, target_user_id=owner_user.id, is_active=False,
        )


async def test_owner_can_act_on_their_own_account(harness):
    """`_assert_not_owner` only blocks a DIFFERENT actor from touching the owner -- the owner acting on themself is allowed."""
    org_id = uuid.uuid4()
    owner_user = await harness.create_user(email="owner3@example.com")
    await harness.employees.add(_employee(nursery_id=org_id, user_id=owner_user.id))
    harness.grant_role(owner_user, org_id=org_id, role_code="owner", permission_codes=[])

    updated = await harness.user_admin_service.set_account_active(
        actor_user_id=owner_user.id, nursery_id=org_id, target_user_id=owner_user.id, is_active=False,
    )
    assert updated.is_active is False


async def test_lock_account_sets_locked_until_in_the_future_and_logs_event(harness):
    org_id = uuid.uuid4()
    actor = await harness.create_user(email="admin3@example.com")
    target = await harness.create_user(email="staff2@example.com")
    await harness.employees.add(_employee(nursery_id=org_id, user_id=target.id))

    before = datetime.now(timezone.utc)
    updated = await harness.user_admin_service.lock_account(
        actor_user_id=actor.id, nursery_id=org_id, target_user_id=target.id, duration_minutes=30,
    )
    assert updated.locked_until is not None
    assert updated.locked_until > before + timedelta(minutes=29)
    assert harness.security_events.events[-1].event_type == SecurityEventType.ACCOUNT_LOCKED


async def test_unlock_account_clears_lock_and_resets_failed_attempts(harness):
    org_id = uuid.uuid4()
    actor = await harness.create_user(email="admin4@example.com")
    target = await harness.create_user(
        email="staff3@example.com",
        locked_until=datetime.now(timezone.utc) + timedelta(minutes=15),
        failed_login_attempts=3,
    )
    await harness.employees.add(_employee(nursery_id=org_id, user_id=target.id))

    updated = await harness.user_admin_service.unlock_account(
        actor_user_id=actor.id, nursery_id=org_id, target_user_id=target.id,
    )
    assert updated.locked_until is None
    assert updated.failed_login_attempts == 0
    assert harness.security_events.events[-1].event_type == SecurityEventType.ACCOUNT_UNLOCKED


async def test_list_and_revoke_sessions(harness):
    org_id = uuid.uuid4()
    actor = await harness.create_user(email="admin5@example.com")
    target = await harness.create_user(email="staff4@example.com")
    await harness.employees.add(_employee(nursery_id=org_id, user_id=target.id))
    token = await harness.refresh_tokens.add(
        RefreshToken(
            id=uuid.uuid4(), user_id=target.id, token_hash="hash-1", family_id=uuid.uuid4(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
    )

    sessions = await harness.user_admin_service.list_sessions(nursery_id=org_id, target_user_id=target.id)
    assert len(sessions) == 1

    await harness.user_admin_service.revoke_session(
        actor_user_id=actor.id, nursery_id=org_id, target_user_id=target.id, session_id=token.id,
    )
    remaining = await harness.user_admin_service.list_sessions(nursery_id=org_id, target_user_id=target.id)
    assert remaining == []
    assert harness.audit_logs.rows[-1].action == "admin.user.session_revoked"


async def test_force_logout_revokes_every_session(harness):
    org_id = uuid.uuid4()
    actor = await harness.create_user(email="admin6@example.com")
    target = await harness.create_user(email="staff5@example.com")
    await harness.employees.add(_employee(nursery_id=org_id, user_id=target.id))
    for i in range(3):
        await harness.refresh_tokens.add(
            RefreshToken(
                id=uuid.uuid4(), user_id=target.id, token_hash=f"hash-{i}", family_id=uuid.uuid4(),
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            )
        )

    await harness.user_admin_service.force_logout(actor_user_id=actor.id, nursery_id=org_id, target_user_id=target.id)
    remaining = await harness.user_admin_service.list_sessions(nursery_id=org_id, target_user_id=target.id)
    assert remaining == []
    assert harness.audit_logs.rows[-1].action == "admin.user.force_logout"


async def test_request_password_reset_creates_token_and_audits(harness):
    org_id = uuid.uuid4()
    actor = await harness.create_user(email="admin7@example.com")
    target = await harness.create_user(email="staff6@example.com")
    await harness.employees.add(_employee(nursery_id=org_id, user_id=target.id))

    await harness.user_admin_service.request_password_reset(actor_user_id=actor.id, nursery_id=org_id, target_user_id=target.id)
    assert len(harness.password_reset_tokens.tokens) == 1
    assert harness.audit_logs.rows[-1].action == "admin.user.password_reset_requested"


async def test_request_email_verification_creates_token_and_audits(harness):
    org_id = uuid.uuid4()
    actor = await harness.create_user(email="admin8@example.com")
    target = await harness.create_user(email="staff7@example.com", is_email_verified=False)
    await harness.employees.add(_employee(nursery_id=org_id, user_id=target.id))

    await harness.user_admin_service.request_email_verification(actor_user_id=actor.id, nursery_id=org_id, target_user_id=target.id)
    assert len(harness.email_verification_tokens.tokens) == 1
    assert harness.audit_logs.rows[-1].action == "admin.user.email_verification_requested"


# ==========================================================================
# FeatureFlagService (Section 7)
# ==========================================================================


async def test_is_enabled_fails_safe_when_no_flag_row_exists_at_any_tier(harness):
    assert await harness.feature_flag_service.is_enabled("nonexistent-key", nursery_id=uuid.uuid4()) is False


async def test_set_flag_platform_default_then_org_override_then_branch_override(harness):
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    actor = await harness.create_user(email="ff-admin@example.com")

    await harness.feature_flag_service.set_flag(
        actor_user_id=actor.id, audit_nursery_id=org_id, key="beta-ui", target_nursery_id=None,
        branch_id=None, is_enabled=True, description="platform default",
    )
    assert await harness.feature_flag_service.is_enabled("beta-ui", nursery_id=uuid.uuid4()) is True

    await harness.feature_flag_service.set_flag(
        actor_user_id=actor.id, audit_nursery_id=org_id, key="beta-ui", target_nursery_id=org_id,
        branch_id=None, is_enabled=False, description="org override",
    )
    assert await harness.feature_flag_service.is_enabled("beta-ui", nursery_id=org_id) is False
    # A different org still sees the platform default (True), not this org's override.
    assert await harness.feature_flag_service.is_enabled("beta-ui", nursery_id=uuid.uuid4()) is True

    await harness.feature_flag_service.set_flag(
        actor_user_id=actor.id, audit_nursery_id=org_id, key="beta-ui", target_nursery_id=org_id,
        branch_id=branch_id, is_enabled=True, description="branch override",
    )
    assert await harness.feature_flag_service.is_enabled("beta-ui", nursery_id=org_id, branch_id=branch_id) is True


async def test_set_flag_rejects_branch_scope_without_an_organization(harness):
    actor = await harness.create_user(email="ff-admin2@example.com")
    with pytest.raises(ValidationError):
        await harness.feature_flag_service.set_flag(
            actor_user_id=actor.id, audit_nursery_id=uuid.uuid4(), key="x", target_nursery_id=None,
            branch_id=uuid.uuid4(), is_enabled=True, description=None,
        )


async def test_set_flag_writes_audit_against_actors_home_org(harness):
    org_id = uuid.uuid4()
    actor = await harness.create_user(email="ff-admin3@example.com")
    await harness.feature_flag_service.set_flag(
        actor_user_id=actor.id, audit_nursery_id=org_id, key="platform-thing", target_nursery_id=None,
        branch_id=None, is_enabled=True, description=None,
    )
    entry = harness.audit_logs.rows[-1]
    assert entry.action == "admin.feature_flag_set"
    assert entry.nursery_id == org_id  # actor's home org, not "no org" -- audit_logs.nursery_id is NOT NULL


# ==========================================================================
# SystemConfigService (Section 6)
# ==========================================================================


async def test_set_config_rejects_invalid_category(harness):
    actor = await harness.create_user(email="sc-admin@example.com")
    with pytest.raises(ValidationError):
        await harness.system_config_service.set_config(
            actor_user_id=actor.id, audit_nursery_id=uuid.uuid4(), key="k", value=1,
            value_type="int", category="not-a-real-category", description=None,
        )


async def test_set_config_rejects_invalid_value_type(harness):
    actor = await harness.create_user(email="sc-admin2@example.com")
    with pytest.raises(ValidationError):
        await harness.system_config_service.set_config(
            actor_user_id=actor.id, audit_nursery_id=uuid.uuid4(), key="k", value=1,
            value_type="not-a-real-type", category="application", description=None,
        )


async def test_set_config_round_trips_value_and_audits_before_after(harness):
    org_id = uuid.uuid4()
    actor = await harness.create_user(email="sc-admin3@example.com")
    await harness.system_config_service.set_config(
        actor_user_id=actor.id, audit_nursery_id=org_id, key="max_upload_mb", value=10,
        value_type="int", category="application", description="initial",
    )
    fetched = await harness.system_config_service.get_config("max_upload_mb")
    assert fetched.value == {"value": 10}

    await harness.system_config_service.set_config(
        actor_user_id=actor.id, audit_nursery_id=org_id, key="max_upload_mb", value=20,
        value_type="int", category="application", description="updated",
    )
    entry = harness.audit_logs.rows[-1]
    assert entry.action == "admin.system_config_set"
    assert entry.diff["before"]["value"] == {"value": 10}
    assert entry.diff["after"]["value"] == {"value": 20}


async def test_get_config_raises_not_found_for_unknown_key(harness):
    with pytest.raises(NotFoundError):
        await harness.system_config_service.get_config("does-not-exist")


# ==========================================================================
# AuditAdminService (Section 8)
# ==========================================================================


async def test_search_audit_logs_and_security_events_are_org_scoped(harness):
    from app.models.platform import AuditLog

    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    await harness.audit_logs.log(
        AuditLog(nursery_id=org_id, actor_user_id=uuid.uuid4(), action="x", entity_type="Y",
                  entity_id=uuid.uuid4(), diff={}, created_at=datetime.now(timezone.utc))
    )
    await harness.audit_logs.log(
        AuditLog(nursery_id=other_org_id, actor_user_id=uuid.uuid4(), action="x", entity_type="Y",
                  entity_id=uuid.uuid4(), diff={}, created_at=datetime.now(timezone.utc))
    )
    rows, total = await harness.audit_admin_service.search_audit_logs(org_id, offset=0, limit=50)
    assert total == 1
    assert rows[0].nursery_id == org_id


async def test_platform_security_events_is_the_one_deliberately_cross_tenant_view(harness):
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    u1 = await harness.create_user(email="p1@example.com")
    u2 = await harness.create_user(email="p2@example.com")
    await harness.employees.add(_employee(nursery_id=org_id, user_id=u1.id))
    await harness.employees.add(_employee(nursery_id=other_org_id, user_id=u2.id))
    from app.models.auth import SecurityEvent

    await harness.security_events.log(
        SecurityEvent(user_id=u1.id, email=u1.email, event_type=SecurityEventType.LOGIN_SUCCESS, created_at=datetime.now(timezone.utc))
    )
    await harness.security_events.log(
        SecurityEvent(user_id=u2.id, email=u2.email, event_type=SecurityEventType.LOGIN_SUCCESS, created_at=datetime.now(timezone.utc))
    )
    rows, total = await harness.audit_admin_service.platform_security_events(offset=0, limit=50)
    assert total == 2  # both orgs' events visible -- authorization for this is enforced at the route layer


# ==========================================================================
# HealthCheckService (Section 9)
# ==========================================================================


async def test_health_check_reports_true_when_database_and_cache_are_reachable(harness):
    from app.services.admin_service import HealthCheckService

    class _WorkingSession:
        async def execute(self, *args, **kwargs):
            return None

    service = HealthCheckService(db_session=_WorkingSession(), cache=harness.cache, settings=harness.settings)
    report = await service.check()
    assert report.database_reachable is True
    assert report.cache_reachable is True
    assert report.api == "ok"
    # Structural guarantee: every field is a bool or a short label, never a
    # secret/credential value -- exercised here by confirming the dataclass
    # has no field that could hold one (mirrors HealthCheckService's own docstring).
    for field_name, value in report.__dict__.items():
        assert isinstance(value, (bool, str))


async def test_health_check_fails_closed_when_database_is_unreachable(harness):
    from app.services.admin_service import HealthCheckService

    class _BrokenSession:
        async def execute(self, *args, **kwargs):
            raise RuntimeError("connection refused")

    service = HealthCheckService(db_session=_BrokenSession(), cache=harness.cache, settings=harness.settings)
    report = await service.check()
    assert report.database_reachable is False


async def test_health_check_fails_closed_when_cache_is_unreachable(harness):
    from app.services.admin_service import HealthCheckService

    class _WorkingSession:
        async def execute(self, *args, **kwargs):
            return None

    class _BrokenCache:
        async def set(self, *args, **kwargs):
            raise RuntimeError("cache down")

        async def get(self, *args, **kwargs):
            raise RuntimeError("cache down")

    service = HealthCheckService(db_session=_WorkingSession(), cache=_BrokenCache(), settings=harness.settings)
    report = await service.check()
    assert report.cache_reachable is False


# ==========================================================================
# AIAdminService (Section 10)
# ==========================================================================


async def test_model_status_reflects_registry_configuration_with_no_write_path(harness):
    statuses = harness.ai_admin_service.model_status()
    assert len(statuses) == 6
    assert all(isinstance(s["configured"], bool) for s in statuses)
    # No method on AIAdminService accepts a configuration value to write --
    # the "no arbitrary model configuration changes" requirement is
    # satisfied structurally (the capability doesn't exist), not just gated.
    assert not hasattr(harness.ai_admin_service, "set_model_status")
    assert not hasattr(harness.ai_admin_service, "update_model_config")


async def test_ai_usage_stats_and_failures_and_knowledge_base_status_delegate(harness):
    from app.db.enums import AIPredictionType
    from app.models.ai import AIInferenceFailure, AIPrediction

    org_id = uuid.uuid4()
    await harness.ai_predictions.add(
        AIPrediction(
            id=uuid.uuid4(), nursery_id=org_id, plant_id=uuid.uuid4(),
            prediction_type=AIPredictionType.DISEASE_DETECTION, model_version="v1",
            result={}, confidence=0.9, latency_ms=120,
            created_at=datetime.now(timezone.utc),
        )
    )
    await harness.ai_inference_failures.add(
        AIInferenceFailure(
            nursery_id=org_id, capability="disease_detection", prediction_type="disease_detection",
            error_type="ModelUnavailableError", error_message="no artifact configured",
        )
    )

    usage = await harness.ai_admin_service.usage_stats(org_id)
    assert len(usage) == 1
    assert usage[0]["count"] == 1

    failures, total = await harness.ai_admin_service.list_failures(org_id, offset=0, limit=10)
    assert total == 1
    assert failures[0].nursery_id == org_id

    kb_status = await harness.ai_admin_service.knowledge_base_status(nursery_id=org_id)
    assert isinstance(kb_status, list)


# ==========================================================================
# DataManagementService (Section 11) -- deliberately read-only
# ==========================================================================


async def test_data_management_service_has_no_deletion_method(harness):
    for forbidden in ("delete", "purge", "remove", "destroy"):
        assert not any(forbidden in name.lower() for name in dir(harness.data_management_service) if not name.startswith("_")), (
            f"DataManagementService must expose no destructive method (found something matching {forbidden!r})"
        )


async def test_retention_summary_is_read_only_and_reports_counts(harness):
    org_id = uuid.uuid4()
    summary = await harness.data_management_service.retention_summary(org_id, older_than_days=30)
    assert summary["audit_logs_older_than_cutoff"] == 0
    assert summary["ai_inference_failures_older_than_cutoff"] == 0
    assert "No deletion is performed" in summary["note"]
