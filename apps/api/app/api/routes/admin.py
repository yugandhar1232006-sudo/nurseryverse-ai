"""
Phase 6 Module 13 (Administration & System Management) REST API.

Two permission shapes coexist in this file, exactly matching the design
laid out in `app/services/admin_service.py`'s own module docstring:

  - Org-scoped routes reuse EXISTING permission codes from earlier
    modules (`employees:read`/`employees:write`, `audit:read`,
    `feature_flags:read`/`feature_flags:manage`) rather than minting new
    ones -- Section 1's role/permission catalog and Section 2's user
    administration are, mechanically, staff-management operations on top
    of the same Employee/User records Module 4 already protects.
  - Platform-wide routes (System Configuration, System Health, AI
    Administration, Data Management, and the platform tier of Feature
    Flags) require `admin:read`/`admin:manage` (migration 0018), checked
    with no path-scoped nursery id -- `require_permission(...)` with no
    `resource_type`/org match, the same org-agnostic shape Module 12's
    report catalog route established. Only the seeded `platform_admin`
    system role is ever granted these two permissions.

Sections 3/4/5 (Employee/Nursery/Branch Administration) are NOT
duplicated here -- `app/api/routes/employees.py`/`organizations.py`/
`branches.py` (Module 4) already expose every capability those sections
ask for; this file adds only the one genuinely missing piece
(`POST /employees/{id}/reactivate`, added directly to employees.py).
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.deps import (
    PageParams,
    TenantContext,
    get_ai_admin_service,
    get_audit_admin_service,
    get_current_user,
    get_data_management_service,
    get_feature_flag_service,
    get_health_check_service,
    get_role_admin_service,
    get_system_config_service,
    get_tenant_context,
    get_user_admin_service,
    request_context,
    require_permission,
)
from app.core.exceptions import ValidationError
from app.core.responses import ErrorResponse, Page, PageMeta
from app.db.enums import ReportFormat, SecurityEventType
from app.models.identity import User
from app.reporting.exporters import render
from app.schemas.admin import (
    AdminAuditLogEntryResponse,
    AdminUserResponse,
    AIInferenceFailureResponse,
    AIModelStatusResponse,
    AIUsageStatsResponse,
    AuthorizationDenialResponse,
    ChangeUserRoleRequest,
    DataRetentionSummaryResponse,
    EffectivePermissionsResponse,
    FeatureFlagResponse,
    HealthReportResponse,
    KnowledgeBaseStatusResponse,
    LockAccountRequest,
    PermissionResponse,
    RolePermissionEntry,
    RoleResponse,
    SecurityEventResponse,
    SessionResponse,
    SetFeatureFlagRequest,
    SetSystemConfigRequest,
    SystemConfigResponse,
)
from app.schemas.reports import DateRangeParams, get_date_range_params
from app.services.admin_service import (
    AIAdminService,
    AuditAdminService,
    DataManagementService,
    FeatureFlagService,
    HealthCheckService,
    RoleAdminService,
    SystemConfigService,
    UserAdminService,
)
from app.services.authorization_service import AuthorizationDecision

router = APIRouter()

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Missing permission or cross-tenant access"},
}
_ADMIN_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Missing admin:read/admin:manage permission"},
}


def _req_ctx(request: Request):
    """Thin `Depends()`-compatible wrapper -- `request_context` (app/api/deps.py) is a plain function taking `Request` directly, called inline everywhere else in this codebase; wrapping it once here lets every route below use the same `Depends(_req_ctx)` shape instead of repeating `request_context(request)` inline at every call site."""
    return request_context(request)


def _require_home_org(tenant: TenantContext) -> uuid.UUID:
    """
    Every mutating platform-wide route still needs *some* `nursery_id` for
    the resulting `AuditLog` row (that column is `NOT NULL` -- Phase 5's
    original schema; see `app/services/admin_service.py`'s module
    docstring for why "the caller's own home org" is the documented
    stand-in). `require_permission("admin:manage")` only ever succeeds for
    a caller who holds SOME RoleAssignment (an empty `ResolvedAccess` -
    ---- grants nothing), so `tenant.org_id` being `None` here would be an
    internal inconsistency, not a normal request -- surfaced as a 422
    rather than silently writing a `NULL`-violating row.
    """
    if tenant.org_id is None:
        raise ValidationError("Unable to resolve an organization to attribute this administrative action to.")
    return tenant.org_id


# ======================================================================
# Section 1: Role & Permission Administration
# ======================================================================


@router.get(
    "/roles", response_model=list[RoleResponse], responses=_ERROR_RESPONSES,
    summary="List system roles (plus this org's own custom roles, if any)",
)
async def list_roles(
    tenant: TenantContext = Depends(get_tenant_context),
    service: RoleAdminService = Depends(get_role_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("employees:read", resource_type="role")),
) -> list[RoleResponse]:
    roles = await service.list_roles(nursery_id=tenant.org_id)
    return [RoleResponse.model_validate(r) for r in roles]


@router.get(
    "/permissions", response_model=list[PermissionResponse], responses=_ERROR_RESPONSES,
    summary="List the full permission catalog",
)
async def list_permissions(
    service: RoleAdminService = Depends(get_role_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("employees:read", resource_type="permission")),
) -> list[PermissionResponse]:
    permissions = await service.list_permissions()
    return [PermissionResponse.model_validate(p) for p in permissions]


@router.get(
    "/roles/{role_id}/permissions", response_model=list[RolePermissionEntry], responses=_ERROR_RESPONSES,
    summary="List the permissions granted to one role",
)
async def get_role_permissions(
    role_id: uuid.UUID,
    service: RoleAdminService = Depends(get_role_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("employees:read", resource_type="role")),
) -> list[RolePermissionEntry]:
    pairs = await service.get_role_permissions(role_id)
    return [RolePermissionEntry(permission_code=code, scope=scope) for code, scope in pairs]


@router.get(
    "/users/{user_id}/effective-permissions", response_model=EffectivePermissionsResponse, responses=_ERROR_RESPONSES,
    summary="Inspect a user's effective (resolved) permissions",
)
async def get_effective_permissions(
    user_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    role_service: RoleAdminService = Depends(get_role_admin_service),
    user_service: UserAdminService = Depends(get_user_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("employees:read", resource_type="user")),
) -> EffectivePermissionsResponse:
    org_id = _require_home_org(tenant)
    await user_service.get_user_detail(nursery_id=org_id, target_user_id=user_id)  # cross-tenant 403 gate
    access = await role_service.get_effective_permissions(user_id)
    return EffectivePermissionsResponse(
        org_id=access.org_id, role_code=access.role_code, branch_ids=access.branch_ids,
        is_org_wide=access.is_org_wide(), permissions=access.permissions,
    )


@router.post(
    "/users/{user_id}/role", response_model=None, status_code=status.HTTP_204_NO_CONTENT,
    responses={**_ERROR_RESPONSES, 422: {"model": ErrorResponse, "description": "Unknown role code or protected role"}},
    summary="Change a staff member's role",
)
async def change_user_role(
    user_id: uuid.UUID,
    body: ChangeUserRoleRequest,
    request_ctx=Depends(_req_ctx),
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    service: RoleAdminService = Depends(get_role_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("employees:write", resource_type="role")),
) -> None:
    org_id = _require_home_org(tenant)
    await service.change_user_role(
        actor_user_id=user.id, nursery_id=org_id, target_user_id=user_id,
        new_role_code=body.new_role_code, request_id=request_ctx.request_id,
    )


# ======================================================================
# Section 2: User Administration
# ======================================================================


def _to_admin_user_response(employee, user: User) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id, employee_id=employee.id, email=user.email, full_name=user.full_name,
        is_active=user.is_active, is_email_verified=user.is_email_verified,
        locked_until=user.locked_until, failed_login_attempts=user.failed_login_attempts,
        last_login_at=user.last_login_at, employee_status=employee.status.value
        if hasattr(employee.status, "value") else employee.status,
        department=employee.department, position=employee.position,
    )


@router.get(
    "/users", response_model=Page[AdminUserResponse], responses=_ERROR_RESPONSES,
    summary="Search this organization's user accounts",
)
async def search_users(
    page_params: PageParams = Depends(),
    tenant: TenantContext = Depends(get_tenant_context),
    service: UserAdminService = Depends(get_user_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("employees:read", resource_type="user")),
) -> Page[AdminUserResponse]:
    org_id = _require_home_org(tenant)
    rows, total = await service.search_users(nursery_id=org_id, offset=page_params.offset, limit=page_params.page_size)
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[_to_admin_user_response(e, u) for e, u in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


@router.get(
    "/users/{user_id}", response_model=AdminUserResponse, responses=_ERROR_RESPONSES,
    summary="Get one user's account details",
)
async def get_user_detail(
    user_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    service: UserAdminService = Depends(get_user_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("employees:read", resource_type="user")),
) -> AdminUserResponse:
    org_id = _require_home_org(tenant)
    employee, user = await service.get_user_detail(nursery_id=org_id, target_user_id=user_id)
    return _to_admin_user_response(employee, user)


@router.post(
    "/users/{user_id}/activate", response_model=AdminUserResponse, responses=_ERROR_RESPONSES,
    summary="Activate a user's account",
)
async def activate_user(
    user_id: uuid.UUID,
    request_ctx=Depends(_req_ctx),
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    service: UserAdminService = Depends(get_user_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("employees:write", resource_type="user")),
) -> AdminUserResponse:
    org_id = _require_home_org(tenant)
    updated = await service.set_account_active(
        actor_user_id=user.id, nursery_id=org_id, target_user_id=user_id, is_active=True,
        request_id=request_ctx.request_id,
    )
    employee, _ = await service.get_user_detail(nursery_id=org_id, target_user_id=user_id)
    return _to_admin_user_response(employee, updated)


@router.post(
    "/users/{user_id}/deactivate", response_model=AdminUserResponse, responses=_ERROR_RESPONSES,
    summary="Deactivate a user's account",
)
async def deactivate_user(
    user_id: uuid.UUID,
    request_ctx=Depends(_req_ctx),
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    service: UserAdminService = Depends(get_user_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("employees:write", resource_type="user")),
) -> AdminUserResponse:
    org_id = _require_home_org(tenant)
    updated = await service.set_account_active(
        actor_user_id=user.id, nursery_id=org_id, target_user_id=user_id, is_active=False,
        request_id=request_ctx.request_id,
    )
    employee, _ = await service.get_user_detail(nursery_id=org_id, target_user_id=user_id)
    return _to_admin_user_response(employee, updated)


@router.post(
    "/users/{user_id}/lock", response_model=AdminUserResponse, responses=_ERROR_RESPONSES,
    summary="Lock a user's account for a fixed duration",
)
async def lock_user(
    user_id: uuid.UUID,
    body: LockAccountRequest,
    request_ctx=Depends(_req_ctx),
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    service: UserAdminService = Depends(get_user_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("employees:write", resource_type="user")),
) -> AdminUserResponse:
    org_id = _require_home_org(tenant)
    updated = await service.lock_account(
        actor_user_id=user.id, nursery_id=org_id, target_user_id=user_id,
        duration_minutes=body.duration_minutes, request_id=request_ctx.request_id,
    )
    employee, _ = await service.get_user_detail(nursery_id=org_id, target_user_id=user_id)
    return _to_admin_user_response(employee, updated)


@router.post(
    "/users/{user_id}/unlock", response_model=AdminUserResponse, responses=_ERROR_RESPONSES,
    summary="Unlock a user's account",
)
async def unlock_user(
    user_id: uuid.UUID,
    request_ctx=Depends(_req_ctx),
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    service: UserAdminService = Depends(get_user_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("employees:write", resource_type="user")),
) -> AdminUserResponse:
    org_id = _require_home_org(tenant)
    updated = await service.unlock_account(
        actor_user_id=user.id, nursery_id=org_id, target_user_id=user_id, request_id=request_ctx.request_id,
    )
    employee, _ = await service.get_user_detail(nursery_id=org_id, target_user_id=user_id)
    return _to_admin_user_response(employee, updated)


@router.get(
    "/users/{user_id}/sessions", response_model=list[SessionResponse], responses=_ERROR_RESPONSES,
    summary="List a user's active sessions",
)
async def list_user_sessions(
    user_id: uuid.UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    service: UserAdminService = Depends(get_user_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("employees:read", resource_type="user")),
) -> list[SessionResponse]:
    org_id = _require_home_org(tenant)
    sessions = await service.list_sessions(nursery_id=org_id, target_user_id=user_id)
    return [SessionResponse.model_validate(s) for s in sessions]


@router.delete(
    "/users/{user_id}/sessions/{session_id}", response_model=None, status_code=status.HTTP_204_NO_CONTENT, responses=_ERROR_RESPONSES,
    summary="Revoke one of a user's sessions",
)
async def revoke_user_session(
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    request_ctx=Depends(_req_ctx),
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    service: UserAdminService = Depends(get_user_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("employees:write", resource_type="user")),
) -> None:
    org_id = _require_home_org(tenant)
    await service.revoke_session(
        actor_user_id=user.id, nursery_id=org_id, target_user_id=user_id, session_id=session_id,
        request_id=request_ctx.request_id,
    )


@router.post(
    "/users/{user_id}/force-logout", response_model=None, status_code=status.HTTP_204_NO_CONTENT, responses=_ERROR_RESPONSES,
    summary="Revoke every session for a user immediately",
)
async def force_logout_user(
    user_id: uuid.UUID,
    request_ctx=Depends(_req_ctx),
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    service: UserAdminService = Depends(get_user_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("employees:write", resource_type="user")),
) -> None:
    org_id = _require_home_org(tenant)
    await service.force_logout(
        actor_user_id=user.id, nursery_id=org_id, target_user_id=user_id, request_id=request_ctx.request_id,
    )


@router.post(
    "/users/{user_id}/password-reset", status_code=status.HTTP_202_ACCEPTED, responses=_ERROR_RESPONSES,
    summary="Trigger a password reset email for a user",
)
async def admin_request_password_reset(
    user_id: uuid.UUID,
    request_ctx=Depends(_req_ctx),
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    service: UserAdminService = Depends(get_user_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("employees:write", resource_type="user")),
) -> None:
    org_id = _require_home_org(tenant)
    await service.request_password_reset(
        actor_user_id=user.id, nursery_id=org_id, target_user_id=user_id, request_id=request_ctx.request_id,
    )


@router.post(
    "/users/{user_id}/email-verification", status_code=status.HTTP_202_ACCEPTED, responses=_ERROR_RESPONSES,
    summary="Trigger an email-verification email for a user",
)
async def admin_request_email_verification(
    user_id: uuid.UUID,
    request_ctx=Depends(_req_ctx),
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    service: UserAdminService = Depends(get_user_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("employees:write", resource_type="user")),
) -> None:
    org_id = _require_home_org(tenant)
    await service.request_email_verification(
        actor_user_id=user.id, nursery_id=org_id, target_user_id=user_id, request_id=request_ctx.request_id,
    )


# ======================================================================
# Section 6: System Configuration (platform-wide)
# ======================================================================


@router.get(
    "/system-config", response_model=list[SystemConfigResponse], responses=_ADMIN_ERROR_RESPONSES,
    summary="List system configuration entries",
)
async def list_system_config(
    category: str | None = Query(None),
    service: SystemConfigService = Depends(get_system_config_service),
    decision: AuthorizationDecision = Depends(require_permission("admin:read")),
) -> list[SystemConfigResponse]:
    configs = await service.list_configs(category=category)
    return [SystemConfigResponse.from_model(c) for c in configs]


@router.get(
    "/system-config/{key}", response_model=SystemConfigResponse, responses=_ADMIN_ERROR_RESPONSES,
    summary="Get one system configuration entry",
)
async def get_system_config(
    key: str,
    service: SystemConfigService = Depends(get_system_config_service),
    decision: AuthorizationDecision = Depends(require_permission("admin:read")),
) -> SystemConfigResponse:
    config = await service.get_config(key)
    return SystemConfigResponse.from_model(config)


@router.put(
    "/system-config/{key}", response_model=SystemConfigResponse, responses=_ADMIN_ERROR_RESPONSES,
    summary="Create or update a system configuration entry",
)
async def set_system_config(
    key: str,
    body: SetSystemConfigRequest,
    request_ctx=Depends(_req_ctx),
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    service: SystemConfigService = Depends(get_system_config_service),
    decision: AuthorizationDecision = Depends(require_permission("admin:manage")),
) -> SystemConfigResponse:
    org_id = _require_home_org(tenant)
    config = await service.set_config(
        actor_user_id=user.id, audit_nursery_id=org_id, key=key, value=body.value,
        value_type=body.value_type, category=body.category, description=body.description,
        request_id=request_ctx.request_id,
    )
    return SystemConfigResponse.from_model(config)


# ======================================================================
# Section 7: Feature Flags
# ======================================================================


@router.get(
    "/feature-flags", response_model=list[FeatureFlagResponse], responses=_ERROR_RESPONSES,
    summary="List feature flags visible to this organization (platform defaults plus this org's own overrides)",
)
async def list_feature_flags(
    tenant: TenantContext = Depends(get_tenant_context),
    service: FeatureFlagService = Depends(get_feature_flag_service),
    decision: AuthorizationDecision = Depends(require_permission("feature_flags:read")),
) -> list[FeatureFlagResponse]:
    flags = await service.list_flags(nursery_id=tenant.org_id)
    return [FeatureFlagResponse.model_validate(f) for f in flags]


@router.put(
    "/feature-flags/{key}/organization", response_model=FeatureFlagResponse, responses=_ERROR_RESPONSES,
    summary="Set this organization's (or one of its branches') override for a feature flag",
)
async def set_org_feature_flag(
    key: str,
    body: SetFeatureFlagRequest,
    request_ctx=Depends(_req_ctx),
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    service: FeatureFlagService = Depends(get_feature_flag_service),
    decision: AuthorizationDecision = Depends(require_permission("feature_flags:manage")),
) -> FeatureFlagResponse:
    org_id = _require_home_org(tenant)
    flag = await service.set_flag(
        actor_user_id=user.id, audit_nursery_id=org_id, key=key, target_nursery_id=org_id,
        branch_id=body.branch_id, is_enabled=body.is_enabled, description=body.description,
        request_id=request_ctx.request_id,
    )
    return FeatureFlagResponse.model_validate(flag)


@router.put(
    "/feature-flags/{key}/platform", response_model=FeatureFlagResponse, responses=_ADMIN_ERROR_RESPONSES,
    summary="Set the platform-wide default for a feature flag",
)
async def set_platform_feature_flag(
    key: str,
    body: SetFeatureFlagRequest,
    request_ctx=Depends(_req_ctx),
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    service: FeatureFlagService = Depends(get_feature_flag_service),
    decision: AuthorizationDecision = Depends(require_permission("admin:manage")),
) -> FeatureFlagResponse:
    org_id = _require_home_org(tenant)
    flag = await service.set_flag(
        actor_user_id=user.id, audit_nursery_id=org_id, key=key, target_nursery_id=None,
        branch_id=None, is_enabled=body.is_enabled, description=body.description,
        request_id=request_ctx.request_id,
    )
    return FeatureFlagResponse.model_validate(flag)


# ======================================================================
# Section 8: Audit & Security Administration
# ======================================================================


@router.get(
    "/audit-logs", response_model=Page[AdminAuditLogEntryResponse], responses=_ERROR_RESPONSES,
    summary="Search this organization's audit log with filters",
)
async def search_audit_logs(
    page_params: PageParams = Depends(),
    date_range: DateRangeParams = Depends(get_date_range_params),
    actor_user_id: uuid.UUID | None = Query(None),
    action: str | None = Query(None),
    entity_type: str | None = Query(None),
    result: str | None = Query(None),
    branch_id: uuid.UUID | None = Query(None),
    tenant: TenantContext = Depends(get_tenant_context),
    service: AuditAdminService = Depends(get_audit_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("audit:read", resource_type="audit_log")),
) -> Page[AdminAuditLogEntryResponse]:
    org_id = _require_home_org(tenant)
    rows, total = await service.search_audit_logs(
        org_id, offset=page_params.offset, limit=page_params.page_size,
        date_from=date_range.date_from, date_to=date_range.date_to, actor_user_id=actor_user_id,
        action=action, entity_type=entity_type, result=result, branch_id=branch_id,
    )
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[AdminAuditLogEntryResponse.model_validate(r) for r in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


@router.get(
    "/audit-logs/export", responses=_ERROR_RESPONSES,
    summary="Export this organization's audit log",
)
async def export_audit_logs(
    format: ReportFormat = Query(ReportFormat.CSV),
    date_range: DateRangeParams = Depends(get_date_range_params),
    tenant: TenantContext = Depends(get_tenant_context),
    service: AuditAdminService = Depends(get_audit_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("audit:read", resource_type="audit_log")),
) -> Response:
    org_id = _require_home_org(tenant)
    rows, _total = await service.search_audit_logs(
        org_id, offset=0, limit=10000, date_from=date_range.date_from, date_to=date_range.date_to,
    )
    headers = ["id", "created_at", "actor_user_id", "action", "entity_type", "entity_id", "branch_id", "result", "request_id"]
    table_rows = [
        [r.id, r.created_at, r.actor_user_id, r.action, r.entity_type, r.entity_id, r.branch_id, r.result, r.request_id]
        for r in rows
    ]
    # `exporters.render()` keys its dispatch table by `ReportFormat` MEMBER
    # NAME ("CSV"), not `.value` ("csv") -- `ReportGenerationService.generate`
    # (Module 12) already established `format.name` as the correct call
    # shape; this route originally passed `.value`, which raised
    # `ValueError: Unsupported report format: csv` for every export,
    # caught by tests/integration/test_admin_routes.py::test_audit_log_search_and_export_are_org_scoped.
    content, extension, content_type = render(format_name=format.name, title="Audit Log Export", headers=headers, rows=table_rows)
    return Response(
        content=content, media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="audit-log.{extension}"'},
    )


@router.get(
    "/security-events", response_model=Page[SecurityEventResponse], responses=_ERROR_RESPONSES,
    summary="Search this organization's security events",
)
async def search_security_events(
    page_params: PageParams = Depends(),
    date_range: DateRangeParams = Depends(get_date_range_params),
    event_type: SecurityEventType | None = Query(None),
    tenant: TenantContext = Depends(get_tenant_context),
    service: AuditAdminService = Depends(get_audit_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("audit:read", resource_type="security_event")),
) -> Page[SecurityEventResponse]:
    org_id = _require_home_org(tenant)
    rows, total = await service.search_security_events(
        org_id, offset=page_params.offset, limit=page_params.page_size,
        date_from=date_range.date_from, date_to=date_range.date_to, event_type=event_type,
    )
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[SecurityEventResponse.model_validate(r) for r in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


@router.get(
    "/security-events/platform", response_model=Page[SecurityEventResponse], responses=_ADMIN_ERROR_RESPONSES,
    summary="Platform-wide security event search (every organization)",
)
async def platform_security_events(
    page_params: PageParams = Depends(),
    date_range: DateRangeParams = Depends(get_date_range_params),
    event_type: SecurityEventType | None = Query(None),
    service: AuditAdminService = Depends(get_audit_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("admin:read")),
) -> Page[SecurityEventResponse]:
    rows, total = await service.platform_security_events(
        offset=page_params.offset, limit=page_params.page_size,
        date_from=date_range.date_from, date_to=date_range.date_to, event_type=event_type,
    )
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[SecurityEventResponse.model_validate(r) for r in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


@router.get(
    "/authorization-denials", response_model=Page[AuthorizationDenialResponse], responses=_ERROR_RESPONSES,
    summary="Search this organization's authorization denials",
)
async def search_authorization_denials(
    page_params: PageParams = Depends(),
    date_range: DateRangeParams = Depends(get_date_range_params),
    tenant: TenantContext = Depends(get_tenant_context),
    service: AuditAdminService = Depends(get_audit_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("audit:read", resource_type="authorization_denial")),
) -> Page[AuthorizationDenialResponse]:
    org_id = _require_home_org(tenant)
    rows, total = await service.search_authorization_denials(
        org_id, offset=page_params.offset, limit=page_params.page_size,
        date_from=date_range.date_from, date_to=date_range.date_to,
    )
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[AuthorizationDenialResponse.model_validate(r) for r in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


# ======================================================================
# Section 9: System Health (platform-wide)
# ======================================================================


@router.get(
    "/health", response_model=HealthReportResponse, responses=_ADMIN_ERROR_RESPONSES,
    summary="Admin system health dashboard",
)
async def admin_health(
    service: HealthCheckService = Depends(get_health_check_service),
    decision: AuthorizationDecision = Depends(require_permission("admin:read")),
) -> HealthReportResponse:
    report = await service.check()
    return HealthReportResponse(
        api=report.api, database_reachable=report.database_reachable, cache_reachable=report.cache_reachable,
        cache_backend=report.cache_backend, storage_configured=report.storage_configured,
        ai_anthropic_configured=report.ai_anthropic_configured,
        ai_model_artifacts_configured=report.ai_model_artifacts_configured,
        notifications_email_configured=report.notifications_email_configured,
        notifications_sms_configured=report.notifications_sms_configured,
        notifications_push_configured=report.notifications_push_configured,
        background_processing_configured=report.background_processing_configured,
    )


# ======================================================================
# Section 10: AI Administration (platform-wide)
# ======================================================================


@router.get(
    "/ai/models", response_model=list[AIModelStatusResponse], responses=_ADMIN_ERROR_RESPONSES,
    summary="AI model configuration status per capability",
)
async def ai_model_status(
    service: AIAdminService = Depends(get_ai_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("admin:read")),
) -> list[AIModelStatusResponse]:
    return [AIModelStatusResponse(**s) for s in service.model_status()]


@router.get(
    "/ai/usage", response_model=list[AIUsageStatsResponse], responses=_ADMIN_ERROR_RESPONSES,
    summary="AI request statistics/latency/usage for one organization",
)
async def ai_usage_stats(
    nursery_id: uuid.UUID = Query(...),
    date_range: DateRangeParams = Depends(get_date_range_params),
    service: AIAdminService = Depends(get_ai_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("admin:read")),
) -> list[AIUsageStatsResponse]:
    rows = await service.usage_stats(nursery_id, date_from=date_range.date_from, date_to=date_range.date_to)
    return [AIUsageStatsResponse(**r) for r in rows]


@router.get(
    "/ai/failures", response_model=Page[AIInferenceFailureResponse], responses=_ADMIN_ERROR_RESPONSES,
    summary="AI inference failures for one organization",
)
async def ai_failures(
    nursery_id: uuid.UUID = Query(...),
    page_params: PageParams = Depends(),
    capability: str | None = Query(None),
    service: AIAdminService = Depends(get_ai_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("admin:read")),
) -> Page[AIInferenceFailureResponse]:
    rows, total = await service.list_failures(
        nursery_id, offset=page_params.offset, limit=page_params.page_size, capability=capability
    )
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[AIInferenceFailureResponse.model_validate(r) for r in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


@router.get(
    "/ai/knowledge-base", response_model=list[KnowledgeBaseStatusResponse], responses=_ADMIN_ERROR_RESPONSES,
    summary="RAG knowledge-base status (chunk counts by source type)",
)
async def ai_knowledge_base_status(
    nursery_id: uuid.UUID | None = Query(None),
    service: AIAdminService = Depends(get_ai_admin_service),
    decision: AuthorizationDecision = Depends(require_permission("admin:read")),
) -> list[KnowledgeBaseStatusResponse]:
    rows = await service.knowledge_base_status(nursery_id=nursery_id)
    return [KnowledgeBaseStatusResponse(**r) for r in rows]


# ======================================================================
# Section 11: Data Management (platform-wide)
# ======================================================================


@router.get(
    "/data-retention", response_model=DataRetentionSummaryResponse, responses=_ADMIN_ERROR_RESPONSES,
    summary="Read-only data retention visibility for one organization (no deletion is performed)",
)
async def data_retention_summary(
    nursery_id: uuid.UUID = Query(...),
    older_than_days: int = Query(365, ge=1, le=3650),
    service: DataManagementService = Depends(get_data_management_service),
    decision: AuthorizationDecision = Depends(require_permission("admin:read")),
) -> DataRetentionSummaryResponse:
    summary = await service.retention_summary(nursery_id, older_than_days=older_than_days)
    return DataRetentionSummaryResponse(**summary)
