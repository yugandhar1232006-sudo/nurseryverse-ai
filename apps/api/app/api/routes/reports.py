"""
Module 12 (Reports & Analytics) REST API.

Mounted with no router-level prefix (like inventory.py/digital_twin.py)
because this module spans three different path roots: `/dashboards/*`,
`/analytics/*`, `/reports/*`. Every route calls `DashboardService`/
`AnalyticsService`/`ReportGenerationService`/`ScheduledReportService`
only -- no query/business logic lives in a route handler here. See those
services' own module docstrings for where the real logic actually lives:
dashboards/analytics are thin pass-throughs onto `ReportingRepository`'s
CQRS read side; report generation/scheduling delegate entirely to
`ReportGenerationService`/`ScheduledReportService`.

Permissions: migration 0002's seed data defines only `reports:read` and
`reports:export` for the `reports` module -- no `reports:write`, no
scheduled-report-specific permission code. Following the same "reuse an
existing permission for a closely related capability" precedent
notifications.py's own module docstring documents: `reports:read` gates
every dashboard/analytics/catalog/status/download/history read;
`reports:export` gates report generation and every scheduled-report write
(create/update/pause/resume/delete/run-due), since both ultimately
produce exportable output.

Tenant/branch isolation: `nursery_id` is ALWAYS `tenant.org_id` (the
authenticated caller's own resolved org) -- no route here accepts a
`nursery_id` path/query/body parameter at all, so there is nothing for a
client to override even if it tried. An optional `branch_id` (query
param for dashboards/analytics/report-history list routes, body field
for report/scheduled-report creation) is authorized through
`_authorize_branch_or_org` below, the same query/body-branch-parameter
shape `app/api/routes/inventory.py`'s own `_report_authorize` helper
established (a query/body `branch_id` isn't a URL path segment, so
`require_branch_match` -- which reads `request.path_params` -- doesn't
apply). By-id resource routes (report status/download, scheduled report
get/update/pause/resume/delete) instead fetch the row first and authorize
against ITS OWN `nursery_id`/`branch_id`, exactly like
`app/api/routes/customers.py`'s `_authorize_customer` -- a cross-tenant
or cross-branch mismatch is a 403 (not a 404), matching every other
by-id resource route in this codebase; a genuinely nonexistent id is a
404. Every one of these paths authorizes against `target_nursery_id=
tenant.org_id` or the fetched resource's own `nursery_id` -- never a
client-supplied value -- so "never trust tenant_id/branch_id supplied by
the client when it conflicts with the authenticated scope" holds by
construction (there is no code path that reads a client-supplied
nursery_id at all).

Report generation runs inside a FastAPI `BackgroundTasks` task
(`ReportGenerationService.generate`) -- `POST /reports` returns
immediately (202 Accepted) with the `Report` row in `PENDING` status; the
client polls `GET /reports/{id}` for status, matching the "never block an
HTTP request unnecessarily for a large report" requirement. Report
download (`GET /reports/{id}/download`) is the ONLY route that resolves a
report's actual bytes -- `ReportResponse.download_url` never exposes
`Report.file_url` (a raw Cloudinary URL or local filesystem path)
directly; see `app/reporting/file_storage.py`'s own docstring.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from fastapi.responses import FileResponse, RedirectResponse

from app.api.deps import (
    PageParams,
    TenantContext,
    get_analytics_service,
    get_authorization_service,
    get_current_user,
    get_dashboard_service,
    get_file_storage,
    get_report_generation_service,
    get_report_repository,
    get_scheduled_report_service,
    get_tenant_context,
    raise_if_denied,
    request_context,
    require_permission,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.core.responses import ErrorResponse, Page, PageMeta
from app.db.enums import ReportStatus, ReportType
from app.models.identity import User
from app.models.reports import Report, ScheduledReport
from app.reporting.catalog import REPORT_TYPE_DESCRIPTIONS, REPORT_TYPE_TITLES
from app.reporting.file_storage import FileStorage, LocalFileStorage
from app.repositories.interfaces import ReportRepository
from app.schemas.reports import (
    AIDashboardResponse,
    BranchSummaryResponse,
    CustomerDashboardResponse,
    DateRangeParams,
    DiseaseTrendPointResponse,
    EmployeeProductivityPointResponse,
    ExecutiveDashboardResponse,
    FinancialDashboardResponse,
    get_date_range_params,
    GrowthTrendPointResponse,
    InventoryDashboardResponse,
    InventoryTrendPointResponse,
    KpiSummaryResponse,
    NurseryDashboardResponse,
    PlantDashboardResponse,
    PlantHealthTrendPointResponse,
    ReportCatalogEntryResponse,
    ReportCreateRequest,
    ReportResponse,
    RevenueTrendPointResponse,
    RunDueResponse,
    RunDueResultResponse,
    SalesDashboardResponse,
    SalesForecastPointResponse,
    ScheduledReportCreateRequest,
    ScheduledReportResponse,
    ScheduledReportUpdateRequest,
)
from app.services.analytics_service import AnalyticsService
from app.services.authorization_service import AuthorizationDecision, AuthorizationService
from app.services.dashboard_service import DashboardService
from app.services.report_generation_service import ReportGenerationService
from app.services.scheduled_report_service import ScheduledReportService

router = APIRouter()

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Missing permission or cross-tenant/cross-branch access"},
    404: {"model": ErrorResponse, "description": "Not found"},
    422: {"model": ErrorResponse, "description": "Validation failed"},
}


# ==============================================================================
# Shared authorization helpers
# ==============================================================================


async def _authorize_branch_or_org(
    *, branch_id: uuid.UUID | None, permission: str, request: Request, user: User, tenant: TenantContext,
    authz: AuthorizationService,
) -> uuid.UUID:
    """
    Shared by every dashboard/analytics route's optional `?branch_id=`
    query param and by report/scheduled-report creation's optional body
    `branch_id`. Mirrors `app/api/routes/inventory.py`'s own
    `_report_authorize` helper exactly, including its behavior when
    `branch_id` is omitted: `AuthorizationService.authorize` only
    enforces the branch-membership check when `target_branch_id` is
    actually supplied (see that method's own docstring on the
    Nursery -> Branch -> Resource order), so an org-wide request
    (`branch_id=None`) is authorized purely on the `permission` check
    against the caller's own org -- the same "omit branch_id to see/act
    on everything your permission allows" behavior every other report-
    style endpoint in this codebase (inventory summary, waste report,
    transfer report, ...) already has. `target_nursery_id` is always
    `tenant.org_id`, never a client-supplied value.

    Returns the caller's own resolved `nursery_id` (guaranteed non-`None`
    at this point) so every call site can use the return value instead of
    `tenant.org_id` directly -- gives mypy a real, narrowed `uuid.UUID`
    instead of `uuid.UUID | None` at every one of the ~20 call sites below,
    without each of them repeating its own `if nursery_id is None: ...`
    guard.
    """
    if tenant.org_id is None:
        raise ValidationError("You must belong to an organization to access reports.")
    decision = await authz.authorize(
        user=user, permission=permission, resource_type="report",
        target_nursery_id=tenant.org_id, target_branch_id=branch_id, context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)
    return tenant.org_id


async def _authorize_report(
    *, report_id: uuid.UUID, permission: str, request: Request, user: User,
    report_repo: ReportRepository, authz: AuthorizationService,
) -> Report:
    """Fetch-then-authorize, identical shape to `customers.py`'s `_authorize_customer` -- a genuinely nonexistent id is a 404; an existing report belonging to another org/branch is a 403 (cross-tenant/cross-branch), not a 404 -- consistent with every other by-id resource route in this codebase."""
    report = await report_repo.get_by_id(report_id)
    if report is None:
        raise NotFoundError(f"Report {report_id} not found.")
    decision = await authz.authorize(
        user=user, permission=permission, resource_type="report", resource_id=report.id,
        target_nursery_id=report.nursery_id, target_branch_id=report.branch_id, context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)
    return report


async def _authorize_scheduled(
    *, scheduled_id: uuid.UUID, permission: str, request: Request, user: User,
    scheduled_service: ScheduledReportService, authz: AuthorizationService,
) -> ScheduledReport:
    scheduled = await scheduled_service.get(scheduled_id)
    if scheduled is None:
        raise NotFoundError(f"Scheduled report {scheduled_id} not found.")
    decision = await authz.authorize(
        user=user, permission=permission, resource_type="scheduled_report", resource_id=scheduled.id,
        target_nursery_id=scheduled.nursery_id, target_branch_id=scheduled.branch_id, context=request_context(request),
    )
    if not decision.allowed:
        raise raise_if_denied(decision)
    return scheduled


def _report_response(report: Report) -> ReportResponse:
    """`download_url` is a stable API reference (`/reports/{id}/download`), never the raw `Report.file_url` -- see this module's own docstring and `app/reporting/file_storage.py`'s. Only present once the report is actually complete."""
    download_url = f"/reports/{report.id}/download" if report.status == ReportStatus.COMPLETE else None
    return ReportResponse(
        id=report.id, nursery_id=report.nursery_id, branch_id=report.branch_id, report_type=report.report_type,
        format=report.format, status=report.status, filters=report.filters, download_url=download_url,
        requested_by_user_id=report.requested_by_user_id, created_at=report.created_at, completed_at=report.completed_at,
    )


# ==============================================================================
# Dashboards
# ==============================================================================


@router.get(
    "/dashboards/executive", response_model=ExecutiveDashboardResponse, responses=_ERROR_RESPONSES,
    summary="Executive Dashboard -- org-wide revenue/plant/disease rollup across every branch",
)
async def executive_dashboard(
    request: Request, user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    authz: AuthorizationService = Depends(get_authorization_service),
    service: DashboardService = Depends(get_dashboard_service),
) -> ExecutiveDashboardResponse:
    nursery_id = await _authorize_branch_or_org(branch_id=None, permission="reports:read", request=request, user=user, tenant=tenant, authz=authz)
    data = await service.executive_dashboard(nursery_id)
    return ExecutiveDashboardResponse(**data)


@router.get(
    "/dashboards/nursery", response_model=NurseryDashboardResponse, responses=_ERROR_RESPONSES,
    summary="Nursery Dashboard -- org-wide plant/branch/employee/stock counts",
)
async def nursery_dashboard(
    request: Request, user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    authz: AuthorizationService = Depends(get_authorization_service),
    service: DashboardService = Depends(get_dashboard_service),
) -> NurseryDashboardResponse:
    nursery_id = await _authorize_branch_or_org(branch_id=None, permission="reports:read", request=request, user=user, tenant=tenant, authz=authz)
    data = await service.nursery_dashboard(nursery_id)
    return NurseryDashboardResponse(nursery_id=nursery_id, **{k: v for k, v in data.items() if k != "nursery_id"})


@router.get(
    "/dashboards/branch/{branch_id}", response_model=BranchSummaryResponse, responses=_ERROR_RESPONSES,
    summary="Branch Dashboard -- one branch's revenue/at-risk-plant/low-stock/disease summary",
)
async def branch_dashboard(
    branch_id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), authz: AuthorizationService = Depends(get_authorization_service),
    service: DashboardService = Depends(get_dashboard_service),
) -> BranchSummaryResponse:
    nursery_id = await _authorize_branch_or_org(branch_id=branch_id, permission="reports:read", request=request, user=user, tenant=tenant, authz=authz)
    data = await service.branch_dashboard(nursery_id, branch_id)
    if not data:
        raise NotFoundError(f"Branch {branch_id} not found.")
    return BranchSummaryResponse(**data)


@router.get(
    "/dashboards/plant", response_model=PlantDashboardResponse, responses=_ERROR_RESPONSES,
    summary="Plant Dashboard -- plant counts by status and by species",
)
async def plant_dashboard(
    request: Request, branch_id: uuid.UUID | None = Query(None), user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), authz: AuthorizationService = Depends(get_authorization_service),
    service: DashboardService = Depends(get_dashboard_service),
) -> PlantDashboardResponse:
    nursery_id = await _authorize_branch_or_org(branch_id=branch_id, permission="reports:read", request=request, user=user, tenant=tenant, authz=authz)
    data = await service.plant_dashboard(nursery_id, branch_id)
    return PlantDashboardResponse(
        by_status={k.value if hasattr(k, "value") else k: v for k, v in data.get("by_status", {}).items()},
        by_species=data.get("by_species", []),
    )


@router.get(
    "/dashboards/inventory", response_model=InventoryDashboardResponse, responses=_ERROR_RESPONSES,
    summary="Inventory Dashboard -- on-hand units, valuation, low-stock items",
)
async def inventory_dashboard(
    request: Request, branch_id: uuid.UUID | None = Query(None), user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), authz: AuthorizationService = Depends(get_authorization_service),
    service: DashboardService = Depends(get_dashboard_service),
) -> InventoryDashboardResponse:
    nursery_id = await _authorize_branch_or_org(branch_id=branch_id, permission="reports:read", request=request, user=user, tenant=tenant, authz=authz)
    data = await service.inventory_dashboard(nursery_id, branch_id)
    return InventoryDashboardResponse(**data)


@router.get(
    "/dashboards/sales", response_model=SalesDashboardResponse, responses=_ERROR_RESPONSES,
    summary="Sales Dashboard -- transaction count/total/average for an optional date range",
)
async def sales_dashboard(
    request: Request, branch_id: uuid.UUID | None = Query(None), date_range: DateRangeParams = Depends(get_date_range_params),
    user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    authz: AuthorizationService = Depends(get_authorization_service), service: DashboardService = Depends(get_dashboard_service),
) -> SalesDashboardResponse:
    nursery_id = await _authorize_branch_or_org(branch_id=branch_id, permission="reports:read", request=request, user=user, tenant=tenant, authz=authz)
    data = await service.sales_dashboard(nursery_id, branch_id, date_range.date_from, date_range.date_to)
    return SalesDashboardResponse(**data)


@router.get(
    "/dashboards/customer", response_model=CustomerDashboardResponse, responses=_ERROR_RESPONSES,
    summary="Customer Dashboard -- total/repeat customer counts and top customers by lifetime value",
)
async def customer_dashboard(
    request: Request, branch_id: uuid.UUID | None = Query(None), user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), authz: AuthorizationService = Depends(get_authorization_service),
    service: DashboardService = Depends(get_dashboard_service),
) -> CustomerDashboardResponse:
    nursery_id = await _authorize_branch_or_org(branch_id=branch_id, permission="reports:read", request=request, user=user, tenant=tenant, authz=authz)
    data = await service.customer_dashboard(nursery_id, branch_id)
    return CustomerDashboardResponse(**data)


@router.get(
    "/dashboards/ai", response_model=AIDashboardResponse, responses=_ERROR_RESPONSES,
    summary="AI Dashboard -- at-risk plants and prediction accuracy",
)
async def ai_dashboard(
    request: Request, branch_id: uuid.UUID | None = Query(None), user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), authz: AuthorizationService = Depends(get_authorization_service),
    service: DashboardService = Depends(get_dashboard_service),
) -> AIDashboardResponse:
    nursery_id = await _authorize_branch_or_org(branch_id=branch_id, permission="reports:read", request=request, user=user, tenant=tenant, authz=authz)
    data = await service.ai_dashboard(nursery_id, branch_id)
    return AIDashboardResponse(**data)


@router.get(
    "/dashboards/financial", response_model=FinancialDashboardResponse, responses=_ERROR_RESPONSES,
    summary="Financial Dashboard -- revenue, estimated COGS/gross profit/margin, outstanding invoices",
)
async def financial_dashboard(
    request: Request, branch_id: uuid.UUID | None = Query(None), date_range: DateRangeParams = Depends(get_date_range_params),
    user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    authz: AuthorizationService = Depends(get_authorization_service), service: DashboardService = Depends(get_dashboard_service),
) -> FinancialDashboardResponse:
    nursery_id = await _authorize_branch_or_org(branch_id=branch_id, permission="reports:read", request=request, user=user, tenant=tenant, authz=authz)
    data = await service.financial_dashboard(nursery_id, branch_id, date_range.date_from, date_range.date_to)
    return FinancialDashboardResponse(**data)


# ==============================================================================
# Analytics
# ==============================================================================


@router.get(
    "/analytics/kpi-summary", response_model=KpiSummaryResponse, responses=_ERROR_RESPONSES,
    summary="Headline KPI summary -- revenue MTD, active/at-risk plant counts, low stock, open disease reports",
)
async def kpi_summary(
    request: Request, branch_id: uuid.UUID | None = Query(None), user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), authz: AuthorizationService = Depends(get_authorization_service),
    service: AnalyticsService = Depends(get_analytics_service),
) -> KpiSummaryResponse:
    nursery_id = await _authorize_branch_or_org(branch_id=branch_id, permission="reports:read", request=request, user=user, tenant=tenant, authz=authz)
    data = await service.kpi_summary(nursery_id, branch_id)
    return KpiSummaryResponse(**data)


@router.get(
    "/analytics/revenue-trend", response_model=list[RevenueTrendPointResponse], responses=_ERROR_RESPONSES,
    summary="Daily revenue/transaction-count trend over a date range (defaults to trailing 90 days)",
)
async def revenue_trend(
    request: Request, branch_id: uuid.UUID | None = Query(None), date_range: DateRangeParams = Depends(get_date_range_params),
    user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    authz: AuthorizationService = Depends(get_authorization_service), service: AnalyticsService = Depends(get_analytics_service),
) -> list[RevenueTrendPointResponse]:
    nursery_id = await _authorize_branch_or_org(branch_id=branch_id, permission="reports:read", request=request, user=user, tenant=tenant, authz=authz)
    rows = await service.revenue_trend(nursery_id, branch_id, date_range.date_from, date_range.date_to)
    return [RevenueTrendPointResponse(**r) for r in rows]


@router.get(
    "/analytics/growth-trend", response_model=list[GrowthTrendPointResponse], responses=_ERROR_RESPONSES,
    summary="Weekly average plant height trend, optionally filtered by species",
)
async def growth_trend(
    request: Request, branch_id: uuid.UUID | None = Query(None), species_id: uuid.UUID | None = Query(None),
    date_range: DateRangeParams = Depends(get_date_range_params), user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), authz: AuthorizationService = Depends(get_authorization_service),
    service: AnalyticsService = Depends(get_analytics_service),
) -> list[GrowthTrendPointResponse]:
    nursery_id = await _authorize_branch_or_org(branch_id=branch_id, permission="reports:read", request=request, user=user, tenant=tenant, authz=authz)
    rows = await service.growth_trend(nursery_id, branch_id, species_id, date_range.date_from, date_range.date_to)
    return [GrowthTrendPointResponse(**r) for r in rows]


@router.get(
    "/analytics/inventory-trend", response_model=list[InventoryTrendPointResponse], responses=_ERROR_RESPONSES,
    summary="Daily net stock-movement quantity trend by movement type",
)
async def inventory_trend(
    request: Request, branch_id: uuid.UUID | None = Query(None), date_range: DateRangeParams = Depends(get_date_range_params),
    user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    authz: AuthorizationService = Depends(get_authorization_service), service: AnalyticsService = Depends(get_analytics_service),
) -> list[InventoryTrendPointResponse]:
    nursery_id = await _authorize_branch_or_org(branch_id=branch_id, permission="reports:read", request=request, user=user, tenant=tenant, authz=authz)
    rows = await service.inventory_trend(nursery_id, branch_id, date_range.date_from, date_range.date_to)
    return [InventoryTrendPointResponse(**r) for r in rows]


@router.get(
    "/analytics/plant-health-trend", response_model=list[PlantHealthTrendPointResponse], responses=_ERROR_RESPONSES,
    summary="Weekly plant health-status distribution trend",
)
async def plant_health_trend(
    request: Request, branch_id: uuid.UUID | None = Query(None), date_range: DateRangeParams = Depends(get_date_range_params),
    user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    authz: AuthorizationService = Depends(get_authorization_service), service: AnalyticsService = Depends(get_analytics_service),
) -> list[PlantHealthTrendPointResponse]:
    nursery_id = await _authorize_branch_or_org(branch_id=branch_id, permission="reports:read", request=request, user=user, tenant=tenant, authz=authz)
    rows = await service.plant_health_trend(nursery_id, branch_id, date_range.date_from, date_range.date_to)
    return [PlantHealthTrendPointResponse(**r) for r in rows]


@router.get(
    "/analytics/sales-forecast", response_model=list[SalesForecastPointResponse], responses=_ERROR_RESPONSES,
    summary="Persisted AI revenue-forecast predictions -- reads previously-generated predictions, never runs a model inline",
)
async def sales_forecast(
    request: Request, branch_id: uuid.UUID | None = Query(None), user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), authz: AuthorizationService = Depends(get_authorization_service),
    service: AnalyticsService = Depends(get_analytics_service),
) -> list[SalesForecastPointResponse]:
    nursery_id = await _authorize_branch_or_org(branch_id=branch_id, permission="reports:read", request=request, user=user, tenant=tenant, authz=authz)
    rows = await service.sales_forecast(nursery_id, branch_id)
    return [SalesForecastPointResponse(**r) for r in rows]


@router.get(
    "/analytics/disease-trend", response_model=list[DiseaseTrendPointResponse], responses=_ERROR_RESPONSES,
    summary="Weekly disease-report count trend by severity",
)
async def disease_trend(
    request: Request, branch_id: uuid.UUID | None = Query(None), date_range: DateRangeParams = Depends(get_date_range_params),
    user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    authz: AuthorizationService = Depends(get_authorization_service), service: AnalyticsService = Depends(get_analytics_service),
) -> list[DiseaseTrendPointResponse]:
    nursery_id = await _authorize_branch_or_org(branch_id=branch_id, permission="reports:read", request=request, user=user, tenant=tenant, authz=authz)
    rows = await service.disease_trend(nursery_id, branch_id, date_range.date_from, date_range.date_to)
    return [DiseaseTrendPointResponse(**r) for r in rows]


@router.get(
    "/analytics/customer-analytics", response_model=CustomerDashboardResponse, responses=_ERROR_RESPONSES,
    summary="Customer analytics -- identical shape to the Customer Dashboard, exposed under /analytics for API symmetry",
)
async def customer_analytics(
    request: Request, branch_id: uuid.UUID | None = Query(None), user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), authz: AuthorizationService = Depends(get_authorization_service),
    service: AnalyticsService = Depends(get_analytics_service),
) -> CustomerDashboardResponse:
    nursery_id = await _authorize_branch_or_org(branch_id=branch_id, permission="reports:read", request=request, user=user, tenant=tenant, authz=authz)
    data = await service.customer_analytics(nursery_id, branch_id)
    return CustomerDashboardResponse(**data)


@router.get(
    "/analytics/employee-productivity", response_model=list[EmployeeProductivityPointResponse], responses=_ERROR_RESPONSES,
    summary="Per-employee sale count/total over a date range, ranked by total sales",
)
async def employee_productivity(
    request: Request, branch_id: uuid.UUID | None = Query(None), date_range: DateRangeParams = Depends(get_date_range_params),
    user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    authz: AuthorizationService = Depends(get_authorization_service), service: AnalyticsService = Depends(get_analytics_service),
) -> list[EmployeeProductivityPointResponse]:
    nursery_id = await _authorize_branch_or_org(branch_id=branch_id, permission="reports:read", request=request, user=user, tenant=tenant, authz=authz)
    rows = await service.employee_productivity(nursery_id, branch_id, date_range.date_from, date_range.date_to)
    return [EmployeeProductivityPointResponse(**r) for r in rows]


@router.get(
    "/analytics/branch-performance", response_model=list[BranchSummaryResponse], responses=_ERROR_RESPONSES,
    summary="Every branch's dashboard summary, ranked by month-to-date revenue -- org-wide only, no branch_id filter",
)
async def branch_performance(
    request: Request, user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    authz: AuthorizationService = Depends(get_authorization_service), service: AnalyticsService = Depends(get_analytics_service),
) -> list[BranchSummaryResponse]:
    nursery_id = await _authorize_branch_or_org(branch_id=None, permission="reports:read", request=request, user=user, tenant=tenant, authz=authz)
    rows = await service.branch_performance(nursery_id)
    return [BranchSummaryResponse(**r) for r in rows]


# ==============================================================================
# Report catalog
# ==============================================================================


@router.get(
    "/reports/catalog", response_model=list[ReportCatalogEntryResponse], responses=_ERROR_RESPONSES,
    summary="Every generatable report type with its display title and description",
)
async def report_catalog(
    _decision: AuthorizationDecision = Depends(require_permission("reports:read")),
) -> list[ReportCatalogEntryResponse]:
    return [
        ReportCatalogEntryResponse(report_type=rt, title=REPORT_TYPE_TITLES[rt], description=REPORT_TYPE_DESCRIPTIONS[rt])
        for rt in ReportType
    ]


# ==============================================================================
# Scheduled reports
#
# Registered BEFORE the parameterized `/reports/{report_id}` routes below
# (same FastAPI/Starlette route-matching rule `app/api/routes/inventory.py`'s
# own module docstring documents, and the exact bug Module 7 already
# caught and fixed once for `/versions/compare` vs `/versions/{version}`):
# every static `/reports/scheduled*` path here would otherwise be
# swallowed by `/reports/{report_id}` (which matches ANY single path
# segment, including the literal string "scheduled", before Pydantic ever
# gets a chance to reject it as an invalid UUID).
# ==============================================================================


@router.get(
    "/reports/scheduled", response_model=Page[ScheduledReportResponse], responses=_ERROR_RESPONSES,
    summary="Saved/recurring report schedules for the caller's organization",
)
async def list_scheduled_reports(
    request: Request, page_params: PageParams = Depends(), user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), authz: AuthorizationService = Depends(get_authorization_service),
    scheduled_service: ScheduledReportService = Depends(get_scheduled_report_service),
) -> Page[ScheduledReportResponse]:
    nursery_id = await _authorize_branch_or_org(branch_id=None, permission="reports:read", request=request, user=user, tenant=tenant, authz=authz)
    all_rows = await scheduled_service.list_for_org(nursery_id)
    total = len(all_rows)
    page_rows = all_rows[page_params.offset : page_params.offset + page_params.page_size]
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[ScheduledReportResponse.model_validate(s) for s in page_rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


@router.post(
    "/reports/scheduled", response_model=ScheduledReportResponse, status_code=status.HTTP_201_CREATED, responses=_ERROR_RESPONSES,
    summary="Create a saved/recurring report schedule",
)
async def create_scheduled_report(
    body: ScheduledReportCreateRequest, request: Request, user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), authz: AuthorizationService = Depends(get_authorization_service),
    scheduled_service: ScheduledReportService = Depends(get_scheduled_report_service),
) -> ScheduledReportResponse:
    nursery_id = await _authorize_branch_or_org(branch_id=body.branch_id, permission="reports:export", request=request, user=user, tenant=tenant, authz=authz)
    scheduled = await scheduled_service.create(
        nursery_id=nursery_id, branch_id=body.branch_id, name=body.name, report_type=body.report_type,
        format=body.format, filters=body.filters.to_json_dict(), frequency=body.frequency,
        created_by_user_id=user.id, next_run_at=body.next_run_at,
    )
    return ScheduledReportResponse.model_validate(scheduled)


@router.post(
    "/reports/scheduled/run-due", response_model=RunDueResponse, responses=_ERROR_RESPONSES,
    summary="Execute every due, active schedule for the caller's organization -- the on-demand substitute for a real cron trigger (see ScheduledReportService's own docstring)",
)
async def run_due_scheduled_reports(
    request: Request, limit: int = Query(100, ge=1, le=500), user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), authz: AuthorizationService = Depends(get_authorization_service),
    scheduled_service: ScheduledReportService = Depends(get_scheduled_report_service),
) -> RunDueResponse:
    """
    Delegates to `ScheduledReportService.run_due_for_org` -- NOT the
    plain `run_due` (that method sweeps every organization's due
    schedules and is meant for a single external, org-agnostic cron
    trigger; calling it from a tenant-scoped route would execute, and
    advance the `next_run_at` of, other organizations' schedules as a
    side effect -- see both methods' own docstrings).
    """
    nursery_id = await _authorize_branch_or_org(branch_id=None, permission="reports:export", request=request, user=user, tenant=tenant, authz=authz)
    results = await scheduled_service.run_due_for_org(nursery_id, limit=limit)
    executed = [RunDueResultResponse(**r) for r in results]
    return RunDueResponse(executed_count=len(executed), results=executed)


@router.get(
    "/reports/scheduled/{scheduled_id}", response_model=ScheduledReportResponse, responses=_ERROR_RESPONSES,
    summary="A single saved report schedule",
)
async def get_scheduled_report(
    scheduled_id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    authz: AuthorizationService = Depends(get_authorization_service),
    scheduled_service: ScheduledReportService = Depends(get_scheduled_report_service),
) -> ScheduledReportResponse:
    scheduled = await _authorize_scheduled(scheduled_id=scheduled_id, permission="reports:read", request=request, user=user, scheduled_service=scheduled_service, authz=authz)
    return ScheduledReportResponse.model_validate(scheduled)


@router.patch(
    "/reports/scheduled/{scheduled_id}", response_model=ScheduledReportResponse, responses=_ERROR_RESPONSES,
    summary="Update a saved report schedule's name/filters/frequency/next_run_at (partial update)",
)
async def update_scheduled_report(
    scheduled_id: uuid.UUID, body: ScheduledReportUpdateRequest, request: Request, user: User = Depends(get_current_user),
    authz: AuthorizationService = Depends(get_authorization_service),
    scheduled_service: ScheduledReportService = Depends(get_scheduled_report_service),
) -> ScheduledReportResponse:
    scheduled = await _authorize_scheduled(scheduled_id=scheduled_id, permission="reports:export", request=request, user=user, scheduled_service=scheduled_service, authz=authz)
    filters_dict = body.filters.to_json_dict() if body.filters is not None else None
    await scheduled_service.update(
        scheduled, name=body.name, filters=filters_dict, frequency=body.frequency, next_run_at=body.next_run_at
    )
    return ScheduledReportResponse.model_validate(scheduled)


@router.post(
    "/reports/scheduled/{scheduled_id}/pause", response_model=ScheduledReportResponse, responses=_ERROR_RESPONSES,
    summary="Pause a schedule -- a paused schedule is never picked up by run-due",
)
async def pause_scheduled_report(
    scheduled_id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    authz: AuthorizationService = Depends(get_authorization_service),
    scheduled_service: ScheduledReportService = Depends(get_scheduled_report_service),
) -> ScheduledReportResponse:
    scheduled = await _authorize_scheduled(scheduled_id=scheduled_id, permission="reports:export", request=request, user=user, scheduled_service=scheduled_service, authz=authz)
    await scheduled_service.set_active(scheduled, is_active=False)
    return ScheduledReportResponse.model_validate(scheduled)


@router.post(
    "/reports/scheduled/{scheduled_id}/resume", response_model=ScheduledReportResponse, responses=_ERROR_RESPONSES,
    summary="Resume a paused schedule",
)
async def resume_scheduled_report(
    scheduled_id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    authz: AuthorizationService = Depends(get_authorization_service),
    scheduled_service: ScheduledReportService = Depends(get_scheduled_report_service),
) -> ScheduledReportResponse:
    scheduled = await _authorize_scheduled(scheduled_id=scheduled_id, permission="reports:export", request=request, user=user, scheduled_service=scheduled_service, authz=authz)
    await scheduled_service.set_active(scheduled, is_active=True)
    return ScheduledReportResponse.model_validate(scheduled)


@router.delete(
    "/reports/scheduled/{scheduled_id}", response_model=None, status_code=status.HTTP_204_NO_CONTENT, responses=_ERROR_RESPONSES,
    summary="Delete a saved report schedule -- a deleted schedule can never execute again",
)
async def delete_scheduled_report(
    scheduled_id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    authz: AuthorizationService = Depends(get_authorization_service),
    scheduled_service: ScheduledReportService = Depends(get_scheduled_report_service),
) -> None:
    scheduled = await _authorize_scheduled(scheduled_id=scheduled_id, permission="reports:export", request=request, user=user, scheduled_service=scheduled_service, authz=authz)
    await scheduled_service.delete(scheduled)


# ==============================================================================
# Report generation, status, download, history
# ==============================================================================


@router.post(
    "/reports", response_model=ReportResponse, status_code=status.HTTP_202_ACCEPTED, responses=_ERROR_RESPONSES,
    summary="Generate a report -- runs in the background; poll GET /reports/{id} for status",
)
async def create_report(
    body: ReportCreateRequest, background_tasks: BackgroundTasks, request: Request,
    user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    authz: AuthorizationService = Depends(get_authorization_service),
    report_repo: ReportRepository = Depends(get_report_repository),
    generation_service: ReportGenerationService = Depends(get_report_generation_service),
) -> ReportResponse:
    nursery_id = await _authorize_branch_or_org(branch_id=body.branch_id, permission="reports:export", request=request, user=user, tenant=tenant, authz=authz)
    report = Report(
        nursery_id=nursery_id, branch_id=body.branch_id, report_type=body.report_type, format=body.format,
        filters=body.filters.to_json_dict(), status=ReportStatus.PENDING, requested_by_user_id=user.id,
    )
    report = await report_repo.add(report)
    # Runs after the response is sent -- `ReportGenerationService.generate`
    # never raises back to its caller (see that method's own docstring),
    # so a failure during generation is persisted onto the `Report` row
    # and published as `ReportFailed`, never surfaced as a 500 here.
    background_tasks.add_task(generation_service.generate, report)
    return _report_response(report)


@router.get(
    "/reports/{report_id}", response_model=ReportResponse, responses=_ERROR_RESPONSES,
    summary="Report status/metadata -- poll this after POST /reports until status is complete or failed",
)
async def get_report_status(
    report_id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    authz: AuthorizationService = Depends(get_authorization_service),
    report_repo: ReportRepository = Depends(get_report_repository),
) -> ReportResponse:
    report = await _authorize_report(report_id=report_id, permission="reports:read", request=request, user=user, report_repo=report_repo, authz=authz)
    return _report_response(report)


@router.get(
    "/reports/{report_id}/download", responses=_ERROR_RESPONSES,
    summary="Download a completed report's file -- redirects to the storage URL (Cloudinary) or streams it directly (local storage fallback)",
)
async def download_report(
    report_id: uuid.UUID, request: Request, user: User = Depends(get_current_user),
    authz: AuthorizationService = Depends(get_authorization_service),
    report_repo: ReportRepository = Depends(get_report_repository),
    file_storage: FileStorage = Depends(get_file_storage),
):
    report = await _authorize_report(report_id=report_id, permission="reports:read", request=request, user=user, report_repo=report_repo, authz=authz)
    if report.status != ReportStatus.COMPLETE or not report.file_url:
        raise NotFoundError(f"Report {report_id} has no downloadable file yet.")
    if report.file_url.startswith("http://") or report.file_url.startswith("https://"):
        return RedirectResponse(url=report.file_url)
    # Local-storage fallback -- `report.file_url` is `/reports/files/{filename}`
    # (see `LocalFileStorage.upload`); never trust it as a raw filesystem
    # path -- `LocalFileStorage.resolve` re-derives and validates the real
    # path, rejecting any `..`/path-separator tampering.
    if isinstance(file_storage, LocalFileStorage):
        filename = report.file_url.rsplit("/", 1)[-1]
        resolved = file_storage.resolve(filename)
        if resolved is None:
            raise NotFoundError(f"Report {report_id}'s file could not be located.")
        return FileResponse(path=resolved, filename=filename)
    raise NotFoundError(f"Report {report_id} has no downloadable file yet.")


@router.get(
    "/reports", response_model=Page[ReportResponse], responses=_ERROR_RESPONSES,
    summary="Report generation history -- the caller's organization's generated reports, newest first",
)
async def list_reports(
    request: Request, page_params: PageParams = Depends(), report_type: ReportType | None = Query(None),
    branch_id: uuid.UUID | None = Query(None), user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context), authz: AuthorizationService = Depends(get_authorization_service),
    report_repo: ReportRepository = Depends(get_report_repository),
) -> Page[ReportResponse]:
    nursery_id = await _authorize_branch_or_org(branch_id=branch_id, permission="reports:read", request=request, user=user, tenant=tenant, authz=authz)
    rows, total = await report_repo.list_for_org(
        nursery_id, report_type=report_type, branch_id=branch_id, offset=page_params.offset, limit=page_params.page_size
    )
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[_report_response(r) for r in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )
