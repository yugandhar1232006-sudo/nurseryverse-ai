"""
Module 7 (Plant Digital Twin Engine) -- read-only Query API.

Every route in this file is a `GET`. There is no `POST`/`PATCH`/`DELETE`
anywhere in this module, by design: the Digital Twin is never written to
through the API (see app/services/digital_twin_service.py's own module
docstring) -- it's written to exactly once, internally, by
`DigitalTwinEventHandler` reacting to a `domain_events` row. This file
being entirely `GET` routes is the structural proof of that guarantee,
not just a claim about it.

Authorization reuses `plants:read` rather than minting a new
`digital_twin:read` permission code -- the Digital Twin is another view
of the same Plant a caller already needs `plants:read` for, the identical
reasoning Module 5 already applied when it reused `species:read` for
`GET /plant-categories`, and Module 6 reused `watering:read`/`watering:
write` for Fertilizer routes. Every route below fetches the underlying
Plant first (`plant_service.get_plant`) both to 404 correctly and to
authorize against its real `nursery_id`/`branch_id` -- the exact
fetch-then-authorize, branch-scoped pattern `plants.py` itself already
established.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import (
    PageParams,
    TenantContext,
    get_authorization_service,
    get_current_user,
    get_digital_twin_service,
    get_plant_service,
    get_tenant_context,
    request_context,
    raise_if_denied,
)
from app.core.responses import ErrorResponse, Page, PageMeta
from app.models.identity import User
from app.schemas.digital_twin import (
    DigitalTwinResponse,
    DigitalTwinVersionResponse,
    DomainEventResponse,
    ReplayConsistencyResponse,
    VersionComparisonResponse,
)
from app.services.authorization_service import AuthorizationService
from app.services.digital_twin_service import DigitalTwinService
from app.services.plant_service import PlantService

router = APIRouter()

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Missing permission or cross-tenant/cross-branch access"},
    404: {"model": ErrorResponse, "description": "Plant or Digital Twin not found"},
}


async def _authorize_for_plant(
    *, plant_id: uuid.UUID, request: Request, user: User, plant_service: PlantService, authz: AuthorizationService,
) -> None:
    plant = await plant_service.get_plant(plant_id)
    decision = await authz.authorize(
        user=user, permission="plants:read", resource_type="plant", resource_id=plant.id,
        target_nursery_id=plant.nursery_id, target_branch_id=plant.branch_id, context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)


@router.get(
    "/plants/{id}/digital-twin", response_model=DigitalTwinResponse, responses=_ERROR_RESPONSES,
    summary="Current Digital Twin -- the read-optimized, event-driven projection for this plant",
)
async def get_current_twin(
    id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    twin_service: DigitalTwinService = Depends(get_digital_twin_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> DigitalTwinResponse:
    await _authorize_for_plant(plant_id=id, request=request, user=user, plant_service=plant_service, authz=authz)
    twin = await twin_service.get_current_twin(id)
    return DigitalTwinResponse.model_validate(twin)


@router.get(
    "/plants/{id}/digital-twin/timeline", response_model=Page[DigitalTwinVersionResponse], responses=_ERROR_RESPONSES,
    summary="Timeline -- one entry per event that updated this plant's Digital Twin, newest first",
)
async def get_twin_timeline(
    id: uuid.UUID, request: Request, page_params: PageParams = Depends(),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    twin_service: DigitalTwinService = Depends(get_digital_twin_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[DigitalTwinVersionResponse]:
    await _authorize_for_plant(plant_id=id, request=request, user=user, plant_service=plant_service, authz=authz)
    rows, total = await twin_service.get_timeline(
        id, offset=page_params.offset, limit=page_params.page_size, sort_dir=sort_dir
    )
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[DigitalTwinVersionResponse.model_validate(r) for r in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


@router.get(
    "/plants/{id}/digital-twin/versions", response_model=Page[DigitalTwinVersionResponse], responses=_ERROR_RESPONSES,
    summary="Version history -- every immutable version of this plant's Digital Twin",
)
async def get_version_history(
    id: uuid.UUID, request: Request, page_params: PageParams = Depends(),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    twin_service: DigitalTwinService = Depends(get_digital_twin_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[DigitalTwinVersionResponse]:
    await _authorize_for_plant(plant_id=id, request=request, user=user, plant_service=plant_service, authz=authz)
    rows, total = await twin_service.get_version_history(
        id, offset=page_params.offset, limit=page_params.page_size, sort_dir=sort_dir
    )
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[DigitalTwinVersionResponse.model_validate(r) for r in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


@router.get(
    "/plants/{id}/digital-twin/versions/compare", response_model=VersionComparisonResponse, responses=_ERROR_RESPONSES,
    summary="Version comparison -- two versions' full snapshots plus which top-level fields differ",
)
async def compare_versions(
    id: uuid.UUID, request: Request, version_a: int = Query(..., ge=1), version_b: int = Query(..., ge=1),
    user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    twin_service: DigitalTwinService = Depends(get_digital_twin_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> VersionComparisonResponse:
    """
    Registered *before* `/versions/{version}` below on purpose: FastAPI/
    Starlette matches routes in registration order, and `{version}` is
    typed `int` -- without this ordering, a request for the literal path
    segment "compare" would match `/versions/{version}` first and fail
    `int` conversion with a spurious 422 instead of ever reaching this
    route.
    """
    await _authorize_for_plant(plant_id=id, request=request, user=user, plant_service=plant_service, authz=authz)
    comparison = await twin_service.compare_versions(id, version_a, version_b)
    return VersionComparisonResponse(
        plant_id=comparison.plant_id, version_a=comparison.version_a, version_b=comparison.version_b,
        snapshot_a=comparison.snapshot_a, snapshot_b=comparison.snapshot_b,
        changed_keys=list(comparison.changed_keys),
    )


@router.get(
    "/plants/{id}/digital-twin/versions/{version}", response_model=DigitalTwinVersionResponse, responses=_ERROR_RESPONSES,
    summary="Snapshot retrieval -- one specific version by number",
)
async def get_version(
    id: uuid.UUID, version: int, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    twin_service: DigitalTwinService = Depends(get_digital_twin_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> DigitalTwinVersionResponse:
    await _authorize_for_plant(plant_id=id, request=request, user=user, plant_service=plant_service, authz=authz)
    row = await twin_service.get_version(id, version)
    return DigitalTwinVersionResponse.model_validate(row)


@router.get(
    "/plants/{id}/digital-twin/snapshot", response_model=DigitalTwinVersionResponse, responses=_ERROR_RESPONSES,
    summary="Snapshot by date -- this plant's Digital Twin state as of a point in time",
)
async def get_snapshot_by_date(
    id: uuid.UUID, request: Request, as_of: datetime = Query(..., description="ISO-8601 timestamp"),
    user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    twin_service: DigitalTwinService = Depends(get_digital_twin_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> DigitalTwinVersionResponse:
    await _authorize_for_plant(plant_id=id, request=request, user=user, plant_service=plant_service, authz=authz)
    row = await twin_service.get_snapshot_by_date(id, as_of=as_of)
    return DigitalTwinVersionResponse.model_validate(row)


@router.get(
    "/plants/{id}/digital-twin/events", response_model=Page[DomainEventResponse], responses=_ERROR_RESPONSES,
    summary="Event history -- the raw domain events that drove this plant's Digital Twin, newest first",
)
async def get_event_history(
    id: uuid.UUID, request: Request, page_params: PageParams = Depends(),
    user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    twin_service: DigitalTwinService = Depends(get_digital_twin_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[DomainEventResponse]:
    await _authorize_for_plant(plant_id=id, request=request, user=user, plant_service=plant_service, authz=authz)
    rows, total = await twin_service.get_event_history(id, offset=page_params.offset, limit=page_params.page_size)
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[DomainEventResponse.model_validate(r) for r in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


@router.get(
    "/plants/{id}/digital-twin/verify", response_model=ReplayConsistencyResponse, responses=_ERROR_RESPONSES,
    summary="Diagnostic: replay this plant's full event history from scratch and compare against the live projection",
)
async def verify_twin_consistency(
    id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    twin_service: DigitalTwinService = Depends(get_digital_twin_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> ReplayConsistencyResponse:
    await _authorize_for_plant(plant_id=id, request=request, user=user, plant_service=plant_service, authz=authz)
    consistent, current_version, differing_keys = await twin_service.verify_consistency(id)
    return ReplayConsistencyResponse(
        plant_id=id, consistent=consistent, current_version=current_version, differing_keys=differing_keys
    )


@router.get(
    "/digital-twins", response_model=Page[DigitalTwinResponse], responses={401: _ERROR_RESPONSES[401], 403: _ERROR_RESPONSES[403]},
    summary="List/filter/sort the caller's organization's Digital Twins",
)
async def list_digital_twins(
    request: Request, page_params: PageParams = Depends(),
    lifecycle_state: str | None = None, branch_id: uuid.UUID | None = None,
    sort_by: str = "updated_at", sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    twin_service: DigitalTwinService = Depends(get_digital_twin_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[DigitalTwinResponse]:
    """
    No single plant to fetch-then-authorize against (mirrors `plants.py`'s
    own `list_plants` route): a branch filter is authorized against that
    specific branch; otherwise this is an org-wide `plants:read` check,
    same as `list_plants`.
    """
    if tenant.org_id is None:
        return Page(items=[], meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=0, total_pages=0))

    target_branch_id = branch_id
    decision = await authz.authorize(
        user=user, permission="plants:read", resource_type="plant",
        target_nursery_id=tenant.org_id, target_branch_id=target_branch_id, context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)

    rows, total = await twin_service.list_twins_for_nursery(
        tenant.org_id, offset=page_params.offset, limit=page_params.page_size,
        lifecycle_state=lifecycle_state, branch_id=branch_id, sort_by=sort_by, sort_dir=sort_dir,
    )
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[DigitalTwinResponse.model_validate(r) for r in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )