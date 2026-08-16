"""
Commerce bounded context: Customer, Sale/SaleItem, Invoice/InvoiceItem.

Maps to docs/architecture/02-low-level-design.md "Module: Sales / POS",
"Module: Customers", "Module: Invoicing". Sale is the single writer to
sales history that Revenue Forecast trains on
(docs/ux/17-sales-workflow.md "Data Feeding Other Modules").
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Enum as PgEnum
from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BranchScopedMixin, Base, TimestampMixin, UUIDPKMixin
from app.db.enums import (
    CommunicationChannel,
    CommunicationDirection,
    CustomerAddressType,
    CustomerType,
    InvoiceStatus,
    OrderPaymentStatus,
    PaymentMethod,
    QuotationStatus,
    RefundStatus,
    ReturnItemCondition,
    ReturnStatus,
    SaleStatus,
    SalesOrderStatus,
)


class Customer(UUIDPKMixin, BranchScopedMixin, TimestampMixin, Base):
    """FR-14. Created at a Branch; visible org-wide to Owner/Admin per the LLD."""

    __tablename__ = "customers"
    __table_args__ = (Index("ix_customers_nursery_name", "nursery_id", "name"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    customer_type: Mapped[CustomerType] = mapped_column(
        PgEnum(CustomerType, name="customer_type"), nullable=False, default=CustomerType.RETAIL
    )

    sales: Mapped[list["Sale"]] = relationship(back_populates="customer")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="customer")


class Sale(UUIDPKMixin, BranchScopedMixin, Base):
    """
    FR-13. `status` transitions completed -> voided only (no PATCH beyond
    that single edge, per docs/ux/17-sales-workflow.md "Void & Correction
    Path" — a sale is never edited in place).
    """

    __tablename__ = "sales"
    __table_args__ = (
        Index("ix_sales_branch_created_at", "branch_id", "created_at"),
        CheckConstraint("total_amount >= 0", name="total_amount_non_negative"),
        UniqueConstraint("branch_id", "idempotency_key", name="uq_sales_branch_idempotency_key"),
    )

    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[SaleStatus] = mapped_column(
        PgEnum(SaleStatus, name="sale_status"), nullable=False, default=SaleStatus.COMPLETED
    )
    subtotal_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    discount_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    total_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Added by Phase 6 Module 9 -- migration 0013. Phase 5's original Sale
    # had subtotal/discount/total but no tax line -- Module 9 is the first
    # to need Tax Calculation as a first-class, reportable amount rather
    # than folded silently into total_amount.
    tax_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    sold_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)

    customer: Mapped["Customer"] = relationship(back_populates="sales")
    items: Mapped[list["SaleItem"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan"
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        secondary="invoice_sales", back_populates="sales"
    )


class SaleItem(UUIDPKMixin, Base):
    """
    FR-13.1. Exactly one of plant_id / inventory_id is set — enforced by
    a check constraint (a sale line item sells either an individually
    tracked plant or a bulk inventory quantity, never both).
    """

    __tablename__ = "sale_items"
    __table_args__ = (
        CheckConstraint(
            "(plant_id IS NOT NULL AND inventory_id IS NULL) OR "
            "(plant_id IS NULL AND inventory_id IS NOT NULL)",
            name="exactly_one_of_plant_or_inventory",
        ),
        Index("ix_sale_items_sale_id", "sale_id"),
    )

    sale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales.id", ondelete="CASCADE"), nullable=False
    )
    plant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plants.id", ondelete="RESTRICT"), nullable=True
    )
    inventory_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory.id", ondelete="RESTRICT"), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    line_total: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)

    sale: Mapped["Sale"] = relationship(back_populates="items")


class Invoice(UUIDPKMixin, BranchScopedMixin, TimestampMixin, Base):
    """FR-15. Generated from one or more Sales (many-to-many via invoice_sales)."""

    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("nursery_id", "invoice_number", name="uq_invoices_nursery_number"),
        Index("ix_invoices_branch_status", "branch_id", "status"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        PgEnum(InvoiceStatus, name="invoice_status"), nullable=False, default=InvoiceStatus.DRAFT
    )
    terms: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g. net_30, net_60
    po_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    # Added by Phase 6 Module 9 -- migration 0013. Frozen snapshot totals
    # (like Passport.content_snapshot) captured at generation time from the
    # constituent Sales, so an Invoice document is self-contained and never
    # needs to re-derive its own subtotal/tax breakdown from `invoice_sales`.
    subtotal_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    discount_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    tax_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    due_date: Mapped[datetime | None] = mapped_column(nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    customer: Mapped["Customer"] = relationship(back_populates="invoices")
    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )
    sales: Mapped[list["Sale"]] = relationship(secondary="invoice_sales", back_populates="invoices")


class InvoiceSale(Base):
    """Join table: Invoice <-> Sale (many-to-many, FR-15.1)."""

    __tablename__ = "invoice_sales"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), primary_key=True
    )
    sale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales.id", ondelete="RESTRICT"), primary_key=True
    )


class InvoiceItem(UUIDPKMixin, Base):
    """Line items as they appear on the invoice document (may summarize multiple sale_items)."""

    __tablename__ = "invoice_items"
    __table_args__ = (Index("ix_invoice_items_invoice_id", "invoice_id"),)

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    line_total: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)

    invoice: Mapped["Invoice"] = relationship(back_populates="items")


class Payment(UUIDPKMixin, Base):
    """
    Itemized payment(s) against an Invoice — added at the Phase 5
    master-table review to support partial payments against wholesale
    invoices (a single net-30 invoice may be paid in installments), which
    a single `invoices.paid_at` timestamp cannot represent on its own.
    `invoices.status` still transitions to `paid` only once the sum of
    Payments meets total_amount — enforced by InvoiceLifecycleService, not
    a database trigger (business-rule timing, e.g. "is a slightly
    short/over payment close enough to reconcile," belongs in the service
    layer, not baked into a trigger).
    """

    __tablename__ = "payments"
    __table_args__ = (Index("ix_payments_invoice_id", "invoice_id"),)

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(50), nullable=False)  # cash, card, ach, check
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    received_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)

    invoice: Mapped["Invoice"] = relationship(back_populates="payments")


# =============================================================================
# Phase 6 Module 9 (Sales, CRM, Plant Passport & QR Intelligence) — migration
# 0013. Everything below is new. `Customer`/`Sale`/`SaleItem`/`Invoice`/
# `InvoiceItem`/`InvoiceSale`/`Payment` above are the pre-existing Phase 5
# schema (migration 0001) that this module's services/routes are the first
# to actually operationalize. `Sale` remains the single, immutable
# "completed transaction" ledger row Revenue Forecast trains on (its own
# docstring, above) — `SalesOrder` below is a *pre*-completion lifecycle
# wrapper (quotation -> confirmed -> processing -> fulfilled) that creates
# exactly one `Sale` row (and, for wholesale terms, one `Invoice`) when it
# is fulfilled, rather than replacing or duplicating either table.
#
# Stock holds for a Sales Order reuse Module 8's `StockReservation` as-is
# (its `reference_type`/`reference_id` loose pointer was deliberately built
# for this — see app/models/inventory.py's own docstring: "nothing in this
# module or before it defines those tables yet, so this is deliberately not
# a foreign key"). `OrderItem.reservation_id` below is a real FK *to* that
# existing table, not a new reservation concept.
# =============================================================================


class CustomerContact(UUIDPKMixin, TimestampMixin, Base):
    """
    A named point of contact at a Customer account (e.g. a wholesale
    buyer's procurement lead). No nursery_id/branch_id of its own —
    always reached through its parent Customer, same shape as
    `app/models/plants.py`'s `PlantImage` (child/history tables scoped by
    a join-based RLS policy through their parent, migration 0003's
    established pattern).
    """

    __tablename__ = "customer_contacts"
    __table_args__ = (Index("ix_customer_contacts_customer_id", "customer_id"),)

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_primary: Mapped[bool] = mapped_column(nullable=False, default=False)

    customer: Mapped["Customer"] = relationship()


class CustomerAddress(UUIDPKMixin, TimestampMixin, Base):
    """Billing/shipping addresses. Join-scoped through Customer, same as CustomerContact."""

    __tablename__ = "customer_addresses"
    __table_args__ = (Index("ix_customer_addresses_customer_id", "customer_id"),)

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    address_type: Mapped[CustomerAddressType] = mapped_column(
        PgEnum(CustomerAddressType, name="customer_address_type"),
        nullable=False,
        default=CustomerAddressType.OTHER,
    )
    line1: Mapped[str] = mapped_column(String(255), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_default: Mapped[bool] = mapped_column(nullable=False, default=False)

    customer: Mapped["Customer"] = relationship()


class CustomerTag(UUIDPKMixin, Base):
    """
    Free-form label attached to a Customer (e.g. "VIP", "wholesale",
    "landscaper"). Deliberately a plain string, not a separate tag-catalog
    table with its own management UI — the module's spec asks for
    "Customer Tags" as a CRM attribute, not a taxonomy-governance feature;
    a per-customer label row is the simplest thing that satisfies it
    without inventing scope. No created_at — a tag either exists or
    doesn't, there's no lifecycle to timestamp.
    """

    __tablename__ = "customer_tags"
    __table_args__ = (
        UniqueConstraint("customer_id", "tag", name="uq_customer_tags_customer_tag"),
        Index("ix_customer_tags_customer_id", "customer_id"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    tag: Mapped[str] = mapped_column(String(50), nullable=False)

    customer: Mapped["Customer"] = relationship()


class CustomerNote(UUIDPKMixin, Base):
    """Free-text staff note against a Customer. Mutable (edit/delete), unlike an audit log."""

    __tablename__ = "customer_notes"
    __table_args__ = (Index("ix_customer_notes_customer_id_created_at", "customer_id", "created_at"),)

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    note: Mapped[str] = mapped_column(Text, nullable=False)
    pinned: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)

    customer: Mapped["Customer"] = relationship()


class CustomerCommunication(UUIDPKMixin, Base):
    """
    A logged interaction with a Customer (a call, an email thread, an
    in-person conversation) — the module's "Communication History" CRM
    item. This is a manual log entry made by staff, not an integration
    with an email/SMS provider (that integration, if ever built, is a
    Module 12 Notifications concern; this table only records that a
    communication happened and its substance).
    """

    __tablename__ = "customer_communications"
    __table_args__ = (
        Index("ix_customer_communications_customer_id_occurred_at", "customer_id", "occurred_at"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[CommunicationChannel] = mapped_column(
        PgEnum(CommunicationChannel, name="communication_channel"), nullable=False
    )
    direction: Mapped[CommunicationDirection] = mapped_column(
        PgEnum(CommunicationDirection, name="communication_direction"),
        nullable=False,
        default=CommunicationDirection.OUTBOUND,
    )
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    logged_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)

    customer: Mapped["Customer"] = relationship()


class Quotation(UUIDPKMixin, BranchScopedMixin, TimestampMixin, Base):
    """
    A non-binding, pre-sale price quote. DRAFT/SENT are editable;
    ACCEPTED/REJECTED/EXPIRED are terminal; CONVERTED means a SalesOrder
    was created from it. No back-reference column here (a Quotation
    doesn't know its own converted order) — `SalesOrder.quotation_id`
    points the other way, avoiding a circular FK between the two tables
    that create-order would otherwise require populating in two steps.
    """

    __tablename__ = "quotations"
    __table_args__ = (Index("ix_quotations_branch_status", "branch_id", "status"),)

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[QuotationStatus] = mapped_column(
        PgEnum(QuotationStatus, name="quotation_status"), nullable=False, default=QuotationStatus.DRAFT
    )
    subtotal_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    discount_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    tax_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    total_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    valid_until: Mapped[datetime | None] = mapped_column(nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    customer: Mapped["Customer"] = relationship()
    items: Mapped[list["QuotationItem"]] = relationship(cascade="all, delete-orphan")


class QuotationItem(UUIDPKMixin, Base):
    """
    A quoted line item. At most one of plant_id/inventory_id may be set
    (unlike SaleItem's *exactly* one — a quotation may legitimately quote
    a described item ("6-inch Ficus, any available") with neither yet
    allocated to a specific plant or inventory line).
    """

    __tablename__ = "quotation_items"
    __table_args__ = (
        CheckConstraint(
            "NOT (plant_id IS NOT NULL AND inventory_id IS NOT NULL)",
            name="not_both_plant_and_inventory",
        ),
        Index("ix_quotation_items_quotation_id", "quotation_id"),
    )

    quotation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False
    )
    plant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plants.id", ondelete="SET NULL"), nullable=True
    )
    inventory_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    discount_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    line_total: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)


class SalesOrder(UUIDPKMixin, BranchScopedMixin, TimestampMixin, Base):
    """
    The order-lifecycle wrapper (Quotation ->) DRAFT -> CONFIRMED ->
    PROCESSING -> FULFILLED, or -> CANCELLED from any non-terminal state.
    Checkout (`SalesService.checkout`) transitions a CONFIRMED/PROCESSING
    order to FULFILLED by creating exactly one `Sale` row (`sale_id`
    below) — the pre-existing, immutable completed-transaction ledger —
    and, for orders that need one, one `Invoice` (`invoice_id`). Stock is
    held via Module 8's `StockReservation` (`OrderItem.reservation_id`),
    not duplicated here.
    """

    __tablename__ = "sales_orders"
    __table_args__ = (
        Index("ix_sales_orders_branch_order_status", "branch_id", "order_status"),
        UniqueConstraint("branch_id", "idempotency_key", name="uq_sales_orders_branch_idempotency_key"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    quotation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quotations.id", ondelete="SET NULL"), nullable=True
    )
    order_status: Mapped[SalesOrderStatus] = mapped_column(
        PgEnum(SalesOrderStatus, name="sales_order_status"),
        nullable=False,
        default=SalesOrderStatus.DRAFT,
    )
    payment_status: Mapped[OrderPaymentStatus] = mapped_column(
        PgEnum(OrderPaymentStatus, name="order_payment_status"),
        nullable=False,
        default=OrderPaymentStatus.UNPAID,
    )
    subtotal_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    discount_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    tax_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    total_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    sale_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales.id", ondelete="SET NULL"), nullable=True
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    fulfilled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    customer: Mapped["Customer"] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(cascade="all, delete-orphan")


class OrderItem(UUIDPKMixin, Base):
    """
    Exactly one of plant_id/inventory_id, same invariant as SaleItem (by
    the time an order is confirmed, its lines are allocated to real
    stock, unlike a Quotation's looser "at most one"). `reservation_id`
    points at the Module 8 `StockReservation` holding this line's stock,
    if one was taken (reservations are optional — an immediate walk-up
    checkout may skip straight to a Sale without ever holding stock via a
    SalesOrder/Reservation first).
    """

    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint(
            "(plant_id IS NOT NULL AND inventory_id IS NULL) OR "
            "(plant_id IS NULL AND inventory_id IS NOT NULL)",
            name="exactly_one_of_plant_or_inventory",
        ),
        Index("ix_order_items_sales_order_id", "sales_order_id"),
    )

    sales_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=False
    )
    plant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plants.id", ondelete="RESTRICT"), nullable=True
    )
    inventory_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory.id", ondelete="RESTRICT"), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    discount_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    tax_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    line_total: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stock_reservations.id", ondelete="SET NULL"), nullable=True
    )


class Return(UUIDPKMixin, BranchScopedMixin, TimestampMixin, Base):
    """A customer return against a completed Sale. REQUESTED -> APPROVED|REJECTED -> COMPLETED."""

    __tablename__ = "returns"
    __table_args__ = (Index("ix_returns_branch_status", "branch_id", "status"),)

    sale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales.id", ondelete="RESTRICT"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[ReturnStatus] = mapped_column(
        PgEnum(ReturnStatus, name="return_status"), nullable=False, default=ReturnStatus.REQUESTED
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    processed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    sale: Mapped["Sale"] = relationship()
    customer: Mapped["Customer"] = relationship()
    items: Mapped[list["ReturnItem"]] = relationship(cascade="all, delete-orphan")


class ReturnItem(UUIDPKMixin, Base):
    """One returned line, referencing the original SaleItem it corresponds to."""

    __tablename__ = "return_items"
    __table_args__ = (Index("ix_return_items_return_id", "return_id"),)

    return_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("returns.id", ondelete="CASCADE"), nullable=False
    )
    sale_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sale_items.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    restock: Mapped[bool] = mapped_column(nullable=False, default=True)
    condition: Mapped[ReturnItemCondition] = mapped_column(
        PgEnum(ReturnItemCondition, name="return_item_condition"),
        nullable=False,
        default=ReturnItemCondition.RESALABLE,
    )
    line_refund_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)


class Refund(UUIDPKMixin, BranchScopedMixin, Base):
    """
    A monetary refund, optionally tied to a Return (goods-back refund) or
    issued standalone against an Invoice/Sale (e.g. a goodwill credit).
    Exactly one of return_id/invoice_id/sale_id should generally be set in
    practice; not enforced as a database constraint (any 0-3 of the three
    is a legitimately reconcilable combination — e.g. a Return whose
    refund is issued against the original Invoice sets both), matching
    this codebase's preference for a check constraint only when the
    invariant is unconditionally true, not "usually true."
    """

    __tablename__ = "refunds"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_refunds_branch_status", "branch_id", "status"),
    )

    return_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("returns.id", ondelete="SET NULL"), nullable=True
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True
    )
    sale_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales.id", ondelete="SET NULL"), nullable=True
    )
    amount: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(
        PgEnum(PaymentMethod, name="payment_method"), nullable=False
    )
    status: Mapped[RefundStatus] = mapped_column(
        PgEnum(RefundStatus, name="refund_status"), nullable=False, default=RefundStatus.PENDING
    )
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    processed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)
