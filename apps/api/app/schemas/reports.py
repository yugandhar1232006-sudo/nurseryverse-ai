"""
Pydantic request/response DTOs for Phase 6 Module 12 (Reports & Analytics).

Dashboard/analytics response models mirror `ReportingRepository`'s own
return shapes field-for-field (see app/repositories/interfaces.py's
Protocol and its Fake/SqlAlchemy implementations) -- this file adds no new
data shapes of its own, only typed envelopes around what that layer
already returns, so OpenAPI documents the real response instead of an
untyped `dict`.

`ReportFilters` is this module's one piece of real validation logic: every
report-generation/scheduled-report request accepts a small set of TYPED
optional filter fields (never an arbitrary client-supplied JSON blob) so
FastAPI/Pydantic can reject a malformed `date_from`/UUID before a route
handler ever runs, and so `date_from <= date_to` is enforced in exactly
one place.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.enums import ReportFormat, ReportScheduleFrequency, ReportStatus, ReportType

# --------------------------------------------------------------------------
# Shared filter block
# --------------------------------------------------------------------------


class ReportFilters(BaseModel):
    """
    Every field here is optional -- a given `ReportType` only consumes the
    subset relevant to it (see `ReportGenerationService`'s own per-type
    provider methods for exactly which). Unused fields are simply ignored
    by whichever provider runs, never an error -- callers are not expected
    to know each report type's exact filter subset up front.
    """

    species_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    customer_type: str | None = Field(default=None, max_length=20)
    status: str | None = Field(default=None, max_length=30, description="Report-type-specific status filter (e.g. a PlantStatus/DiseaseReportStatus/EmployeeStatus value)")
    category: str | None = Field(default=None, max_length=30, description="NotificationCategory value, for Notification Reports")
    prediction_type: str | None = Field(default=None, max_length=30, description="AIPredictionType value, for AI Prediction Reports")
    low_stock_only: bool = False
    date_from: datetime | None = None
    date_to: datetime | None = None

    @model_validator(mode="after")
    def _validate_date_range(self) -> "ReportFilters":
        if self.date_from is not None and self.date_to is not None and self.date_from > self.date_to:
            raise ValueError("date_from must not be after date_to.")
        return self

    def to_json_dict(self) -> dict[str, Any]:
        """Storage shape for `Report.filters`/`ScheduledReport.filters` (JSON column) -- UUIDs/datetimes as strings, unset fields omitted, matching what `ReportGenerationService._parse_uuid`/`_parse_datetime` expect to read back."""
        data = self.model_dump(exclude_none=True)
        return {k: (v.isoformat() if isinstance(v, datetime) else str(v) if isinstance(v, uuid.UUID) else v) for k, v in data.items()}


class DateRangeParams:
    """
    Shared `?date_from=&date_to=` query-parameter parsing for the analytics
    trend endpoints -- same `PageParams`-style dependency-class shape
    app/api/deps.py already established, kept here (not deps.py) since
    it's Module 12-specific and only analytics routes use it. Un-supplied
    bounds are left `None` -- `AnalyticsService`'s own `_default_range`
    fills in the trailing-90-days default, so this class's only job is
    rejecting an inverted range early.
    """

    def __init__(self, date_from: datetime | None = None, date_to: datetime | None = None) -> None:
        if date_from is not None and date_to is not None and date_from > date_to:
            from app.core.exceptions import ValidationError

            raise ValidationError("date_from must not be after date_to.", context={"date_from": str(date_from), "date_to": str(date_to)})
        self.date_from = date_from
        self.date_to = date_to


def get_date_range_params(date_from: datetime | None = None, date_to: datetime | None = None) -> DateRangeParams:
    """
    Plain-function wrapper around `DateRangeParams` -- routes depend on
    THIS (`Depends(get_date_range_params)`), never bare `Depends()` off
    the `DateRangeParams` class annotation directly. Reason: this module
    has `from __future__ import annotations` (needed elsewhere in this
    file for `ReportFilters`'s/`ScheduledReportCreateRequest`'s own
    `-> "ReportFilters"`-style self-referencing return types), which turns
    every annotation in the module -- including `DateRangeParams.__init__`'s
    `date_from: datetime | None` -- into a string FastAPI must resolve at
    route-registration time. FastAPI resolves those forward refs using
    `call.__globals__`; for an ordinary function `call.__globals__` is
    this module's own globals (where `datetime` is imported, so resolution
    succeeds), but for a bare *class* used as the inferred dependency
    callable, `getattr(cls, "__globals__", {})` has no such attribute and
    silently falls back to an EMPTY namespace -- which raised
    `pydantic.errors.PydanticUndefinedAnnotation: name 'datetime' is not
    defined` when routes first tried `date_range: DateRangeParams = Depends()`
    (caught by this module's own live-uvicorn/router-import smoke test,
    not by a raw `py_compile`, since the failure only happens when FastAPI
    actually builds each route's dependant graph at import time).
    """
    return DateRangeParams(date_from=date_from, date_to=date_to)


# --------------------------------------------------------------------------
# Dashboards
# --------------------------------------------------------------------------


class BranchSummaryResponse(BaseModel):
    branch_id: uuid.UUID
    nursery_id: uuid.UUID
    branch_name: str | None = None
    revenue_today: float = 0
    revenue_mtd: float = 0
    at_risk_plant_count: int = 0
    low_stock_count: int = 0
    pending_disease_reports: int = 0
    last_refreshed_at: datetime | None = None


class RevenueTrendPointResponse(BaseModel):
    day: Any
    revenue: float
    sale_count: int


class ExecutiveDashboardResponse(BaseModel):
    revenue_today: float
    revenue_mtd: float
    active_plant_count: int
    at_risk_plant_count: int
    open_disease_reports: int
    branches: list[BranchSummaryResponse]
    revenue_trend: list[RevenueTrendPointResponse]
    last_refreshed_at: datetime | None = None


class NurseryDashboardResponse(BaseModel):
    nursery_id: uuid.UUID
    total_plants: int = 0
    active_plant_count: int = 0
    branch_count: int = 0
    employee_count: int = 0
    low_stock_count: int = 0
    pending_disease_reports: int = 0
    last_refreshed_at: datetime | None = None


class PlantDashboardResponse(BaseModel):
    by_status: dict[str, int]
    by_species: list[dict[str, Any]]


class LowStockItemResponse(BaseModel):
    id: uuid.UUID
    name: str
    quantity: int
    low_stock_threshold: int


class InventoryDashboardResponse(BaseModel):
    total_line_items: int
    total_units_on_hand: int
    total_inventory_value: float
    low_stock_count: int
    low_stock_items: list[LowStockItemResponse]


class SalesDashboardResponse(BaseModel):
    transaction_count: int
    total_sales: float
    average_sale_value: float


class CustomerLifetimeValueResponse(BaseModel):
    customer_id: uuid.UUID
    nursery_id: uuid.UUID
    branch_id: uuid.UUID | None = None
    customer_name: str
    total_orders: int
    total_spent: float
    first_purchase_at: datetime | None = None
    last_purchase_at: datetime | None = None


class CustomerDashboardResponse(BaseModel):
    total_customers: int
    repeat_customer_count: int
    repeat_customer_rate: float
    top_customers: list[CustomerLifetimeValueResponse]


class AtRiskPlantResponse(BaseModel):
    plant_id: uuid.UUID
    common_label: str | None = None
    result: dict[str, Any]
    confidence: float | None = None
    created_at: datetime


class AIPredictionAccuracyResponse(BaseModel):
    nursery_id: uuid.UUID
    prediction_type: str
    scored_prediction_count: int
    correct_prediction_count: int
    last_refreshed_at: datetime | None = None


class AIDashboardResponse(BaseModel):
    at_risk_plants: list[AtRiskPlantResponse]
    prediction_accuracy: AIPredictionAccuracyResponse | None = None


class FinancialDashboardResponse(BaseModel):
    revenue: float
    estimated_cogs: float
    estimated_gross_profit: float
    estimated_gross_margin: float
    outstanding_invoice_count: int
    outstanding_invoice_total: float


# --------------------------------------------------------------------------
# Analytics
# --------------------------------------------------------------------------


class KpiSummaryResponse(BaseModel):
    revenue_mtd: float
    active_plant_count: int
    at_risk_plant_count: int
    low_stock_count: int
    open_disease_reports: int


class GrowthTrendPointResponse(BaseModel):
    week: Any
    average_height_cm: float | None = None
    record_count: int


class InventoryTrendPointResponse(BaseModel):
    day: Any
    movement_type: str
    net_quantity_delta: int


class PlantHealthTrendPointResponse(BaseModel):
    week: Any
    health_status: str
    count: int


class DiseaseTrendPointResponse(BaseModel):
    week: Any
    severity: str
    count: int


class SalesForecastPointResponse(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID | None = None
    result: dict[str, Any]
    confidence: float | None = None
    created_at: datetime


class EmployeeProductivityPointResponse(BaseModel):
    user_id: uuid.UUID
    sale_count: int
    total_sales: float


# --------------------------------------------------------------------------
# Report catalog / generation / history
# --------------------------------------------------------------------------


class ReportCatalogEntryResponse(BaseModel):
    report_type: ReportType
    title: str
    description: str


class ReportCreateRequest(BaseModel):
    report_type: ReportType
    format: ReportFormat
    branch_id: uuid.UUID | None = Field(default=None, description="Restricts the report to one branch. Omit for an org-wide report.")
    filters: ReportFilters = Field(default_factory=ReportFilters)


class ReportResponse(BaseModel):
    """
    `download_url` -- not `file_url` -- is the only download reference
    this API ever returns (see `app/reporting/file_storage.py`'s own
    docstring): a stable `/reports/{id}/download` path the download route
    resolves server-side, so a client never sees (or could tamper with) a
    local filesystem path or an unauthenticated third-party URL directly.
    """

    id: uuid.UUID
    nursery_id: uuid.UUID
    branch_id: uuid.UUID | None
    report_type: ReportType
    format: ReportFormat
    status: ReportStatus
    filters: dict[str, Any] | None
    download_url: str | None
    requested_by_user_id: uuid.UUID
    created_at: datetime
    completed_at: datetime | None


# --------------------------------------------------------------------------
# Scheduled reports
# --------------------------------------------------------------------------


class ScheduledReportCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    report_type: ReportType
    format: ReportFormat
    branch_id: uuid.UUID | None = None
    filters: ReportFilters = Field(default_factory=ReportFilters)
    frequency: ReportScheduleFrequency
    next_run_at: datetime = Field(..., description="First run time. Must not be in the past.")

    @model_validator(mode="after")
    def _validate_next_run_at(self) -> "ScheduledReportCreateRequest":
        from datetime import timezone

        now = datetime.now(timezone.utc)
        next_run = self.next_run_at if self.next_run_at.tzinfo else self.next_run_at.replace(tzinfo=timezone.utc)
        if next_run < now:
            raise ValueError("next_run_at must not be in the past.")
        return self


class ScheduledReportUpdateRequest(BaseModel):
    """Partial update -- every field optional; only supplied fields change. `PATCH /reports/scheduled/{id}`."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    filters: ReportFilters | None = None
    frequency: ReportScheduleFrequency | None = None
    next_run_at: datetime | None = None

    @model_validator(mode="after")
    def _validate_next_run_at(self) -> "ScheduledReportUpdateRequest":
        if self.next_run_at is None:
            return self
        from datetime import timezone

        now = datetime.now(timezone.utc)
        next_run = self.next_run_at if self.next_run_at.tzinfo else self.next_run_at.replace(tzinfo=timezone.utc)
        if next_run < now:
            raise ValueError("next_run_at must not be in the past.")
        return self


class ScheduledReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID
    branch_id: uuid.UUID | None
    name: str
    report_type: ReportType
    format: ReportFormat
    filters: dict[str, Any] | None
    frequency: ReportScheduleFrequency
    is_active: bool
    created_by_user_id: uuid.UUID
    next_run_at: datetime
    last_run_at: datetime | None
    created_at: datetime


class RunDueResultResponse(BaseModel):
    scheduled_report_id: uuid.UUID
    report_id: uuid.UUID
    status: str
    next_run_at: datetime


class RunDueResponse(BaseModel):
    executed_count: int
    results: list[RunDueResultResponse]
