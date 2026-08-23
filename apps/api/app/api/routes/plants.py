"""
Module 6 (Plant Lifecycle Management) — Plant Registration, Profile,
Movement, Status, Archive, Images, and Timeline REST API.

Flat `/plants` collection, same shape as every prior module's flat
resources (see branches.py's module docstring for the general rationale).
Plant is genuinely *branch*-scoped (`Plant.branch_id`, `BranchScopedMixin`)
though, not just org-scoped like Species -- the permission matrix marks
`plants:read`/`plants:write`/`plants:transfer` as "B" (branch-scoped) for
Horticulturist/Sales Staff, meaning a caller's role may only cover some of
an org's branches. Every route below therefore passes `target_branch_id`
into `AuthorizationService.authorize()` wherever a specific branch is
known -- for the by-id routes via fetch-then-authorize (learning the
plant's real branch), and for `POST /plants` via the request body's own
`branch_id` (there is no plant yet to fetch). This is one real step
further than Module 4's Employee/Branch routes took (those never had a
single, always-known target branch to check against), not a deviation
from them.
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
    get_plant_service,
    get_plant_timeline_service,
    get_tenant_context,
    raise_if_denied,
    request_context,
)
from app.core.exceptions import ValidationError
from app.core.responses import ErrorResponse, Page, PageMeta
from app.db.enums import PlantStatus
from app.models.identity import User
from app.models.plants import Plant
from app.schemas.plants import (
    ArchivePlantRequest,
    BulkRegisterPlantsRequest,
    MovePlantRequest,
    PlantImageResponse,
    PlantResponse,
    PlantTimelineEntryResponse,
    PlantTransferResponse,
    RegisterPlantRequest,
    TransitionStatusRequest,
    UpdatePlantProfileRequest,
    UploadPlantImageRequest,
)
from app.services.authorization_service import AuthorizationService
from app.services.plant_service import PlantService
from app.services.plant_timeline_service import PlantTimelineService

router = APIRouter()

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Missing permission or cross-tenant/cross-branch access"},
    404: {"model": ErrorResponse, "description": "Plant not found"},
}


async def _authorize_plant(
    *, plant_id: uuid.UUID, permission: str, request: Request, user: User,
    plant_service: PlantService, authz: AuthorizationService,
) -> Plant:
    """Fetch-then-authorize for the by-id routes, scoped to both the plant's org *and* branch -- see module docstring."""
    plant = await plant_service.get_plant(plant_id)
    decision = await authz.authorize(
        user=user, permission=permission, resource_type="plant", resource_id=plant.id,
        target_nursery_id=plant.nursery_id, target_branch_id=plant.branch_id,
        context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)
    return plant


async def _authorize_branch_write(
    *, branch_id: uuid.UUID, permission: str, request: Request, user: User, tenant: TenantContext,
    authz: AuthorizationService,
) -> None:
    """Register/bulk-register: the plant doesn't exist yet, so the target branch comes from the request body instead of a fetched resource."""
    decision = await authz.authorize(
        user=user, permission=permission, resource_type="plant",
        target_nursery_id=tenant.org_id, target_branch_id=branch_id,
        context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)


def _register_kwargs(body: RegisterPlantRequest) -> dict:
    return {
        "branch_id": body.branch_id, "species_id": body.species_id, "variety_id": body.variety_id,
        "common_label": body.common_label, "zone": body.zone, "batch_number": body.batch_number,
        "supplier_id": body.supplier_id, "purchase_price": body.purchase_price,
        "purchase_date": body.purchase_date, "price": body.price, "planted_at": body.planted_at,
        "description": body.description,
    }


@router.get(
    "",
    response_model=Page[PlantResponse],
    responses={401: _ERROR_RESPONSES[401], 403: _ERROR_RESPONSES[403]},
    summary="List/search/filter/sort the caller's organization's plants",
    description=(
        "Requires `plants:read`. Supports `branch_id`, `species_id`, `status`, `zone`, `batch_number` filters, "
        "`search` (matches common label/QR token/batch number), and `sort_by`/`sort_dir`."
    ),
)
async def list_plants(
    request: Request,
    page_params: PageParams = Depends(),
    branch_id: uuid.UUID | None = None,
    species_id: uuid.UUID | None = None,
    status_filter: PlantStatus | None = None,
    zone: str | None = None,
    batch_number: str | None = None,
    search: str | None = None,
    include_archived: bool = False,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    plant_service: PlantService = Depends(get_plant_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[PlantResponse]:
    if tenant.org_id is None:
        return Page(items=[], meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=0, total_pages=0))

    if branch_id is not None:
        await _authorize_branch_write(
            branch_id=branch_id, permission="plants:read", request=request, user=user, tenant=tenant, authz=authz
        )
    else:
        decision = await authz.authorize(
            user=user, permission="plants:read", resource_type="plant",
            target_nursery_id=tenant.org_id, context=request_context(request),
        )
        if not decision.allowed:
            raise raise_if_denied(decision)

    rows, total = await plant_service.list_plants(
        nursery_id=tenant.org_id, offset=page_params.offset, limit=page_params.page_size,
        branch_id=branch_id, species_id=species_id, status=status_filter, zone=zone,
        batch_number=batch_number, search=search, include_archived=include_archived,
        sort_by=sort_by, sort_dir=sort_dir,
    )
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[PlantResponse.model_validate(p) for p in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


@router.post(
    "",
    response_model=PlantResponse,
    responses={
        **_ERROR_RESPONSES,
        422: {"model": ErrorResponse, "description": "Unknown branch/species/variety/supplier"},
    },
    status_code=status.HTTP_201_CREATED,
    summary="Register a new plant (creates its Digital Twin and generates a unique QR code)",
)
async def register_plant(
    body: RegisterPlantRequest,
    request: Request,
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    plant_service: PlantService = Depends(get_plant_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> PlantResponse:
    if tenant.org_id is None:
        raise ValidationError("You must belong to an organization to register a plant.")
    await _authorize_branch_write(
        branch_id=body.branch_id, permission="plants:write", request=request, user=user, tenant=tenant, authz=authz
    )

    plant = await plant_service.register_plant(
        nursery_id=tenant.org_id, actor_user_id=user.id,
        request_id=request_context(request).request_id, **_register_kwargs(body),
    )
    return PlantResponse.model_validate(plant)


@router.post(
    "/bulk",
    response_model=list[PlantResponse],
    responses={
        **_ERROR_RESPONSES,
        422: {"model": ErrorResponse, "description": "Unknown branch/species/variety/supplier in one or more items"},
    },
    status_code=status.HTTP_201_CREATED,
    summary="Bulk-register multiple plants in one request (all-or-nothing)",
)
async def bulk_register_plants(
    body: BulkRegisterPlantsRequest,
    request: Request,
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    plant_service: PlantService = Depends(get_plant_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> list[PlantResponse]:
    if tenant.org_id is None:
        raise ValidationError("You must belong to an organization to register plants.")

    for branch_id in {item.branch_id for item in body.plants}:
        await _authorize_branch_write(
            branch_id=branch_id, permission="plants:write", request=request, user=user, tenant=tenant, authz=authz
        )

    plants = await plant_service.bulk_register_plants(
        nursery_id=tenant.org_id, actor_user_id=user.id, request_id=request_context(request).request_id,
        items=[_register_kwargs(item) for item in body.plants],
    )
    return [PlantResponse.model_validate(p) for p in plants]


@router.get("/qr/{token}", response_model=PlantResponse, responses=_ERROR_RESPONSES, summary="Look up a plant by its QR code token")
async def get_plant_by_qr(
    token: str,
    request: Request,
    user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> PlantResponse:
    plant = await plant_service.get_by_qr_token(token)
    decision = await authz.authorize(
        user=user, permission="plants:read", resource_type="plant", resource_id=plant.id,
        target_nursery_id=plant.nursery_id, target_branch_id=plant.branch_id, context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)
    return PlantResponse.model_validate(plant)


@router.get("/{id}", response_model=PlantResponse, responses=_ERROR_RESPONSES, summary="Get a plant by id")
async def get_plant(
    id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> PlantResponse:
    plant = await _authorize_plant(
        plant_id=id, permission="plants:read", request=request, user=user, plant_service=plant_service, authz=authz
    )
    return PlantResponse.model_validate(plant)


@router.patch("/{id}", response_model=PlantResponse, responses=_ERROR_RESPONSES, summary="Update a plant's profile")
async def update_plant(
    id: uuid.UUID, body: UpdatePlantProfileRequest, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> PlantResponse:
    await _authorize_plant(
        plant_id=id, permission="plants:write", request=request, user=user, plant_service=plant_service, authz=authz
    )
    plant = await plant_service.update_plant_profile(
        plant_id=id, actor_user_id=user.id, common_label=body.common_label, variety_id=body.variety_id,
        batch_number=body.batch_number, supplier_id=body.supplier_id, purchase_price=body.purchase_price,
        purchase_date=body.purchase_date, price=body.price, description=body.description,
        request_id=request_context(request).request_id,
    )
    return PlantResponse.model_validate(plant)


@router.post(
    "/{id}/status", response_model=PlantResponse,
    responses={**_ERROR_RESPONSES, 409: {"model": ErrorResponse, "description": "Illegal status transition"}},
    summary="Transition a plant's status (docs/ux/13-digital-twin-lifecycle.md's state machine)",
)
async def transition_plant_status(
    id: uuid.UUID, body: TransitionStatusRequest, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> PlantResponse:
    await _authorize_plant(
        plant_id=id, permission="plants:write", request=request, user=user, plant_service=plant_service, authz=authz
    )
    plant = await plant_service.transition_status(
        plant_id=id, to_status=body.to_status, actor_user_id=user.id, reason=body.reason,
        request_id=request_context(request).request_id,
    )
    return PlantResponse.model_validate(plant)


@router.post(
    "/{id}/move", response_model=PlantResponse, responses=_ERROR_RESPONSES,
    summary="Move a plant (branch transfer, zone/greenhouse/outdoor movement)",
)
async def move_plant(
    id: uuid.UUID, body: MovePlantRequest, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> PlantResponse:
    await _authorize_plant(
        plant_id=id, permission="plants:transfer", request=request, user=user, plant_service=plant_service, authz=authz
    )
    # A branch-to-branch move additionally needs write access to the *destination* branch.
    if body.to_branch_id is not None:
        plant_for_dest_check = await plant_service.get_plant(id)
        if body.to_branch_id != plant_for_dest_check.branch_id:
            decision = await authz.authorize(
                user=user, permission="plants:transfer", resource_type="plant",
                target_nursery_id=plant_for_dest_check.nursery_id, target_branch_id=body.to_branch_id,
                context=request_context(request),
            )
            if not decision.allowed:
                raise raise_if_denied(decision)

    plant = await plant_service.move_plant(
        plant_id=id, actor_user_id=user.id, to_branch_id=body.to_branch_id, to_zone=body.to_zone,
        note=body.note, request_id=request_context(request).request_id,
    )
    return PlantResponse.model_validate(plant)


@router.get(
    "/{id}/movement-history", response_model=list[PlantTransferResponse], responses=_ERROR_RESPONSES,
    summary="Full branch/zone movement history for a plant",
)
async def get_movement_history(
    id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> list[PlantTransferResponse]:
    await _authorize_plant(
        plant_id=id, permission="plants:read", request=request, user=user, plant_service=plant_service, authz=authz
    )
    transfers = await plant_service.list_movement_history(id)
    return [PlantTransferResponse.model_validate(t) for t in transfers]


@router.post(
    "/{id}/archive", response_model=PlantResponse,
    responses={**_ERROR_RESPONSES, 409: {"model": ErrorResponse, "description": "Already archived, or not in a terminal status"}},
    summary="Archive a plant (administrative: hides it from default listings, keeps full history)",
)
async def archive_plant(
    id: uuid.UUID, body: ArchivePlantRequest, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> PlantResponse:
    await _authorize_plant(
        plant_id=id, permission="plants:write", request=request, user=user, plant_service=plant_service, authz=authz
    )
    plant = await plant_service.archive_plant(
        plant_id=id, actor_user_id=user.id, reason=body.reason, request_id=request_context(request).request_id
    )
    return PlantResponse.model_validate(plant)


@router.post(
    "/{id}/images", response_model=PlantImageResponse, status_code=status.HTTP_201_CREATED,
    responses=_ERROR_RESPONSES, summary="Upload an image for a plant",
)
async def upload_plant_image(
    id: uuid.UUID, body: UploadPlantImageRequest, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> PlantImageResponse:
    await _authorize_plant(
        plant_id=id, permission="plants:write", request=request, user=user, plant_service=plant_service, authz=authz
    )
    image = await plant_service.upload_image(
        plant_id=id, url=body.url, thumbnail_url=body.thumbnail_url, caption=body.caption,
        actor_user_id=user.id, request_id=request_context(request).request_id,
    )
    return PlantImageResponse.model_validate(image)


@router.get("/{id}/images", response_model=list[PlantImageResponse], responses=_ERROR_RESPONSES, summary="List a plant's images")
async def list_plant_images(
    id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> list[PlantImageResponse]:
    await _authorize_plant(
        plant_id=id, permission="plants:read", request=request, user=user, plant_service=plant_service, authz=authz
    )
    images = await plant_service.list_images(id)
    return [PlantImageResponse.model_validate(i) for i in images]


@router.get(
    "/{id}/timeline", response_model=Page[PlantTimelineEntryResponse], responses=_ERROR_RESPONSES,
    summary="Immutable, chronologically ordered feed of every lifecycle event for this plant",
)
async def get_plant_timeline(
    id: uuid.UUID, request: Request, page_params: PageParams = Depends(), user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    timeline_service: PlantTimelineService = Depends(get_plant_timeline_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[PlantTimelineEntryResponse]:
    await _authorize_plant(
        plant_id=id, permission="plants:read", request=request, user=user, plant_service=plant_service, authz=authz
    )
    entries, total = await timeline_service.get_timeline(id, offset=page_params.offset, limit=page_params.page_size)
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[PlantTimelineEntryResponse.model_validate(e) for e in entries],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )
