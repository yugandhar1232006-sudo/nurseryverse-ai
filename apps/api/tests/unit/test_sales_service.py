"""
Unit tests for Module 9's Sales bounded context -- `QuotationService`,
`SalesOrderService` (Reservations/Checkout/Invoice Generation/Tax/
Discounts), `PaymentService` (Multiple/Partial Payments), `ReturnService`,
`RefundService`, and `SalesReportingService`. Exercised directly against
`harness`, the same split every prior module's unit test files use.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.core.exceptions import ConflictError, ValidationError
from app.db.enums import (
    InvoiceStatus,
    OrderPaymentStatus,
    PaymentMethod,
    QuotationStatus,
    RefundStatus,
    ReturnStatus,
    SalesOrderStatus,
    SaleStatus,
)
from app.models.catalog import Species
from app.models.organization import Branch
from app.services.sales_service import LineItemInput

pytestmark = pytest.mark.unit


def _branch(*, nursery_id: uuid.UUID, name: str = "Main") -> Branch:
    now = datetime.now(timezone.utc)
    return Branch(
        id=uuid.uuid4(), nursery_id=nursery_id, name=name, address_line1="123 St", city="Springfield",
        country="US", timezone="UTC", created_at=now, updated_at=now,
    )


def _species(*, nursery_id: uuid.UUID) -> Species:
    now = datetime.now(timezone.utc)
    return Species(
        id=uuid.uuid4(), nursery_id=nursery_id, category_id=uuid.uuid4(), common_name="Fig", botanical_name="Ficus lyrata",
        created_at=now, updated_at=now,
    )


async def _setup(harness):
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    return org_id, branch, species


async def _register_plant(harness, *, org_id, branch, species):
    return await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )


async def _make_inventory_line(harness, *, org_id, branch, initial_quantity=20):
    return await harness.inventory_service.create_inventory_line(
        nursery_id=org_id, branch_id=branch.id, category_id=uuid.uuid4(), unit_id=uuid.uuid4(),
        name="Basil 4in", initial_quantity=initial_quantity, low_stock_threshold=5, unit_price=9.99,
        actor_user_id=uuid.uuid4(),
    )


# ------------------------------------------------------------------
# Tax Calculation / Discounts (QuotationService, shared _compute_totals)
# ------------------------------------------------------------------


async def test_quotation_totals_apply_tax_after_discount(harness):
    org_id, branch, species = await _setup(harness)
    plant = await _register_plant(harness, org_id=org_id, branch=branch, species=species)
    customer = await harness.customer_service.create_customer(
        nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), name="Jane Doe"
    )
    quotation = await harness.quotation_service.create_quotation(
        nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), customer_id=customer.id,
        items=[LineItemInput(quantity=2, unit_price=Decimal("50.00"), plant_id=plant.id, discount_amount=Decimal("10.00"))],
        tax_rate=0.1, header_discount=Decimal("5.00"),
    )
    # subtotal = 100.00, discount = line(10) + header(5) = 15.00, taxable = 85.00, tax = 8.50, total = 93.50
    assert quotation.subtotal_amount == Decimal("100.00")
    assert quotation.discount_amount == Decimal("15.00")
    assert quotation.tax_amount == Decimal("8.50")
    assert quotation.total_amount == Decimal("93.50")


async def test_quotation_requires_at_least_one_item(harness):
    org_id, branch, _ = await _setup(harness)
    with pytest.raises(ValidationError):
        await harness.quotation_service.create_quotation(
            nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), customer_id=uuid.uuid4(), items=[]
        )


async def test_quotation_status_transitions(harness):
    org_id, branch, species = await _setup(harness)
    plant = await _register_plant(harness, org_id=org_id, branch=branch, species=species)
    quotation = await harness.quotation_service.create_quotation(
        nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), customer_id=uuid.uuid4(),
        items=[LineItemInput(quantity=1, unit_price=Decimal("20.00"), plant_id=plant.id)],
    )
    assert quotation.status == QuotationStatus.DRAFT

    sent = await harness.quotation_service.change_status(
        quotation, to_status=QuotationStatus.SENT, actor_user_id=uuid.uuid4()
    )
    assert sent.status == QuotationStatus.SENT

    accepted = await harness.quotation_service.change_status(
        sent, to_status=QuotationStatus.ACCEPTED, actor_user_id=uuid.uuid4()
    )
    assert accepted.status == QuotationStatus.ACCEPTED

    with pytest.raises(ConflictError):
        # ACCEPTED is terminal for change_status -- only mark_converted may leave it.
        await harness.quotation_service.change_status(
            accepted, to_status=QuotationStatus.SENT, actor_user_id=uuid.uuid4()
        )


# ------------------------------------------------------------------
# Sales Orders: Order Items, Reservations, Checkout, Invoice Generation
# ------------------------------------------------------------------


async def test_create_order_requires_plant_or_inventory_reference(harness):
    org_id, branch, _ = await _setup(harness)
    with pytest.raises(ValidationError):
        await harness.sales_order_service.create_order(
            nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), customer_id=uuid.uuid4(),
            items=[LineItemInput(quantity=1, unit_price=Decimal("10.00"))],
        )


async def test_confirm_order_reserves_inventory_stock(harness):
    org_id, branch, _ = await _setup(harness)
    line = await _make_inventory_line(harness, org_id=org_id, branch=branch, initial_quantity=20)
    order = await harness.sales_order_service.create_order(
        nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), customer_id=uuid.uuid4(),
        items=[LineItemInput(quantity=3, unit_price=Decimal("9.99"), inventory_id=line.id)],
    )
    assert order.order_status == SalesOrderStatus.DRAFT

    confirmed = await harness.sales_order_service.confirm_order(order, actor_user_id=uuid.uuid4())
    assert confirmed.order_status == SalesOrderStatus.CONFIRMED

    items = await harness.sales_order_service.list_order_items(order.id)
    assert items[0].reservation_id is not None
    reservation = await harness.inventory_service.get_reservation(items[0].reservation_id)
    assert reservation.quantity == 3

    updated_line = await harness.inventory_service.get_inventory(line.id)
    assert updated_line.reserved_quantity == 3


async def test_cancel_order_releases_reservation(harness):
    org_id, branch, _ = await _setup(harness)
    line = await _make_inventory_line(harness, org_id=org_id, branch=branch, initial_quantity=20)
    order = await harness.sales_order_service.create_order(
        nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), customer_id=uuid.uuid4(),
        items=[LineItemInput(quantity=3, unit_price=Decimal("9.99"), inventory_id=line.id)],
    )
    order = await harness.sales_order_service.confirm_order(order, actor_user_id=uuid.uuid4())

    cancelled = await harness.sales_order_service.cancel_order(order, actor_user_id=uuid.uuid4(), reason="changed mind")
    assert cancelled.order_status == SalesOrderStatus.CANCELLED

    updated_line = await harness.inventory_service.get_inventory(line.id)
    assert updated_line.reserved_quantity == 0


async def test_checkout_creates_sale_invoice_and_publishes_plant_sold(harness):
    org_id, branch, species = await _setup(harness)
    plant = await _register_plant(harness, org_id=org_id, branch=branch, species=species)
    customer = await harness.customer_service.create_customer(
        nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), name="Jane Doe"
    )
    order = await harness.sales_order_service.create_order(
        nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), customer_id=customer.id,
        items=[LineItemInput(quantity=1, unit_price=Decimal("45.00"), plant_id=plant.id)], tax_rate=0.1,
    )
    fulfilled = await harness.sales_order_service.checkout(order, actor_user_id=uuid.uuid4())

    assert fulfilled.order_status == SalesOrderStatus.FULFILLED
    assert fulfilled.sale_id is not None
    assert fulfilled.invoice_id is not None

    sale = await harness.sales.get_by_id(fulfilled.sale_id)
    assert sale.status == SaleStatus.COMPLETED
    assert sale.total_amount == Decimal("49.50")

    invoice = await harness.invoices.get_by_id(fulfilled.invoice_id)
    assert invoice.status == InvoiceStatus.SENT
    assert invoice.total_amount == sale.total_amount

    # Every sold plant receives a Plant Passport (flagship feature) --
    # generated synchronously by checkout(), not deferred.
    passport = await harness.passports.get_latest_for_plant(plant.id)
    assert passport is not None
    assert passport.version == 1

    # Digital Twin: Ownership Timeline transferred nursery -> customer, Sales Timeline updated.
    twin = await harness.digital_twin_service.get_current_twin(plant.id)
    assert twin.snapshot["ownership"]["owner_type"] == "customer"
    assert twin.snapshot["ownership"]["customer_id"] == str(customer.id)
    assert twin.snapshot["counts"]["plant_sold"] == 1
    assert twin.snapshot["counts"]["passports_generated"] == 1
    assert twin.snapshot["latest"]["sale"]["unit_price"] == "45.00"


async def test_checkout_is_idempotent(harness):
    org_id, branch, species = await _setup(harness)
    plant = await _register_plant(harness, org_id=org_id, branch=branch, species=species)
    order = await harness.sales_order_service.create_order(
        nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), customer_id=uuid.uuid4(),
        items=[LineItemInput(quantity=1, unit_price=Decimal("45.00"), plant_id=plant.id)],
    )
    first = await harness.sales_order_service.checkout(order, actor_user_id=uuid.uuid4())
    second = await harness.sales_order_service.checkout(first, actor_user_id=uuid.uuid4())

    assert second.sale_id == first.sale_id
    passports, total = await harness.passports.list_for_nursery(org_id, offset=0, limit=10)
    assert total == 1  # not regenerated on the idempotent no-op call


async def test_checkout_with_reservation_fulfills_it(harness):
    org_id, branch, _ = await _setup(harness)
    line = await _make_inventory_line(harness, org_id=org_id, branch=branch, initial_quantity=20)
    order = await harness.sales_order_service.create_order(
        nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), customer_id=uuid.uuid4(),
        items=[LineItemInput(quantity=4, unit_price=Decimal("9.99"), inventory_id=line.id)],
    )
    order = await harness.sales_order_service.confirm_order(order, actor_user_id=uuid.uuid4())
    order = await harness.sales_order_service.checkout(order, actor_user_id=uuid.uuid4())

    assert order.order_status == SalesOrderStatus.FULFILLED
    updated_line = await harness.inventory_service.get_inventory(line.id)
    assert updated_line.quantity == 16
    assert updated_line.reserved_quantity == 0


# ------------------------------------------------------------------
# Payments: Cash/UPI/Card/Bank Transfer, Multiple/Partial Payments
# ------------------------------------------------------------------


async def test_partial_then_full_payment_updates_invoice_status(harness):
    org_id, branch, species = await _setup(harness)
    plant = await _register_plant(harness, org_id=org_id, branch=branch, species=species)
    order = await harness.sales_order_service.create_order(
        nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), customer_id=uuid.uuid4(),
        items=[LineItemInput(quantity=1, unit_price=Decimal("100.00"), plant_id=plant.id)],
    )
    order = await harness.sales_order_service.checkout(order, actor_user_id=uuid.uuid4())
    invoice = await harness.invoices.get_by_id(order.invoice_id)

    await harness.payment_service.record_payment(
        invoice, actor_user_id=uuid.uuid4(), amount=Decimal("40.00"), method=PaymentMethod.CASH, sales_order=order,
    )
    assert order.payment_status == OrderPaymentStatus.PARTIALLY_PAID
    invoice = await harness.invoices.get_by_id(order.invoice_id)
    assert invoice.status != InvoiceStatus.PAID

    await harness.payment_service.record_payment(
        invoice, actor_user_id=uuid.uuid4(), amount=Decimal("60.00"), method=PaymentMethod.UPI, sales_order=order,
    )
    assert order.payment_status == OrderPaymentStatus.PAID
    invoice = await harness.invoices.get_by_id(order.invoice_id)
    assert invoice.status == InvoiceStatus.PAID

    payments = await harness.payment_service.list_payments(invoice.id)
    assert len(payments) == 2
    assert {p.method for p in payments} == {"cash", "upi"}
    assert await harness.payment_service.total_paid(invoice.id) == 100.0


async def test_record_payment_rejects_non_positive_amount(harness):
    org_id, branch, species = await _setup(harness)
    plant = await _register_plant(harness, org_id=org_id, branch=branch, species=species)
    order = await harness.sales_order_service.create_order(
        nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), customer_id=uuid.uuid4(),
        items=[LineItemInput(quantity=1, unit_price=Decimal("10.00"), plant_id=plant.id)],
    )
    order = await harness.sales_order_service.checkout(order, actor_user_id=uuid.uuid4())
    invoice = await harness.invoices.get_by_id(order.invoice_id)
    with pytest.raises(ValidationError):
        await harness.payment_service.record_payment(
            invoice, actor_user_id=uuid.uuid4(), amount=Decimal("0"), method=PaymentMethod.CARD
        )


# ------------------------------------------------------------------
# Returns & Refunds
# ------------------------------------------------------------------


async def test_return_workflow_restocks_and_publishes_plant_returned(harness):
    org_id, branch, species = await _setup(harness)
    plant = await _register_plant(harness, org_id=org_id, branch=branch, species=species)
    customer = await harness.customer_service.create_customer(
        nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), name="Jane Doe"
    )
    order = await harness.sales_order_service.create_order(
        nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), customer_id=customer.id,
        items=[LineItemInput(quantity=1, unit_price=Decimal("30.00"), plant_id=plant.id)],
    )
    order = await harness.sales_order_service.checkout(order, actor_user_id=uuid.uuid4())
    sale = await harness.sales.get_by_id(order.sale_id)
    sale_items = await harness.sale_items.list_for_sale(sale.id)

    return_ = await harness.return_service.create_return(
        sale, actor_user_id=uuid.uuid4(), customer_id=customer.id, reason="Wilted on arrival",
        items=[{"sale_item_id": sale_items[0].id, "quantity": 1, "restock": True}],
    )
    assert return_.status == ReturnStatus.REQUESTED

    approved = await harness.return_service.approve_return(return_, actor_user_id=uuid.uuid4())
    assert approved.status == ReturnStatus.APPROVED

    completed = await harness.return_service.complete_return(approved, actor_user_id=uuid.uuid4())
    assert completed.status == ReturnStatus.COMPLETED

    # Ownership Timeline reverts customer -> nursery; Sales Timeline records the return.
    twin = await harness.digital_twin_service.get_current_twin(plant.id)
    assert twin.snapshot["ownership"]["owner_type"] == "nursery"
    assert twin.snapshot["counts"]["plant_returned"] == 1
    assert twin.snapshot["latest"]["return"]["refund_amount"] == 30.0


async def test_return_quantity_cannot_exceed_original_sale_quantity(harness):
    org_id, branch, species = await _setup(harness)
    plant = await _register_plant(harness, org_id=org_id, branch=branch, species=species)
    order = await harness.sales_order_service.create_order(
        nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), customer_id=uuid.uuid4(),
        items=[LineItemInput(quantity=1, unit_price=Decimal("30.00"), plant_id=plant.id)],
    )
    order = await harness.sales_order_service.checkout(order, actor_user_id=uuid.uuid4())
    sale = await harness.sales.get_by_id(order.sale_id)
    sale_items = await harness.sale_items.list_for_sale(sale.id)

    with pytest.raises(ValidationError):
        await harness.return_service.create_return(
            sale, actor_user_id=uuid.uuid4(), customer_id=uuid.uuid4(), reason=None,
            items=[{"sale_item_id": sale_items[0].id, "quantity": 5}],
        )


async def test_complete_return_requires_approved_status(harness):
    org_id, branch, species = await _setup(harness)
    plant = await _register_plant(harness, org_id=org_id, branch=branch, species=species)
    order = await harness.sales_order_service.create_order(
        nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), customer_id=uuid.uuid4(),
        items=[LineItemInput(quantity=1, unit_price=Decimal("30.00"), plant_id=plant.id)],
    )
    order = await harness.sales_order_service.checkout(order, actor_user_id=uuid.uuid4())
    sale = await harness.sales.get_by_id(order.sale_id)
    sale_items = await harness.sale_items.list_for_sale(sale.id)
    return_ = await harness.return_service.create_return(
        sale, actor_user_id=uuid.uuid4(), customer_id=uuid.uuid4(), reason=None,
        items=[{"sale_item_id": sale_items[0].id, "quantity": 1}],
    )
    with pytest.raises(ConflictError):
        await harness.return_service.complete_return(return_, actor_user_id=uuid.uuid4())


async def test_process_refund_completes_immediately(harness):
    org_id, branch, _ = await _setup(harness)
    refund = await harness.refund_service.process_refund(
        nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), amount=Decimal("30.00"),
        method=PaymentMethod.CASH,
    )
    assert refund.status == RefundStatus.COMPLETED
    assert refund.processed_at is not None


async def test_process_refund_rejects_non_positive_amount(harness):
    org_id, branch, _ = await _setup(harness)
    with pytest.raises(ValidationError):
        await harness.refund_service.process_refund(
            nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), amount=Decimal("0"),
            method=PaymentMethod.CASH,
        )


# ------------------------------------------------------------------
# Sales Reports / Revenue Reports
# ------------------------------------------------------------------


async def test_sales_report_aggregates_completed_sales_only(harness):
    org_id, branch, species = await _setup(harness)
    plant_a = await _register_plant(harness, org_id=org_id, branch=branch, species=species)
    plant_b = await _register_plant(harness, org_id=org_id, branch=branch, species=species)

    order_a = await harness.sales_order_service.create_order(
        nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), customer_id=uuid.uuid4(),
        items=[LineItemInput(quantity=1, unit_price=Decimal("40.00"), plant_id=plant_a.id)],
    )
    await harness.sales_order_service.checkout(order_a, actor_user_id=uuid.uuid4())

    order_b = await harness.sales_order_service.create_order(
        nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), customer_id=uuid.uuid4(),
        items=[LineItemInput(quantity=1, unit_price=Decimal("60.00"), plant_id=plant_b.id)],
    )
    await harness.sales_order_service.checkout(order_b, actor_user_id=uuid.uuid4())

    report = await harness.sales_reporting_service.sales_report(org_id)
    assert report["sale_count"] == 2
    assert report["total_revenue"] == 100.0
    assert report["average_sale_value"] == 50.0

    revenue_rows = await harness.sales_reporting_service.revenue_report(org_id)
    assert sum(r["revenue"] for r in revenue_rows) == 100.0
