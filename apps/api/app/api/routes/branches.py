"""
Module 4 (Nursery & Organization Management) — Branch Management REST API.

Per docs/architecture/07-api-design.md: a *flat* `/branches` collection, not
`/orgs/{id}/branches` -- the organization is always the caller's own
(`TenantContext.org_id`), never a path parameter, so there is no nested
resource path to design around and no way to even ask for another org's
branches.

The collection routes (`GET`/`POST /branches`) get their org id from
`TenantContext` (Module 3's `get_tenant_context`) via the ordinary
`require_permission` dependency. The by-id routes (`GET`/`PATCH`/`DELETE
/branches/{id}`) are different: `{id}` here is the *branch's* id, not the
org's, so `require_org_match` (which compares `request.path_params against
the caller's org) doesn't apply -- there is no nursery id in this path at
all. Instead each by-id handler fetches the branch first (learning its real
`nursery_id`), then performs one manual `AuthorizationService.authorize()`
call via the `raise_if_denied`/`request_context` aliases (see deps.py's
docstring on those two names) -- a cross-tenant branch id is rejected with
exactly the same `CROSS_TENANT_ORG` denial and audit trail as every other
route in the system, just constructed one step later than usual.
"""
from __future__ import annotations

from typing import Any

import uuid

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import (
    TenantContext,
    get_authorization_service,
    get_branch_service,
    get_current_user,
    get_tenant_context,
    raise_if_denied,
    request_context,
    require_permission,
)
from app.core.exceptions import ValidationError
from app.core.responses import ErrorResponse
from app.models.identity import User
from app.schemas.branch import BranchResponse, CreateBranchRequest, UpdateBranchRequest
from app.services.authorization_service import AuthorizationDecision, AuthorizationService
from app.services.branch_service import BranchService

router = APIRouter()

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Missing permission or cross-tenant access"},
    404: {"model": ErrorResponse, "description": "Branch not found"},
}


async def _authorize_branch(
    *,
    branch_id: uuid.UUID,
    permission: str,
    request: Request,
    user: User,
    branch_service: BranchService,
    authz: AuthorizationService,
):
    """
    Shared by every by-id route below: fetch-then-authorize, since a flat
    `/branches/{id}` path carries no `nursery_id` to check up front. Raises
    `NotFoundError` (via `branch_service.get_branch`) or
    `PermissionDeniedError` (via `raise_if_denied`) and otherwise returns
    the loaded `Branch`.
    """
    branch = await branch_service.get_branch(branch_id)
    decision = await authz.authorize(
        user=user,
        permission=permission,
        resource_type="branch",
        resource_id=branch.id,
        target_nursery_id=branch.nursery_id,
        context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)
    return branch


@router.get(
    "",
    response_model=list[BranchResponse],
    responses=_ERROR_RESPONSES,
    summary="List the caller's organization's branches",
)
async def list_branches(
    include_inactive: bool = False,
    tenant: TenantContext = Depends(get_tenant_context),
    branch_service: BranchService = Depends(get_branch_service),
    decision: AuthorizationDecision = Depends(require_permission("branch:read", resource_type="branch")),
) -> list[BranchResponse]:
    if tenant.org_id is None:
        return []
    branches = await branch_service.list_branches(nursery_id=tenant.org_id, include_inactive=include_inactive)
    return [BranchResponse.model_validate(b) for b in branches]


@router.post(
    "",
    response_model=BranchResponse,
    responses={**_ERROR_RESPONSES, 409: {"model": ErrorResponse, "description": "Branch name already in use"}},
    status_code=status.HTTP_201_CREATED,
    summary="Create a branch in the caller's organization",
)
async def create_branch(
    body: CreateBranchRequest,
    request: Request,
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    branch_service: BranchService = Depends(get_branch_service),
    decision: AuthorizationDecision = Depends(require_permission("branch:write", resource_type="branch")),
) -> BranchResponse:
    if tenant.org_id is None:
        raise ValidationError("You must belong to an organization to create a branch.")

    branch = await branch_service.create_branch(
        nursery_id=tenant.org_id,
        name=body.name,
        address_line1=body.address_line1,
        address_line2=body.address_line2,
        city=body.city,
        region=body.region,
        postal_code=body.postal_code,
        country=body.country,
        timezone_name=body.timezone,
        phone=body.phone,
        email=body.email,
        latitude=body.latitude,
        longitude=body.longitude,
        operating_hours=(
            {k: (v.model_dump() if v is not None else None) for k, v in body.operating_hours.items()}
            if body.operating_hours is not None
            else None
        ),
        actor_user_id=user.id,
        request_id=request_context(request).request_id,
    )
    return BranchResponse.model_validate(branch)


@router.get(
    "/{id}",
    response_model=BranchResponse,
    responses=_ERROR_RESPONSES,
    summary="Get a branch by id",
)
async def get_branch(
    id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    branch_service: BranchService = Depends(get_branch_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> BranchResponse:
    branch = await _authorize_branch(
        branch_id=id,
        permission="branch:read",
        request=request,
        user=user,
        branch_service=branch_service,
        authz=authz,
    )
    return BranchResponse.model_validate(branch)


@router.patch(
    "/{id}",
    response_model=BranchResponse,
    responses={**_ERROR_RESPONSES, 409: {"model": ErrorResponse, "description": "Branch name already in use"}},
    summary="Update a branch",
)
async def update_branch(
    id: uuid.UUID,
    body: UpdateBranchRequest,
    request: Request,
    user: User = Depends(get_current_user),
    branch_service: BranchService = Depends(get_branch_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> BranchResponse:
    await _authorize_branch(
        branch_id=id,
        permission="branch:write",
        request=request,
        user=user,
        branch_service=branch_service,
        authz=authz,
    )
    branch = await branch_service.update_branch(
        branch_id=id,
        actor_user_id=user.id,
        name=body.name,
        address_line1=body.address_line1,
        address_line2=body.address_line2,
        city=body.city,
        region=body.region,
        postal_code=body.postal_code,
        country=body.country,
        timezone_name=body.timezone,
        phone=body.phone,
        email=body.email,
        latitude=body.latitude,
        longitude=body.longitude,
        operating_hours=(
            {k: (v.model_dump() if v is not None else None) for k, v in body.operating_hours.items()}
            if body.operating_hours is not None
            else None
        ),
        request_id=request_context(request).request_id,
    )
    return BranchResponse.model_validate(branch)


@router.delete(
    "/{id}",
    response_model=BranchResponse,
    responses={**_ERROR_RESPONSES, 409: {"model": ErrorResponse, "description": "Already archived"}},
    summary="Archive a branch (soft delete)",
)
async def archive_branch(
    id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    branch_service: BranchService = Depends(get_branch_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> BranchResponse:
    await _authorize_branch(
        branch_id=id,
        permission="branch:delete",
        request=request,
        user=user,
        branch_service=branch_service,
        authz=authz,
    )
    branch = await branch_service.archive_branch(
        branch_id=id, actor_user_id=user.id, request_id=request_context(request).request_id
    )
    return BranchResponse.model_validate(branch)
