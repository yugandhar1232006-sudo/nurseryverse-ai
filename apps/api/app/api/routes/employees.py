"""
Module 4 (Nursery & Organization Management) — Employee Management +
Organization Membership REST API.

Per docs/architecture/07-api-design.md's Employees resource: `GET
/employees`, `POST /employees/invite`, `GET/PATCH /employees/{id}`, `POST
/employees/{id}/deactivate`. Same flat-collection / fetch-then-authorize
pattern as `app/api/routes/branches.py` for the by-id routes (see that
file's module docstring for the full rationale) -- `{id}` here is the
employee's id, not the org's.

Two additions beyond that minimal doc list, both genuine Module 4
requirements ("Transfer Staff / Branch Reassignment", "Ownership
Transfer") that don't fit `PATCH /employees/{id}` (a plain profile edit):
`POST /employees/{id}/transfer-branches` and `POST
/employees/{id}/deactivate` uses `remove_employee` (Module 4's "Remove
Staff"). Ownership transfer is a *whole-organization* operation (it
changes who holds the org's single Owner role) and lives on the Orgs
resource instead -- see `app/api/routes/organizations.py`'s
`transfer_ownership` route.
"""
from __future__ import annotations

from typing import Any

import uuid

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import (
    PageParams,
    TenantContext,
    get_authorization_service,
    get_current_user,
    get_employee_service,
    get_tenant_context,
    raise_if_denied,
    request_context,
    require_permission,
)
from app.core.exceptions import ValidationError
from app.core.responses import ErrorResponse, Page, PageMeta
from app.db.enums import EmployeeStatus
from app.models.identity import User
from app.schemas.employee import (
    EmployeeResponse,
    InviteEmployeeRequest,
    InviteResponse,
    ReactivateEmployeeRequest,
    RemoveEmployeeRequest,
    TransferBranchesRequest,
    UpdateEmployeeProfileRequest,
)
from app.services.authorization_service import AuthorizationDecision, AuthorizationService
from app.services.employee_service import EmployeeService

router = APIRouter()

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Missing permission or cross-tenant access"},
    404: {"model": ErrorResponse, "description": "Employee not found"},
}


async def _authorize_employee(
    *,
    employee_id: uuid.UUID,
    permission: str,
    request: Request,
    user: User,
    employee_service: EmployeeService,
    authz: AuthorizationService,
):
    """Fetch-then-authorize for the by-id routes -- see branches.py's `_authorize_branch` for the full rationale."""
    employee = await employee_service.get_employee(employee_id)
    decision = await authz.authorize(
        user=user,
        permission=permission,
        resource_type="employee",
        resource_id=employee.id,
        target_nursery_id=employee.nursery_id,
        context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)
    return employee


@router.get(
    "",
    response_model=Page[EmployeeResponse],
    responses=_ERROR_RESPONSES,
    summary="List the caller's organization's employees",
)
async def list_employees(
    page_params: PageParams = Depends(),
    status_filter: EmployeeStatus | None = None,
    tenant: TenantContext = Depends(get_tenant_context),
    employee_service: EmployeeService = Depends(get_employee_service),
    decision: AuthorizationDecision = Depends(require_permission("employees:read", resource_type="employee")),
) -> Page[EmployeeResponse]:
    if tenant.org_id is None:
        return Page(items=[], meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=0, total_pages=0))

    rows, total = await employee_service.list_employees(
        nursery_id=tenant.org_id, offset=page_params.offset, limit=page_params.page_size, status=status_filter
    )
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[EmployeeResponse.model_validate(e) for e in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


@router.post(
    "/invite",
    response_model=InviteResponse,
    responses={
        **_ERROR_RESPONSES,
        409: {"model": ErrorResponse, "description": "Already a member or already invited"},
        422: {"model": ErrorResponse, "description": "Unknown role code or branch not in this organization"},
    },
    status_code=status.HTTP_201_CREATED,
    summary="Invite a person to join the organization as an employee",
)
async def invite_employee(
    body: InviteEmployeeRequest,
    request: Request,
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    employee_service: EmployeeService = Depends(get_employee_service),
    decision: AuthorizationDecision = Depends(require_permission("employees:write", resource_type="employee")),
) -> InviteResponse:
    if tenant.org_id is None:
        raise ValidationError("You must belong to an organization to invite an employee.")

    invite = await employee_service.invite_employee(
        nursery_id=tenant.org_id,
        email=body.email,
        role_code=body.role_code,
        invited_by_user_id=user.id,
        branch_ids=body.branch_ids,
        request_id=request_context(request).request_id,
    )
    return InviteResponse.model_validate(invite)


@router.get(
    "/{id}",
    response_model=EmployeeResponse,
    responses=_ERROR_RESPONSES,
    summary="Get an employee by id",
)
async def get_employee(
    id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    employee_service: EmployeeService = Depends(get_employee_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> EmployeeResponse:
    employee = await _authorize_employee(
        employee_id=id,
        permission="employees:read",
        request=request,
        user=user,
        employee_service=employee_service,
        authz=authz,
    )
    return EmployeeResponse.model_validate(employee)


@router.patch(
    "/{id}",
    response_model=EmployeeResponse,
    responses=_ERROR_RESPONSES,
    summary="Update an employee's profile (department/position)",
)
async def update_employee(
    id: uuid.UUID,
    body: UpdateEmployeeProfileRequest,
    request: Request,
    user: User = Depends(get_current_user),
    employee_service: EmployeeService = Depends(get_employee_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> EmployeeResponse:
    await _authorize_employee(
        employee_id=id,
        permission="employees:write",
        request=request,
        user=user,
        employee_service=employee_service,
        authz=authz,
    )
    employee = await employee_service.update_profile(
        employee_id=id,
        actor_user_id=user.id,
        department=body.department,
        position=body.position,
        request_id=request_context(request).request_id,
    )
    return EmployeeResponse.model_validate(employee)


@router.post(
    "/{id}/transfer-branches",
    response_model=EmployeeResponse,
    responses={**_ERROR_RESPONSES, 409: {"model": ErrorResponse, "description": "Employee is not active"}},
    summary="Reassign an employee to a different set of branches",
)
async def transfer_employee_branches(
    id: uuid.UUID,
    body: TransferBranchesRequest,
    request: Request,
    user: User = Depends(get_current_user),
    employee_service: EmployeeService = Depends(get_employee_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> EmployeeResponse:
    await _authorize_employee(
        employee_id=id,
        permission="employees:write",
        request=request,
        user=user,
        employee_service=employee_service,
        authz=authz,
    )
    employee = await employee_service.transfer_branches(
        employee_id=id,
        new_branch_ids=body.branch_ids,
        actor_user_id=user.id,
        request_id=request_context(request).request_id,
    )
    return EmployeeResponse.model_validate(employee)


@router.post(
    "/{id}/deactivate",
    response_model=EmployeeResponse,
    responses={**_ERROR_RESPONSES, 409: {"model": ErrorResponse, "description": "Employee already removed"}},
    summary="Remove an employee from the organization",
)
async def deactivate_employee(
    id: uuid.UUID,
    body: RemoveEmployeeRequest,
    request: Request,
    user: User = Depends(get_current_user),
    employee_service: EmployeeService = Depends(get_employee_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> EmployeeResponse:
    await _authorize_employee(
        employee_id=id,
        permission="employees:delete",
        request=request,
        user=user,
        employee_service=employee_service,
        authz=authz,
    )
    employee = await employee_service.remove_employee(
        employee_id=id,
        actor_user_id=user.id,
        reason=body.reason,
        request_id=request_context(request).request_id,
    )
    return EmployeeResponse.model_validate(employee)


@router.post(
    "/{id}/reactivate",
    response_model=EmployeeResponse,
    responses={
        **_ERROR_RESPONSES,
        409: {"model": ErrorResponse, "description": "Employee is not deactivated, or already holds an active role assignment"},
        422: {"model": ErrorResponse, "description": "Unknown role code"},
    },
    summary="Reactivate a previously-removed employee (Phase 6 Module 13)",
)
async def reactivate_employee(
    id: uuid.UUID,
    body: ReactivateEmployeeRequest,
    request: Request,
    user: User = Depends(get_current_user),
    employee_service: EmployeeService = Depends(get_employee_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> EmployeeResponse:
    await _authorize_employee(
        employee_id=id,
        permission="employees:write",
        request=request,
        user=user,
        employee_service=employee_service,
        authz=authz,
    )
    employee = await employee_service.reactivate_employee(
        employee_id=id,
        actor_user_id=user.id,
        role_code=body.role_code,
        branch_ids=body.branch_ids,
        request_id=request_context(request).request_id,
    )
    return EmployeeResponse.model_validate(employee)
