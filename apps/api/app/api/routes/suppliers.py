"""Minimal Suppliers read-only route for the Plant Registration dropdown.

Suppliers & Purchasing is a full Module in the architecture, but the
plant-registration workflow needs a supplier dropdown today. This route
provides a read-only list scoped to the caller's org. Full CRUD (create/
update/archive/supplier contacts/purchase orders) belongs to the real
Suppliers & Purchasing module when it's built.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.deps import (
    TenantContext,
    get_authorization_service,
    get_current_user,
    get_supplier_repository,
    get_tenant_context,
    raise_if_denied,
    request_context,
    require_permission,
)
from app.core.responses import ErrorResponse
from app.models.identity import User
from app.schemas.purchasing import SupplierResponse
from app.repositories.interfaces import SupplierRepository

router = APIRouter()

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Missing permission or cross-tenant access"},
}


@router.get(
    "",
    response_model=list[SupplierResponse],
    responses=_ERROR_RESPONSES,
    summary="List suppliers for the caller's organization",
    description="Requires `plants:read` (used in service of the Plant Registration workflow).",
)
async def list_suppliers(
    request: Request,
    tenant: TenantContext = Depends(get_tenant_context),
    user: User = Depends(get_current_user),
    supplier_repo: SupplierRepository = Depends(get_supplier_repository),
    authz=Depends(get_authorization_service),
) -> list[SupplierResponse]:
    decision = await authz.authorize(
        user=user, permission="plants:read", resource_type="supplier",
        target_nursery_id=tenant.org_id,
        context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)

    if tenant.org_id is None:
        return []

    suppliers = await supplier_repo.list_for_nursery(tenant.org_id)
    return [SupplierResponse.model_validate(s) for s in suppliers]
