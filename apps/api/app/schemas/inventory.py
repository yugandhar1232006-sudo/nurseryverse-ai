"""Pydantic request/response DTOs for Module 8 (Inventory & Stock Management)."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import InventoryAdjustmentReason, InventoryLocationType, StockMovementType, StockReservationStatus


# ------------------------------------------------------------------
# InventoryLocation
# ------------------------------------------------------------------


class CreateInventoryLocationRequest(BaseModel):
    branch_id: uuid.UUID
    location_type: InventoryLocationType
    name: str = Field(..., max_length=255)
    code: str | None = Field(None, max_length=50)
    parent_location_id: uuid.UUID | None = None


class InventoryLocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID
    branch_id: uuid.UUID
    parent_location_id: uuid.UUID | None
    location_type: InventoryLocationType
    name: str
    code: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UnitResponse(BaseModel):
    """
    Global, system-seeded reference data (migration 0002) -- the unit of
    measure dropdown `CreateInventoryLineRequest.unit_id` needs. See
    `GET /units`'s summary and `UnitRepository`'s docstring for why this
    exists (a real gap found while building 7I: unlike `category_id`,
    `unit_id` had no route a caller could use to discover valid ids).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    unit_type: str


# ------------------------------------------------------------------
# Inventory
# ------------------------------------------------------------------


class CreateInventoryLineRequest(BaseModel):
    branch_id: uuid.UUID
    category_id: uuid.UUID
    unit_id: uuid.UUID
    name: str = Field(..., max_length=255)
    species_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    unit_cost: float | None = Field(None, ge=0)
    unit_price: float | None = Field(None, ge=0)
    low_stock_threshold: int = Field(10, ge=0)
    initial_quantity: int = Field(0, ge=0)


class InventoryResponse(BaseModel):
    """
    "Real-Time Stock": Current/Reserved/Damaged/Disposed are real,
    persisted `Inventory` columns; `available_quantity` (= quantity -
    reserved - damaged) is derived, not stored (avoiding a fifth mutable
    column that could drift out of sync with the other four) -- computed
    once here by `inventory_response()` rather than left to every route
    to recompute individually.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID
    branch_id: uuid.UUID
    species_id: uuid.UUID | None
    category_id: uuid.UUID
    unit_id: uuid.UUID
    location_id: uuid.UUID | None
    name: str
    quantity: int
    reserved_quantity: int
    damaged_quantity: int
    disposed_quantity: int
    available_quantity: int
    unit_cost: float | None
    unit_price: float | None
    low_stock_threshold: int
    archived_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


def inventory_response(item) -> InventoryResponse:
    data = {
        "id": item.id, "nursery_id": item.nursery_id, "branch_id": item.branch_id,
        "species_id": item.species_id, "category_id": item.category_id, "unit_id": item.unit_id,
        "location_id": item.location_id, "name": item.name, "quantity": item.quantity,
        "reserved_quantity": item.reserved_quantity, "damaged_quantity": item.damaged_quantity,
        "disposed_quantity": item.disposed_quantity,
        "available_quantity": item.quantity - item.reserved_quantity - item.damaged_quantity,
        "unit_cost": item.unit_cost, "unit_price": item.unit_price,
        "low_stock_threshold": item.low_stock_threshold, "archived_at": item.archived_at,
        "version": item.version, "created_at": item.created_at, "updated_at": item.updated_at,
    }
    return InventoryResponse(**data)


class ReceiveStockRequest(BaseModel):
    quantity: int = Field(..., gt=0)
    to_location_id: uuid.UUID | None = None
    reference_purchase_order_id: uuid.UUID | None = None
    note: str | None = Field(None, max_length=1000)


class TransferStockRequest(BaseModel):
    quantity: int = Field(..., gt=0)
    to_location_id: uuid.UUID | None = None
    to_branch_id: uuid.UUID | None = None
    note: str | None = Field(None, max_length=1000)


class AdjustStockRequest(BaseModel):
    quantity_delta: int = Field(..., description="Signed -- positive adds stock, negative removes it. Cannot be zero.")
    reason: InventoryAdjustmentReason
    note: str | None = Field(None, max_length=1000)


class MarkDamagedRequest(BaseModel):
    quantity: int = Field(..., gt=0)
    note: str | None = Field(None, max_length=1000)


class DisposeStockRequest(BaseModel):
    quantity: int = Field(..., gt=0)
    from_damaged: bool = False
    plant_id: uuid.UUID | None = None
    note: str | None = Field(None, max_length=1000)


class SellStockRequest(BaseModel):
    quantity: int = Field(..., gt=0)
    reference_sale_id: uuid.UUID | None = None
    plant_id: uuid.UUID | None = None


class ArchiveInventoryRequest(BaseModel):
    reason: str | None = Field(None, max_length=500)


# ------------------------------------------------------------------
# StockMovement
# ------------------------------------------------------------------


class StockMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    inventory_id: uuid.UUID
    movement_type: StockMovementType
    quantity_delta: int
    quantity_after: int
    reason: InventoryAdjustmentReason | None
    from_location_id: uuid.UUID | None
    to_location_id: uuid.UUID | None
    plant_id: uuid.UUID | None
    reservation_id: uuid.UUID | None
    transfer_group_id: uuid.UUID | None
    reference_sale_id: uuid.UUID | None
    reference_purchase_order_id: uuid.UUID | None
    note: str | None
    performed_by_user_id: uuid.UUID | None
    created_at: datetime


# ------------------------------------------------------------------
# StockReservation
# ------------------------------------------------------------------


class ReserveStockRequest(BaseModel):
    quantity: int = Field(..., gt=0)
    reference_type: str | None = Field(None, max_length=50)
    reference_id: uuid.UUID | None = None
    expires_at: datetime | None = None
    note: str | None = Field(None, max_length=1000)


class FulfillReservationRequest(BaseModel):
    reference_sale_id: uuid.UUID | None = None
    plant_id: uuid.UUID | None = None


class StockReservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID
    branch_id: uuid.UUID
    inventory_id: uuid.UUID
    quantity: int
    status: StockReservationStatus
    reference_type: str | None
    reference_id: uuid.UUID | None
    reserved_by_user_id: uuid.UUID | None
    reserved_at: datetime
    released_at: datetime | None
    expires_at: datetime | None
    note: str | None


# ------------------------------------------------------------------
# Reporting
# ------------------------------------------------------------------


class InventorySummaryResponse(BaseModel):
    line_count: int
    total_quantity: int
    total_reserved_quantity: int
    total_damaged_quantity: int
    total_disposed_quantity: int
    total_available_quantity: int
    low_stock_count: int
    total_valuation: float


class WasteReportResponse(BaseModel):
    movement_count: int
    total_quantity_disposed: int
    movements: list[StockMovementResponse]


class TransferReportResponse(BaseModel):
    movement_count: int
    movements: list[StockMovementResponse]


class StockValuationResponse(BaseModel):
    line_count: int
    total_cost_value: float
    total_retail_value: float
    potential_margin: float
