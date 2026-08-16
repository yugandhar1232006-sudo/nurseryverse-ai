"""
Integration tests for Module 13's REST API (app/api/routes/admin.py):
authentication, the two coexisting permission shapes (org-scoped reused
codes vs. platform-wide `admin:read`/`admin:manage`), cross-tenant
isolation, the "owner role/account is untouchable" invariants, and the
one route (`/admin/health`) that needs a real `AsyncSession` stub since
`HealthCheckService` is deliberately NOT part of the shared harness
overrides (see tests/conftest.py's own comment on why) -- end to end
through the real ASGI app, the same `auth_client`/`authenticated_client`
harness-backed split every other module's route tests use.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db.enums import EmployeeStatus
from app.models.organization import Employee

pytestmark = pytest.mark.integration

_PLACEHOLDER_ID = "00000000-0000-0000-0000-000000000000"


def _grant(harness, user, *, org_id, role_code, permission_codes):
    harness.grant_role(user, org_id=org_id, role_code=role_code, permission_codes=permission_codes)


async def _add_employee(harness, *, nursery_id, user_id, status=EmployeeStatus.ACTIVE):
    return await harness.employees.add(Employee(id=uuid.uuid4(), nursery_id=nursery_id, user_id=user_id, status=status))


# --------------------------------------------------------------------------
# Authentication -- every route requires a bearer token
# --------------------------------------------------------------------------

_UNAUTH_ROUTES = [
    ("get", "/api/v1/admin/roles"),
    ("get", "/api/v1/admin/permissions"),
    ("get", f"/api/v1/admin/roles/{_PLACEHOLDER_ID}/permissions"),
    ("get", f"/api/v1/admin/users/{_PLACEHOLDER_ID}/effective-permissions"),
    ("post", f"/api/v1/admin/users/{_PLACEHOLDER_ID}/role"),
    ("get", "/api/v1/admin/users"),
    ("get", f"/api/v1/admin/users/{_PLACEHOLDER_ID}"),
    ("post", f"/api/v1/admin/users/{_PLACEHOLDER_ID}/activate"),
    ("post", f"/api/v1/admin/users/{_PLACEHOLDER_ID}/deactivate"),
    ("post", f"/api/v1/admin/users/{_PLACEHOLDER_ID}/lock"),
    ("post", f"/api/v1/admin/users/{_PLACEHOLDER_ID}/unlock"),
    ("get", f"/api/v1/admin/users/{_PLACEHOLDER_ID}/sessions"),
    ("delete", f"/api/v1/admin/users/{_PLACEHOLDER_ID}/sessions/{_PLACEHOLDER_ID}"),
    ("post", f"/api/v1/admin/users/{_PLACEHOLDER_ID}/force-logout"),
    ("post", f"/api/v1/admin/users/{_PLACEHOLDER_ID}/password-reset"),
    ("post", f"/api/v1/admin/users/{_PLACEHOLDER_ID}/email-verification"),
    ("get", "/api/v1/admin/system-config"),
    ("get", "/api/v1/admin/system-config/some-key"),
    ("put", "/api/v1/admin/system-config/some-key"),
    ("get", "/api/v1/admin/feature-flags"),
    ("put", "/api/v1/admin/feature-flags/some-key/organization"),
    ("put", "/api/v1/admin/feature-flags/some-key/platform"),
    ("get", "/api/v1/admin/audit-logs"),
    ("get", "/api/v1/admin/audit-logs/export"),
    ("get", "/api/v1/admin/security-events"),
    ("get", "/api/v1/admin/security-events/platform"),
    ("get", "/api/v1/admin/authorization-denials"),
    ("get", "/api/v1/admin/health"),
    ("get", "/api/v1/admin/ai/models"),
    ("get", f"/api/v1/admin/ai/usage?nursery_id={_PLACEHOLDER_ID}"),
    ("get", f"/api/v1/admin/ai/failures?nursery_id={_PLACEHOLDER_ID}"),
    ("get", "/api/v1/admin/ai/knowledge-base"),
    ("get", f"/api/v1/admin/data-retention?nursery_id={_PLACEHOLDER_ID}"),
]


@pytest.mark.parametrize("method,path", _UNAUTH_ROUTES, ids=[f"{m}:{p}" for m, p in _UNAUTH_ROUTES])
async def test_route_requires_authentication(auth_client, method, path):
    response = await getattr(auth_client, method)(path)
    assert response.status_code == 401


# --------------------------------------------------------------------------
# Authorization -- org-scoped routes reject a caller with no permission
# --------------------------------------------------------------------------


async def test_org_scoped_route_denied_without_employees_read(authenticated_client, harness):
    ac, user = authenticated_client
    _grant(harness, user, org_id=uuid.uuid4(), role_code="sales_staff", permission_codes=[])
    response = await ac.get("/api/v1/admin/users")
    assert response.status_code == 403


async def test_platform_route_denied_without_admin_read(authenticated_client, harness):
    ac, user = authenticated_client
    _grant(harness, user, org_id=uuid.uuid4(), role_code="org_admin", permission_codes=["employees:read"])
    response = await ac.get("/api/v1/admin/system-config")
    assert response.status_code == 403


async def test_platform_mutation_denied_with_only_admin_read(authenticated_client, harness):
    """`admin:read` alone is not enough to write -- `admin:manage` gates every platform-wide mutation."""
    ac, user = authenticated_client
    _grant(harness, user, org_id=uuid.uuid4(), role_code="platform_viewer", permission_codes=["admin:read"])
    response = await ac.put("/api/v1/admin/system-config/max_upload_mb", json={"value": 5, "value_type": "int", "category": "application"})
    assert response.status_code == 403


# --------------------------------------------------------------------------
# Section 1: Role & Permission Administration
# --------------------------------------------------------------------------


async def test_list_roles_and_permissions_and_role_permissions(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    role = harness.seed_system_role("branch_manager", ["employees:read", "audit:read"])
    _grant(harness, user, org_id=org_id, role_code="org_admin", permission_codes=["employees:read"])

    roles_resp = await ac.get("/api/v1/admin/roles")
    assert roles_resp.status_code == 200
    assert any(r["code"] == "branch_manager" for r in roles_resp.json())

    perms_resp = await ac.get("/api/v1/admin/permissions")
    assert perms_resp.status_code == 200
    assert {"employees:read", "audit:read"}.issubset({p["code"] for p in perms_resp.json()})

    role_perms_resp = await ac.get(f"/api/v1/admin/roles/{role.id}/permissions")
    assert role_perms_resp.status_code == 200
    assert {e["permission_code"] for e in role_perms_resp.json()} == {"employees:read", "audit:read"}


async def test_get_effective_permissions_cross_tenant_is_403(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    target = await harness.create_user(email="eff-target@example.com")
    await _add_employee(harness, nursery_id=other_org_id, user_id=target.id)
    _grant(harness, user, org_id=org_id, role_code="org_admin", permission_codes=["employees:read"])

    response = await ac.get(f"/api/v1/admin/users/{target.id}/effective-permissions")
    assert response.status_code == 403


async def test_change_user_role_success_then_effective_permissions_reflect_it(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    target = await harness.create_user(email="role-target@example.com")
    await _add_employee(harness, nursery_id=org_id, user_id=target.id)
    _grant(harness, target, org_id=org_id, role_code="staff", permission_codes=["employees:read"])
    harness.seed_system_role("manager", ["employees:read", "employees:write"])
    _grant(harness, user, org_id=org_id, role_code="org_admin", permission_codes=["employees:read", "employees:write"])

    response = await ac.post(f"/api/v1/admin/users/{target.id}/role", json={"new_role_code": "manager"})
    assert response.status_code == 204

    effective = await ac.get(f"/api/v1/admin/users/{target.id}/effective-permissions")
    assert effective.status_code == 200
    assert effective.json()["role_code"] == "manager"


async def test_change_user_role_rejects_owner_role_change(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    owner = await harness.create_user(email="owner-role@example.com")
    await _add_employee(harness, nursery_id=org_id, user_id=owner.id)
    _grant(harness, owner, org_id=org_id, role_code="owner", permission_codes=[])
    harness.seed_system_role("manager", ["employees:read"])
    _grant(harness, user, org_id=org_id, role_code="org_admin", permission_codes=["employees:read", "employees:write"])

    response = await ac.post(f"/api/v1/admin/users/{owner.id}/role", json={"new_role_code": "manager"})
    assert response.status_code == 422


# --------------------------------------------------------------------------
# Section 2: User Administration
# --------------------------------------------------------------------------


async def test_search_and_get_user_detail(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    target = await harness.create_user(email="detail-target@example.com")
    await _add_employee(harness, nursery_id=org_id, user_id=target.id)
    _grant(harness, user, org_id=org_id, role_code="org_admin", permission_codes=["employees:read"])

    search_resp = await ac.get("/api/v1/admin/users")
    assert search_resp.status_code == 200
    assert search_resp.json()["meta"]["total_items"] == 1

    detail_resp = await ac.get(f"/api/v1/admin/users/{target.id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["email"] == "detail-target@example.com"


async def test_get_user_detail_cross_tenant_is_403(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    target = await harness.create_user(email="othertenant@example.com")
    await _add_employee(harness, nursery_id=other_org_id, user_id=target.id)
    _grant(harness, user, org_id=org_id, role_code="org_admin", permission_codes=["employees:read"])

    response = await ac.get(f"/api/v1/admin/users/{target.id}")
    assert response.status_code == 403


async def test_activate_deactivate_lock_unlock_user(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    target = await harness.create_user(email="lifecycle-target@example.com", is_active=True)
    await _add_employee(harness, nursery_id=org_id, user_id=target.id)
    _grant(harness, user, org_id=org_id, role_code="org_admin", permission_codes=["employees:read", "employees:write"])

    deactivate_resp = await ac.post(f"/api/v1/admin/users/{target.id}/deactivate")
    assert deactivate_resp.status_code == 200
    assert deactivate_resp.json()["is_active"] is False

    activate_resp = await ac.post(f"/api/v1/admin/users/{target.id}/activate")
    assert activate_resp.status_code == 200
    assert activate_resp.json()["is_active"] is True

    lock_resp = await ac.post(f"/api/v1/admin/users/{target.id}/lock", json={"duration_minutes": 30})
    assert lock_resp.status_code == 200
    assert lock_resp.json()["locked_until"] is not None

    unlock_resp = await ac.post(f"/api/v1/admin/users/{target.id}/unlock")
    assert unlock_resp.status_code == 200
    assert unlock_resp.json()["locked_until"] is None


async def test_cannot_deactivate_the_organization_owner(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    owner = await harness.create_user(email="owner-deact@example.com")
    await _add_employee(harness, nursery_id=org_id, user_id=owner.id)
    _grant(harness, owner, org_id=org_id, role_code="owner", permission_codes=[])
    _grant(harness, user, org_id=org_id, role_code="org_admin", permission_codes=["employees:read", "employees:write"])

    response = await ac.post(f"/api/v1/admin/users/{owner.id}/deactivate")
    assert response.status_code == 403


async def test_session_list_revoke_and_force_logout(authenticated_client, harness):
    from app.models.auth import RefreshToken

    ac, user = authenticated_client
    org_id = uuid.uuid4()
    target = await harness.create_user(email="session-target@example.com")
    await _add_employee(harness, nursery_id=org_id, user_id=target.id)
    _grant(harness, user, org_id=org_id, role_code="org_admin", permission_codes=["employees:read", "employees:write"])
    token = await harness.refresh_tokens.add(
        RefreshToken(
            id=uuid.uuid4(), user_id=target.id, token_hash="ih1", family_id=uuid.uuid4(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
    )

    list_resp = await ac.get(f"/api/v1/admin/users/{target.id}/sessions")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    revoke_resp = await ac.delete(f"/api/v1/admin/users/{target.id}/sessions/{token.id}")
    assert revoke_resp.status_code == 204

    await harness.refresh_tokens.add(
        RefreshToken(
            id=uuid.uuid4(), user_id=target.id, token_hash="ih2", family_id=uuid.uuid4(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
    )
    logout_resp = await ac.post(f"/api/v1/admin/users/{target.id}/force-logout")
    assert logout_resp.status_code == 204
    final_list = await ac.get(f"/api/v1/admin/users/{target.id}/sessions")
    assert final_list.json() == []


async def test_admin_password_reset_and_email_verification(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    target = await harness.create_user(email="pwtarget@example.com", is_email_verified=False)
    await _add_employee(harness, nursery_id=org_id, user_id=target.id)
    _grant(harness, user, org_id=org_id, role_code="org_admin", permission_codes=["employees:read", "employees:write"])

    reset_resp = await ac.post(f"/api/v1/admin/users/{target.id}/password-reset")
    assert reset_resp.status_code == 202
    assert len(harness.password_reset_tokens.tokens) == 1

    verify_resp = await ac.post(f"/api/v1/admin/users/{target.id}/email-verification")
    assert verify_resp.status_code == 202
    assert len(harness.email_verification_tokens.tokens) == 1


# --------------------------------------------------------------------------
# Section 6: System Configuration (platform-wide)
# --------------------------------------------------------------------------


async def test_system_config_crud_round_trip(authenticated_client, harness):
    ac, user = authenticated_client
    _grant(harness, user, org_id=uuid.uuid4(), role_code="platform_admin", permission_codes=["admin:read", "admin:manage"])

    put_resp = await ac.put(
        "/api/v1/admin/system-config/session_timeout_minutes",
        json={"value": 60, "value_type": "int", "category": "application", "description": "idle timeout"},
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["value"] == 60

    get_resp = await ac.get("/api/v1/admin/system-config/session_timeout_minutes")
    assert get_resp.status_code == 200
    assert get_resp.json()["value"] == 60

    list_resp = await ac.get("/api/v1/admin/system-config", params={"category": "application"})
    assert list_resp.status_code == 200
    assert any(c["key"] == "session_timeout_minutes" for c in list_resp.json())


async def test_get_system_config_unknown_key_is_404(authenticated_client, harness):
    ac, user = authenticated_client
    _grant(harness, user, org_id=uuid.uuid4(), role_code="platform_admin", permission_codes=["admin:read"])
    response = await ac.get("/api/v1/admin/system-config/does-not-exist")
    assert response.status_code == 404


async def test_set_system_config_rejects_invalid_category(authenticated_client, harness):
    ac, user = authenticated_client
    _grant(harness, user, org_id=uuid.uuid4(), role_code="platform_admin", permission_codes=["admin:read", "admin:manage"])
    response = await ac.put(
        "/api/v1/admin/system-config/bad-key",
        json={"value": 1, "value_type": "int", "category": "not-a-category"},
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------
# Section 7: Feature Flags
# --------------------------------------------------------------------------


async def test_feature_flag_platform_then_org_override(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    _grant(
        harness, user, org_id=org_id, role_code="platform_admin",
        permission_codes=["admin:read", "admin:manage", "feature_flags:read", "feature_flags:manage"],
    )

    platform_resp = await ac.put(
        "/api/v1/admin/feature-flags/new-dashboard/platform", json={"is_enabled": True, "description": "beta"}
    )
    assert platform_resp.status_code == 200
    assert platform_resp.json()["nursery_id"] is None

    org_resp = await ac.put(
        "/api/v1/admin/feature-flags/new-dashboard/organization", json={"is_enabled": False, "description": "opt out"}
    )
    assert org_resp.status_code == 200
    assert org_resp.json()["nursery_id"] == str(org_id)

    list_resp = await ac.get("/api/v1/admin/feature-flags")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 2


async def test_org_feature_flag_write_denied_with_only_read_permission(authenticated_client, harness):
    ac, user = authenticated_client
    _grant(harness, user, org_id=uuid.uuid4(), role_code="viewer", permission_codes=["feature_flags:read"])
    response = await ac.put("/api/v1/admin/feature-flags/x/organization", json={"is_enabled": True})
    assert response.status_code == 403


async def test_platform_feature_flag_write_denied_with_only_org_manage_permission(authenticated_client, harness):
    """`feature_flags:manage` (org tier) must NOT be enough to write the platform-wide default -- that needs `admin:manage`."""
    ac, user = authenticated_client
    _grant(harness, user, org_id=uuid.uuid4(), role_code="org_admin", permission_codes=["feature_flags:read", "feature_flags:manage"])
    response = await ac.put("/api/v1/admin/feature-flags/x/platform", json={"is_enabled": True})
    assert response.status_code == 403


# --------------------------------------------------------------------------
# Section 8: Audit & Security Administration
# --------------------------------------------------------------------------


async def test_audit_log_search_and_export_are_org_scoped(authenticated_client, harness):
    from app.models.platform import AuditLog

    ac, user = authenticated_client
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    await harness.audit_logs.log(
        AuditLog(nursery_id=org_id, actor_user_id=uuid.uuid4(), action="plant.created", entity_type="Plant",
                  entity_id=uuid.uuid4(), diff={}, created_at=datetime.now(timezone.utc))
    )
    await harness.audit_logs.log(
        AuditLog(nursery_id=other_org_id, actor_user_id=uuid.uuid4(), action="plant.created", entity_type="Plant",
                  entity_id=uuid.uuid4(), diff={}, created_at=datetime.now(timezone.utc))
    )
    _grant(harness, user, org_id=org_id, role_code="org_admin", permission_codes=["audit:read"])

    search_resp = await ac.get("/api/v1/admin/audit-logs")
    assert search_resp.status_code == 200
    assert search_resp.json()["meta"]["total_items"] == 1

    export_resp = await ac.get("/api/v1/admin/audit-logs/export", params={"format": "csv"})
    assert export_resp.status_code == 200
    assert "attachment" in export_resp.headers["content-disposition"]


async def test_security_events_org_scoped_vs_platform_wide(authenticated_client, harness):
    from app.models.auth import SecurityEvent
    from app.db.enums import SecurityEventType

    ac, user = authenticated_client
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    u1 = await harness.create_user(email="sec1@example.com")
    u2 = await harness.create_user(email="sec2@example.com")
    await _add_employee(harness, nursery_id=org_id, user_id=u1.id)
    await _add_employee(harness, nursery_id=other_org_id, user_id=u2.id)
    await harness.security_events.log(
        SecurityEvent(user_id=u1.id, email=u1.email, event_type=SecurityEventType.LOGIN_SUCCESS, created_at=datetime.now(timezone.utc))
    )
    await harness.security_events.log(
        SecurityEvent(user_id=u2.id, email=u2.email, event_type=SecurityEventType.LOGIN_SUCCESS, created_at=datetime.now(timezone.utc))
    )
    _grant(harness, user, org_id=org_id, role_code="org_admin", permission_codes=["audit:read"])

    org_resp = await ac.get("/api/v1/admin/security-events")
    assert org_resp.status_code == 200
    assert org_resp.json()["meta"]["total_items"] == 1

    platform_resp = await ac.get("/api/v1/admin/security-events/platform")
    assert platform_resp.status_code == 403  # audit:read alone doesn't grant the platform-wide view

    # A separate user/client rather than re-granting the SAME user a new
    # role mid-test: `grant_role` is a raw test-setup helper that mutates
    # `FakePermissionRepository` directly -- it doesn't go through
    # `RoleAdminService.change_user_role`'s `permission_service.invalidate_user(...)`
    # call, so the already-resolved-and-cached permission set for `user`
    # (warmed by the `GET /security-events` call above) would stay stale.
    platform_user = await harness.create_user(email="platform-viewer@example.com")
    _grant(harness, platform_user, org_id=org_id, role_code="platform_admin", permission_codes=["admin:read"])
    from httpx import ASGITransport, AsyncClient

    from app.api.deps import get_current_user
    from app.main import create_app
    from tests.conftest import _apply_common_overrides

    app = create_app(settings=harness.settings)
    _apply_common_overrides(app, harness)
    app.dependency_overrides[get_current_user] = lambda: platform_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as platform_ac:
        platform_resp = await platform_ac.get("/api/v1/admin/security-events/platform")
    app.dependency_overrides.clear()

    assert platform_resp.status_code == 200
    assert platform_resp.json()["meta"]["total_items"] == 2


async def test_authorization_denials_search_is_org_scoped(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    _grant(harness, user, org_id=org_id, role_code="org_admin", permission_codes=["audit:read"])

    class _Denial:
        def __init__(self):
            self.id = uuid.uuid4()
            self.user_id = uuid.uuid4()
            self.permission_code = "employees:write"
            self.resource_type = None
            self.resource_id = None
            self.nursery_id = org_id
            self.branch_id = None
            self.reason = "no_permission"
            self.explanation = "missing permission"
            self.request_id = None
            self.created_at = datetime.now(timezone.utc)

    harness.denials.denials.append(_Denial())
    response = await ac.get("/api/v1/admin/authorization-denials")
    assert response.status_code == 200
    assert response.json()["meta"]["total_items"] == 1


# --------------------------------------------------------------------------
# Section 9: System Health -- the one route needing a real `AsyncSession`
# stub, since `HealthCheckService` is deliberately not part of the shared
# harness overrides (see tests/conftest.py's own comment).
# --------------------------------------------------------------------------


async def test_admin_health_reports_reachable_when_dependencies_work(harness):
    from httpx import ASGITransport, AsyncClient

    from app.api.deps import get_current_user, get_health_check_service
    from app.main import create_app
    from app.services.admin_service import HealthCheckService
    from tests.conftest import _apply_common_overrides

    class _WorkingSession:
        async def execute(self, *args, **kwargs):
            return None

    user = await harness.create_user(email="health-admin@example.com")
    _grant(harness, user, org_id=uuid.uuid4(), role_code="platform_admin", permission_codes=["admin:read"])

    app = create_app(settings=harness.settings)
    _apply_common_overrides(app, harness)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_health_check_service] = lambda: HealthCheckService(
        db_session=_WorkingSession(), cache=harness.cache, settings=harness.settings
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        response = await ac.get("/api/v1/admin/health")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["database_reachable"] is True
    assert body["cache_reachable"] is True
    assert body["api"] == "ok"


async def test_admin_health_reports_unreachable_database_without_leaking_a_stack_trace(harness):
    from httpx import ASGITransport, AsyncClient

    from app.api.deps import get_current_user, get_health_check_service
    from app.main import create_app
    from app.services.admin_service import HealthCheckService
    from tests.conftest import _apply_common_overrides

    class _BrokenSession:
        async def execute(self, *args, **kwargs):
            raise RuntimeError("connection refused")

    user = await harness.create_user(email="health-admin2@example.com")
    _grant(harness, user, org_id=uuid.uuid4(), role_code="platform_admin", permission_codes=["admin:read"])

    app = create_app(settings=harness.settings)
    _apply_common_overrides(app, harness)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_health_check_service] = lambda: HealthCheckService(
        db_session=_BrokenSession(), cache=harness.cache, settings=harness.settings
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        response = await ac.get("/api/v1/admin/health")
    app.dependency_overrides.clear()

    assert response.status_code == 200  # still 200 -- health reports DEGRADED state, doesn't 500
    body = response.json()
    assert body["database_reachable"] is False
    assert "RuntimeError" not in str(body)
    assert "connection refused" not in str(body)


# --------------------------------------------------------------------------
# Section 10: AI Administration (platform-wide)
# --------------------------------------------------------------------------


async def test_ai_model_status_usage_failures_and_knowledge_base(authenticated_client, harness):
    from app.db.enums import AIPredictionType
    from app.models.ai import AIInferenceFailure, AIPrediction

    ac, user = authenticated_client
    org_id = uuid.uuid4()
    _grant(harness, user, org_id=org_id, role_code="platform_admin", permission_codes=["admin:read"])
    await harness.ai_predictions.add(
        AIPrediction(
            id=uuid.uuid4(), nursery_id=org_id, plant_id=uuid.uuid4(),
            prediction_type=AIPredictionType.DISEASE_DETECTION, model_version="v1",
            result={}, confidence=0.8, latency_ms=90, created_at=datetime.now(timezone.utc),
        )
    )
    await harness.ai_inference_failures.add(
        AIInferenceFailure(
            nursery_id=org_id, capability="disease_detection", prediction_type="disease_detection",
            error_type="ModelUnavailableError", error_message="no artifact configured",
        )
    )

    models_resp = await ac.get("/api/v1/admin/ai/models")
    assert models_resp.status_code == 200
    assert len(models_resp.json()) == 6

    usage_resp = await ac.get("/api/v1/admin/ai/usage", params={"nursery_id": str(org_id)})
    assert usage_resp.status_code == 200
    assert usage_resp.json()[0]["count"] == 1

    failures_resp = await ac.get("/api/v1/admin/ai/failures", params={"nursery_id": str(org_id)})
    assert failures_resp.status_code == 200
    assert failures_resp.json()["meta"]["total_items"] == 1

    kb_resp = await ac.get("/api/v1/admin/ai/knowledge-base")
    assert kb_resp.status_code == 200


# --------------------------------------------------------------------------
# Section 11: Data Management -- read-only
# --------------------------------------------------------------------------


async def test_data_retention_summary_is_read_only(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    _grant(harness, user, org_id=org_id, role_code="platform_admin", permission_codes=["admin:read"])

    response = await ac.get("/api/v1/admin/data-retention", params={"nursery_id": str(org_id)})
    assert response.status_code == 200
    body = response.json()
    assert body["audit_logs_older_than_cutoff"] == 0
    assert "No deletion is performed" in body["note"]
