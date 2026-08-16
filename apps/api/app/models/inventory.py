"""
Inventory bounded context (Phase 5 skeleton; full write-path built out in
Phase 6 Module 8). Bulk stock, deliberately separate from the
individually-tracked Plant entity (docs/ux/16-inventory-workflow.md
"Relationship to the Digital Twin") -- this bounded context never reads or
writes a `plants` row for its own quantity bookkeeping.

Maps to docs/architecture/02-low-level-design.md "Module: Inventory".
Every quantity change flows through InventoryService's internal
`_apply_change()` (single write-path pattern, matching the LLD's
`InventoryService.apply_change()` invariant) and is always paired with
exactly one immutable StockMovement row for the audit trail
(docs/architecture/05-database-architecture.md §6, Transactions).

Module 8 schema evolution over the Phase 5 skeleton (same "first module to
build on this table" pattern Module 5 applied to species/categories and
Module 6 applied to plants):
  - `Inventory` gains `location_id` (where the stock currently sits),
    `reserved_quantity`/`damaged_quantity`/`disposed_quantity` (the
    "Real-Time Stock" model the spec names), `archived_at`, and `version`
    (optimistic-concurrency column -- see InventoryService docstring for
    why optimistic, not row-locking, is this module's concurrency
    strategy).
  - `InventoryAdjustment` (adjustment-only, no location/type richness) is
    renamed to `StockMovement` and generalized into the one ledger table
    that records all ten movement types the spec requires (Incoming,
    Outgoing, Transfer, Adjustment, Waste, Damage, Reservation, Release,
    Sale, Archive) -- one immutable table modeling every kind of
    movement, not ten separate ones. `adjusted_by_user_id` is renamed to
    `performed_by_user_id` to match (nothing outside this module
    referenced the old name yet; Module 8 is the first module to build a
    service layer on this table).
  - New `InventoryLocation` (sub-branch physical hierarchy) and
    `StockReservation` (hold-without-decrementing workflow) tables.

Digital Twin linkage (docs/architecture/23-module7-digital-twin-engine.md's
"Inventory Timeline" section, corrected by this module): `StockMovement.
plant_id` is nullable and populated ONLY in the narrow, already-documented
case where a movement concerns a specific individually-tracked plant (e.g.
"Plant demoted from individual tracking" per docs/ux/16-inventory-workflow.md's
own flowchart). When set, InventoryService publishes one additional
`plant.inventory_movement_recorded` domain event (aggregate_type="Plant")
that the existing Module 7 dispatcher already knows how to route to the
Digital Twin projector -- this is the ONLY coupling point between the two
bounded contexts, and it is a domain event, never a direct write. The vast
majority of stock movements (ordinary bulk SKU receiving/transfer/
adjustment) leave `plant_id` NULL and never touch the Digital Twin at all.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Enum as PgEnum
from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BranchScopedMixin, Base, TimestampMixin, UUIDPKMixin
from app.db.enums import (
    InventoryAdjustmentReason,
    InventoryLocationType,
    StockMovementType,
    StockReservationStatus,
)


class InventoryLocation(UUIDPKMixin, BranchScopedMixin, TimestampMixin, Base):
    """
    Module 8 "Location Management". Sub-branch physical hierarchy: Zone,
    Greenhouse, Outdoor Area, Rack, Bench, Section. Nursery/Branch are
    NOT represented as InventoryLocation rows -- they're the existing
    Nursery/Branch tables; every InventoryLocation nests under exactly
    one branch_id and, optionally, one parent_location_id for finer
    subdivision (e.g. Bench "B3" inside Greenhouse "GH2").
    """

    __tablename__ = "inventory_locations"
    __table_args__ = (
        Index("ix_inventory_locations_nursery_branch", "nursery_id", "branch_id"),
        Index("ix_inventory_locations_parent", "parent_location_id"),
    )

    parent_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_locations.id", ondelete="SET NULL"), nullable=True
    )
    location_type: Mapped[InventoryLocationType] = mapped_column(
        PgEnum(InventoryLocationType, name="inventory_location_type"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    stock_lines: Mapped[list["Inventory"]] = relationship(back_populates="location")


class Inventory(UUIDPKMixin, BranchScopedMixin, TimestampMixin, Base):
    """FR-12. Bulk stock line — one row per (branch, product/species) pair."""

    __tablename__ = "inventory"
    __table_args__ = (
        UniqueConstraint("branch_id", "name", name="uq_inventory_branch_name"),
        CheckConstraint("quantity >= 0", name="quantity_non_negative"),
        CheckConstraint("reserved_quantity >= 0", name="reserved_quantity_non_negative"),
        CheckConstraint("damaged_quantity >= 0", name="damaged_quantity_non_negative"),
        CheckConstraint("disposed_quantity >= 0", name="disposed_quantity_non_negative"),
        CheckConstraint(
            "reserved_quantity + damaged_quantity <= quantity", name="reserved_damaged_le_quantity"
        ),
        Index("ix_inventory_nursery_branch", "nursery_id", "branch_id"),
        Index("ix_inventory_location_id", "location_id"),
    )

    species_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("species.id", ondelete="SET NULL"), nullable=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plant_categories.id", ondelete="RESTRICT"), nullable=False
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_locations.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    damaged_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    disposed_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_cost: Mapped[Numeric | None] = mapped_column(Numeric(10, 2), nullable=True)
    unit_price: Mapped[Numeric | None] = mapped_column(Numeric(10, 2), nullable=True)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    archived_at: Mapped[datetime | None] = mapped_column(nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    location: Mapped["InventoryLocation | None"] = relationship(back_populates="stock_lines")
    movements: Mapped[list["StockMovement"]] = relationship(
        back_populates="inventory", cascade="all, delete-orphan"
    )
    reservations: Mapped[list["StockReservation"]] = relationship(
        back_populates="inventory", cascade="all, delete-orphan"
    )


class StockMovement(UUIDPKMixin, Base):
    """
    Append-only, immutable (DB-level REVOKE UPDATE/DELETE + trigger,
    migration 0012). Every Incoming/Outgoing/Transfer/Adjustment/Waste/
    Damage/Reservation/Release/Sale/Archive change to an Inventory line
    produces exactly one of these rows -- the single ledger this module's
    Movement History, Waste Report, Transfer Report, and Reservation
    Report are all derived from.
    """

    __tablename__ = "stock_movements"
    __table_args__ = (
        Index("ix_stock_movements_inventory_created", "inventory_id", "created_at"),
        Index("ix_stock_movements_movement_type", "movement_type"),
        Index("ix_stock_movements_plant_id", "plant_id"),
        Index("ix_stock_movements_transfer_group", "transfer_group_id"),
    )

    inventory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory.id", ondelete="CASCADE"), nullable=False
    )
    movement_type: Mapped[StockMovementType] = mapped_column(
        PgEnum(StockMovementType, name="stock_movement_type"), nullable=False
    )
    quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False)  # signed; 0 for RESERVATION/RELEASE/DAMAGE-mark
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[InventoryAdjustmentReason | None] = mapped_column(
        PgEnum(InventoryAdjustmentReason, name="inventory_adjustment_reason"), nullable=True
    )
    from_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_locations.id", ondelete="SET NULL"), nullable=True
    )
    to_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_locations.id", ondelete="SET NULL"), nullable=True
    )
    plant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plants.id", ondelete="SET NULL"), nullable=True
    )
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stock_reservations.id", ondelete="SET NULL"), nullable=True
    )
    transfer_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reference_sale_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales.id", ondelete="SET NULL"), nullable=True
    )
    reference_purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    performed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)

    inventory: Mapped["Inventory"] = relationship(back_populates="movements")


class StockReservation(UUIDPKMixin, BranchScopedMixin, Base):
    """
    Module 8 "Reservations". A hold against `Inventory.quantity` that
    earmarks stock without physically decrementing it -- ACTIVE reduces
    `available_quantity` (quantity - reserved - damaged); RELEASED gives
    it back; FULFILLED converts the hold into an actual SALE movement
    (decrements `quantity` for real). `reference_type`/`reference_id` are
    a loose, non-FK pointer (e.g. a future Sales-module cart/order id) so
    this module never hard-depends on Module 9's schema.
    """

    __tablename__ = "stock_reservations"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        Index("ix_stock_reservations_inventory_status", "inventory_id", "status"),
    )

    inventory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[StockReservationStatus] = mapped_column(
        PgEnum(StockReservationStatus, name="stock_reservation_status"),
        nullable=False,
        default=StockReservationStatus.ACTIVE,
    )
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reserved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reserved_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    inventory: Mapped["Inventory"] = relationship(back_populates="reservations")
