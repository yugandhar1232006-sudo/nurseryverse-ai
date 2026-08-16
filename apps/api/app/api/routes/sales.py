"""
Module 9 (Sales, CRM, Plant Passport & QR Intelligence) — Sales,
Payments, Returns & Refunds REST API.

Mounted with no router-level prefix, spanning `/quotations`,
`/sales-orders`, `/sales`, `/invoices`, `/returns`, `/refunds`. Reuses the
pre-seeded `sales:read`/`sales:write`/`sales:void` and
`invoices:read`/`invoices:write`/`invoices:void` permission codes
(migration 0002) -- Quotations and Sales Orders reuse the `sales:*`
codes (they are Sales' own pre-completion pipeline); Payments reuse
`invoices:*` (a payment is recorded against an Invoice); Returns reuse
`sales:*` (`sales:void` for the reversal-finalizing `complete` action,
matching the semantic weight Module-Phase-5's own Sale void action
already carries that code for); Refunds reuse `invoices:*` (money
movement, same ledger family as Payments).

Route ordering: `/sales/reports/*` is registered before `/sales/{id}`,
per the same FastAPI route-matching rule Module 7 and Module 8 already
applied.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import (
    PageParams,
    TenantContext,
    get_authorization_service,
    get_current_user,
    get_invoice_item_repository,
    get_invoice_repository,
    get_payment_service,
    get_quotation_service,
    get_refund_service,
    get_return_service,
    get_sale_item_repository,
    get_sale_repository,
    get_sales_order_service,
    get_sales_reporting_service,
    get_tenant_context,
    raise_if_denied,
    request_context,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.core.responses import ErrorResponse, Page, PageMeta
from app.db.enums import QuotationStatus, RefundStatus, ReturnStatus, SalesOrderStatus
from app.models.commerce import Invoice, Quotation, Return, Sale, SalesOrder
from app.models.identity import User
from app.repositories.interfaces import (
    InvoiceItemRepository,
    InvoiceRepository,
    SaleItemRepository,
    SaleRepository,
)
from app.schemas.sales import (
    CancelOrderRequest,
    CreateQuotationRequest,
    CreateReturnRequest,
    CreateSalesOrderRequest,
    InvoiceItemResponse,
    InvoiceResponse,
    OrderItemResponse,
    PaymentResponse,
    ProcessRefundRequest,
    QuotationItemResponse,
    QuotationResponse,
    QuotationStatusChangeRequest,
    RecordPaymentRequest,
    RefundResponse,
    RejectReturnRequest,
    ReturnItemResponse,
    ReturnResponse,
    RevenueReportRow,
    SaleItemResponse,
    SaleResponse,
    SalesOrderResponse,
    SalesReportResponse,
    invoice_response,
)
from app.services.authorization_service import AuthorizationService
from app.services.sales_service import (
    LineItemInput,
    PaymentService,
    QuotationService,
    RefundService,
    ReturnService,
    SalesOrderService,
    SalesReportingService,
)

router = APIRouter()

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Missing permission or cross-tenant/cross-branch access"},
    404: {"model": ErrorResponse, "description": "Not found"},
}


def _to_line_items(items: list) -> list[LineItemInput]:
    return [
        LineItemInput(
            quantity=i.quantity, unit_price=Decimal(str(i.unit_price)), plant_id=i.plant_id,
            inventory_id=i.inventory_id, description=i.description, discount_amount=Decimal(str(i.discount_amount)),
        )
        for i in items
    ]


async def _authorize_branch(
    *, branch_id: uuid.UUID, permission: str, resource_type: str, request: Request, user: User, tenant: TenantContext,
    authz: AuthorizationService,
) -> None:
    decision = await authz.authorize(
        user=user, permission=permission, resource_type=resource_type,
        target_nursery_id=tenant.org_id, target_branch_id=branch_id, context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)


async def _authorize_resource(
    *, resource, resource_type: str, permission: str, request: Request, user: User, authz: AuthorizationService,
) -> None:
    decision = await authz.authorize(
        user=user, permission=permission, resource_type=resource_type, resource_id=resource.id,
        target_nursery_id=resource.nursery_id, target_branch_id=resource.branch_id, context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)


async def _report_authorize(
    *, branch_id: uuid.UUID | None, permission: str, resource_type: str, request: Request, user: User,
    tenant: TenantContext, authz: AuthorizationService,
) -> None:
    if branch_id is not None:
        await _authorize_branch(branch_id=branch_id, permission=permission, resource_type=resource_type, request=request, user=user, tenant=tenant, authz=authz)
    else:
        decision = await authz.authorize(
            user=user, permission=permission, resource_type=resource_type, target_nursery_id=tenant.org_id, context=request_context(request)
        )
        if not decision.allowed:
            raise raise_if_denied(decision)


# ==============================================================================
# Quotations
# ==============================================================================


@router.post("/quotations", response_model=QuotationResponse, status_code=status.HTTP_201_CREATED, responses=_ERROR_RESPONSES, summary="Create a quotation")
async def create_quotation(
    body: CreateQuotationRequest, request: Request, user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), quotation_service: QuotationService = Depends(get_quotation_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> QuotationResponse:
    if tenant.org_id is None:
        raise ValidationError("You must belong to an organization to create a quotation.")
    await _authorize_branch(branch_id=body.branch_id, permission="sales:write", resource_type="quotation", request=request, user=user, tenant=tenant, authz=authz)
    quotation = await quotation_service.create_quotation(
        nursery_id=tenant.org_id, branch_id=body.branch_id, actor_user_id=user.id, customer_id=body.customer_id,
        items=_to_line_items(body.items), tax_rate=body.tax_rate, header_discount=body.header_discount,
        valid_until=body.valid_until, note=body.note, request_id=request_context(request).request_id,
    )
    return QuotationResponse.model_validate(quotation)


@router.get("/quotations", response_model=Page[QuotationResponse], responses=_ERROR_RESPONSES, summary="List/filter quotations")
async def list_quotations(
    request: Request, page_params: PageParams = Depends(), branch_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None, status_filter: QuotationStatus | None = None, user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), quotation_service: QuotationService = Depends(get_quotation_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[QuotationResponse]:
    if tenant.org_id is None:
        return Page(items=[], meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=0, total_pages=0))
    await _report_authorize(branch_id=branch_id, permission="sales:read", resource_type="quotation", request=request, user=user, tenant=tenant, authz=authz)
    rows, total = await quotation_service.list_quotations(
        tenant.org_id, offset=page_params.offset, limit=page_params.page_size, branch_id=branch_id, customer_id=customer_id, status=status_filter
    )
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(items=[QuotationResponse.model_validate(q) for q in rows], meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages))


async def _authorize_quotation(*, quotation_id: uuid.UUID, permission: str, request: Request, user: User, quotation_service: QuotationService, authz: AuthorizationService) -> Quotation:
    quotation = await quotation_service.get_quotation(quotation_id)
    await _authorize_resource(resource=quotation, resource_type="quotation", permission=permission, request=request, user=user, authz=authz)
    return quotation


@router.get("/quotations/{id}", response_model=QuotationResponse, responses=_ERROR_RESPONSES, summary="Get a quotation")
async def get_quotation(id: uuid.UUID, request: Request, user: User = Depends(get_current_user), quotation_service: QuotationService = Depends(get_quotation_service), authz: AuthorizationService = Depends(get_authorization_service)) -> QuotationResponse:
    quotation = await _authorize_quotation(quotation_id=id, permission="sales:read", request=request, user=user, quotation_service=quotation_service, authz=authz)
    return QuotationResponse.model_validate(quotation)


@router.get("/quotations/{id}/items", response_model=list[QuotationItemResponse], responses=_ERROR_RESPONSES, summary="List a quotation's line items")
async def list_quotation_items(id: uuid.UUID, request: Request, user: User = Depends(get_current_user), quotation_service: QuotationService = Depends(get_quotation_service), authz: AuthorizationService = Depends(get_authorization_service)) -> list[QuotationItemResponse]:
    await _authorize_quotation(quotation_id=id, permission="sales:read", request=request, user=user, quotation_service=quotation_service, authz=authz)
    items = await quotation_service.list_items(id)
    return [QuotationItemResponse.model_validate(i) for i in items]


@router.post("/quotations/{id}/status", response_model=QuotationResponse, responses=_ERROR_RESPONSES, summary="Change a quotation's status (send/accept/reject/expire)")
async def change_quotation_status(id: uuid.UUID, body: QuotationStatusChangeRequest, request: Request, user: User = Depends(get_current_user), quotation_service: QuotationService = Depends(get_quotation_service), authz: AuthorizationService = Depends(get_authorization_service)) -> QuotationResponse:
    quotation = await _authorize_quotation(quotation_id=id, permission="sales:write", request=request, user=user, quotation_service=quotation_service, authz=authz)
    updated = await quotation_service.change_status(quotation, to_status=body.status, actor_user_id=user.id, request_id=request_context(request).request_id)
    return QuotationResponse.model_validate(updated)


@router.post("/quotations/{id}/convert", response_model=SalesOrderResponse, responses=_ERROR_RESPONSES, summary="Convert an ACCEPTED quotation into a Sales Order")
async def convert_quotation(
    id: uuid.UUID, request: Request, user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    quotation_service: QuotationService = Depends(get_quotation_service), order_service: SalesOrderService = Depends(get_sales_order_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> SalesOrderResponse:
    quotation = await _authorize_quotation(quotation_id=id, permission="sales:write", request=request, user=user, quotation_service=quotation_service, authz=authz)
    items = await quotation_service.list_items(id)
    order_items = [
        LineItemInput(
            quantity=i.quantity, unit_price=Decimal(str(i.unit_price)), plant_id=i.plant_id, inventory_id=i.inventory_id,
            discount_amount=Decimal(str(i.discount_amount)),
        )
        for i in items
        if i.plant_id or i.inventory_id
    ]
    if not order_items:
        raise ValidationError("Quotation has no allocatable line items (each must reference a plant or inventory line) to convert.")
    # `Quotation` persists only `tax_amount` (a dollar figure), not the
    # `tax_rate` fraction that produced it (see app/models/commerce.py --
    # no `tax_rate` column exists on `quotations`). Re-deriving the
    # effective rate from the already-stored subtotal/discount/tax here
    # is what makes this conversion numerically lossless: `order_items`
    # above reconstructs the exact same quantity/unit_price/discount_amount
    # per line as the quotation had, so re-running `_compute_totals` with
    # this derived rate reproduces the identical subtotal/discount/tax/
    # total on the new SalesOrder -- caught by tests/integration/
    # test_sales_routes.py's `test_full_sales_workflow` asserting the
    # Sales Report's `total_revenue` matches the quotation's own taxed
    # total, not a tax-free amount.
    # `.subtotal_amount`/`.discount_amount`/`.tax_amount` are declared
    # `Mapped[Numeric]` -- the SQLAlchemy type-engine class reused as the
    # Python-side annotation (the real runtime value is `decimal.Decimal`;
    # see app/services/sales_service.py's `_money`/`_as_float` docstrings
    # for the same pre-existing codebase-wide imprecision) -- so mypy
    # can't see a `-`/`/` operator on `Numeric` itself; wrapping each
    # operand in `Decimal(str(...))` first gives it real `Decimal` types.
    taxable = Decimal(str(quotation.subtotal_amount)) - Decimal(str(quotation.discount_amount))
    effective_tax_rate = float(Decimal(str(quotation.tax_amount)) / taxable) if taxable else 0.0
    order = await order_service.create_order(
        nursery_id=quotation.nursery_id, branch_id=quotation.branch_id, actor_user_id=user.id, customer_id=quotation.customer_id,
        items=order_items, tax_rate=effective_tax_rate, quotation_id=quotation.id,
        request_id=request_context(request).request_id,
    )
    await quotation_service.mark_converted(quotation, actor_user_id=user.id, request_id=request_context(request).request_id)
    return SalesOrderResponse.model_validate(order)


# ==============================================================================
# Sales Orders
# ==============================================================================


@router.post("/sales-orders", response_model=SalesOrderResponse, status_code=status.HTTP_201_CREATED, responses=_ERROR_RESPONSES, summary="Create a Sales Order")
async def create_sales_order(
    body: CreateSalesOrderRequest, request: Request, user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    order_service: SalesOrderService = Depends(get_sales_order_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> SalesOrderResponse:
    if tenant.org_id is None:
        raise ValidationError("You must belong to an organization to create a sales order.")
    await _authorize_branch(branch_id=body.branch_id, permission="sales:write", resource_type="sales_order", request=request, user=user, tenant=tenant, authz=authz)
    order = await order_service.create_order(
        nursery_id=tenant.org_id, branch_id=body.branch_id, actor_user_id=user.id, customer_id=body.customer_id,
        items=_to_line_items(body.items), tax_rate=body.tax_rate, header_discount=body.header_discount,
        idempotency_key=body.idempotency_key, request_id=request_context(request).request_id,
    )
    return SalesOrderResponse.model_validate(order)


@router.get("/sales-orders", response_model=Page[SalesOrderResponse], responses=_ERROR_RESPONSES, summary="List/filter Sales Orders")
async def list_sales_orders(
    request: Request, page_params: PageParams = Depends(), branch_id: uuid.UUID | None = None, customer_id: uuid.UUID | None = None,
    order_status: SalesOrderStatus | None = None, user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    order_service: SalesOrderService = Depends(get_sales_order_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[SalesOrderResponse]:
    if tenant.org_id is None:
        return Page(items=[], meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=0, total_pages=0))
    await _report_authorize(branch_id=branch_id, permission="sales:read", resource_type="sales_order", request=request, user=user, tenant=tenant, authz=authz)
    rows, total = await order_service.list_orders(tenant.org_id, offset=page_params.offset, limit=page_params.page_size, branch_id=branch_id, customer_id=customer_id, order_status=order_status)
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(items=[SalesOrderResponse.model_validate(o) for o in rows], meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages))


async def _authorize_order(*, order_id: uuid.UUID, permission: str, request: Request, user: User, order_service: SalesOrderService, authz: AuthorizationService) -> SalesOrder:
    order = await order_service.get_order(order_id)
    await _authorize_resource(resource=order, resource_type="sales_order", permission=permission, request=request, user=user, authz=authz)
    return order


@router.get("/sales-orders/{id}", response_model=SalesOrderResponse, responses=_ERROR_RESPONSES, summary="Get a Sales Order")
async def get_sales_order(id: uuid.UUID, request: Request, user: User = Depends(get_current_user), order_service: SalesOrderService = Depends(get_sales_order_service), authz: AuthorizationService = Depends(get_authorization_service)) -> SalesOrderResponse:
    order = await _authorize_order(order_id=id, permission="sales:read", request=request, user=user, order_service=order_service, authz=authz)
    return SalesOrderResponse.model_validate(order)


@router.get("/sales-orders/{id}/items", response_model=list[OrderItemResponse], responses=_ERROR_RESPONSES, summary="List a Sales Order's line items (incl. Reservations)")
async def list_order_items(id: uuid.UUID, request: Request, user: User = Depends(get_current_user), order_service: SalesOrderService = Depends(get_sales_order_service), authz: AuthorizationService = Depends(get_authorization_service)) -> list[OrderItemResponse]:
    await _authorize_order(order_id=id, permission="sales:read", request=request, user=user, order_service=order_service, authz=authz)
    items = await order_service.list_order_items(id)
    return [OrderItemResponse.model_validate(i) for i in items]


@router.post("/sales-orders/{id}/confirm", response_model=SalesOrderResponse, responses=_ERROR_RESPONSES, summary="Confirm a Sales Order (takes Inventory Reservations for bulk-stock lines)")
async def confirm_sales_order(id: uuid.UUID, request: Request, user: User = Depends(get_current_user), order_service: SalesOrderService = Depends(get_sales_order_service), authz: AuthorizationService = Depends(get_authorization_service)) -> SalesOrderResponse:
    order = await _authorize_order(order_id=id, permission="sales:write", request=request, user=user, order_service=order_service, authz=authz)
    updated = await order_service.confirm_order(order, actor_user_id=user.id, request_id=request_context(request).request_id)
    return SalesOrderResponse.model_validate(updated)


@router.post("/sales-orders/{id}/cancel", response_model=SalesOrderResponse, responses=_ERROR_RESPONSES, summary="Cancel a Sales Order (releases any active Reservations)")
async def cancel_sales_order(id: uuid.UUID, body: CancelOrderRequest, request: Request, user: User = Depends(get_current_user), order_service: SalesOrderService = Depends(get_sales_order_service), authz: AuthorizationService = Depends(get_authorization_service)) -> SalesOrderResponse:
    order = await _authorize_order(order_id=id, permission="sales:write", request=request, user=user, order_service=order_service, authz=authz)
    updated = await order_service.cancel_order(order, actor_user_id=user.id, reason=body.reason, request_id=request_context(request).request_id)
    return SalesOrderResponse.model_validate(updated)


@router.post("/sales-orders/{id}/checkout", response_model=SalesOrderResponse, responses=_ERROR_RESPONSES, summary="Checkout: fulfill a Sales Order (creates the completed Sale + generated Invoice)")
async def checkout_sales_order(id: uuid.UUID, request: Request, user: User = Depends(get_current_user), order_service: SalesOrderService = Depends(get_sales_order_service), authz: AuthorizationService = Depends(get_authorization_service)) -> SalesOrderResponse:
    order = await _authorize_order(order_id=id, permission="sales:write", request=request, user=user, order_service=order_service, authz=authz)
    updated = await order_service.checkout(order, actor_user_id=user.id, request_id=request_context(request).request_id)
    return SalesOrderResponse.model_validate(updated)


# ==============================================================================
# Sales (completed transactions) -- Reports registered before /sales/{id}
# ==============================================================================


@router.get("/sales/reports/summary", response_model=SalesReportResponse, responses=_ERROR_RESPONSES, summary="Sales Report")
async def get_sales_report(
    request: Request, branch_id: uuid.UUID | None = None, customer_id: uuid.UUID | None = None, user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), reporting_service: SalesReportingService = Depends(get_sales_reporting_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> SalesReportResponse:
    if tenant.org_id is None:
        return SalesReportResponse(sale_count=0, total_revenue=0.0, total_tax=0.0, total_discount=0.0, average_sale_value=0.0)
    await _report_authorize(branch_id=branch_id, permission="sales:read", resource_type="sale", request=request, user=user, tenant=tenant, authz=authz)
    report = await reporting_service.sales_report(tenant.org_id, branch_id=branch_id, customer_id=customer_id)
    return SalesReportResponse(**report)


@router.get("/sales/reports/revenue", response_model=list[RevenueReportRow], responses=_ERROR_RESPONSES, summary="Revenue Report (by day)")
async def get_revenue_report(
    request: Request, branch_id: uuid.UUID | None = None, user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), reporting_service: SalesReportingService = Depends(get_sales_reporting_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> list[RevenueReportRow]:
    if tenant.org_id is None:
        return []
    await _report_authorize(branch_id=branch_id, permission="sales:read", resource_type="sale", request=request, user=user, tenant=tenant, authz=authz)
    rows = await reporting_service.revenue_report(tenant.org_id, branch_id=branch_id)
    return [RevenueReportRow(**r) for r in rows]


@router.get("/sales", response_model=Page[SaleResponse], responses=_ERROR_RESPONSES, summary="List/filter completed Sales")
async def list_sales(
    request: Request, page_params: PageParams = Depends(), branch_id: uuid.UUID | None = None, customer_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    sale_repo: SaleRepository = Depends(get_sale_repository), authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[SaleResponse]:
    if tenant.org_id is None:
        return Page(items=[], meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=0, total_pages=0))
    await _report_authorize(branch_id=branch_id, permission="sales:read", resource_type="sale", request=request, user=user, tenant=tenant, authz=authz)
    rows, total = await sale_repo.list_for_nursery(tenant.org_id, offset=page_params.offset, limit=page_params.page_size, branch_id=branch_id, customer_id=customer_id)
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(items=[SaleResponse.model_validate(s) for s in rows], meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages))


async def _get_sale_or_404(sale_id: uuid.UUID, sale_repo: SaleRepository) -> Sale:
    sale = await sale_repo.get_by_id(sale_id)
    if sale is None:
        raise NotFoundError("Sale not found.")
    return sale


@router.get("/sales/{id}", response_model=SaleResponse, responses=_ERROR_RESPONSES, summary="Get a completed Sale")
async def get_sale(id: uuid.UUID, request: Request, user: User = Depends(get_current_user), sale_repo: SaleRepository = Depends(get_sale_repository), authz: AuthorizationService = Depends(get_authorization_service)) -> SaleResponse:
    sale = await _get_sale_or_404(id, sale_repo)
    await _authorize_resource(resource=sale, resource_type="sale", permission="sales:read", request=request, user=user, authz=authz)
    return SaleResponse.model_validate(sale)


@router.get("/sales/{id}/items", response_model=list[SaleItemResponse], responses=_ERROR_RESPONSES, summary="List a Sale's line items")
async def list_sale_items(id: uuid.UUID, request: Request, user: User = Depends(get_current_user), sale_repo: SaleRepository = Depends(get_sale_repository), sale_item_repo: SaleItemRepository = Depends(get_sale_item_repository), authz: AuthorizationService = Depends(get_authorization_service)) -> list[SaleItemResponse]:
    sale = await _get_sale_or_404(id, sale_repo)
    await _authorize_resource(resource=sale, resource_type="sale", permission="sales:read", request=request, user=user, authz=authz)
    items = await sale_item_repo.list_for_sale(id)
    return [SaleItemResponse.model_validate(i) for i in items]


# ==============================================================================
# Invoices & Payments
# ==============================================================================


async def _authorize_invoice(*, invoice_id: uuid.UUID, permission: str, request: Request, user: User, invoice_repo: InvoiceRepository, authz: AuthorizationService) -> Invoice:
    invoice = await invoice_repo.get_by_id(invoice_id)
    if invoice is None:
        raise NotFoundError("Invoice not found.")
    await _authorize_resource(resource=invoice, resource_type="invoice", permission=permission, request=request, user=user, authz=authz)
    return invoice


@router.get("/invoices/{id}", response_model=InvoiceResponse, responses=_ERROR_RESPONSES, summary="Get an Invoice (payment_status is derived from recorded Payments)")
async def get_invoice(id: uuid.UUID, request: Request, user: User = Depends(get_current_user), invoice_repo: InvoiceRepository = Depends(get_invoice_repository), payment_service: PaymentService = Depends(get_payment_service), authz: AuthorizationService = Depends(get_authorization_service)) -> InvoiceResponse:
    invoice = await _authorize_invoice(invoice_id=id, permission="invoices:read", request=request, user=user, invoice_repo=invoice_repo, authz=authz)
    paid = Decimal(str(await payment_service.total_paid(id)))
    return invoice_response(invoice, amount_paid=paid)


@router.get("/invoices/{id}/items", response_model=list[InvoiceItemResponse], responses=_ERROR_RESPONSES, summary="List an Invoice's line items")
async def list_invoice_items(id: uuid.UUID, request: Request, user: User = Depends(get_current_user), invoice_repo: InvoiceRepository = Depends(get_invoice_repository), invoice_item_repo: InvoiceItemRepository = Depends(get_invoice_item_repository), authz: AuthorizationService = Depends(get_authorization_service)) -> list[InvoiceItemResponse]:
    await _authorize_invoice(invoice_id=id, permission="invoices:read", request=request, user=user, invoice_repo=invoice_repo, authz=authz)
    items = await invoice_item_repo.list_for_invoice(id)
    return [InvoiceItemResponse.model_validate(i) for i in items]


@router.post("/invoices/{id}/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED, responses=_ERROR_RESPONSES, summary="Record a Payment (Cash/UPI/Card/Bank Transfer) against an Invoice -- supports multiple/partial payments")
async def record_payment(id: uuid.UUID, body: RecordPaymentRequest, request: Request, user: User = Depends(get_current_user), invoice_repo: InvoiceRepository = Depends(get_invoice_repository), payment_service: PaymentService = Depends(get_payment_service), authz: AuthorizationService = Depends(get_authorization_service)) -> PaymentResponse:
    invoice = await _authorize_invoice(invoice_id=id, permission="invoices:write", request=request, user=user, invoice_repo=invoice_repo, authz=authz)
    payment = await payment_service.record_payment(invoice, actor_user_id=user.id, amount=body.amount, method=body.method, reference=body.reference, request_id=request_context(request).request_id)
    return PaymentResponse.model_validate(payment)


@router.get("/invoices/{id}/payments", response_model=list[PaymentResponse], responses=_ERROR_RESPONSES, summary="Payment History for an Invoice")
async def list_payments(id: uuid.UUID, request: Request, user: User = Depends(get_current_user), invoice_repo: InvoiceRepository = Depends(get_invoice_repository), payment_service: PaymentService = Depends(get_payment_service), authz: AuthorizationService = Depends(get_authorization_service)) -> list[PaymentResponse]:
    await _authorize_invoice(invoice_id=id, permission="invoices:read", request=request, user=user, invoice_repo=invoice_repo, authz=authz)
    payments = await payment_service.list_payments(id)
    return [PaymentResponse.model_validate(p) for p in payments]


# ==============================================================================
# Returns
# ==============================================================================


@router.post("/sales/{sale_id}/returns", response_model=ReturnResponse, status_code=status.HTTP_201_CREATED, responses=_ERROR_RESPONSES, summary="Create a Return against a completed Sale")
async def create_return(
    sale_id: uuid.UUID, body: CreateReturnRequest, request: Request, user: User = Depends(get_current_user),
    sale_repo: SaleRepository = Depends(get_sale_repository), return_service: ReturnService = Depends(get_return_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> ReturnResponse:
    sale = await _get_sale_or_404(sale_id, sale_repo)
    await _authorize_resource(resource=sale, resource_type="sale", permission="sales:write", request=request, user=user, authz=authz)
    return_ = await return_service.create_return(
        sale, actor_user_id=user.id, customer_id=body.customer_id, reason=body.reason,
        items=[i.model_dump() for i in body.items], request_id=request_context(request).request_id,
    )
    return ReturnResponse.model_validate(return_)


@router.get("/returns", response_model=Page[ReturnResponse], responses=_ERROR_RESPONSES, summary="List/filter Returns")
async def list_returns(
    request: Request, page_params: PageParams = Depends(), branch_id: uuid.UUID | None = None, status_filter: ReturnStatus | None = None,
    user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    return_service: ReturnService = Depends(get_return_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[ReturnResponse]:
    if tenant.org_id is None:
        return Page(items=[], meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=0, total_pages=0))
    await _report_authorize(branch_id=branch_id, permission="sales:read", resource_type="return", request=request, user=user, tenant=tenant, authz=authz)
    rows, total = await return_service.list_returns(tenant.org_id, offset=page_params.offset, limit=page_params.page_size, branch_id=branch_id, status=status_filter)
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(items=[ReturnResponse.model_validate(r) for r in rows], meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages))


async def _authorize_return(*, return_id: uuid.UUID, permission: str, request: Request, user: User, return_service: ReturnService, authz: AuthorizationService) -> Return:
    return_ = await return_service.get_return(return_id)
    await _authorize_resource(resource=return_, resource_type="return", permission=permission, request=request, user=user, authz=authz)
    return return_


@router.get("/returns/{id}", response_model=ReturnResponse, responses=_ERROR_RESPONSES, summary="Get a Return")
async def get_return(id: uuid.UUID, request: Request, user: User = Depends(get_current_user), return_service: ReturnService = Depends(get_return_service), authz: AuthorizationService = Depends(get_authorization_service)) -> ReturnResponse:
    return_ = await _authorize_return(return_id=id, permission="sales:read", request=request, user=user, return_service=return_service, authz=authz)
    return ReturnResponse.model_validate(return_)


@router.get("/returns/{id}/items", response_model=list[ReturnItemResponse], responses=_ERROR_RESPONSES, summary="List a Return's line items")
async def list_return_items(id: uuid.UUID, request: Request, user: User = Depends(get_current_user), return_service: ReturnService = Depends(get_return_service), authz: AuthorizationService = Depends(get_authorization_service)) -> list[ReturnItemResponse]:
    await _authorize_return(return_id=id, permission="sales:read", request=request, user=user, return_service=return_service, authz=authz)
    items = await return_service.list_return_items(id)
    return [ReturnItemResponse.model_validate(i) for i in items]


@router.post("/returns/{id}/approve", response_model=ReturnResponse, responses=_ERROR_RESPONSES, summary="Approve a requested Return")
async def approve_return(id: uuid.UUID, request: Request, user: User = Depends(get_current_user), return_service: ReturnService = Depends(get_return_service), authz: AuthorizationService = Depends(get_authorization_service)) -> ReturnResponse:
    return_ = await _authorize_return(return_id=id, permission="sales:write", request=request, user=user, return_service=return_service, authz=authz)
    updated = await return_service.approve_return(return_, actor_user_id=user.id)
    return ReturnResponse.model_validate(updated)


@router.post("/returns/{id}/reject", response_model=ReturnResponse, responses=_ERROR_RESPONSES, summary="Reject a requested Return")
async def reject_return(id: uuid.UUID, body: RejectReturnRequest, request: Request, user: User = Depends(get_current_user), return_service: ReturnService = Depends(get_return_service), authz: AuthorizationService = Depends(get_authorization_service)) -> ReturnResponse:
    return_ = await _authorize_return(return_id=id, permission="sales:write", request=request, user=user, return_service=return_service, authz=authz)
    updated = await return_service.reject_return(return_, actor_user_id=user.id, reason=body.reason)
    return ReturnResponse.model_validate(updated)


@router.post("/returns/{id}/complete", response_model=ReturnResponse, responses=_ERROR_RESPONSES, summary="Complete an approved Return (restocks Inventory, publishes PlantReturned for plant-tracked lines)")
async def complete_return(id: uuid.UUID, request: Request, user: User = Depends(get_current_user), return_service: ReturnService = Depends(get_return_service), authz: AuthorizationService = Depends(get_authorization_service)) -> ReturnResponse:
    return_ = await _authorize_return(return_id=id, permission="sales:void", request=request, user=user, return_service=return_service, authz=authz)
    updated = await return_service.complete_return(return_, actor_user_id=user.id, request_id=request_context(request).request_id)
    return ReturnResponse.model_validate(updated)


# ==============================================================================
# Refunds
# ==============================================================================


@router.post("/refunds", response_model=RefundResponse, status_code=status.HTTP_201_CREATED, responses=_ERROR_RESPONSES, summary="Process a Refund")
async def process_refund(
    body: ProcessRefundRequest, request: Request, user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    refund_service: RefundService = Depends(get_refund_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> RefundResponse:
    if tenant.org_id is None:
        raise ValidationError("You must belong to an organization to process a refund.")
    await _authorize_branch(branch_id=body.branch_id, permission="invoices:write", resource_type="refund", request=request, user=user, tenant=tenant, authz=authz)
    refund = await refund_service.process_refund(
        nursery_id=tenant.org_id, branch_id=body.branch_id, actor_user_id=user.id, amount=body.amount, method=body.method,
        return_id=body.return_id, invoice_id=body.invoice_id, sale_id=body.sale_id, reference=body.reference,
        request_id=request_context(request).request_id,
    )
    return RefundResponse.model_validate(refund)


@router.get("/refunds", response_model=Page[RefundResponse], responses=_ERROR_RESPONSES, summary="List/filter Refunds")
async def list_refunds(
    request: Request, page_params: PageParams = Depends(), branch_id: uuid.UUID | None = None, status_filter: RefundStatus | None = None,
    user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    refund_service: RefundService = Depends(get_refund_service), authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[RefundResponse]:
    if tenant.org_id is None:
        return Page(items=[], meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=0, total_pages=0))
    await _report_authorize(branch_id=branch_id, permission="invoices:read", resource_type="refund", request=request, user=user, tenant=tenant, authz=authz)
    rows, total = await refund_service.list_refunds(tenant.org_id, offset=page_params.offset, limit=page_params.page_size, branch_id=branch_id, status=status_filter)
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(items=[RefundResponse.model_validate(r) for r in rows], meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages))


@router.get("/refunds/{id}", response_model=RefundResponse, responses=_ERROR_RESPONSES, summary="Get a Refund")
async def get_refund(id: uuid.UUID, request: Request, user: User = Depends(get_current_user), refund_service: RefundService = Depends(get_refund_service), authz: AuthorizationService = Depends(get_authorization_service)) -> RefundResponse:
    refund = await refund_service.get_refund(id)
    await _authorize_resource(resource=refund, resource_type="refund", permission="invoices:read", request=request, user=user, authz=authz)
    return RefundResponse.model_validate(refund)
