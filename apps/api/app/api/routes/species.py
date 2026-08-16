"""
Module 5 (Species Catalog) — plant-categories reference data + Species
CRUD REST API (FR-4).

Per docs/architecture/02-low-level-design.md's Species Catalog module and
docs/architecture/07-api-design.md's Species resource: `GET/POST
/species`, `GET/PATCH /species/{id}`, `DELETE /species/{id}`. `GET
/plant-categories` is an addition beyond that minimal list -- the global,
system-seeded reference data (migration 0002) a Species create/edit form's
category dropdown needs, gated on `species:read` rather than a new
permission code since it exists only in service of the Species workflow.

Same flat-collection / fetch-then-authorize pattern as Module 4's
`branches.py` for the by-id routes (see that file's module docstring for
the full rationale) -- Species is per-Org, not branch-scoped (FR-4.2), so
the collection routes resolve their org from `TenantContext` and the by-id
routes fetch-then-authorize since `{id}` carries no `nursery_id`.
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
    get_species_service,
    get_tenant_context,
    raise_if_denied,
    request_context,
    require_permission,
)
from app.core.exceptions import ValidationError
from app.core.responses import ErrorResponse, Page, PageMeta
from app.models.identity import User
from app.schemas.catalog import (
    CreateSpeciesRequest,
    PlantCategoryResponse,
    SpeciesResponse,
    UpdateSpeciesRequest,
)
from app.services.authorization_service import AuthorizationDecision, AuthorizationService
from app.services.species_service import SpeciesService

router = APIRouter()

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Missing permission or cross-tenant access"},
    404: {"model": ErrorResponse, "description": "Species not found"},
}


def _to_growth_curve(payload) -> list[dict] | None:
    if payload is None:
        return None
    return [point.model_dump() for point in payload]


@router.get(
    "/plant-categories",
    response_model=list[PlantCategoryResponse],
    responses={401: _ERROR_RESPONSES[401], 403: _ERROR_RESPONSES[403]},
    summary="List the global plant category taxonomy",
)
async def list_plant_categories(
    species_service: SpeciesService = Depends(get_species_service),
    decision: AuthorizationDecision = Depends(require_permission("species:read", resource_type="plant_category")),
) -> list[PlantCategoryResponse]:
    categories = await species_service.list_categories()
    return [PlantCategoryResponse.model_validate(c) for c in categories]


@router.get(
    "/species",
    response_model=Page[SpeciesResponse],
    responses={401: _ERROR_RESPONSES[401], 403: _ERROR_RESPONSES[403]},
    summary="List/search the caller's organization's species catalog",
    description="Requires `species:read`. Supports `search` (matches common/botanical name), `category_id`, and `light_requirement` filters (FR-4.4).",
)
async def list_species(
    page_params: PageParams = Depends(),
    search: str | None = None,
    category_id: uuid.UUID | None = None,
    light_requirement: str | None = None,
    tenant: TenantContext = Depends(get_tenant_context),
    species_service: SpeciesService = Depends(get_species_service),
    decision: AuthorizationDecision = Depends(require_permission("species:read", resource_type="species")),
) -> Page[SpeciesResponse]:
    if tenant.org_id is None:
        return Page(items=[], meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=0, total_pages=0))

    rows, total = await species_service.list_species(
        nursery_id=tenant.org_id,
        offset=page_params.offset,
        limit=page_params.page_size,
        search=search,
        category_id=category_id,
        light_requirement=light_requirement,
    )
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[SpeciesResponse.model_validate(s) for s in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


@router.post(
    "/species",
    response_model=SpeciesResponse,
    responses={
        **_ERROR_RESPONSES,
        409: {"model": ErrorResponse, "description": "Botanical name already in use"},
        422: {"model": ErrorResponse, "description": "Unknown category or invalid care-attribute data"},
    },
    status_code=status.HTTP_201_CREATED,
    summary="Create a species in the caller's organization's catalog",
)
async def create_species(
    body: CreateSpeciesRequest,
    request: Request,
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    species_service: SpeciesService = Depends(get_species_service),
    decision: AuthorizationDecision = Depends(require_permission("species:write", resource_type="species")),
) -> SpeciesResponse:
    if tenant.org_id is None:
        raise ValidationError("You must belong to an organization to create a species.")

    species = await species_service.create_species(
        nursery_id=tenant.org_id,
        category_id=body.category_id,
        common_name=body.common_name,
        botanical_name=body.botanical_name,
        actor_user_id=user.id,
        light_requirement=body.light_requirement,
        water_baseline_ml_per_week=body.water_baseline_ml_per_week,
        soil_type=body.soil_type,
        temperature_min_celsius=body.temperature_min_celsius,
        temperature_max_celsius=body.temperature_max_celsius,
        growth_curve_baseline=_to_growth_curve(body.growth_curve_baseline),
        disease_susceptibility=body.disease_susceptibility,
        request_id=request_context(request).request_id,
    )
    return SpeciesResponse.model_validate(species)


async def _authorize_species(
    *,
    species_id: uuid.UUID,
    permission: str,
    request: Request,
    user: User,
    species_service: SpeciesService,
    authz: AuthorizationService,
):
    """Fetch-then-authorize for the by-id routes -- see app/api/routes/branches.py's `_authorize_branch` for the full rationale."""
    species = await species_service.get_species(species_id)
    decision = await authz.authorize(
        user=user,
        permission=permission,
        resource_type="species",
        resource_id=species.id,
        target_nursery_id=species.nursery_id,
        context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)
    return species


@router.get(
    "/species/{id}",
    response_model=SpeciesResponse,
    responses=_ERROR_RESPONSES,
    summary="Get a species by id",
)
async def get_species(
    id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    species_service: SpeciesService = Depends(get_species_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> SpeciesResponse:
    species = await _authorize_species(
        species_id=id, permission="species:read", request=request, user=user,
        species_service=species_service, authz=authz,
    )
    return SpeciesResponse.model_validate(species)


@router.patch(
    "/species/{id}",
    response_model=SpeciesResponse,
    responses={
        **_ERROR_RESPONSES,
        409: {"model": ErrorResponse, "description": "Botanical name already in use"},
        422: {"model": ErrorResponse, "description": "Unknown category or invalid care-attribute data"},
    },
    summary="Update a species",
)
async def update_species(
    id: uuid.UUID,
    body: UpdateSpeciesRequest,
    request: Request,
    user: User = Depends(get_current_user),
    species_service: SpeciesService = Depends(get_species_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> SpeciesResponse:
    await _authorize_species(
        species_id=id, permission="species:write", request=request, user=user,
        species_service=species_service, authz=authz,
    )
    species = await species_service.update_species(
        species_id=id,
        actor_user_id=user.id,
        category_id=body.category_id,
        common_name=body.common_name,
        botanical_name=body.botanical_name,
        light_requirement=body.light_requirement,
        water_baseline_ml_per_week=body.water_baseline_ml_per_week,
        soil_type=body.soil_type,
        temperature_min_celsius=body.temperature_min_celsius,
        temperature_max_celsius=body.temperature_max_celsius,
        growth_curve_baseline=_to_growth_curve(body.growth_curve_baseline),
        disease_susceptibility=body.disease_susceptibility,
        request_id=request_context(request).request_id,
    )
    return SpeciesResponse.model_validate(species)


@router.delete(
    "/species/{id}",
    response_model=SpeciesResponse,
    responses={**_ERROR_RESPONSES, 409: {"model": ErrorResponse, "description": "Species still referenced by a plant record"}},
    summary="Delete a species (blocked if any plant record still references it)",
)
async def delete_species(
    id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    species_service: SpeciesService = Depends(get_species_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> SpeciesResponse:
    species = await _authorize_species(
        species_id=id, permission="species:delete", request=request, user=user,
        species_service=species_service, authz=authz,
    )
    await species_service.delete_species(
        species_id=id, actor_user_id=user.id, request_id=request_context(request).request_id
    )
    return SpeciesResponse.model_validate(species)
