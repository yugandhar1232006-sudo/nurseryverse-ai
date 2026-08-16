"""
Phase 6 Module 9 (Sales, CRM, Plant Passport & QR Intelligence) — Sales:
Quotations, Sales Orders, Order Items, Reservations, Checkout, Invoice
Generation, Tax Calculation, Discounts, Order/Payment Status, Returns,
Refunds, and Sales/Revenue reporting.

ARCHITECTURE. Sales is its own bounded context (the module's own
instruction). Concretely:

  - Sales never reads or writes `plants`/`growth_timeline`/etc. It calls
    `InventoryService` directly (`reserve_stock`, `fulfill_reservation`,
    `sell_stock_direct`, `adjust_stock`) for bulk-stock line items --
    this is NOT the forbidden coupling: `StockReservation.reference_type`/
    `reference_id` (Module 8) was deliberately built as a loose, non-FK
    pointer for exactly this caller ("nothing in this module or before it
    defines those tables yet, so this is deliberately not a foreign key"
    -- app/models/inventory.py). A real, direct service call for an
    in-request, transactional operation (take a stock hold as part of
    confirming an order) is a different thing from what the ARCHITECTURE
    PRINCIPLES section actually forbids: Sales does NOT call `PlantService`
    anywhere in this file, and does not flip `Plant.status` to SOLD --
    see `PlantSold`'s docstring in app/domain_events/events.py for the
    full reasoning on that specific, deliberate omission.
  - `Sale`/`SaleItem`/`Invoice`/`InvoiceItem`/`InvoiceSale`/`Payment` are
    the pre-existing Phase 5 tables (migration 0001); `SalesOrder` is this
    module's own pre-completion lifecycle wrapper around them -- see
    app/models/commerce.py's Module 9 docstring block for the full
    reasoning.
  - Tax Calculation: a `tax_rate` (0.0-1.0) is supplied by the caller per
    Quotation/Order (there is no persisted org-wide tax-rate setting in
    this schema to read from -- adding one was judged out of this
    module's scope), applied uniformly to (subtotal - discounts). This is
    a deliberate simplification over full line-item/jurisdiction-specific
    tax rules, which no part of this module's spec asks for.
  - Invoice numbering (`_next_invoice_number`) is a simple
    count-based-per-nursery scheme (`INV-<year>-<sequence>`), not a
    dedicated database sequence -- correct in the single-writer test/dev
    path this module is verified against, but not race-safe under two
    truly concurrent checkouts for the same nursery (a real deployment
    would want a `SEQUENCE`/advisory lock); disclosed here rather than
    silently assumed safe, the same disclosure style every prior module
    has used for its own known tradeoffs.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.enums import (
    InventoryAdjustmentReason,
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
from app.domain_events import (
    DomainEventPublisher,
    InvoiceGenerated,
    OrderCreated,
    OrderStatusChanged,
    PaymentReceived,
    PlantReturned,
    PlantSold,
    QuotationCreated,
    QuotationStatusChanged,
    RefundProcessed,
    ReservationCreated,
    ReservationReleased,
)
from app.models.commerce import (
    Invoice,
    InvoiceItem,
    OrderItem,
    Payment,
    Quotation,
    QuotationItem,
    Refund,
    Return,
    ReturnItem,
    Sale,
    SaleItem,
    SalesOrder,
)
from app.models.platform import AuditLog
from app.repositories.interfaces import (
    AuditLogRepository,
    InvoiceItemRepository,
    InvoiceRepository,
    InvoiceSaleRepository,
    OrderItemRepository,
    PaymentRepository,
    PlantRepository,
    QuotationItemRepository,
    QuotationRepository,
    RefundRepository,
    ReturnItemRepository,
    ReturnRepository,
    SaleItemRepository,
    SaleRepository,
    SalesOrderRepository,
)
from app.services.inventory_service import InventoryService
from app.services.passport_service import PassportService

TWO_PLACES = Decimal("0.01")


def _money(value: object) -> Decimal:
    """
    Always quantizes to 2 places, even when `value` is already a
    `Decimal` -- an earlier version of this function returned an
    already-`Decimal` input unchanged, which looked safe but wasn't:
    arithmetic between two already-quantized Decimals can still produce
    more than 2 decimal places (`Decimal("50.00") * Decimal("0.1")` ==
    `Decimal("5.000")`, 3 places), so `_compute_totals`'s own
    `taxable * Decimal(str(tax_rate))` line was silently leaking a
    3-decimal-place `tax`/`total` into persisted rows and API responses
    (caught by tests/integration/test_sales_routes.py's
    `test_full_sales_workflow` asserting `total_amount == "55.00"` and
    getting back `"55.000"`). Quantizing unconditionally is the fix.
    """
    d = value if isinstance(value, Decimal) else Decimal(str(value))
    return d.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _as_float(value: object) -> float:
    """See app/services/inventory_service.py's identical helper — same pre-existing `Mapped[Numeric | None]` typing imprecision, same fix. Used by the reporting methods below, which aggregate across many rows and want plain floats rather than Decimals."""
    return float(value or 0)  # type: ignore[arg-type]


@dataclass
class LineItemInput:
    quantity: int
    unit_price: Decimal
    plant_id: uuid.UUID | None = None
    inventory_id: uuid.UUID | None = None
    description: str | None = None
    discount_amount: Decimal = field(default_factory=lambda: Decimal("0"))

    def __post_init__(self) -> None:
        if bool(self.plant_id) and bool(self.inventory_id):
            raise ValidationError("A line item may reference at most one of plant_id/inventory_id.")
        if self.quantity <= 0:
            raise ValidationError("Line item quantity must be positive.")
        self.unit_price = _money(self.unit_price)
        self.discount_amount = _money(self.discount_amount)

    @property
    def line_total(self) -> Decimal:
        return _money(Decimal(self.quantity) * self.unit_price - self.discount_amount)


@dataclass
class OrderTotals:
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal


def _compute_totals(items: list[LineItemInput], *, header_discount: Decimal, tax_rate: float) -> OrderTotals:
    subtotal = _money(sum((Decimal(i.quantity) * i.unit_price for i in items), Decimal("0")))
    line_discounts = _money(sum((i.discount_amount for i in items), Decimal("0")))
    discount = _money(line_discounts + header_discount)
    taxable = max(subtotal - discount, Decimal("0"))
    tax = _money(taxable * Decimal(str(tax_rate)))
    total = _money(taxable + tax)
    return OrderTotals(subtotal=subtotal, discount=discount, tax=tax, total=total)


class QuotationService:
    def __init__(
        self,
        *,
        quotation_repo: QuotationRepository,
        quotation_item_repo: QuotationItemRepository,
        audit_repo: AuditLogRepository,
        event_publisher: DomainEventPublisher,
    ) -> None:
        self._quotations = quotation_repo
        self._items = quotation_item_repo
        self._audit = audit_repo
        self._events = event_publisher

    async def create_quotation(
        self,
        *,
        nursery_id: uuid.UUID,
        branch_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        customer_id: uuid.UUID,
        items: list[LineItemInput],
        tax_rate: float = 0.0,
        header_discount: Decimal = Decimal("0"),
        valid_until: datetime | None = None,
        note: str | None = None,
        request_id: str | None = None,
    ) -> Quotation:
        if not items:
            raise ValidationError("A quotation requires at least one line item.")
        totals = _compute_totals(items, header_discount=header_discount, tax_rate=tax_rate)
        quotation = Quotation(
            nursery_id=nursery_id,
            branch_id=branch_id,
            customer_id=customer_id,
            status=QuotationStatus.DRAFT,
            subtotal_amount=totals.subtotal,
            discount_amount=totals.discount,
            tax_amount=totals.tax,
            total_amount=totals.total,
            valid_until=valid_until,
            note=note,
            created_by_user_id=actor_user_id,
        )
        await self._quotations.add(quotation)
        for item in items:
            await self._items.add(
                QuotationItem(
                    quotation_id=quotation.id,
                    plant_id=item.plant_id,
                    inventory_id=item.inventory_id,
                    description=item.description,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    discount_amount=item.discount_amount,
                    line_total=item.line_total,
                )
            )
        await self._log_audit(
            nursery_id, actor_user_id, "quotation.created", quotation.id,
            {"total_amount": str(totals.total)}, request_id,
        )
        await self._events.publish(
            QuotationCreated(
                aggregate_id=quotation.id, nursery_id=nursery_id, actor_user_id=actor_user_id,
                branch_id=branch_id, customer_id=customer_id, total_amount=str(totals.total),
            ),
            request_id=request_id,
        )
        return quotation

    async def get_quotation(self, quotation_id: uuid.UUID) -> Quotation:
        quotation = await self._quotations.get_by_id(quotation_id)
        if quotation is None:
            raise NotFoundError("Quotation not found.")
        return quotation

    async def list_items(self, quotation_id: uuid.UUID) -> list[QuotationItem]:
        return await self._items.list_for_quotation(quotation_id)

    async def list_quotations(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int, **filters: Any
    ) -> tuple[list[Quotation], int]:
        return await self._quotations.list_for_nursery(nursery_id, offset=offset, limit=limit, **filters)

    _VALID_TRANSITIONS: dict[QuotationStatus, set[QuotationStatus]] = {
        QuotationStatus.DRAFT: {QuotationStatus.SENT, QuotationStatus.REJECTED, QuotationStatus.EXPIRED},
        QuotationStatus.SENT: {
            QuotationStatus.ACCEPTED, QuotationStatus.REJECTED, QuotationStatus.EXPIRED, QuotationStatus.DRAFT,
        },
    }

    async def change_status(
        self, quotation: Quotation, *, to_status: QuotationStatus, actor_user_id: uuid.UUID, request_id: str | None = None
    ) -> Quotation:
        allowed = self._VALID_TRANSITIONS.get(quotation.status, set())
        if to_status not in allowed:
            raise ConflictError(
                f"Cannot transition quotation from {quotation.status.value} to {to_status.value}.",
                context={"reason": "invalid_status_transition"},
            )
        from_status = quotation.status
        quotation.status = to_status
        await self._quotations.update(quotation)
        await self._events.publish(
            QuotationStatusChanged(
                aggregate_id=quotation.id, nursery_id=quotation.nursery_id, actor_user_id=actor_user_id,
                from_status=from_status.value, to_status=to_status.value,
            ),
            request_id=request_id,
        )
        return quotation

    async def mark_converted(self, quotation: Quotation, *, actor_user_id: uuid.UUID, request_id: str | None = None) -> Quotation:
        if quotation.status != QuotationStatus.ACCEPTED:
            raise ConflictError(
                "Only an ACCEPTED quotation may be converted to a Sales Order.",
                context={"reason": "invalid_status_transition"},
            )
        quotation.status = QuotationStatus.CONVERTED
        await self._quotations.update(quotation)
        await self._events.publish(
            QuotationStatusChanged(
                aggregate_id=quotation.id, nursery_id=quotation.nursery_id, actor_user_id=actor_user_id,
                from_status=QuotationStatus.ACCEPTED.value, to_status=QuotationStatus.CONVERTED.value,
            ),
            request_id=request_id,
        )
        return quotation

    async def _log_audit(self, nursery_id, actor_user_id, action, entity_id, diff, request_id) -> None:
        await self._audit.log(
            AuditLog(
                nursery_id=nursery_id, actor_user_id=actor_user_id, action=action, entity_type="Quotation",
                entity_id=entity_id, diff=diff, request_id=request_id, created_at=datetime.now(timezone.utc),
            )
        )


class SalesOrderService:
    def __init__(
        self,
        *,
        order_repo: SalesOrderRepository,
        order_item_repo: OrderItemRepository,
        sale_repo: SaleRepository,
        sale_item_repo: SaleItemRepository,
        invoice_repo: InvoiceRepository,
        invoice_item_repo: InvoiceItemRepository,
        invoice_sale_repo: InvoiceSaleRepository,
        inventory_service: InventoryService,
        passport_service: PassportService,
        plant_repo: PlantRepository,
        audit_repo: AuditLogRepository,
        event_publisher: DomainEventPublisher,
    ) -> None:
        self._orders = order_repo
        self._order_items = order_item_repo
        self._sales = sale_repo
        self._sale_items = sale_item_repo
        self._invoices = invoice_repo
        self._invoice_items = invoice_item_repo
        self._invoice_sales = invoice_sale_repo
        self._inventory = inventory_service
        self._passports = passport_service
        self._plants = plant_repo
        self._audit = audit_repo
        self._events = event_publisher

    async def create_order(
        self,
        *,
        nursery_id: uuid.UUID,
        branch_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        customer_id: uuid.UUID,
        items: list[LineItemInput],
        tax_rate: float = 0.0,
        header_discount: Decimal = Decimal("0"),
        quotation_id: uuid.UUID | None = None,
        idempotency_key: str | None = None,
        request_id: str | None = None,
    ) -> SalesOrder:
        if idempotency_key:
            existing = await self._orders.get_by_idempotency_key(branch_id, idempotency_key)
            if existing is not None:
                return existing
        if not items:
            raise ValidationError("A sales order requires at least one line item.")
        for item in items:
            if not item.plant_id and not item.inventory_id:
                raise ValidationError("Each order line must reference exactly one of plant_id/inventory_id.")
        totals = _compute_totals(items, header_discount=header_discount, tax_rate=tax_rate)
        order = SalesOrder(
            nursery_id=nursery_id,
            branch_id=branch_id,
            customer_id=customer_id,
            quotation_id=quotation_id,
            order_status=SalesOrderStatus.DRAFT,
            payment_status=OrderPaymentStatus.UNPAID,
            subtotal_amount=totals.subtotal,
            discount_amount=totals.discount,
            tax_amount=totals.tax,
            total_amount=totals.total,
            idempotency_key=idempotency_key,
            created_by_user_id=actor_user_id,
        )
        await self._orders.add(order)
        for item in items:
            await self._order_items.add(
                OrderItem(
                    sales_order_id=order.id,
                    plant_id=item.plant_id,
                    inventory_id=item.inventory_id,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    discount_amount=item.discount_amount,
                    line_total=item.line_total,
                )
            )
        await self._log_audit(
            nursery_id, actor_user_id, "sales_order.created", order.id, {"total_amount": str(totals.total)}, request_id
        )
        await self._events.publish(
            OrderCreated(
                aggregate_id=order.id, nursery_id=nursery_id, actor_user_id=actor_user_id,
                branch_id=branch_id, customer_id=customer_id, quotation_id=quotation_id,
            ),
            request_id=request_id,
        )
        return order

    async def get_order(self, order_id: uuid.UUID) -> SalesOrder:
        order = await self._orders.get_by_id(order_id)
        if order is None:
            raise NotFoundError("Sales order not found.")
        return order

    async def list_order_items(self, order_id: uuid.UUID) -> list[OrderItem]:
        return await self._order_items.list_for_order(order_id)

    async def list_orders(self, nursery_id: uuid.UUID, *, offset: int, limit: int, **filters: Any) -> tuple[list[SalesOrder], int]:
        return await self._orders.list_for_nursery(nursery_id, offset=offset, limit=limit, **filters)

    async def confirm_order(self, order: SalesOrder, *, actor_user_id: uuid.UUID, request_id: str | None = None) -> SalesOrder:
        if order.order_status != SalesOrderStatus.DRAFT:
            raise ConflictError(
                f"Cannot confirm an order in status {order.order_status.value}.",
                context={"reason": "invalid_status_transition"},
            )
        items = await self._order_items.list_for_order(order.id)
        for item in items:
            if item.inventory_id is None:
                continue
            reservation = await self._inventory.reserve_stock(
                inventory_id=item.inventory_id, quantity=item.quantity,
                reference_type="sales_order", reference_id=order.id,
                actor_user_id=actor_user_id, request_id=request_id,
            )
            item.reservation_id = reservation.id
            await self._order_items.update(item)
            await self._events.publish(
                ReservationCreated(
                    aggregate_id=order.id, nursery_id=order.nursery_id, actor_user_id=actor_user_id,
                    order_item_id=item.id, inventory_reservation_id=reservation.id, quantity=item.quantity,
                ),
                request_id=request_id,
            )
        from_status = order.order_status
        order.order_status = SalesOrderStatus.CONFIRMED
        order.confirmed_at = datetime.now(timezone.utc)
        await self._orders.update(order)
        await self._events.publish(
            OrderStatusChanged(
                aggregate_id=order.id, nursery_id=order.nursery_id, actor_user_id=actor_user_id,
                from_status=from_status.value, to_status=order.order_status.value,
            ),
            request_id=request_id,
        )
        return order

    async def cancel_order(
        self, order: SalesOrder, *, actor_user_id: uuid.UUID, reason: str | None = None, request_id: str | None = None
    ) -> SalesOrder:
        if order.order_status in (SalesOrderStatus.FULFILLED, SalesOrderStatus.CANCELLED):
            raise ConflictError(
                f"Cannot cancel an order in status {order.order_status.value}.",
                context={"reason": "invalid_status_transition"},
            )
        items = await self._order_items.list_for_order(order.id)
        for item in items:
            if item.reservation_id is None:
                continue
            await self._inventory.release_reservation(
                reservation_id=item.reservation_id, actor_user_id=actor_user_id, request_id=request_id
            )
            await self._events.publish(
                ReservationReleased(
                    aggregate_id=order.id, nursery_id=order.nursery_id, actor_user_id=actor_user_id,
                    order_item_id=item.id, inventory_reservation_id=item.reservation_id,
                ),
                request_id=request_id,
            )
        from_status = order.order_status
        order.order_status = SalesOrderStatus.CANCELLED
        order.cancelled_at = datetime.now(timezone.utc)
        order.cancel_reason = reason
        await self._orders.update(order)
        await self._events.publish(
            OrderStatusChanged(
                aggregate_id=order.id, nursery_id=order.nursery_id, actor_user_id=actor_user_id,
                from_status=from_status.value, to_status=order.order_status.value,
            ),
            request_id=request_id,
        )
        return order

    async def checkout(
        self, order: SalesOrder, *, actor_user_id: uuid.UUID, request_id: str | None = None
    ) -> SalesOrder:
        """
        Fulfills a CONFIRMED/PROCESSING order: creates exactly one `Sale` +
        one `Invoice`, moves inventory for each bulk-stock line
        (via a reservation if one was taken at `confirm_order`, or a
        direct sale otherwise -- a walk-up checkout may skip straight
        here without ever confirming/reserving first), and publishes
        `PlantSold` for every individually-tracked plant line. Idempotent:
        calling this again on an already-fulfilled order is a no-op.
        """
        if order.sale_id is not None:
            return order
        if order.order_status not in (SalesOrderStatus.DRAFT, SalesOrderStatus.CONFIRMED, SalesOrderStatus.PROCESSING):
            raise ConflictError(
                f"Cannot check out an order in status {order.order_status.value}.",
                context={"reason": "invalid_status_transition"},
            )
        items = await self._order_items.list_for_order(order.id)
        if not items:
            raise ValidationError("Cannot check out an order with no line items.")

        sale = Sale(
            nursery_id=order.nursery_id,
            branch_id=order.branch_id,
            customer_id=order.customer_id,
            status=SaleStatus.COMPLETED,
            subtotal_amount=order.subtotal_amount,
            discount_amount=order.discount_amount,
            tax_amount=order.tax_amount,
            total_amount=order.total_amount,
            sold_by_user_id=actor_user_id,
        )
        await self._sales.add(sale)

        for item in items:
            sale_item = await self._sale_items.add(
                SaleItem(
                    sale_id=sale.id, plant_id=item.plant_id, inventory_id=item.inventory_id,
                    quantity=item.quantity, unit_price=item.unit_price, line_total=item.line_total,
                )
            )
            if item.inventory_id is not None:
                if item.reservation_id is not None:
                    await self._inventory.fulfill_reservation(
                        reservation_id=item.reservation_id, reference_sale_id=sale.id,
                        actor_user_id=actor_user_id, request_id=request_id,
                    )
                else:
                    await self._inventory.sell_stock_direct(
                        inventory_id=item.inventory_id, quantity=item.quantity, reference_sale_id=sale.id,
                        actor_user_id=actor_user_id, request_id=request_id,
                    )
            if item.plant_id is not None:
                await self._events.publish(
                    PlantSold(
                        aggregate_id=item.plant_id, nursery_id=order.nursery_id, actor_user_id=actor_user_id,
                        sale_id=sale.id, sale_item_id=sale_item.id, customer_id=order.customer_id,
                        unit_price=str(item.unit_price),
                    ),
                    request_id=request_id,
                )
                # Flagship feature: "every sold plant receives one"
                # [Plant Passport] -- a synchronous, in-request call
                # (same pattern as calling InventoryService above), not
                # deferred to an async PlantSold subscriber, so the
                # Passport/QR are guaranteed to exist by the time this
                # checkout() call returns to the caller. Passport itself
                # is this same module's own bounded context (Sales, CRM,
                # Plant Passport & QR Intelligence is one module/one
                # spec), so this is not the forbidden Sales->Plant
                # Lifecycle coupling -- PassportService never calls
                # PlantService and never writes `plants`.
                plant = await self._plants.get_by_id(item.plant_id)
                if plant is not None:
                    await self._passports.generate_passport(
                        plant, actor_user_id=actor_user_id, sale=sale, sale_item=sale_item, request_id=request_id,
                    )

        invoice = await self._generate_invoice_for_sale(sale, items, actor_user_id=actor_user_id, request_id=request_id)
        await self._invoice_sales.link(invoice.id, sale.id)

        order.sale_id = sale.id
        order.invoice_id = invoice.id
        from_status = order.order_status
        order.order_status = SalesOrderStatus.FULFILLED
        order.fulfilled_at = datetime.now(timezone.utc)
        await self._orders.update(order)
        await self._log_audit(
            order.nursery_id, actor_user_id, "sales_order.fulfilled", order.id,
            {"sale_id": str(sale.id), "invoice_id": str(invoice.id)}, request_id,
        )
        await self._events.publish(
            OrderStatusChanged(
                aggregate_id=order.id, nursery_id=order.nursery_id, actor_user_id=actor_user_id,
                from_status=from_status.value, to_status=order.order_status.value,
            ),
            request_id=request_id,
        )
        return order

    async def _generate_invoice_for_sale(
        self, sale: Sale, items: list[OrderItem], *, actor_user_id: uuid.UUID, request_id: str | None
    ) -> Invoice:
        invoice_number = await self._next_invoice_number(sale.nursery_id)
        invoice = Invoice(
            nursery_id=sale.nursery_id,
            branch_id=sale.branch_id,
            customer_id=sale.customer_id,
            invoice_number=invoice_number,
            status=InvoiceStatus.SENT,
            subtotal_amount=sale.subtotal_amount,
            discount_amount=sale.discount_amount,
            tax_amount=sale.tax_amount,
            total_amount=sale.total_amount,
        )
        await self._invoices.add(invoice)
        for item in items:
            kind = "Plant" if item.plant_id else "Inventory"
            await self._invoice_items.add(
                InvoiceItem(
                    invoice_id=invoice.id,
                    description=f"{item.quantity} x {kind} item",
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    line_total=item.line_total,
                )
            )
        await self._events.publish(
            InvoiceGenerated(
                aggregate_id=invoice.id, nursery_id=invoice.nursery_id, actor_user_id=actor_user_id,
                branch_id=invoice.branch_id, customer_id=invoice.customer_id,
                total_amount=str(invoice.total_amount), sale_id=sale.id,
            ),
            request_id=request_id,
        )
        return invoice

    async def _next_invoice_number(self, nursery_id: uuid.UUID) -> str:
        _rows, total = await self._invoices.list_for_nursery(nursery_id, offset=0, limit=1)
        year = datetime.now(timezone.utc).year
        return f"INV-{year}-{total + 1:06d}"

    async def _log_audit(self, nursery_id, actor_user_id, action, entity_id, diff, request_id) -> None:
        await self._audit.log(
            AuditLog(
                nursery_id=nursery_id, actor_user_id=actor_user_id, action=action, entity_type="SalesOrder",
                entity_id=entity_id, diff=diff, request_id=request_id, created_at=datetime.now(timezone.utc),
            )
        )


class PaymentService:
    """Multiple/Partial Payments and Payment History against an Invoice."""

    def __init__(
        self,
        *,
        payment_repo: PaymentRepository,
        invoice_repo: InvoiceRepository,
        order_repo: SalesOrderRepository,
        audit_repo: AuditLogRepository,
        event_publisher: DomainEventPublisher,
    ) -> None:
        self._payments = payment_repo
        self._invoices = invoice_repo
        self._orders = order_repo
        self._audit = audit_repo
        self._events = event_publisher

    async def record_payment(
        self,
        invoice: Invoice,
        *,
        actor_user_id: uuid.UUID,
        amount: Decimal,
        method: PaymentMethod,
        reference: str | None = None,
        sales_order: SalesOrder | None = None,
        request_id: str | None = None,
    ) -> Payment:
        amount = _money(amount)
        if amount <= 0:
            raise ValidationError("Payment amount must be positive.")
        if invoice.status == InvoiceStatus.VOID:
            raise ConflictError("Cannot record a payment against a voided invoice.", context={"reason": "invoice_void"})

        payment = await self._payments.add(
            Payment(invoice_id=invoice.id, amount=amount, method=method.value, received_by_user_id=actor_user_id)
        )
        total_paid = _money(await self._payments.sum_for_invoice(invoice.id))
        fully_paid = total_paid >= _money(invoice.total_amount)

        if fully_paid and invoice.status != InvoiceStatus.PAID:
            invoice.status = InvoiceStatus.PAID
            invoice.paid_at = datetime.now(timezone.utc)
            await self._invoices.update(invoice)

        if sales_order is not None:
            sales_order.payment_status = (
                OrderPaymentStatus.PAID
                if fully_paid
                else (OrderPaymentStatus.PARTIALLY_PAID if total_paid > 0 else OrderPaymentStatus.UNPAID)
            )
            await self._orders.update(sales_order)

        await self._audit.log(
            AuditLog(
                nursery_id=invoice.nursery_id, actor_user_id=actor_user_id, action="invoice.payment_received",
                entity_type="Invoice", entity_id=invoice.id, diff={"payment_id": str(payment.id), "amount": str(amount)},
                request_id=request_id, created_at=datetime.now(timezone.utc),
            )
        )
        await self._events.publish(
            PaymentReceived(
                aggregate_id=invoice.id, nursery_id=invoice.nursery_id, actor_user_id=actor_user_id,
                payment_id=payment.id, amount=str(amount), method=method.value, invoice_fully_paid=fully_paid,
            ),
            request_id=request_id,
        )
        return payment

    async def list_payments(self, invoice_id: uuid.UUID) -> list[Payment]:
        return await self._payments.list_for_invoice(invoice_id)

    async def total_paid(self, invoice_id: uuid.UUID) -> float:
        return await self._payments.sum_for_invoice(invoice_id)


class ReturnService:
    def __init__(
        self,
        *,
        return_repo: ReturnRepository,
        return_item_repo: ReturnItemRepository,
        sale_item_repo: SaleItemRepository,
        inventory_service: InventoryService,
        audit_repo: AuditLogRepository,
        event_publisher: DomainEventPublisher,
    ) -> None:
        self._returns = return_repo
        self._items = return_item_repo
        self._sale_items = sale_item_repo
        self._inventory = inventory_service
        self._audit = audit_repo
        self._events = event_publisher

    async def create_return(
        self,
        sale: Sale,
        *,
        actor_user_id: uuid.UUID,
        customer_id: uuid.UUID,
        reason: str | None,
        items: list[dict[str, Any]],
        request_id: str | None = None,
    ) -> Return:
        if not items:
            raise ValidationError("A return requires at least one line item.")
        return_ = Return(
            nursery_id=sale.nursery_id, branch_id=sale.branch_id, sale_id=sale.id, customer_id=customer_id,
            status=ReturnStatus.REQUESTED, reason=reason, requested_by_user_id=actor_user_id,
        )
        await self._returns.add(return_)
        for spec in items:
            sale_item = await self._sale_items.get_by_id(spec["sale_item_id"])
            if sale_item is None or sale_item.sale_id != sale.id:
                raise ValidationError(f"Sale item '{spec['sale_item_id']}' does not belong to this sale.")
            quantity = int(spec["quantity"])
            if quantity <= 0 or quantity > sale_item.quantity:
                raise ValidationError("Return quantity must be positive and not exceed the original sale quantity.")
            refund_amount = _money(_money(sale_item.unit_price) * quantity)
            await self._items.add(
                ReturnItem(
                    return_id=return_.id, sale_item_id=sale_item.id, quantity=quantity,
                    restock=bool(spec.get("restock", True)),
                    condition=spec.get("condition", ReturnItemCondition.RESALABLE),
                    line_refund_amount=refund_amount,
                )
            )
        await self._log_audit(sale.nursery_id, actor_user_id, "return.created", return_.id, {}, request_id)
        return return_

    async def get_return(self, return_id: uuid.UUID) -> Return:
        return_ = await self._returns.get_by_id(return_id)
        if return_ is None:
            raise NotFoundError("Return not found.")
        return return_

    async def list_return_items(self, return_id: uuid.UUID) -> list[ReturnItem]:
        return await self._items.list_for_return(return_id)

    async def list_returns(self, nursery_id: uuid.UUID, *, offset: int, limit: int, **filters: Any) -> tuple[list[Return], int]:
        return await self._returns.list_for_nursery(nursery_id, offset=offset, limit=limit, **filters)

    async def approve_return(self, return_: Return, *, actor_user_id: uuid.UUID) -> Return:
        if return_.status != ReturnStatus.REQUESTED:
            raise ConflictError("Only a REQUESTED return may be approved.", context={"reason": "invalid_status_transition"})
        return_.status = ReturnStatus.APPROVED
        await self._returns.update(return_)
        return return_

    async def reject_return(self, return_: Return, *, actor_user_id: uuid.UUID, reason: str | None = None) -> Return:
        if return_.status != ReturnStatus.REQUESTED:
            raise ConflictError("Only a REQUESTED return may be rejected.", context={"reason": "invalid_status_transition"})
        return_.status = ReturnStatus.REJECTED
        return_.processed_by_user_id = actor_user_id
        return_.processed_at = datetime.now(timezone.utc)
        if reason:
            return_.reason = reason
        await self._returns.update(return_)
        return return_

    async def complete_return(self, return_: Return, *, actor_user_id: uuid.UUID, request_id: str | None = None) -> Return:
        """
        Restocks Inventory (as an ADJUSTMENT movement, `reason=RETURN` --
        the enum value migration 0012 added specifically for this) for
        bulk-stock lines marked `restock=True` and not DISPOSED; publishes
        `PlantReturned` for individually-tracked plant lines. A DAMAGED-
        condition restock still returns the physical unit to `quantity`
        (not `damaged_quantity`) -- a deliberate simplification (see
        module docstring); staff can separately call Module 8's own
        `mark_damaged` afterward if the condition warrants it.
        """
        if return_.status != ReturnStatus.APPROVED:
            raise ConflictError("Only an APPROVED return may be completed.", context={"reason": "invalid_status_transition"})
        items = await self._items.list_for_return(return_.id)
        for item in items:
            sale_item = await self._sale_items.get_by_id(item.sale_item_id)
            if sale_item is None:
                continue
            if item.restock and item.condition != ReturnItemCondition.DISPOSED and sale_item.inventory_id is not None:
                await self._inventory.adjust_stock(
                    inventory_id=sale_item.inventory_id, quantity_delta=item.quantity,
                    reason=InventoryAdjustmentReason.RETURN, note=f"Return {return_.id}",
                    actor_user_id=actor_user_id, request_id=request_id,
                )
            if sale_item.plant_id is not None:
                await self._events.publish(
                    PlantReturned(
                        aggregate_id=sale_item.plant_id, nursery_id=return_.nursery_id, actor_user_id=actor_user_id,
                        return_id=return_.id, return_item_id=item.id, condition=item.condition.value,
                    ),
                    request_id=request_id,
                )
        return_.status = ReturnStatus.COMPLETED
        return_.processed_by_user_id = actor_user_id
        return_.processed_at = datetime.now(timezone.utc)
        await self._returns.update(return_)
        await self._log_audit(return_.nursery_id, actor_user_id, "return.completed", return_.id, {}, request_id)
        return return_

    async def _log_audit(self, nursery_id, actor_user_id, action, entity_id, diff, request_id) -> None:
        await self._audit.log(
            AuditLog(
                nursery_id=nursery_id, actor_user_id=actor_user_id, action=action, entity_type="Return",
                entity_id=entity_id, diff=diff, request_id=request_id, created_at=datetime.now(timezone.utc),
            )
        )


class RefundService:
    def __init__(
        self,
        *,
        refund_repo: RefundRepository,
        audit_repo: AuditLogRepository,
        event_publisher: DomainEventPublisher,
    ) -> None:
        self._refunds = refund_repo
        self._audit = audit_repo
        self._events = event_publisher

    async def process_refund(
        self,
        *,
        nursery_id: uuid.UUID,
        branch_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        amount: Decimal,
        method: PaymentMethod,
        return_id: uuid.UUID | None = None,
        invoice_id: uuid.UUID | None = None,
        sale_id: uuid.UUID | None = None,
        reference: str | None = None,
        request_id: str | None = None,
    ) -> Refund:
        amount = _money(amount)
        if amount <= 0:
            raise ValidationError("Refund amount must be positive.")
        refund = Refund(
            nursery_id=nursery_id, branch_id=branch_id, return_id=return_id, invoice_id=invoice_id, sale_id=sale_id,
            amount=amount, method=method, status=RefundStatus.PENDING, reference=reference,
            processed_by_user_id=actor_user_id,
        )
        await self._refunds.add(refund)
        # No real payment-gateway integration exists in this sandbox (same
        # honest disclosure as SMTP being real but a payment processor not
        # being one) -- a refund is recorded as immediately COMPLETED,
        # synchronously, rather than left PENDING against a webhook that
        # will never arrive.
        refund.status = RefundStatus.COMPLETED
        refund.processed_at = datetime.now(timezone.utc)
        await self._refunds.update(refund)
        await self._audit.log(
            AuditLog(
                nursery_id=nursery_id, actor_user_id=actor_user_id, action="refund.processed",
                entity_type="Refund", entity_id=refund.id, diff={"amount": str(amount)},
                request_id=request_id, created_at=datetime.now(timezone.utc),
            )
        )
        await self._events.publish(
            RefundProcessed(
                aggregate_id=refund.id, nursery_id=nursery_id, actor_user_id=actor_user_id,
                amount=str(amount), method=method.value, return_id=return_id, invoice_id=invoice_id, sale_id=sale_id,
            ),
            request_id=request_id,
        )
        return refund

    async def get_refund(self, refund_id: uuid.UUID) -> Refund:
        refund = await self._refunds.get_by_id(refund_id)
        if refund is None:
            raise NotFoundError("Refund not found.")
        return refund

    async def list_refunds(self, nursery_id: uuid.UUID, *, offset: int, limit: int, **filters: Any) -> tuple[list[Refund], int]:
        return await self._refunds.list_for_nursery(nursery_id, offset=offset, limit=limit, **filters)


class SalesReportingService:
    """Sales Reports / Revenue Reports -- full-scan pagination aggregation, same disclosed tradeoff as Module 8's reporting methods."""

    _PAGE_SIZE = 200

    def __init__(self, *, sale_repo: SaleRepository) -> None:
        self._sales = sale_repo

    async def _all_sales(self, nursery_id: uuid.UUID, **filters: Any) -> list[Sale]:
        rows: list[Sale] = []
        offset = 0
        while True:
            page, total = await self._sales.list_for_nursery(nursery_id, offset=offset, limit=self._PAGE_SIZE, **filters)
            rows.extend(page)
            offset += self._PAGE_SIZE
            if offset >= total or not page:
                break
        return rows

    async def sales_report(self, nursery_id: uuid.UUID, **filters: Any) -> dict[str, Any]:
        sales = [s for s in await self._all_sales(nursery_id, **filters) if s.status != SaleStatus.VOIDED]
        count = len(sales)
        total_revenue = sum((_as_float(s.total_amount) for s in sales), 0.0)
        total_tax = sum((_as_float(s.tax_amount) for s in sales), 0.0)
        total_discount = sum((_as_float(s.discount_amount) for s in sales), 0.0)
        return {
            "sale_count": count,
            "total_revenue": round(total_revenue, 2),
            "total_tax": round(total_tax, 2),
            "total_discount": round(total_discount, 2),
            "average_sale_value": round(total_revenue / count, 2) if count else 0.0,
        }

    async def revenue_report(self, nursery_id: uuid.UUID, **filters: Any) -> list[dict[str, Any]]:
        sales = [s for s in await self._all_sales(nursery_id, **filters) if s.status != SaleStatus.VOIDED]
        by_day: dict[str, float] = {}
        for sale in sales:
            key = sale.created_at.date().isoformat()
            by_day[key] = by_day.get(key, 0.0) + _as_float(sale.total_amount)
        return [{"date": day, "revenue": round(amount, 2)} for day, amount in sorted(by_day.items())]
