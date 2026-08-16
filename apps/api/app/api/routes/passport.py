"""
Module 9 (Sales, CRM, Plant Passport & QR Intelligence) — Plant Passport
& QR Intelligence REST API.

Two routers in this one file, deliberately kept separate:

  - `router` -- internal, authenticated management routes (`/passports`,
    `/plants/{plant_id}/passports`), reusing the pre-seeded
    `passport:generate`/`passport:read` permission codes, going through
    the exact same `get_current_user`/`AuthorizationService.authorize()`
    path every other authenticated route in this codebase uses.
  - `public_router` -- the module's one unauthenticated surface
    (`/public/passport/{token}`, `/public/qr/{token}`). Neither route
    below takes a `User`, `TenantContext`, or `AuthorizationService`
    dependency, and neither calls `get_current_user`/`get_tenant_context`
    -- per the module's own instruction ("customers must NOT
    authenticate... access controlled by secure public tokens only").
    Both are backed by `PassportService.get_passport_by_token`/
    `QRService.scan`, which verify the HMAC-signed token (see
    app/services/passport_service.py's module docstring) before any data
    is returned; a bad/forged/expired token yields the same generic 404
    regardless of which of those three failure modes occurred.

Both routers are mounted with no shared prefix in app/api/router.py,
matching Module 7/Module 8's own "router mounts its own absolute paths"
precedent for a module whose resources don't share one clean prefix.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import (
    TenantContext,
    get_authorization_service,
    get_current_user,
    get_passport_service,
    get_plant_repository,
    get_public_passport_service,
    get_qr_service,
    get_sale_item_repository,
    get_sale_repository,
    get_tenant_context,
    raise_if_denied,
    request_context,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.core.responses import ErrorResponse, Page, PageMeta
from app.models.identity import User
from app.repositories.interfaces import PlantRepository, SaleItemRepository, SaleRepository
from app.schemas.passport import (
    GeneratePassportRequest,
    PassportReportResponse,
    PassportResponse,
    PublicPassportResponse,
    QRScanResponse,
    passport_response,
    public_passport_response,
)
from app.services.authorization_service import AuthorizationService
from app.services.passport_service import PassportService, QRService

router = APIRouter()
public_router = APIRouter()

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Missing permission or cross-tenant/cross-branch access"},
    404: {"model": ErrorResponse, "description": "Not found"},
}
_PUBLIC_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "Invalid, forged, tampered, or expired passport token"},
}


# ==============================================================================
# Internal (authenticated) management routes
# ==============================================================================


@router.post(
    "/plants/{plant_id}/passports", response_model=PassportResponse, status_code=status.HTTP_201_CREATED,
    responses=_ERROR_RESPONSES, summary="Generate a Plant Passport for a plant (append-only/versioned)",
)
async def generate_passport(
    plant_id: uuid.UUID, body: GeneratePassportRequest, request: Request, user: User = Depends(get_current_user),
    plant_repo: PlantRepository = Depends(get_plant_repository), sale_repo: SaleRepository = Depends(get_sale_repository),
    sale_item_repo: SaleItemRepository = Depends(get_sale_item_repository),
    passport_service: PassportService = Depends(get_passport_service), qr_service: QRService = Depends(get_qr_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> PassportResponse:
    """
    `sale_id`/`sale_item_id` are optional and purely additive: passed
    through as plain, already-fetched rows to embed in the frozen
    `content_snapshot`'s `purchase_information` (Sales Order checkout
    calls `PassportService.generate_passport` the same way internally --
    see app/services/sales_service.py). Reading a Sale/SaleItem by id
    here is not "coupling Sales directly to Plant Lifecycle" (the
    module's own forbidden direction); it is Plant Passport, in its own
    bounded context, reading a fact Sales already published, exactly as
    `PassportService._build_snapshot`'s docstring describes.
    """
    plant = await plant_repo.get_by_id(plant_id)
    if plant is None:
        raise NotFoundError("Plant not found.")
    decision = await authz.authorize(
        user=user, permission="passport:generate", resource_type="passport", resource_id=plant.id,
        target_nursery_id=plant.nursery_id, target_branch_id=plant.branch_id, context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)

    sale = None
    sale_item = None
    if body.sale_id is not None:
        sale = await sale_repo.get_by_id(body.sale_id)
        if sale is None or sale.nursery_id != plant.nursery_id:
            raise ValidationError("sale_id does not reference a valid sale for this nursery.")
    if body.sale_item_id is not None:
        sale_item = await sale_item_repo.get_by_id(body.sale_item_id)
        if sale_item is None or sale_item.plant_id != plant.id or (sale is not None and sale_item.sale_id != sale.id):
            raise ValidationError("sale_item_id does not reference a valid sale item for this plant/sale.")

    passport = await passport_service.generate_passport(
        plant, actor_user_id=user.id, sale=sale, sale_item=sale_item, expires_at=body.expires_at,
        request_id=request_context(request).request_id,
    )
    return passport_response(passport, public_url=qr_service.qr_payload_url(passport))


@router.get("/passports/{id}", response_model=PassportResponse, responses=_ERROR_RESPONSES, summary="Get a Plant Passport (internal, authenticated view)")
async def get_passport(
    id: uuid.UUID, request: Request, user: User = Depends(get_current_user), plant_repo: PlantRepository = Depends(get_plant_repository),
    passport_service: PassportService = Depends(get_passport_service), qr_service: QRService = Depends(get_qr_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> PassportResponse:
    passport = await passport_service.get_passport(id)
    plant = await plant_repo.get_by_id(passport.plant_id)
    if plant is None:
        raise NotFoundError("Passport not found.")
    decision = await authz.authorize(
        user=user, permission="passport:read", resource_type="passport", resource_id=passport.id,
        target_nursery_id=plant.nursery_id, target_branch_id=plant.branch_id, context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)
    return passport_response(passport, public_url=qr_service.qr_payload_url(passport))


@router.get("/plants/{plant_id}/passports", response_model=list[PassportResponse], responses=_ERROR_RESPONSES, summary="List all Passport versions issued for a plant")
async def list_plant_passports(
    plant_id: uuid.UUID, request: Request, user: User = Depends(get_current_user), plant_repo: PlantRepository = Depends(get_plant_repository),
    passport_service: PassportService = Depends(get_passport_service), qr_service: QRService = Depends(get_qr_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> list[PassportResponse]:
    plant = await plant_repo.get_by_id(plant_id)
    if plant is None:
        raise NotFoundError("Plant not found.")
    decision = await authz.authorize(
        user=user, permission="passport:read", resource_type="passport", resource_id=plant.id,
        target_nursery_id=plant.nursery_id, target_branch_id=plant.branch_id, context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)
    passports = await passport_service.list_for_plant(plant_id)
    return [passport_response(p, public_url=qr_service.qr_payload_url(p)) for p in passports]


@router.get("/passports", response_model=Page[PassportResponse], responses=_ERROR_RESPONSES, summary="List all Passports issued for the organization")
async def list_passports(
    request: Request, page: int = 1, page_size: int = 25, user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), passport_service: PassportService = Depends(get_passport_service),
    qr_service: QRService = Depends(get_qr_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[PassportResponse]:
    if tenant.org_id is None:
        return Page(items=[], meta=PageMeta(page=page, page_size=page_size, total_items=0, total_pages=0))
    decision = await authz.authorize(
        user=user, permission="passport:read", resource_type="passport", target_nursery_id=tenant.org_id, context=request_context(request)
    )
    if not decision.allowed:
        raise raise_if_denied(decision)
    offset = (page - 1) * page_size
    rows, total = await passport_service.list_for_nursery(tenant.org_id, offset=offset, limit=page_size)
    total_pages = (total + page_size - 1) // page_size if total else 0
    return Page(
        items=[passport_response(p, public_url=qr_service.qr_payload_url(p)) for p in rows],
        meta=PageMeta(page=page, page_size=page_size, total_items=total, total_pages=total_pages),
    )


@router.get("/passports/reports/summary", response_model=PassportReportResponse, responses=_ERROR_RESPONSES, summary="Passport Report (issuance/versions/expiring-soon counts)")
async def get_passport_report(
    request: Request, user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    passport_service: PassportService = Depends(get_passport_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> PassportReportResponse:
    if tenant.org_id is None:
        return PassportReportResponse(total_passports=0, distinct_plants_with_passport=0, expiring_within_30_days=0)
    decision = await authz.authorize(
        user=user, permission="reports:read", resource_type="passport", target_nursery_id=tenant.org_id, context=request_context(request)
    )
    if not decision.allowed:
        raise raise_if_denied(decision)
    report = await passport_service.passport_report(tenant.org_id)
    return PassportReportResponse(**report)


# ==============================================================================
# Public (unauthenticated) QR Intelligence routes -- NO auth dependency of any kind
# ==============================================================================


@public_router.get(
    "/public/passport/{token}", response_model=PublicPassportResponse, responses=_PUBLIC_ERROR_RESPONSES,
    summary="Public Plant Passport lookup by signed token -- no authentication, no internal ids ever returned",
)
async def get_public_passport(token: str, passport_service: PassportService = Depends(get_public_passport_service)) -> PublicPassportResponse:
    passport = await passport_service.get_passport_by_token(token)
    return public_passport_response(passport)


@public_router.get(
    "/public/qr/{token}", response_model=QRScanResponse, responses=_PUBLIC_ERROR_RESPONSES,
    summary="Scan a Plant Passport QR code -- no authentication; returns Passport, Care Instructions, Water/Fertilizer Schedule, Health Status, Growth Timeline, AI Recommendations",
)
async def scan_qr(token: str, request: Request, qr_service: QRService = Depends(get_qr_service)) -> QRScanResponse:
    result = await qr_service.scan(token, user_agent=request.headers.get("user-agent"), referrer=request.headers.get("referer"))
    return QRScanResponse(**result)
