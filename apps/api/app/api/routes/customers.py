"""
Module 9 (Sales, CRM, Plant Passport & QR Intelligence) — Customer CRM
REST API.

Mounted with no router-level prefix, same as inventory.py/digital_twin.py,
since it spans `/customers` and its nested sub-resources. Reuses the
`customers:read`/`customers:write` permission codes migration 0002 already
seeded -- every CRM sub-resource (contacts, addresses, tags, notes,
communications) reuses the same two codes rather than minting one per
sub-table, the identical "a sub-resource of an already-permissioned
entity reuses its permission" precedent Module 7 established for
`plants:read` and Module 8 continued for `inventory:read`/`write`.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import (
    PageParams,
    TenantContext,
    get_authorization_service,
    get_current_user,
    get_customer_service,
    get_tenant_context,
    raise_if_denied,
    request_context,
)
from app.core.exceptions import ValidationError
from app.core.responses import ErrorResponse, Page, PageMeta
from app.models.commerce import Customer
from app.models.identity import User
from app.schemas.customer import (
    AddCustomerTagRequest,
    CreateCustomerAddressRequest,
    CreateCustomerContactRequest,
    CreateCustomerNoteRequest,
    CreateCustomerRequest,
    CustomerAddressResponse,
    CustomerAnalyticsResponse,
    CustomerCommunicationResponse,
    CustomerContactResponse,
    CustomerNoteResponse,
    CustomerReportRow,
    CustomerResponse,
    CustomerTagResponse,
    LogCommunicationRequest,
    UpdateCustomerRequest,
)
from app.schemas.sales import SaleResponse
from app.services.authorization_service import AuthorizationService
from app.services.customer_service import CustomerService

router = APIRouter()

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Missing permission or cross-tenant/cross-branch access"},
    404: {"model": ErrorResponse, "description": "Not found"},
}


async def _authorize_customer(
    *, customer_id: uuid.UUID, permission: str, request: Request, user: User,
    customer_service: CustomerService, authz: AuthorizationService,
) -> Customer:
    customer = await customer_service.get_customer(customer_id)
    decision = await authz.authorize(
        user=user, permission=permission, resource_type="customer", resource_id=customer.id,
        target_nursery_id=customer.nursery_id, target_branch_id=customer.branch_id, context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)
    return customer


async def _authorize_branch_write(
    *, branch_id: uuid.UUID, permission: str, request: Request, user: User, tenant: TenantContext,
    authz: AuthorizationService,
) -> None:
    decision = await authz.authorize(
        user=user, permission=permission, resource_type="customer",
        target_nursery_id=tenant.org_id, target_branch_id=branch_id, context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)


async def _report_authorize(
    *, branch_id: uuid.UUID | None, request: Request, user: User, tenant: TenantContext, authz: AuthorizationService
) -> None:
    if branch_id is not None:
        await _authorize_branch_write(
            branch_id=branch_id, permission="customers:read", request=request, user=user, tenant=tenant, authz=authz
        )
    else:
        decision = await authz.authorize(
            user=user, permission="customers:read", resource_type="customer",
            target_nursery_id=tenant.org_id, context=request_context(request),
        )
        if not decision.allowed:
            raise raise_if_denied(decision)


# ==============================================================================
# Reports (registered before /customers/{id})
# ==============================================================================


@router.get("/customers/report", response_model=list[CustomerReportRow], responses=_ERROR_RESPONSES, summary="Customer Report -- top customers by spend")
async def get_customer_report(
    request: Request, branch_id: uuid.UUID | None = None, top_n: int = 10, user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), customer_service: CustomerService = Depends(get_customer_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> list[CustomerReportRow]:
    if tenant.org_id is None:
        return []
    await _report_authorize(branch_id=branch_id, request=request, user=user, tenant=tenant, authz=authz)
    rows = await customer_service.customer_report(tenant.org_id, branch_id=branch_id, top_n=top_n)
    return [CustomerReportRow(**row) for row in rows]


# ==============================================================================
# Customer Profiles
# ==============================================================================


@router.post("/customers", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED, responses=_ERROR_RESPONSES, summary="Create a customer profile")
async def create_customer(
    body: CreateCustomerRequest, request: Request, user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), customer_service: CustomerService = Depends(get_customer_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> CustomerResponse:
    if tenant.org_id is None:
        raise ValidationError("You must belong to an organization to create a customer.")
    await _authorize_branch_write(branch_id=body.branch_id, permission="customers:write", request=request, user=user, tenant=tenant, authz=authz)
    customer = await customer_service.create_customer(
        nursery_id=tenant.org_id, branch_id=body.branch_id, actor_user_id=user.id, name=body.name, email=body.email,
        phone=body.phone, customer_type=body.customer_type, request_id=request_context(request).request_id,
    )
    return CustomerResponse.model_validate(customer)


@router.get("/customers", response_model=Page[CustomerResponse], responses=_ERROR_RESPONSES, summary="List/search/filter/sort customers")
async def list_customers(
    request: Request, page_params: PageParams = Depends(), branch_id: uuid.UUID | None = None,
    customer_type=None, tag: str | None = None, search: str | None = None, sort_by: str = "created_at",
    sort_dir: str = "desc", user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    customer_service: CustomerService = Depends(get_customer_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[CustomerResponse]:
    if tenant.org_id is None:
        return Page(items=[], meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=0, total_pages=0))
    await _report_authorize(branch_id=branch_id, request=request, user=user, tenant=tenant, authz=authz)
    rows, total = await customer_service.list_customers(
        tenant.org_id, offset=page_params.offset, limit=page_params.page_size, branch_id=branch_id,
        customer_type=customer_type, tag=tag, search=search, sort_by=sort_by, sort_dir=sort_dir,
    )
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[CustomerResponse.model_validate(c) for c in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


@router.get("/customers/{id}", response_model=CustomerResponse, responses=_ERROR_RESPONSES, summary="Get a customer by id")
async def get_customer(
    id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> CustomerResponse:
    customer = await _authorize_customer(customer_id=id, permission="customers:read", request=request, user=user, customer_service=customer_service, authz=authz)
    return CustomerResponse.model_validate(customer)


@router.patch("/customers/{id}", response_model=CustomerResponse, responses=_ERROR_RESPONSES, summary="Update a customer profile")
async def update_customer(
    id: uuid.UUID, body: UpdateCustomerRequest, request: Request, user: User = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> CustomerResponse:
    customer = await _authorize_customer(customer_id=id, permission="customers:write", request=request, user=user, customer_service=customer_service, authz=authz)
    updated = await customer_service.update_customer(
        customer, actor_user_id=user.id, name=body.name, email=body.email, phone=body.phone,
        customer_type=body.customer_type, request_id=request_context(request).request_id,
    )
    return CustomerResponse.model_validate(updated)


@router.get("/customers/{id}/purchase-history", response_model=Page[SaleResponse], responses=_ERROR_RESPONSES, summary="Purchase History for a customer")
async def get_purchase_history(
    id: uuid.UUID, request: Request, page_params: PageParams = Depends(), user: User = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[SaleResponse]:
    customer = await _authorize_customer(customer_id=id, permission="customers:read", request=request, user=user, customer_service=customer_service, authz=authz)
    rows, total = await customer_service.purchase_history(customer, offset=page_params.offset, limit=page_params.page_size)
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[SaleResponse.model_validate(s) for s in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


@router.get("/customers/{id}/analytics", response_model=CustomerAnalyticsResponse, responses=_ERROR_RESPONSES, summary="Customer Analytics (lifetime spend/orders)")
async def get_customer_analytics(
    id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> CustomerAnalyticsResponse:
    customer = await _authorize_customer(customer_id=id, permission="customers:read", request=request, user=user, customer_service=customer_service, authz=authz)
    analytics = await customer_service.customer_analytics(customer)
    return CustomerAnalyticsResponse(
        customer_id=analytics.customer_id, total_orders=analytics.total_orders, total_spent=analytics.total_spent,
        average_order_value=analytics.average_order_value, last_purchase_at=analytics.last_purchase_at,
    )


# ==============================================================================
# Customer Contacts
# ==============================================================================


@router.post("/customers/{id}/contacts", response_model=CustomerContactResponse, status_code=status.HTTP_201_CREATED, responses=_ERROR_RESPONSES, summary="Add a customer contact")
async def add_customer_contact(
    id: uuid.UUID, body: CreateCustomerContactRequest, request: Request, user: User = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> CustomerContactResponse:
    customer = await _authorize_customer(customer_id=id, permission="customers:write", request=request, user=user, customer_service=customer_service, authz=authz)
    contact = await customer_service.add_contact(customer, name=body.name, role=body.role, email=body.email, phone=body.phone, is_primary=body.is_primary)
    return CustomerContactResponse.model_validate(contact)


@router.get("/customers/{id}/contacts", response_model=list[CustomerContactResponse], responses=_ERROR_RESPONSES, summary="List a customer's contacts")
async def list_customer_contacts(
    id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> list[CustomerContactResponse]:
    await _authorize_customer(customer_id=id, permission="customers:read", request=request, user=user, customer_service=customer_service, authz=authz)
    contacts = await customer_service.list_contacts(id)
    return [CustomerContactResponse.model_validate(c) for c in contacts]


# ==============================================================================
# Customer Addresses
# ==============================================================================


@router.post("/customers/{id}/addresses", response_model=CustomerAddressResponse, status_code=status.HTTP_201_CREATED, responses=_ERROR_RESPONSES, summary="Add a customer address")
async def add_customer_address(
    id: uuid.UUID, body: CreateCustomerAddressRequest, request: Request, user: User = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> CustomerAddressResponse:
    customer = await _authorize_customer(customer_id=id, permission="customers:write", request=request, user=user, customer_service=customer_service, authz=authz)
    address = await customer_service.add_address(customer, **body.model_dump())
    return CustomerAddressResponse.model_validate(address)


@router.get("/customers/{id}/addresses", response_model=list[CustomerAddressResponse], responses=_ERROR_RESPONSES, summary="List a customer's addresses")
async def list_customer_addresses(
    id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> list[CustomerAddressResponse]:
    await _authorize_customer(customer_id=id, permission="customers:read", request=request, user=user, customer_service=customer_service, authz=authz)
    addresses = await customer_service.list_addresses(id)
    return [CustomerAddressResponse.model_validate(a) for a in addresses]


# ==============================================================================
# Customer Tags
# ==============================================================================


@router.post("/customers/{id}/tags", response_model=CustomerTagResponse, status_code=status.HTTP_201_CREATED, responses=_ERROR_RESPONSES, summary="Add a customer tag")
async def add_customer_tag(
    id: uuid.UUID, body: AddCustomerTagRequest, request: Request, user: User = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> CustomerTagResponse:
    customer = await _authorize_customer(customer_id=id, permission="customers:write", request=request, user=user, customer_service=customer_service, authz=authz)
    tag = await customer_service.add_tag(customer, body.tag)
    return CustomerTagResponse.model_validate(tag)


@router.get("/customers/{id}/tags", response_model=list[CustomerTagResponse], responses=_ERROR_RESPONSES, summary="List a customer's tags")
async def list_customer_tags(
    id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> list[CustomerTagResponse]:
    await _authorize_customer(customer_id=id, permission="customers:read", request=request, user=user, customer_service=customer_service, authz=authz)
    tags = await customer_service.list_tags(id)
    return [CustomerTagResponse.model_validate(t) for t in tags]


@router.delete("/customers/{id}/tags/{tag}", response_model=None, status_code=status.HTTP_204_NO_CONTENT, responses=_ERROR_RESPONSES, summary="Remove a customer tag")
async def remove_customer_tag(
    id: uuid.UUID, tag: str, request: Request, user: User = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> None:
    customer = await _authorize_customer(customer_id=id, permission="customers:write", request=request, user=user, customer_service=customer_service, authz=authz)
    await customer_service.remove_tag(customer, tag)


# ==============================================================================
# Customer Notes
# ==============================================================================


@router.post("/customers/{id}/notes", response_model=CustomerNoteResponse, status_code=status.HTTP_201_CREATED, responses=_ERROR_RESPONSES, summary="Add a customer note")
async def add_customer_note(
    id: uuid.UUID, body: CreateCustomerNoteRequest, request: Request, user: User = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> CustomerNoteResponse:
    customer = await _authorize_customer(customer_id=id, permission="customers:write", request=request, user=user, customer_service=customer_service, authz=authz)
    note = await customer_service.add_note(customer, actor_user_id=user.id, note=body.note, pinned=body.pinned)
    return CustomerNoteResponse.model_validate(note)


@router.get("/customers/{id}/notes", response_model=Page[CustomerNoteResponse], responses=_ERROR_RESPONSES, summary="List a customer's notes")
async def list_customer_notes(
    id: uuid.UUID, request: Request, page_params: PageParams = Depends(), user: User = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[CustomerNoteResponse]:
    await _authorize_customer(customer_id=id, permission="customers:read", request=request, user=user, customer_service=customer_service, authz=authz)
    rows, total = await customer_service.list_notes(id, offset=page_params.offset, limit=page_params.page_size)
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[CustomerNoteResponse.model_validate(n) for n in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


# ==============================================================================
# Communication History
# ==============================================================================


@router.post("/customers/{id}/communications", response_model=CustomerCommunicationResponse, status_code=status.HTTP_201_CREATED, responses=_ERROR_RESPONSES, summary="Log a customer communication")
async def log_customer_communication(
    id: uuid.UUID, body: LogCommunicationRequest, request: Request, user: User = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> CustomerCommunicationResponse:
    customer = await _authorize_customer(customer_id=id, permission="customers:write", request=request, user=user, customer_service=customer_service, authz=authz)
    communication = await customer_service.log_communication(
        customer, actor_user_id=user.id, channel=body.channel, direction=body.direction, subject=body.subject, notes=body.notes
    )
    return CustomerCommunicationResponse.model_validate(communication)


@router.get("/customers/{id}/communications", response_model=Page[CustomerCommunicationResponse], responses=_ERROR_RESPONSES, summary="Communication History for a customer")
async def list_customer_communications(
    id: uuid.UUID, request: Request, page_params: PageParams = Depends(), user: User = Depends(get_current_user),
    customer_service: CustomerService = Depends(get_customer_service),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> Page[CustomerCommunicationResponse]:
    await _authorize_customer(customer_id=id, permission="customers:read", request=request, user=user, customer_service=customer_service, authz=authz)
    rows, total = await customer_service.list_communications(id, offset=page_params.offset, limit=page_params.page_size)
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[CustomerCommunicationResponse.model_validate(c) for c in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )
