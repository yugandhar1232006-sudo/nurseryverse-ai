"""
Module 6 -- Growth/Health/Watering/Fertilizer/Environmental Records REST
API, all nested under `/plants/{plant_id}/...` per the LLD's own public
interface list for those four modules (`GET/POST /plants/{id}/growth-
timeline`, etc.). Every route fetches the parent Plant first (via
`PlantService`, itself already used for the same fetch-then-authorize
pattern in `plants.py`) to authorize against its real org/branch, then
delegates the actual record write/read to the matching record service --
routes stay thin, exactly as the module's own quality requirement asks.

No PATCH/DELETE anywhere in this file: every record type here is
immutable once created (plant_records_service.py's own module docstring
explains why), so there is nothing to update or remove.

Fertilizer routes are gated on `watering:read`/`watering:write` rather
than a `fertilizer:*` permission -- no such permission code was ever
seeded (migrations/versions/0002_seed_system_metadata.py), consistent
with `FertilizerLog`'s own docstring describing fertilizing as "folded
... under general 'care'" alongside watering rather than broken out as
its own RBAC-gated workflow in the pre-approved permission matrix
(docs/ux/07-role-permission-matrix.md). Reusing an existing, closely-
related permission is the same choice Module 5 made for `GET /plant-
categories` (gated on `species:read`).
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import (
    PageParams,
    get_authorization_service,
    get_current_user,
    get_environmental_service,
    get_fertilizer_service,
    get_growth_service,
    get_health_service,
    get_plant_service,
    get_watering_service,
    raise_if_denied,
    request_context,
)
from app.core.responses import ErrorResponse, Page, PageMeta
from app.models.identity import User
from app.models.plants import Plant
from app.schemas.plants import (
    EnvironmentalRecordResponse,
    FertilizerRecordResponse,
    GrowthRecordResponse,
    HealthRecordResponse,
    RecordEnvironmentalRequest,
    RecordFertilizerRequest,
    RecordGrowthRequest,
    RecordHealthRequest,
    RecordWateringRequest,
    WateringRecordResponse,
)
from app.services.authorization_service import AuthorizationService
from app.services.plant_records_service import (
    EnvironmentalService,
    FertilizerService,
    GrowthService,
    HealthService,
    WateringService,
)
from app.services.plant_service import PlantService

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
    plant = await plant_service.get_plant(plant_id)
    decision = await authz.authorize(
        user=user, permission=permission, resource_type="plant", resource_id=plant.id,
        target_nursery_id=plant.nursery_id, target_branch_id=plant.branch_id,
        context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)
    return plant


def _page(items: list, total: int, page_params: PageParams) -> Page:
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=items,
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


# ==============================================================================
# Growth
# ==============================================================================


@router.get(
    "/{plant_id}/growth-timeline", response_model=Page[GrowthRecordResponse], responses=_ERROR_RESPONSES,
    summary="List a plant's growth measurements",
)
async def list_growth(
    plant_id: uuid.UUID, request: Request, page_params: PageParams = Depends(), user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service), growth_service: GrowthService = Depends(get_growth_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[GrowthRecordResponse]:
    await _authorize_plant(plant_id=plant_id, permission="growth:read", request=request, user=user, plant_service=plant_service, authz=authz)
    rows, total = await growth_service.list_growth(plant_id, offset=page_params.offset, limit=page_params.page_size)
    return _page([GrowthRecordResponse.model_validate(r) for r in rows], total, page_params)


@router.post(
    "/{plant_id}/growth-timeline", response_model=GrowthRecordResponse, status_code=status.HTTP_201_CREATED,
    responses=_ERROR_RESPONSES, summary="Record a growth measurement (immutable once created)",
)
async def record_growth(
    plant_id: uuid.UUID, body: RecordGrowthRequest, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service), growth_service: GrowthService = Depends(get_growth_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> GrowthRecordResponse:
    await _authorize_plant(plant_id=plant_id, permission="growth:write", request=request, user=user, plant_service=plant_service, authz=authz)
    entry = await growth_service.record_growth(
        plant_id=plant_id, actor_user_id=user.id, height_cm=body.height_cm, spread_cm=body.spread_cm,
        leaf_count=body.leaf_count, flower_count=body.flower_count, fruit_count=body.fruit_count,
        growth_stage=body.growth_stage, notes=body.notes, photo_urls=body.photo_urls,
        measured_at=body.measured_at, request_id=request_context(request).request_id,
    )
    return GrowthRecordResponse.model_validate(entry)


# ==============================================================================
# Health
# ==============================================================================


@router.get(
    "/{plant_id}/health-history", response_model=Page[HealthRecordResponse], responses=_ERROR_RESPONSES,
    summary="List a plant's health observations",
)
async def list_health(
    plant_id: uuid.UUID, request: Request, page_params: PageParams = Depends(), user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service), health_service: HealthService = Depends(get_health_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[HealthRecordResponse]:
    await _authorize_plant(plant_id=plant_id, permission="health:read", request=request, user=user, plant_service=plant_service, authz=authz)
    rows, total = await health_service.list_health(plant_id, offset=page_params.offset, limit=page_params.page_size)
    return _page([HealthRecordResponse.model_validate(r) for r in rows], total, page_params)


@router.post(
    "/{plant_id}/health-history", response_model=HealthRecordResponse, status_code=status.HTTP_201_CREATED,
    responses=_ERROR_RESPONSES, summary="Record a health observation (manual or AI; immutable once created)",
)
async def record_health(
    plant_id: uuid.UUID, body: RecordHealthRequest, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service), health_service: HealthService = Depends(get_health_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> HealthRecordResponse:
    await _authorize_plant(plant_id=plant_id, permission="health:write", request=request, user=user, plant_service=plant_service, authz=authz)
    entry = await health_service.record_health(
        plant_id=plant_id, status_label=body.status_label, actor_user_id=user.id, health_score=body.health_score,
        notes=body.notes, photo_url=body.photo_url, is_ai_observation=body.is_ai_observation,
        observed_at=body.observed_at, request_id=request_context(request).request_id,
    )
    return HealthRecordResponse.model_validate(entry)


# ==============================================================================
# Watering
# ==============================================================================


@router.get(
    "/{plant_id}/watering-logs", response_model=Page[WateringRecordResponse], responses=_ERROR_RESPONSES,
    summary="List a plant's watering history",
)
async def list_watering(
    plant_id: uuid.UUID, request: Request, page_params: PageParams = Depends(), user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service), watering_service: WateringService = Depends(get_watering_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[WateringRecordResponse]:
    await _authorize_plant(plant_id=plant_id, permission="watering:read", request=request, user=user, plant_service=plant_service, authz=authz)
    rows, total = await watering_service.list_watering(plant_id, offset=page_params.offset, limit=page_params.page_size)
    return _page([WateringRecordResponse.model_validate(r) for r in rows], total, page_params)


@router.post(
    "/{plant_id}/watering-logs", response_model=WateringRecordResponse, status_code=status.HTTP_201_CREATED,
    responses=_ERROR_RESPONSES, summary="Record a watering event (immutable once created)",
)
async def record_watering(
    plant_id: uuid.UUID, body: RecordWateringRequest, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service), watering_service: WateringService = Depends(get_watering_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> WateringRecordResponse:
    await _authorize_plant(plant_id=plant_id, permission="watering:write", request=request, user=user, plant_service=plant_service, authz=authz)
    entry = await watering_service.record_watering(
        plant_id=plant_id, actor_user_id=user.id, volume_ml=body.volume_ml, method=body.method,
        notes=body.notes, watered_at=body.watered_at, request_id=request_context(request).request_id,
    )
    return WateringRecordResponse.model_validate(entry)


# ==============================================================================
# Fertilizer (gated on watering:* -- see module docstring)
# ==============================================================================


@router.get(
    "/{plant_id}/fertilizer-logs", response_model=Page[FertilizerRecordResponse], responses=_ERROR_RESPONSES,
    summary="List a plant's fertilizer application history",
)
async def list_fertilizer(
    plant_id: uuid.UUID, request: Request, page_params: PageParams = Depends(), user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service), fertilizer_service: FertilizerService = Depends(get_fertilizer_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[FertilizerRecordResponse]:
    await _authorize_plant(plant_id=plant_id, permission="watering:read", request=request, user=user, plant_service=plant_service, authz=authz)
    rows, total = await fertilizer_service.list_fertilizer(plant_id, offset=page_params.offset, limit=page_params.page_size)
    return _page([FertilizerRecordResponse.model_validate(r) for r in rows], total, page_params)


@router.post(
    "/{plant_id}/fertilizer-logs", response_model=FertilizerRecordResponse, status_code=status.HTTP_201_CREATED,
    responses=_ERROR_RESPONSES, summary="Record a fertilizer application (immutable once created)",
)
async def record_fertilizer(
    plant_id: uuid.UUID, body: RecordFertilizerRequest, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service), fertilizer_service: FertilizerService = Depends(get_fertilizer_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> FertilizerRecordResponse:
    await _authorize_plant(plant_id=plant_id, permission="watering:write", request=request, user=user, plant_service=plant_service, authz=authz)
    entry = await fertilizer_service.record_fertilizer(
        plant_id=plant_id, product_name=body.product_name, actor_user_id=user.id, quantity_ml=body.quantity_ml,
        npk_ratio=body.npk_ratio, method=body.method, schedule=body.schedule,
        next_application_date=body.next_application_date, notes=body.notes, applied_at=body.applied_at,
        request_id=request_context(request).request_id,
    )
    return FertilizerRecordResponse.model_validate(entry)


# ==============================================================================
# Environmental
# ==============================================================================


@router.get(
    "/{plant_id}/environmental-readings", response_model=Page[EnvironmentalRecordResponse], responses=_ERROR_RESPONSES,
    summary="List a plant's environmental readings",
)
async def list_environmental(
    plant_id: uuid.UUID, request: Request, page_params: PageParams = Depends(), user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    environmental_service: EnvironmentalService = Depends(get_environmental_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[EnvironmentalRecordResponse]:
    await _authorize_plant(plant_id=plant_id, permission="environmental:read", request=request, user=user, plant_service=plant_service, authz=authz)
    rows, total = await environmental_service.list_readings(plant_id, offset=page_params.offset, limit=page_params.page_size)
    return _page([EnvironmentalRecordResponse.model_validate(r) for r in rows], total, page_params)


@router.post(
    "/{plant_id}/environmental-readings", response_model=EnvironmentalRecordResponse, status_code=status.HTTP_201_CREATED,
    responses=_ERROR_RESPONSES, summary="Record an environmental reading (immutable once created)",
)
async def record_environmental(
    plant_id: uuid.UUID, body: RecordEnvironmentalRequest, request: Request, user: User = Depends(get_current_user),
    plant_service: PlantService = Depends(get_plant_service),
    environmental_service: EnvironmentalService = Depends(get_environmental_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> EnvironmentalRecordResponse:
    await _authorize_plant(plant_id=plant_id, permission="environmental:write", request=request, user=user, plant_service=plant_service, authz=authz)
    entry = await environmental_service.record_reading(
        plant_id=plant_id, actor_user_id=user.id, temperature_celsius=body.temperature_celsius,
        humidity_percent=body.humidity_percent, soil_moisture_percent=body.soil_moisture_percent,
        light_lux=body.light_lux, ph_level=body.ph_level, weather_snapshot=body.weather_snapshot,
        source=body.source, recorded_at=body.recorded_at, request_id=request_context(request).request_id,
    )
    return EnvironmentalRecordResponse.model_validate(entry)
