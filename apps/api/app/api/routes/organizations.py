"""
Module 4 (Nursery & Organization Management) — Organization Management
REST API: create/read/update/archive a Nursery, and its Settings.

Per docs/architecture/07-api-design.md's Orgs resource
(`POST/GET/PATCH /orgs/{id}`) and docs/ux/07-role-permission-matrix.md's
`org:read`/`org:write`/`org:delete` permissions. `POST /orgs` is the one
route in this file with no `{id}` in its path (it creates a new one) and
therefore cannot use `require_org_match` (which reads `nursery_id` out of
`request.path_params`) -- it instead checks the caller has *no* existing
org membership at all (v1's one-org-per-user constraint) and, on success,
makes the caller that org's Owner in the same request via
`EmployeeService.provision_owner` (both calls share the request's DB
session/transaction -- see app/db/session.py's `get_db_session` docstring
for why that makes this atomic).

`org:delete` maps to "archive" (soft delete) per `Nursery.status` -- there
is no hard-delete endpoint; see `docs/architecture/02-low-level-design.md`,
Module 4, "Archive Nursery" (never a destructive DROP of tenant data).
"""
from __future__ import annotations

from typing import Any

import uuid

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import (
    get_current_user,
    get_employee_service,
    get_organization_service,
    get_permission_service,
    request_context,
    require_org_match,
)
from app.core.exceptions import ConflictError
from app.core.responses import ErrorResponse
from app.models.identity import User
from app.schemas.employee import TransferOwnershipRequest
from app.schemas.organization import (
    CreateNurseryRequest,
    NurseryResponse,
    OrgSettingsResponse,
    UpdateNurseryRequest,
    UpdateOrgSettingsRequest,
)
from app.services.authorization_service import AuthorizationDecision
from app.services.employee_service import EmployeeService
from app.services.organization_service import OrganizationService
from app.services.permission_service import PermissionService

router = APIRouter()

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Missing permission or cross-tenant access"},
    404: {"model": ErrorResponse, "description": "Organization not found"},
}


@router.post(
    "",
    response_model=NurseryResponse,
    responses={
        **_ERROR_RESPONSES,
        409: {"model": ErrorResponse, "description": "Caller already belongs to an organization"},
    },
    status_code=status.HTTP_201_CREATED,
    summary="Create a new organization (the caller becomes its Owner)",
)
async def create_organization(
    body: CreateNurseryRequest,
    request: Request,
    user: User = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
    org_service: OrganizationService = Depends(get_organization_service),
    employee_service: EmployeeService = Depends(get_employee_service),
) -> NurseryResponse:
    access = await permission_service.resolve_for_user(user.id)
    if access.org_id is not None:
        raise ConflictError("You already belong to an organization.")

    request_id = request_context(request).request_id
    nursery = await org_service.create_nursery(
        name=body.name,
        contact_email=body.contact_email,
        contact_phone=body.contact_phone,
        logo_url=body.logo_url,
        actor_user_id=user.id,
        request_id=request_id,
    )
    await employee_service.provision_owner(nursery_id=nursery.id, user_id=user.id, request_id=request_id)
    # The caller just went from "no role assignment" to "Owner" -- without
    # this, a subsequent request within the cache TTL could still see the
    # pre-creation "no org" resolution (PermissionService's own cache).
    await permission_service.invalidate_user(user.id)
    return NurseryResponse.model_validate(nursery)


@router.get(
    "/{id}",
    response_model=NurseryResponse,
    responses=_ERROR_RESPONSES,
    summary="Get an organization by id",
)
async def get_organization(
    id: str,
    org_service: OrganizationService = Depends(get_organization_service),
    decision: AuthorizationDecision = Depends(require_org_match("org:read", nursery_id_param="id")),
) -> NurseryResponse:
    nursery = await org_service.get_nursery(uuid.UUID(id))
    return NurseryResponse.model_validate(nursery)


@router.patch(
    "/{id}",
    response_model=NurseryResponse,
    responses=_ERROR_RESPONSES,
    summary="Update an organization's name/contact/logo",
)
async def update_organization(
    id: str,
    body: UpdateNurseryRequest,
    request: Request,
    user: User = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service),
    decision: AuthorizationDecision = Depends(require_org_match("org:write", nursery_id_param="id")),
) -> NurseryResponse:
    nursery = await org_service.update_nursery(
        nursery_id=uuid.UUID(id),
        actor_user_id=user.id,
        name=body.name,
        contact_email=body.contact_email,
        contact_phone=body.contact_phone,
        logo_url=body.logo_url,
        request_id=request_context(request).request_id,
    )
    return NurseryResponse.model_validate(nursery)


@router.post(
    "/{id}/archive",
    response_model=NurseryResponse,
    responses={**_ERROR_RESPONSES, 409: {"model": ErrorResponse, "description": "Already archived"}},
    summary="Archive an organization (soft delete)",
)
async def archive_organization(
    id: str,
    request: Request,
    user: User = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service),
    decision: AuthorizationDecision = Depends(require_org_match("org:delete", nursery_id_param="id")),
) -> NurseryResponse:
    nursery = await org_service.archive_nursery(
        nursery_id=uuid.UUID(id),
        actor_user_id=user.id,
        request_id=request_context(request).request_id,
    )
    return NurseryResponse.model_validate(nursery)


@router.get(
    "/{id}/settings",
    response_model=OrgSettingsResponse,
    responses=_ERROR_RESPONSES,
    summary="Get an organization's settings (branding, currency, timezone)",
)
async def get_organization_settings(
    id: str,
    org_service: OrganizationService = Depends(get_organization_service),
    decision: AuthorizationDecision = Depends(require_org_match("org:read", nursery_id_param="id")),
) -> OrgSettingsResponse:
    settings = await org_service.get_settings(uuid.UUID(id))
    return OrgSettingsResponse.model_validate(settings)


@router.patch(
    "/{id}/settings",
    response_model=OrgSettingsResponse,
    responses=_ERROR_RESPONSES,
    summary="Update an organization's settings",
)
async def update_organization_settings(
    id: str,
    body: UpdateOrgSettingsRequest,
    request: Request,
    user: User = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service),
    decision: AuthorizationDecision = Depends(require_org_match("org:write", nursery_id_param="id")),
) -> OrgSettingsResponse:
    settings = await org_service.update_settings(
        nursery_id=uuid.UUID(id),
        actor_user_id=user.id,
        currency=body.currency,
        timezone_name=body.timezone,
        branding_primary_color=body.branding_primary_color,
        email_sender_identity=body.email_sender_identity,
        sms_enabled=body.sms_enabled,
        request_id=request_context(request).request_id,
    )
    return OrgSettingsResponse.model_validate(settings)


@router.post(
    "/{id}/transfer-ownership",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    responses={
        **_ERROR_RESPONSES,
        422: {"model": ErrorResponse, "description": "New owner is not already an employee of this organization"},
    },
    summary="Transfer the organization's Owner role to another employee",
)
async def transfer_ownership(
    id: str,
    body: TransferOwnershipRequest,
    request: Request,
    user: User = Depends(get_current_user),
    employee_service: EmployeeService = Depends(get_employee_service),
    # `org:delete` is Owner-only in the default role set
    # (docs/ux/07-role-permission-matrix.md) -- reusing it here rather than
    # inventing a new permission code keeps "only the Owner may hand off
    # ownership" a property of the existing permission matrix instead of a
    # hardcoded role-name check in this route or in
    # `EmployeeService.transfer_ownership` (which independently verifies
    # `current_owner_user_id` actually holds the `owner` role -- this
    # permission check and that service-layer check are deliberately
    # redundant, not the same guarantee: this one says "you're allowed to
    # call this endpoint", that one says "the specific transfer you asked
    # for is valid").
    decision: AuthorizationDecision = Depends(require_org_match("org:delete", nursery_id_param="id")),
) -> None:
    await employee_service.transfer_ownership(
        nursery_id=uuid.UUID(id),
        current_owner_user_id=user.id,
        new_owner_user_id=body.new_owner_user_id,
        actor_user_id=user.id,
        request_id=request_context(request).request_id,
    )
