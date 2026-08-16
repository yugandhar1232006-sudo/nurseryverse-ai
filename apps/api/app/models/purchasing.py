"""
Suppliers & Purchasing bounded context.

Maps to docs/architecture/02-low-level-design.md "Module: Suppliers &
Purchasing". Receiving a PurchaseOrder is transactional with Inventory
(docs/architecture/11-sequence-diagrams.md §5) via InventoryService.apply_change().
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Enum as PgEnum
from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BranchScopedMixin, Base, TimestampMixin, UUIDPKMixin
from app.db.enums import PurchaseOrderStatus


class Supplier(UUIDPKMixin, BranchScopedMixin, TimestampMixin, Base):
    """FR-16.1."""

    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("branch_id", "name", name="uq_suppliers_branch_name"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="supplier")


class PurchaseOrder(UUIDPKMixin, BranchScopedMixin, TimestampMixin, Base):
    """FR-16.2."""

    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint("nursery_id", "po_number", name="uq_purchase_orders_nursery_number"),
        Index("ix_purchase_orders_branch_status", "branch_id", "status"),
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False
    )
    po_number: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        PgEnum(PurchaseOrderStatus, name="purchase_order_status"),
        nullable=False,
        default=PurchaseOrderStatus.DRAFT,
    )
    total_cost: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)

    supplier: Mapped["Supplier"] = relationship(back_populates="purchase_orders")
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )


class PurchaseOrderItem(UUIDPKMixin, Base):
    """FR-16.2/16.3. `received_quantity` <= `ordered_quantity`, enforced by check constraint."""

    __tablename__ = "purchase_order_items"
    __table_args__ = (
        CheckConstraint(
            "received_quantity <= ordered_quantity", name="received_not_exceeding_ordered"
        ),
        Index("ix_purchase_order_items_po_id", "purchase_order_id"),
    )

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False
    )
    inventory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory.id", ondelete="RESTRICT"), nullable=False
    )
    ordered_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    received_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_cost: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="items")
