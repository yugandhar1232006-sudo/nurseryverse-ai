"""
Module 5 (Species Catalog) — PlantVariety (cultivar) REST API.

Extension beyond docs/architecture/07-api-design.md's minimal Species
endpoint list, same justification pattern as Module 4's documented
extensions (see app/api/routes/organizations.py's module docstring): the
`PlantCategory -> Species -> PlantVariety` hierarchy already exists in the
schema (Phase 5) and cultivar/variety management is a genuine part of
Species Catalog maintenance the LLD's "species reference data CRUD"
responsibility implies, even though the doc's abbreviated endpoint table
only spells out `/species`.

Flat `/plant-varieties` collection (not nested under `/species/{id}/`),
matching Module 4's `/branches` precedent: the organization is always the
caller's own, and `species_id` is a normal filter/body field rather than a
path segment. Same fetch-then-authorize pattern as every other flat
by-id resource in this codebase for the same reason (`{id}` carries no
`nursery_id`).
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import (
    PageParams,
    TenantContext,
    get_authorization_service,
    get_current_user,
    get_plant_variety_service,
    get_tenant_context,
    raise_if_denied,
    request_context,
    require_permission,
)
from app.core.exceptions import ValidationError
from app.core.responses import ErrorResponse, Page, PageMeta
from app.models.identity import User
from app.schemas.catalog import CreatePlantVarietyRequest, PlantVarietyResponse, UpdatePlantVarietyRequest
from app.services.authorization_service import AuthorizationDecision, AuthorizationService
from app.services.plant_variety_service import PlantVarietyService

router = APIRouter()

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Missing permission or cross-tenant access"},
    404: {"model": ErrorResponse, "description": "Plant variety not found"},
}


@router.get(
    "",
    response_model=Page[PlantVarietyResponse],
    responses={401: _ERROR_RESPONSES[401], 403: _ERROR_RESPONSES[403]},
    summary="List the caller's organization's plant varieties",
    description="Requires `species:read`. Filter to a single species with `?species_id=`.",
)
async def list_plant_varieties(
    page_params: PageParams = Depends(),
    species_id: uuid.UUID | None = None,
    tenant: TenantContext = Depends(get_tenant_context),
    variety_service: PlantVarietyService = Depends(get_plant_variety_service),
    decision: AuthorizationDecision = Depends(require_permission("species:read", resource_type="plant_variety")),
) -> Page[PlantVarietyResponse]:
    if tenant.org_id is None:
        return Page(items=[], meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=0, total_pages=0))

    rows, total = await variety_service.list_varieties(
        nursery_id=tenant.org_id, offset=page_params.offset, limit=page_params.page_size, species_id=species_id
    )
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[PlantVarietyResponse.model_validate(v) for v in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


@router.post(
    "",
    response_model=PlantVarietyResponse,
    responses={
        **_ERROR_RESPONSES,
        409: {"model": ErrorResponse, "description": "Variety name already in use for this species"},
        422: {"model": ErrorResponse, "description": "Species does not belong to this organization"},
    },
    status_code=status.HTTP_201_CREATED,
    summary="Create a plant variety under a species",
)
async def create_plant_variety(
    body: CreatePlantVarietyRequest,
    request: Request,
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    variety_service: PlantVarietyService = Depends(get_plant_variety_service),
    decision: AuthorizationDecision = Depends(require_permission("species:write", resource_type="plant_variety")),
) -> PlantVarietyResponse:
    if tenant.org_id is None:
        raise ValidationError("You must belong to an organization to create a plant variety.")

    variety = await variety_service.create_variety(
        nursery_id=tenant.org_id,
        species_id=body.species_id,
        name=body.name,
        actor_user_id=user.id,
        description=body.description,
        request_id=request_context(request).request_id,
    )
    return PlantVarietyResponse.model_validate(variety)


async def _authorize_variety(
    *,
    variety_id: uuid.UUID,
    permission: str,
    request: Request,
    user: User,
    variety_service: PlantVarietyService,
    authz: AuthorizationService,
):
    """Fetch-then-authorize for the by-id routes -- see app/api/routes/branches.py's `_authorize_branch` for the full rationale."""
    variety = await variety_service.get_variety(variety_id)
    decision = await authz.authorize(
        user=user,
        permission=permission,
        resource_type="plant_variety",
        resource_id=variety.id,
        target_nursery_id=variety.nursery_id,
        context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)
    return variety


@router.get(
    "/{id}",
    response_model=PlantVarietyResponse,
    responses=_ERROR_RESPONSES,
    summary="Get a plant variety by id",
)
async def get_plant_variety(
    id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    variety_service: PlantVarietyService = Depends(get_plant_variety_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> PlantVarietyResponse:
    variety = await _authorize_variety(
        variety_id=id, permission="species:read", request=request, user=user,
        variety_service=variety_service, authz=authz,
    )
    return PlantVarietyResponse.model_validate(variety)


@router.patch(
    "/{id}",
    response_model=PlantVarietyResponse,
    responses={**_ERROR_RESPONSES, 409: {"model": ErrorResponse, "description": "Variety name already in use for this species"}},
    summary="Update a plant variety",
)
async def update_plant_variety(
    id: uuid.UUID,
    body: UpdatePlantVarietyRequest,
    request: Request,
    user: User = Depends(get_current_user),
    variety_service: PlantVarietyService = Depends(get_plant_variety_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> PlantVarietyResponse:
    await _authorize_variety(
        variety_id=id, permission="species:write", request=request, user=user,
        variety_service=variety_service, authz=authz,
    )
    variety = await variety_service.update_variety(
        variety_id=id,
        actor_user_id=user.id,
        name=body.name,
        description=body.description,
        request_id=request_context(request).request_id,
    )
    return PlantVarietyResponse.model_validate(variety)


@router.delete(
    "/{id}",
    response_model=PlantVarietyResponse,
    responses={**_ERROR_RESPONSES, 409: {"model": ErrorResponse, "description": "Variety still referenced by a plant record"}},
    summary="Delete a plant variety (blocked if any plant record still references it)",
)
async def delete_plant_variety(
    id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    variety_service: PlantVarietyService = Depends(get_plant_variety_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> PlantVarietyResponse:
    variety = await _authorize_variety(
        variety_id=id, permission="species:delete", request=request, user=user,
        variety_service=variety_service, authz=authz,
    )
    await variety_service.delete_variety(
        variety_id=id, actor_user_id=user.id, request_id=request_context(request).request_id
    )
    return PlantVarietyResponse.model_validate(variety)
