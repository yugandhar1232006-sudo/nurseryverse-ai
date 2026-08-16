"""Pydantic request/response DTOs for Module 9's Sales, Payments, Returns & Refunds."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.enums import (
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


class LineItemRequest(BaseModel):
    plant_id: uuid.UUID | None = None
    inventory_id: uuid.UUID | None = None
    description: str | None = Field(None, max_length=500)
    quantity: int = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)
    discount_amount: Decimal = Field(Decimal("0"), ge=0)

    @model_validator(mode="after")
    def _at_most_one_reference(self) -> "LineItemRequest":
        if self.plant_id and self.inventory_id:
            raise ValueError("A line item may reference at most one of plant_id/inventory_id.")
        return self


# ------------------------------------------------------------------
# Quotations
# ------------------------------------------------------------------


class CreateQuotationRequest(BaseModel):
    branch_id: uuid.UUID
    customer_id: uuid.UUID
    items: list[LineItemRequest] = Field(..., min_length=1)
    tax_rate: float = Field(0.0, ge=0, le=1)
    header_discount: Decimal = Field(Decimal("0"), ge=0)
    valid_until: datetime | None = None
    note: str | None = Field(None, max_length=2000)


class QuotationStatusChangeRequest(BaseModel):
    status: QuotationStatus


class QuotationItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    quotation_id: uuid.UUID
    plant_id: uuid.UUID | None
    inventory_id: uuid.UUID | None
    description: str | None
    quantity: int
    unit_price: Decimal
    discount_amount: Decimal
    line_total: Decimal


class QuotationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID
    branch_id: uuid.UUID
    customer_id: uuid.UUID
    status: QuotationStatus
    subtotal_amount: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    valid_until: datetime | None
    note: str | None
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------
# Sales Orders
# ------------------------------------------------------------------


class CreateSalesOrderRequest(BaseModel):
    branch_id: uuid.UUID
    customer_id: uuid.UUID
    items: list[LineItemRequest] = Field(..., min_length=1)
    tax_rate: float = Field(0.0, ge=0, le=1)
    header_discount: Decimal = Field(Decimal("0"), ge=0)
    idempotency_key: str | None = Field(None, max_length=128)


class CancelOrderRequest(BaseModel):
    reason: str | None = Field(None, max_length=1000)


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sales_order_id: uuid.UUID
    plant_id: uuid.UUID | None
    inventory_id: uuid.UUID | None
    quantity: int
    unit_price: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    line_total: Decimal
    reservation_id: uuid.UUID | None


class SalesOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID
    branch_id: uuid.UUID
    customer_id: uuid.UUID
    quotation_id: uuid.UUID | None
    order_status: SalesOrderStatus
    payment_status: OrderPaymentStatus
    subtotal_amount: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    sale_id: uuid.UUID | None
    invoice_id: uuid.UUID | None
    created_by_user_id: uuid.UUID
    confirmed_at: datetime | None
    fulfilled_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------
# Sales (completed transactions) & Invoices
# ------------------------------------------------------------------


class SaleItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sale_id: uuid.UUID
    plant_id: uuid.UUID | None
    inventory_id: uuid.UUID | None
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class SaleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID
    branch_id: uuid.UUID
    customer_id: uuid.UUID | None
    status: SaleStatus
    subtotal_amount: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    payment_method: str | None
    sold_by_user_id: uuid.UUID
    created_at: datetime


class InvoiceItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    description: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class InvoiceResponse(BaseModel):
    """`payment_status` is derived (sum of Payments vs. total_amount), not a stored column -- see `invoice_response()`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID
    branch_id: uuid.UUID
    customer_id: uuid.UUID
    invoice_number: str
    status: InvoiceStatus
    subtotal_amount: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    amount_paid: Decimal
    payment_status: OrderPaymentStatus
    due_date: datetime | None
    paid_at: datetime | None
    created_at: datetime


def invoice_response(invoice, *, amount_paid: Decimal) -> InvoiceResponse:
    if amount_paid >= Decimal(str(invoice.total_amount)) and amount_paid > 0:
        payment_status = OrderPaymentStatus.PAID
    elif amount_paid > 0:
        payment_status = OrderPaymentStatus.PARTIALLY_PAID
    else:
        payment_status = OrderPaymentStatus.UNPAID
    return InvoiceResponse(
        id=invoice.id, nursery_id=invoice.nursery_id, branch_id=invoice.branch_id, customer_id=invoice.customer_id,
        invoice_number=invoice.invoice_number, status=invoice.status, subtotal_amount=invoice.subtotal_amount,
        discount_amount=invoice.discount_amount, tax_amount=invoice.tax_amount, total_amount=invoice.total_amount,
        amount_paid=amount_paid, payment_status=payment_status, due_date=invoice.due_date, paid_at=invoice.paid_at,
        created_at=invoice.created_at,
    )


# ------------------------------------------------------------------
# Payments
# ------------------------------------------------------------------


class RecordPaymentRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    method: PaymentMethod
    reference: str | None = Field(None, max_length=100)


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    amount: Decimal
    method: str
    reference: str | None
    received_by_user_id: uuid.UUID
    received_at: datetime


# ------------------------------------------------------------------
# Returns & Refunds
# ------------------------------------------------------------------


class ReturnItemRequest(BaseModel):
    sale_item_id: uuid.UUID
    quantity: int = Field(..., gt=0)
    restock: bool = True
    condition: ReturnItemCondition = ReturnItemCondition.RESALABLE


class CreateReturnRequest(BaseModel):
    customer_id: uuid.UUID
    reason: str | None = Field(None, max_length=2000)
    items: list[ReturnItemRequest] = Field(..., min_length=1)


class RejectReturnRequest(BaseModel):
    reason: str | None = Field(None, max_length=1000)


class ReturnItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    return_id: uuid.UUID
    sale_item_id: uuid.UUID
    quantity: int
    restock: bool
    condition: ReturnItemCondition
    line_refund_amount: Decimal


class ReturnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID
    branch_id: uuid.UUID
    sale_id: uuid.UUID
    customer_id: uuid.UUID
    status: ReturnStatus
    reason: str | None
    requested_by_user_id: uuid.UUID
    processed_by_user_id: uuid.UUID | None
    processed_at: datetime | None
    created_at: datetime


class ProcessRefundRequest(BaseModel):
    branch_id: uuid.UUID
    amount: Decimal = Field(..., gt=0)
    method: PaymentMethod
    return_id: uuid.UUID | None = None
    invoice_id: uuid.UUID | None = None
    sale_id: uuid.UUID | None = None
    reference: str | None = Field(None, max_length=100)


class RefundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID
    branch_id: uuid.UUID
    return_id: uuid.UUID | None
    invoice_id: uuid.UUID | None
    sale_id: uuid.UUID | None
    amount: Decimal
    method: PaymentMethod
    status: RefundStatus
    reference: str | None
    processed_by_user_id: uuid.UUID
    processed_at: datetime | None
    created_at: datetime


# ------------------------------------------------------------------
# Reporting
# ------------------------------------------------------------------


class SalesReportResponse(BaseModel):
    sale_count: int
    total_revenue: float
    total_tax: float
    total_discount: float
    average_sale_value: float


class RevenueReportRow(BaseModel):
    date: str
    revenue: float
