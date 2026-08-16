"""
Module 3's worked example of the full authorization stack protecting a
real, useful capability: the audit-log viewer. `audit:read` is a genuine
seeded permission (docs/ux/07-role-permission-matrix.md line 78), granted
Full (org-wide) to Owner and Org Admin only — every other role gets a 403,
which is itself proof the permission engine and route protection are wired
correctly end to end (Module 3's validation checklist: "every endpoint
protected").

Reads `audit_logs` (Phase 5, migration 0004) scoped to the caller's own
org — via `get_scoped_db`, so even a bug in this route's own WHERE clause
couldn't leak another org's rows, since Postgres RLS would filter them out
regardless. The explicit `nursery_id` filter below is not redundant with
RLS: RLS is the defense-in-depth backstop; the application-level filter is
what makes the *count* and pagination correct without relying on knowing
RLS is even active (e.g. in a unit test running against the in-memory
fake, where there is no real RLS to fall back on).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import PageParams, TenantContext, get_audit_log_repository, get_tenant_context, require_permission
from app.core.responses import ErrorResponse, Page, PageMeta
from app.repositories.interfaces import AuditLogRepository
from app.schemas.audit import AuditLogEntryResponse
from app.services.authorization_service import AuthorizationDecision

router = APIRouter()

# Phase 6 Module 14 (Production Readiness) defect fix: same
# `mypy app`-only typing gap fixed in app/api/routes/auth.py's own
# `_ERROR_RESPONSES` -- see that file's comment for the full explanation.
_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Missing audit:read permission"},
}


@router.get(
    "",
    response_model=Page[AuditLogEntryResponse],
    responses=_ERROR_RESPONSES,
    summary="List the caller's organization's audit log, newest first",
    description=(
        "Requires `audit:read` (Owner/Org Admin only in the default role "
        "set). Scoped to the caller's own organization at both the "
        "application layer and the database's row-level-security layer — "
        "cross-tenant access is not possible regardless of query "
        "parameters."
    ),
)
async def list_audit_log(
    page_params: PageParams = Depends(),
    tenant: TenantContext = Depends(get_tenant_context),
    repo: AuditLogRepository = Depends(get_audit_log_repository),
    decision: AuthorizationDecision = Depends(require_permission("audit:read", resource_type="audit_log")),
) -> Page[AuditLogEntryResponse]:
    if tenant.org_id is None:
        # Authenticated but no org membership -- nothing to list. Distinct
        # from a 403: the caller *would* be allowed to read an org's audit
        # log, they just don't belong to one yet.
        return Page(items=[], meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=0, total_pages=0))

    rows, total = await repo.list_for_org(tenant.org_id, offset=page_params.offset, limit=page_params.page_size)
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0

    return Page(
        items=[AuditLogEntryResponse.model_validate(row) for row in rows],
        meta=PageMeta(
            page=page_params.page,
            page_size=page_params.page_size,
            total_items=total,
            total_pages=total_pages,
        ),
    )
