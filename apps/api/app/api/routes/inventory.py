"""
Module 8 (Inventory & Stock Management) REST API.

Mounted with no router-level prefix (like digital_twin.py) because this
module spans three different path roots: `/inventory-locations`,
`/inventory`, and `/stock-reservations`. Authorization mirrors plants.py's
own pattern exactly: `_authorize_inventory` (fetch-then-authorize, scoped
to both org and branch) for by-id routes, `_authorize_branch_write`
(target branch known from the request body, resource doesn't exist yet)
for creation routes. Reuses the three permission codes migration 0002
already seeded (`inventory:read`/`inventory:write`/`inventory:adjust`) --
no new permission codes minted, same "reuse what's already seeded"
precedent Module 7 applied to `plants:read`. `inventory:adjust` gates the
quantity-correcting/write-off actions (Adjust, Damage, Dispose, Archive)
per the LLD's own "`inventory:adjust` permission-gated" security note;
`inventory:write` gates the normal operational flows (create, receive,
transfer, reserve, release, fulfill, sell).

Route-ordering: every static report path (`/inventory/summary`,
`/inventory/low-stock`, etc.) is registered before the parameterized
`/inventory/{id}`, per the exact FastAPI route-matching bug Module 7
already caught and fixed once (digital_twin.py's `/versions/compare` vs
`/versions/{version}`).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import (
    PageParams,
    TenantContext,
    get_authorization_service,
    get_current_user,
    get_inventory_location_service,
    get_inventory_service,
    get_tenant_context,
    raise_if_denied,
    request_context,
    require_permission,
)
from app.core.exceptions import ValidationError
from app.core.responses import ErrorResponse, Page, PageMeta
from app.db.enums import StockMovementType, StockReservationStatus
from app.models.identity import User
from app.models.inventory import Inventory, InventoryLocation, StockReservation
from app.schemas.inventory import (
    AdjustStockRequest,
    ArchiveInventoryRequest,
    CreateInventoryLineRequest,
    CreateInventoryLocationRequest,
    DisposeStockRequest,
    FulfillReservationRequest,
    InventoryLocationResponse,
    InventoryResponse,
    InventorySummaryResponse,
    MarkDamagedRequest,
    ReceiveStockRequest,
    ReserveStockRequest,
    SellStockRequest,
    StockMovementResponse,
    StockReservationResponse,
    StockValuationResponse,
    TransferReportResponse,
    TransferStockRequest,
    UnitResponse,
    WasteReportResponse,
    inventory_response,
)
from app.services.authorization_service import AuthorizationDecision, AuthorizationService
from app.services.inventory_service import InventoryLocationService, InventoryService

router = APIRouter()

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Missing permission or cross-tenant/cross-branch access"},
    404: {"model": ErrorResponse, "description": "Not found"},
}


async def _authorize_inventory(
    *, inventory_id: uuid.UUID, permission: str, request: Request, user: User,
    inventory_service: InventoryService, authz: AuthorizationService,
) -> Inventory:
    item = await inventory_service.get_inventory(inventory_id)
    decision = await authz.authorize(
        user=user, permission=permission, resource_type="inventory", resource_id=item.id,
        target_nursery_id=item.nursery_id, target_branch_id=item.branch_id, context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)
    return item


async def _authorize_location(
    *, location_id: uuid.UUID, permission: str, request: Request, user: User,
    location_service: InventoryLocationService, authz: AuthorizationService,
) -> InventoryLocation:
    location = await location_service.get_location(location_id)
    decision = await authz.authorize(
        user=user, permission=permission, resource_type="inventory_location", resource_id=location.id,
        target_nursery_id=location.nursery_id, target_branch_id=location.branch_id, context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)
    return location


async def _authorize_branch_write(
    *, branch_id: uuid.UUID, permission: str, request: Request, user: User, tenant: TenantContext,
    authz: AuthorizationService,
) -> None:
    decision = await authz.authorize(
        user=user, permission=permission, resource_type="inventory",
        target_nursery_id=tenant.org_id, target_branch_id=branch_id, context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)


async def _authorize_reservation(
    *, reservation_id: uuid.UUID, permission: str, request: Request, user: User,
    inventory_service: InventoryService, authz: AuthorizationService,
) -> StockReservation:
    reservation = await inventory_service.get_reservation(reservation_id)
    decision = await authz.authorize(
        user=user, permission=permission, resource_type="stock_reservation", resource_id=reservation.id,
        target_nursery_id=reservation.nursery_id, target_branch_id=reservation.branch_id,
        context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)
    return reservation


# ==============================================================================
# Inventory Locations
# ==============================================================================


@router.post(
    "/inventory-locations", response_model=InventoryLocationResponse, status_code=status.HTTP_201_CREATED,
    responses=_ERROR_RESPONSES, summary="Create a sub-branch inventory location (Zone/Greenhouse/Outdoor/Rack/Bench/Section)",
)
async def create_inventory_location(
    body: CreateInventoryLocationRequest, request: Request, user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    location_service: InventoryLocationService = Depends(get_inventory_location_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> InventoryLocationResponse:
    if tenant.org_id is None:
        raise ValidationError("You must belong to an organization to create an inventory location.")
    await _authorize_branch_write(
        branch_id=body.branch_id, permission="inventory:write", request=request, user=user, tenant=tenant, authz=authz
    )
    location = await location_service.create_location(
        nursery_id=tenant.org_id, branch_id=body.branch_id, location_type=body.location_type, name=body.name,
        code=body.code, parent_location_id=body.parent_location_id, actor_user_id=user.id,
        request_id=request_context(request).request_id,
    )
    return InventoryLocationResponse.model_validate(location)


@router.get(
    "/inventory-locations", response_model=list[InventoryLocationResponse], responses=_ERROR_RESPONSES,
    summary="List a branch's inventory locations",
)
async def list_inventory_locations(
    branch_id: uuid.UUID, request: Request, include_inactive: bool = False, user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    location_service: InventoryLocationService = Depends(get_inventory_location_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> list[InventoryLocationResponse]:
    await _authorize_branch_write(
        branch_id=branch_id, permission="inventory:read", request=request, user=user, tenant=tenant, authz=authz
    )
    locations = await location_service.list_locations(branch_id, include_inactive=include_inactive)
    return [InventoryLocationResponse.model_validate(loc) for loc in locations]


@router.get(
    "/inventory-locations/{id}", response_model=InventoryLocationResponse, responses=_ERROR_RESPONSES,
    summary="Get an inventory location by id",
)
async def get_inventory_location(
    id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    location_service: InventoryLocationService = Depends(get_inventory_location_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> InventoryLocationResponse:
    location = await _authorize_location(
        location_id=id, permission="inventory:read", request=request, user=user,
        location_service=location_service, authz=authz,
    )
    return InventoryLocationResponse.model_validate(location)


@router.post(
    "/inventory-locations/{id}/deactivate", response_model=InventoryLocationResponse, responses=_ERROR_RESPONSES,
    summary="Deactivate an inventory location",
)
async def deactivate_inventory_location(
    id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    location_service: InventoryLocationService = Depends(get_inventory_location_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> InventoryLocationResponse:
    await _authorize_location(
        location_id=id, permission="inventory:write", request=request, user=user,
        location_service=location_service, authz=authz,
    )
    location = await location_service.deactivate_location(
        id, actor_user_id=user.id, request_id=request_context(request).request_id
    )
    return InventoryLocationResponse.model_validate(location)


@router.get(
    "/units", response_model=list[UnitResponse], responses={401: _ERROR_RESPONSES[401], 403: _ERROR_RESPONSES[403]},
    summary="List the global unit-of-measure reference data (Inventory line create form's unit dropdown)",
)
async def list_units(
    location_service: InventoryLocationService = Depends(get_inventory_location_service),
    decision: AuthorizationDecision = Depends(require_permission("inventory:read", resource_type="unit")),
) -> list[UnitResponse]:
    units = await location_service.list_units()
    return [UnitResponse.model_validate(u) for u in units]


# ==============================================================================
# Inventory: Reporting (registered before /inventory/{id} -- see module docstring)
# ==============================================================================


@router.get("/inventory/summary", response_model=InventorySummaryResponse, responses=_ERROR_RESPONSES, summary="Inventory Summary report")
async def get_inventory_summary(
    request: Request, branch_id: uuid.UUID | None = None, user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), inventory_service: InventoryService = Depends(get_inventory_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> InventorySummaryResponse:
    if tenant.org_id is None:
        return InventorySummaryResponse(
            line_count=0, total_quantity=0, total_reserved_quantity=0, total_damaged_quantity=0,
            total_disposed_quantity=0, total_available_quantity=0, low_stock_count=0, total_valuation=0.0,
        )
    await _report_authorize(branch_id=branch_id, request=request, user=user, tenant=tenant, authz=authz)
    summary = await inventory_service.inventory_summary(tenant.org_id, branch_id=branch_id)
    return InventorySummaryResponse(**summary)


@router.get("/inventory/low-stock", response_model=list[InventoryResponse], responses=_ERROR_RESPONSES, summary="Low Stock report")
async def get_low_stock_report(
    request: Request, branch_id: uuid.UUID | None = None, user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), inventory_service: InventoryService = Depends(get_inventory_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> list[InventoryResponse]:
    if tenant.org_id is None:
        return []
    await _report_authorize(branch_id=branch_id, request=request, user=user, tenant=tenant, authz=authz)
    items = await inventory_service.low_stock_report(tenant.org_id, branch_id=branch_id)
    return [inventory_response(item) for item in items]


@router.get("/inventory/valuation", response_model=StockValuationResponse, responses=_ERROR_RESPONSES, summary="Stock Valuation report")
async def get_stock_valuation(
    request: Request, branch_id: uuid.UUID | None = None, user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), inventory_service: InventoryService = Depends(get_inventory_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> StockValuationResponse:
    if tenant.org_id is None:
        return StockValuationResponse(line_count=0, total_cost_value=0.0, total_retail_value=0.0, potential_margin=0.0)
    await _report_authorize(branch_id=branch_id, request=request, user=user, tenant=tenant, authz=authz)
    valuation = await inventory_service.stock_valuation(tenant.org_id, branch_id=branch_id)
    return StockValuationResponse(**valuation)


@router.get("/inventory/waste-report", response_model=WasteReportResponse, responses=_ERROR_RESPONSES, summary="Waste report")
async def get_waste_report(
    request: Request, branch_id: uuid.UUID | None = None, date_from: datetime | None = None,
    date_to: datetime | None = None, user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), inventory_service: InventoryService = Depends(get_inventory_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> WasteReportResponse:
    if tenant.org_id is None:
        return WasteReportResponse(movement_count=0, total_quantity_disposed=0, movements=[])
    await _report_authorize(branch_id=branch_id, request=request, user=user, tenant=tenant, authz=authz)
    report = await inventory_service.waste_report(tenant.org_id, branch_id=branch_id, date_from=date_from, date_to=date_to)
    return WasteReportResponse(
        movement_count=report["movement_count"], total_quantity_disposed=report["total_quantity_disposed"],
        movements=[StockMovementResponse.model_validate(m) for m in report["movements"]],
    )


@router.get("/inventory/transfer-report", response_model=TransferReportResponse, responses=_ERROR_RESPONSES, summary="Transfer report")
async def get_transfer_report(
    request: Request, branch_id: uuid.UUID | None = None, date_from: datetime | None = None,
    date_to: datetime | None = None, user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), inventory_service: InventoryService = Depends(get_inventory_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> TransferReportResponse:
    if tenant.org_id is None:
        return TransferReportResponse(movement_count=0, movements=[])
    await _report_authorize(branch_id=branch_id, request=request, user=user, tenant=tenant, authz=authz)
    report = await inventory_service.transfer_report(tenant.org_id, branch_id=branch_id, date_from=date_from, date_to=date_to)
    return TransferReportResponse(
        movement_count=report["movement_count"], movements=[StockMovementResponse.model_validate(m) for m in report["movements"]]
    )


@router.get("/inventory/movements", response_model=Page[StockMovementResponse], responses=_ERROR_RESPONSES, summary="Movement History report (org-wide)")
async def get_movement_history(
    request: Request, page_params: PageParams = Depends(), branch_id: uuid.UUID | None = None,
    movement_type: StockMovementType | None = None, date_from: datetime | None = None, date_to: datetime | None = None,
    user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    inventory_service: InventoryService = Depends(get_inventory_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[StockMovementResponse]:
    if tenant.org_id is None:
        return Page(items=[], meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=0, total_pages=0))
    await _report_authorize(branch_id=branch_id, request=request, user=user, tenant=tenant, authz=authz)
    rows, total = await inventory_service.movement_history(
        tenant.org_id, offset=page_params.offset, limit=page_params.page_size, branch_id=branch_id,
        movement_type=movement_type, date_from=date_from, date_to=date_to,
    )
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[StockMovementResponse.model_validate(m) for m in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


@router.get("/inventory/reservations", response_model=Page[StockReservationResponse], responses=_ERROR_RESPONSES, summary="Reservation report (active reservations, org-wide)")
async def get_reservation_report(
    request: Request, page_params: PageParams = Depends(), branch_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    inventory_service: InventoryService = Depends(get_inventory_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[StockReservationResponse]:
    if tenant.org_id is None:
        return Page(items=[], meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=0, total_pages=0))
    await _report_authorize(branch_id=branch_id, request=request, user=user, tenant=tenant, authz=authz)
    rows, total = await inventory_service.reservation_report(
        tenant.org_id, branch_id=branch_id, offset=page_params.offset, limit=page_params.page_size
    )
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[StockReservationResponse.model_validate(r) for r in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


async def _report_authorize(
    *, branch_id: uuid.UUID | None, request: Request, user: User, tenant: TenantContext, authz: AuthorizationService
) -> None:
    if branch_id is not None:
        await _authorize_branch_write(
            branch_id=branch_id, permission="inventory:read", request=request, user=user, tenant=tenant, authz=authz
        )
    else:
        decision = await authz.authorize(
            user=user, permission="inventory:read", resource_type="inventory",
            target_nursery_id=tenant.org_id, context=request_context(request),
        )
        if not decision.allowed:
            raise raise_if_denied(decision)


# ==============================================================================
# Inventory: CRUD + Search
# ==============================================================================


@router.get("/inventory", response_model=Page[InventoryResponse], responses=_ERROR_RESPONSES, summary="List/search/filter/sort the caller's organization's inventory")
async def list_inventory(
    request: Request, page_params: PageParams = Depends(), branch_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None, species_id: uuid.UUID | None = None, location_id: uuid.UUID | None = None,
    search: str | None = None, low_stock_only: bool = False, include_archived: bool = False,
    sort_by: str = "created_at", sort_dir: str = "desc", user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), inventory_service: InventoryService = Depends(get_inventory_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[InventoryResponse]:
    if tenant.org_id is None:
        return Page(items=[], meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=0, total_pages=0))
    await _report_authorize(branch_id=branch_id, request=request, user=user, tenant=tenant, authz=authz)
    rows, total = await inventory_service.list_inventory(
        tenant.org_id, offset=page_params.offset, limit=page_params.page_size, branch_id=branch_id,
        category_id=category_id, species_id=species_id, location_id=location_id, search=search,
        low_stock_only=low_stock_only, include_archived=include_archived, sort_by=sort_by, sort_dir=sort_dir,
    )
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[inventory_response(item) for item in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


@router.post("/inventory", response_model=InventoryResponse, status_code=status.HTTP_201_CREATED, responses=_ERROR_RESPONSES, summary="Create an inventory line (PG-36)")
async def create_inventory_line(
    body: CreateInventoryLineRequest, request: Request, user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), inventory_service: InventoryService = Depends(get_inventory_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> InventoryResponse:
    if tenant.org_id is None:
        raise ValidationError("You must belong to an organization to create an inventory line.")
    await _authorize_branch_write(
        branch_id=body.branch_id, permission="inventory:write", request=request, user=user, tenant=tenant, authz=authz
    )
    item = await inventory_service.create_inventory_line(
        nursery_id=tenant.org_id, branch_id=body.branch_id, category_id=body.category_id, unit_id=body.unit_id,
        name=body.name, species_id=body.species_id, location_id=body.location_id, unit_cost=body.unit_cost,
        unit_price=body.unit_price, low_stock_threshold=body.low_stock_threshold,
        initial_quantity=body.initial_quantity, actor_user_id=user.id, request_id=request_context(request).request_id,
    )
    return inventory_response(item)


@router.get("/inventory/{id}", response_model=InventoryResponse, responses=_ERROR_RESPONSES, summary="Get an inventory line by id")
async def get_inventory(
    id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> InventoryResponse:
    item = await _authorize_inventory(
        inventory_id=id, permission="inventory:read", request=request, user=user,
        inventory_service=inventory_service, authz=authz,
    )
    return inventory_response(item)


@router.get("/inventory/{id}/movements", response_model=Page[StockMovementResponse], responses=_ERROR_RESPONSES, summary="Movement history for one inventory line")
async def get_line_movements(
    id: uuid.UUID, request: Request, page_params: PageParams = Depends(), movement_type: StockMovementType | None = None,
    user: User = Depends(get_current_user), inventory_service: InventoryService = Depends(get_inventory_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[StockMovementResponse]:
    await _authorize_inventory(
        inventory_id=id, permission="inventory:read", request=request, user=user,
        inventory_service=inventory_service, authz=authz,
    )
    rows, total = await inventory_service.list_movements(
        id, offset=page_params.offset, limit=page_params.page_size, movement_type=movement_type
    )
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[StockMovementResponse.model_validate(m) for m in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


@router.get("/inventory/{id}/reservations", response_model=list[StockReservationResponse], responses=_ERROR_RESPONSES, summary="Reservations for one inventory line")
async def get_line_reservations(
    id: uuid.UUID, request: Request, status_filter: StockReservationStatus | None = Query(None, alias="status"),
    user: User = Depends(get_current_user), inventory_service: InventoryService = Depends(get_inventory_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> list[StockReservationResponse]:
    await _authorize_inventory(
        inventory_id=id, permission="inventory:read", request=request, user=user,
        inventory_service=inventory_service, authz=authz,
    )
    reservations = await inventory_service.list_reservations(id, status=status_filter)
    return [StockReservationResponse.model_validate(r) for r in reservations]


# ==============================================================================
# Inventory: mutating actions
# ==============================================================================


@router.post("/inventory/{id}/receive", response_model=InventoryResponse, responses=_ERROR_RESPONSES, summary="Receive stock (PG-50 purchase-order receipt or manual restock)")
async def receive_stock(
    id: uuid.UUID, body: ReceiveStockRequest, request: Request, user: User = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> InventoryResponse:
    await _authorize_inventory(
        inventory_id=id, permission="inventory:write", request=request, user=user,
        inventory_service=inventory_service, authz=authz,
    )
    item, _movement = await inventory_service.receive_stock(
        inventory_id=id, quantity=body.quantity, to_location_id=body.to_location_id,
        reference_purchase_order_id=body.reference_purchase_order_id, note=body.note, actor_user_id=user.id,
        request_id=request_context(request).request_id,
    )
    return inventory_response(item)


@router.post("/inventory/{id}/transfer", response_model=InventoryResponse, responses=_ERROR_RESPONSES, summary="Transfer stock (same-branch location move or cross-branch transfer)")
async def transfer_stock(
    id: uuid.UUID, body: TransferStockRequest, request: Request, user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), inventory_service: InventoryService = Depends(get_inventory_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> InventoryResponse:
    await _authorize_inventory(
        inventory_id=id, permission="inventory:write", request=request, user=user,
        inventory_service=inventory_service, authz=authz,
    )
    if body.to_branch_id is not None:
        # Cross-branch transfer additionally needs write access to the destination branch.
        await _authorize_branch_write(
            branch_id=body.to_branch_id, permission="inventory:write", request=request, user=user, tenant=tenant, authz=authz
        )
    item, _movement = await inventory_service.transfer_stock(
        inventory_id=id, quantity=body.quantity, to_location_id=body.to_location_id, to_branch_id=body.to_branch_id,
        note=body.note, actor_user_id=user.id, request_id=request_context(request).request_id,
    )
    return inventory_response(item)


@router.post("/inventory/{id}/reserve", response_model=StockReservationResponse, responses=_ERROR_RESPONSES, summary="Reserve stock (hold without decrementing)")
async def reserve_stock(
    id: uuid.UUID, body: ReserveStockRequest, request: Request, user: User = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> StockReservationResponse:
    await _authorize_inventory(
        inventory_id=id, permission="inventory:write", request=request, user=user,
        inventory_service=inventory_service, authz=authz,
    )
    reservation = await inventory_service.reserve_stock(
        inventory_id=id, quantity=body.quantity, reference_type=body.reference_type, reference_id=body.reference_id,
        expires_at=body.expires_at, note=body.note, actor_user_id=user.id, request_id=request_context(request).request_id,
    )
    return StockReservationResponse.model_validate(reservation)


@router.post("/inventory/{id}/adjust", response_model=InventoryResponse, responses=_ERROR_RESPONSES, summary="Manual stock adjustment (stocktake/count correction/internal use/other) -- requires a reason")
async def adjust_stock(
    id: uuid.UUID, body: AdjustStockRequest, request: Request, user: User = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> InventoryResponse:
    await _authorize_inventory(
        inventory_id=id, permission="inventory:adjust", request=request, user=user,
        inventory_service=inventory_service, authz=authz,
    )
    item, _movement = await inventory_service.adjust_stock(
        inventory_id=id, quantity_delta=body.quantity_delta, reason=body.reason, note=body.note,
        actor_user_id=user.id, request_id=request_context(request).request_id,
    )
    return inventory_response(item)


@router.post("/inventory/{id}/damage", response_model=InventoryResponse, responses=_ERROR_RESPONSES, summary="Mark stock as damaged (still on hand, no longer sellable)")
async def mark_damaged(
    id: uuid.UUID, body: MarkDamagedRequest, request: Request, user: User = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> InventoryResponse:
    await _authorize_inventory(
        inventory_id=id, permission="inventory:adjust", request=request, user=user,
        inventory_service=inventory_service, authz=authz,
    )
    item, _movement = await inventory_service.mark_damaged(
        inventory_id=id, quantity=body.quantity, note=body.note, actor_user_id=user.id,
        request_id=request_context(request).request_id,
    )
    return inventory_response(item)


@router.post("/inventory/{id}/dispose", response_model=InventoryResponse, responses=_ERROR_RESPONSES, summary="Dispose stock (Waste -- permanent removal)")
async def dispose_stock(
    id: uuid.UUID, body: DisposeStockRequest, request: Request, user: User = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> InventoryResponse:
    await _authorize_inventory(
        inventory_id=id, permission="inventory:adjust", request=request, user=user,
        inventory_service=inventory_service, authz=authz,
    )
    item, _movement = await inventory_service.dispose_stock(
        inventory_id=id, quantity=body.quantity, from_damaged=body.from_damaged, plant_id=body.plant_id,
        note=body.note, actor_user_id=user.id, request_id=request_context(request).request_id,
    )
    return inventory_response(item)


@router.post("/inventory/{id}/sell", response_model=InventoryResponse, responses=_ERROR_RESPONSES, summary="Direct stock decrement for a sale (no prior reservation)")
async def sell_stock(
    id: uuid.UUID, body: SellStockRequest, request: Request, user: User = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> InventoryResponse:
    await _authorize_inventory(
        inventory_id=id, permission="inventory:write", request=request, user=user,
        inventory_service=inventory_service, authz=authz,
    )
    item, _movement = await inventory_service.sell_stock_direct(
        inventory_id=id, quantity=body.quantity, reference_sale_id=body.reference_sale_id, plant_id=body.plant_id,
        actor_user_id=user.id, request_id=request_context(request).request_id,
    )
    return inventory_response(item)


@router.post("/inventory/{id}/archive", response_model=InventoryResponse, responses=_ERROR_RESPONSES, summary="Archive an inventory line")
async def archive_inventory_line(
    id: uuid.UUID, body: ArchiveInventoryRequest, request: Request, user: User = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> InventoryResponse:
    await _authorize_inventory(
        inventory_id=id, permission="inventory:adjust", request=request, user=user,
        inventory_service=inventory_service, authz=authz,
    )
    item = await inventory_service.archive_inventory_line(
        inventory_id=id, reason=body.reason, actor_user_id=user.id, request_id=request_context(request).request_id,
    )
    return inventory_response(item)


# ==============================================================================
# Stock Reservations: release / fulfill
# ==============================================================================


@router.post("/stock-reservations/{id}/release", response_model=StockReservationResponse, responses=_ERROR_RESPONSES, summary="Release an active reservation")
async def release_reservation(
    id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> StockReservationResponse:
    await _authorize_reservation(
        reservation_id=id, permission="inventory:write", request=request, user=user,
        inventory_service=inventory_service, authz=authz,
    )
    reservation = await inventory_service.release_reservation(
        reservation_id=id, actor_user_id=user.id, request_id=request_context(request).request_id
    )
    return StockReservationResponse.model_validate(reservation)


@router.post("/stock-reservations/{id}/fulfill", response_model=StockReservationResponse, responses=_ERROR_RESPONSES, summary="Fulfill an active reservation (converts the hold into an actual departure of stock)")
async def fulfill_reservation(
    id: uuid.UUID, body: FulfillReservationRequest, request: Request, user: User = Depends(get_current_user),
    inventory_service: InventoryService = Depends(get_inventory_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> StockReservationResponse:
    await _authorize_reservation(
        reservation_id=id, permission="inventory:adjust", request=request, user=user,
        inventory_service=inventory_service, authz=authz,
    )
    reservation = await inventory_service.fulfill_reservation(
        reservation_id=id, reference_sale_id=body.reference_sale_id, plant_id=body.plant_id, actor_user_id=user.id,
        request_id=request_context(request).request_id,
    )
    return StockReservationResponse.model_validate(reservation)
