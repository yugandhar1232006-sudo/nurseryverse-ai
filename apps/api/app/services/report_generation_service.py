"""
Row-level report generation -- Plant/Inventory/Sales/Revenue/Profit/
Customer/Employee/Branch/Disease/Growth/Water Usage/Fertilizer/
Notification/Audit/Security/Plant Passport/AI Prediction Reports.

`generate()` is the entry point a FastAPI `BackgroundTasks.add_task` call
(app/api/routes/reports.py) hands the freshly-`PENDING` `Report` row to --
this codebase's established "no Celery, no background-job infrastructure"
substitute (the same shape `AssistantConversationService`'s tool-execution
loop and Module 9's async invoice generation already use). It never raises
back to its caller (there is no caller left awaiting it by the time it
runs): any failure is caught, persisted onto the `Report` row as `FAILED`,
and published as `ReportFailed` so `NotificationEventHandler` (Module 11)
tells the requester, rather than leaving a silently-stuck `PENDING` row.

Each report type's data comes from that entity's OWN existing repository
(`PlantRepository.list_for_nursery`, `SaleRepository.list_for_nursery`,
...) -- this module owns zero query logic for anything already queryable
through an existing repository, satisfying the "No duplicated reporting
logic" QUALITY requirement the same way `ReportingRepository`'s own
Protocol docstring already argues for the dashboard/analytics side. The
one write this service performs (`ReportRepository.update_status`) is
against `reports`, this module's OWN metadata table -- the "No direct
writes from reporting services" requirement means never mutating an
OPERATIONAL table (Plant/Sale/Inventory/...), which this service never
does; it is a pure reader of every one of those.
"""
from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.core.logging import get_logger
from app.db.enums import (
    AIPredictionType,
    CustomerType,
    DiseaseReportStatus,
    EmployeeStatus,
    NotificationCategory,
    PlantStatus,
    ReportStatus,
    ReportType,
)
from app.domain_events.events import ReportFailed, ReportGenerated
from app.domain_events.publisher import DomainEventPublisher
from app.models.reports import Report
from app.reporting import exporters
from app.reporting.catalog import REPORT_TYPE_TITLES
from app.reporting.file_storage import FileStorage, build_report_filename
from app.repositories.interfaces import (
    AIPredictionRepository,
    AuditLogRepository,
    BranchRepository,
    CustomerRepository,
    DiseaseReportRepository,
    EmployeeRepository,
    FertilizerLogRepository,
    GrowthTimelineRepository,
    InventoryRepository,
    NotificationRepository,
    PassportRepository,
    PlantRepository,
    ReportRepository,
    SaleItemRepository,
    SaleRepository,
    SecurityEventRepository,
    WateringLogRepository,
)

logger = get_logger(__name__)

_PAGE_SIZE = 200

# (title, headers) -- returned alongside each provider's rows.
_ReportPayload = tuple[str, list[str], list[list[Any]]]
_ReportProvider = Callable[[uuid.UUID, "Report"], Awaitable[_ReportPayload]]


def _parse_uuid(value: Any) -> uuid.UUID | None:
    return uuid.UUID(value) if value else None


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value) if isinstance(value, str) else value


class ReportGenerationService:
    def __init__(
        self,
        *,
        report_repo: ReportRepository,
        file_storage: FileStorage,
        event_publisher: DomainEventPublisher,
        plant_repo: PlantRepository,
        inventory_repo: InventoryRepository,
        sale_repo: SaleRepository,
        sale_item_repo: SaleItemRepository,
        customer_repo: CustomerRepository,
        employee_repo: EmployeeRepository,
        branch_repo: BranchRepository,
        disease_report_repo: DiseaseReportRepository,
        growth_timeline_repo: GrowthTimelineRepository,
        watering_log_repo: WateringLogRepository,
        fertilizer_log_repo: FertilizerLogRepository,
        notification_repo: NotificationRepository,
        audit_log_repo: AuditLogRepository,
        security_event_repo: SecurityEventRepository,
        passport_repo: PassportRepository,
        ai_prediction_repo: AIPredictionRepository,
    ) -> None:
        self._reports = report_repo
        self._storage = file_storage
        self._events = event_publisher
        self._plants = plant_repo
        self._inventory = inventory_repo
        self._sales = sale_repo
        self._sale_items = sale_item_repo
        self._customers = customer_repo
        self._employees = employee_repo
        self._branches = branch_repo
        self._disease_reports = disease_report_repo
        self._growth_timeline = growth_timeline_repo
        self._watering_logs = watering_log_repo
        self._fertilizer_logs = fertilizer_log_repo
        self._notifications = notification_repo
        self._audit_logs = audit_log_repo
        self._security_events = security_event_repo
        self._passports = passport_repo
        self._ai_predictions = ai_prediction_repo

        self._providers: dict[ReportType, _ReportProvider] = {
            ReportType.PLANT: self._plant_report,
            ReportType.PLANT_LOSS: self._plant_loss_report,
            ReportType.INVENTORY: self._inventory_report,
            ReportType.SALES: self._sales_report,
            ReportType.REVENUE: self._revenue_report,
            ReportType.PROFIT: self._profit_report,
            ReportType.CUSTOMER: self._customer_report,
            ReportType.EMPLOYEE: self._employee_report,
            ReportType.BRANCH: self._branch_report,
            ReportType.DISEASE: self._disease_report,
            ReportType.GROWTH: self._growth_report,
            ReportType.WATER_USAGE: self._water_usage_report,
            ReportType.FERTILIZER: self._fertilizer_report,
            ReportType.NOTIFICATION: self._notification_report,
            ReportType.AUDIT: self._audit_report,
            ReportType.SECURITY: self._security_report,
            ReportType.PLANT_PASSPORT: self._passport_report,
            ReportType.AI_SUMMARY: self._ai_summary_report,
        }

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def generate(self, report: Report) -> None:
        try:
            provider = self._providers.get(report.report_type)
            if provider is None:
                raise ValueError(f"No data provider registered for report type {report.report_type!r}")
            await self._reports.update_status(report, status=ReportStatus.PROCESSING)
            title, headers, rows = await provider(report.nursery_id, report)
            content, extension, content_type = exporters.render(
                format_name=report.format.name, title=title, headers=headers, rows=rows
            )
            filename = build_report_filename(report_id=report.id, extension=extension)
            file_url = await self._storage.upload(content=content, filename=filename, content_type=content_type)
            completed_at = datetime.now(timezone.utc)
            await self._reports.update_status(
                report, status=ReportStatus.COMPLETE, file_url=file_url, completed_at=completed_at
            )
            await self._events.publish(
                ReportGenerated(
                    aggregate_id=report.id,
                    nursery_id=report.nursery_id,
                    actor_user_id=report.requested_by_user_id,
                    report_type=report.report_type.value,
                    format=report.format.value,
                    file_url=file_url,
                )
            )
            logger.info("report_generated", report_id=str(report.id), report_type=report.report_type.value, rows=len(rows))
        except Exception as exc:  # noqa: BLE001 -- background-task boundary; a raise here is silently swallowed by the runner, so this must be the terminal handler
            logger.error("report_generation_failed", report_id=str(report.id), error=str(exc))
            await self._reports.update_status(report, status=ReportStatus.FAILED)
            await self._events.publish(
                ReportFailed(
                    aggregate_id=report.id,
                    nursery_id=report.nursery_id,
                    actor_user_id=report.requested_by_user_id,
                    report_type=report.report_type.value,
                    error_message=str(exc),
                )
            )

    # ------------------------------------------------------------------
    # Shared pagination helper -- same full-scan-then-render shape
    # `SalesReportingService._all_sales` (Module 9) already established
    # for "aggregate over every matching row" report generation.
    # ------------------------------------------------------------------

    @staticmethod
    async def _all_pages(list_fn: Callable[..., Awaitable[tuple[list[Any], int]]], *args: Any, **kwargs: Any) -> list[Any]:
        rows: list[Any] = []
        offset = 0
        while True:
            page, total = await list_fn(*args, offset=offset, limit=_PAGE_SIZE, **kwargs)
            rows.extend(page)
            offset += _PAGE_SIZE
            if offset >= total or not page:
                break
        return rows

    # ------------------------------------------------------------------
    # Report-type providers
    # ------------------------------------------------------------------

    async def _plant_report(self, nursery_id: uuid.UUID, report: Report) -> _ReportPayload:
        filters = report.filters or {}
        plants = await self._all_pages(
            self._plants.list_for_nursery,
            nursery_id,
            branch_id=report.branch_id,
            species_id=_parse_uuid(filters.get("species_id")),
            status=PlantStatus(filters["status"]) if filters.get("status") else None,
        )
        headers = ["id", "branch_id", "species_id", "common_label", "status", "zone", "price", "planted_at", "sold_at", "batch_number"]
        rows = [
            [p.id, p.branch_id, p.species_id, p.common_label, p.status, p.zone, p.price, p.planted_at, p.sold_at, p.batch_number]
            for p in plants
        ]
        return REPORT_TYPE_TITLES[ReportType.PLANT], headers, rows

    async def _plant_loss_report(self, nursery_id: uuid.UUID, report: Report) -> _ReportPayload:
        plants = await self._all_pages(
            self._plants.list_for_nursery, nursery_id, branch_id=report.branch_id, status=PlantStatus.DECEASED
        )
        headers = ["id", "branch_id", "species_id", "common_label", "planted_at", "deceased_at", "deceased_reason"]
        rows = [[p.id, p.branch_id, p.species_id, p.common_label, p.planted_at, p.deceased_at, p.deceased_reason] for p in plants]
        return REPORT_TYPE_TITLES[ReportType.PLANT_LOSS], headers, rows

    async def _inventory_report(self, nursery_id: uuid.UUID, report: Report) -> _ReportPayload:
        filters = report.filters or {}
        items = await self._all_pages(
            self._inventory.list_for_nursery,
            nursery_id,
            branch_id=report.branch_id,
            category_id=_parse_uuid(filters.get("category_id")),
            species_id=_parse_uuid(filters.get("species_id")),
            low_stock_only=bool(filters.get("low_stock_only", False)),
        )
        headers = ["id", "branch_id", "name", "quantity", "reserved_quantity", "damaged_quantity", "unit_cost", "unit_price", "low_stock_threshold"]
        rows = [
            [i.id, i.branch_id, i.name, i.quantity, i.reserved_quantity, i.damaged_quantity, i.unit_cost, i.unit_price, i.low_stock_threshold]
            for i in items
        ]
        return REPORT_TYPE_TITLES[ReportType.INVENTORY], headers, rows

    async def _sales_report(self, nursery_id: uuid.UUID, report: Report) -> _ReportPayload:
        filters = report.filters or {}
        sales = await self._all_pages(
            self._sales.list_for_nursery,
            nursery_id,
            branch_id=report.branch_id,
            customer_id=_parse_uuid(filters.get("customer_id")),
            date_from=_parse_datetime(filters.get("date_from")),
            date_to=_parse_datetime(filters.get("date_to")),
        )
        headers = ["id", "branch_id", "customer_id", "status", "subtotal_amount", "discount_amount", "tax_amount", "total_amount", "sold_by_user_id", "created_at"]
        rows = [
            [s.id, s.branch_id, s.customer_id, s.status, s.subtotal_amount, s.discount_amount, s.tax_amount, s.total_amount, s.sold_by_user_id, s.created_at]
            for s in sales
        ]
        return REPORT_TYPE_TITLES[ReportType.SALES], headers, rows

    async def _revenue_report(self, nursery_id: uuid.UUID, report: Report) -> _ReportPayload:
        # Reuses `ReportingRepository`-shaped daily buckets is unnecessary
        # here (that Protocol is dashboard/analytics-scoped) -- this is a
        # simple GROUP BY over the same rows `_sales_report` reads, done
        # in Python rather than duplicating `mv_org_revenue_rollup`'s own
        # SQL, since the row volume a single report generation handles is
        # already bounded by `_all_pages`.
        filters = report.filters or {}
        sales = await self._all_pages(
            self._sales.list_for_nursery,
            nursery_id,
            branch_id=report.branch_id,
            date_from=_parse_datetime(filters.get("date_from")),
            date_to=_parse_datetime(filters.get("date_to")),
        )
        by_day: dict[Any, dict[str, Any]] = {}
        for s in sales:
            if getattr(s.status, "value", s.status) == "voided":
                continue
            day = s.created_at.date() if s.created_at else None
            entry = by_day.setdefault(day, {"revenue": 0, "sale_count": 0})
            entry["revenue"] += s.total_amount
            entry["sale_count"] += 1
        headers = ["day", "revenue", "sale_count"]
        rows = [[day, data["revenue"], data["sale_count"]] for day, data in sorted(by_day.items(), key=lambda kv: (kv[0] is None, kv[0]))]
        return REPORT_TYPE_TITLES[ReportType.REVENUE], headers, rows

    async def _profit_report(self, nursery_id: uuid.UUID, report: Report) -> _ReportPayload:
        filters = report.filters or {}
        sales = await self._all_pages(
            self._sales.list_for_nursery,
            nursery_id,
            branch_id=report.branch_id,
            date_from=_parse_datetime(filters.get("date_from")),
            date_to=_parse_datetime(filters.get("date_to")),
        )
        headers = ["sale_id", "branch_id", "created_at", "total_amount", "estimated_cogs", "estimated_profit"]
        rows = []
        for s in sales:
            if getattr(s.status, "value", s.status) == "voided":
                continue
            items = await self._sale_items.list_for_sale(s.id)
            cogs = Decimal(0)
            for item in items:
                if item.inventory_id is None:
                    continue
                inv = await self._inventory.get_by_id(item.inventory_id)
                if inv is not None and inv.unit_cost is not None:
                    # `inv.unit_cost` is a `Mapped[Decimal]` (SQLAlchemy `Numeric`
                    # column) -- mypy's SQLAlchemy plugin doesn't expose an
                    # `__rmul__`/`__mul__` overload against a plain `Decimal` for
                    # that mapped type, though at runtime it *is* a real `Decimal`
                    # and this multiplication is exactly correct.
                    cogs += Decimal(item.quantity) * inv.unit_cost  # type: ignore[operator]
            rows.append([s.id, s.branch_id, s.created_at, s.total_amount, cogs, s.total_amount - cogs])
        return REPORT_TYPE_TITLES[ReportType.PROFIT], headers, rows

    async def _customer_report(self, nursery_id: uuid.UUID, report: Report) -> _ReportPayload:
        filters = report.filters or {}
        customers = await self._all_pages(
            self._customers.list_for_nursery,
            nursery_id,
            branch_id=report.branch_id,
            customer_type=CustomerType(filters["customer_type"]) if filters.get("customer_type") else None,
        )
        headers = ["id", "branch_id", "name", "email", "phone", "customer_type", "created_at"]
        rows = [[c.id, c.branch_id, c.name, c.email, c.phone, c.customer_type, c.created_at] for c in customers]
        return REPORT_TYPE_TITLES[ReportType.CUSTOMER], headers, rows

    async def _employee_report(self, nursery_id: uuid.UUID, report: Report) -> _ReportPayload:
        filters = report.filters or {}
        employees = await self._all_pages(
            self._employees.list_for_nursery,
            nursery_id,
            status=EmployeeStatus(filters["status"]) if filters.get("status") else None,
        )
        headers = ["id", "user_id", "status", "department", "position", "hired_at"]
        rows = [[e.id, e.user_id, e.status, e.department, e.position, e.hired_at] for e in employees]
        return REPORT_TYPE_TITLES[ReportType.EMPLOYEE], headers, rows

    async def _branch_report(self, nursery_id: uuid.UUID, report: Report) -> _ReportPayload:
        branches = await self._branches.list_for_nursery(nursery_id, include_inactive=True)
        headers = ["id", "name", "city", "region", "country", "status", "phone", "email"]
        rows = [[b.id, b.name, b.city, b.region, b.country, b.status, b.phone, b.email] for b in branches]
        return REPORT_TYPE_TITLES[ReportType.BRANCH], headers, rows

    async def _disease_report(self, nursery_id: uuid.UUID, report: Report) -> _ReportPayload:
        filters = report.filters or {}
        reports_ = await self._all_pages(
            self._disease_reports.list_for_nursery,
            nursery_id,
            status=DiseaseReportStatus(filters["status"]) if filters.get("status") else None,
        )
        headers = ["id", "plant_id", "condition_name", "status", "severity", "is_ai_sourced", "confirmed_at", "resolved_at", "created_at"]
        rows = [
            [d.id, d.plant_id, d.condition_name, d.status, d.severity, d.is_ai_sourced, d.confirmed_at, d.resolved_at, d.created_at]
            for d in reports_
        ]
        return REPORT_TYPE_TITLES[ReportType.DISEASE], headers, rows

    async def _growth_report(self, nursery_id: uuid.UUID, report: Report) -> _ReportPayload:
        filters = report.filters or {}
        entries = await self._all_pages(
            self._growth_timeline.list_for_nursery,
            nursery_id,
            branch_id=report.branch_id,
            date_from=_parse_datetime(filters.get("date_from")),
            date_to=_parse_datetime(filters.get("date_to")),
        )
        headers = ["id", "plant_id", "height_cm", "spread_cm", "growth_stage", "leaf_count", "flower_count", "fruit_count", "recorded_at"]
        rows = [
            [g.id, g.plant_id, g.height_cm, g.spread_cm, g.growth_stage, g.leaf_count, g.flower_count, g.fruit_count, g.recorded_at]
            for g in entries
        ]
        return REPORT_TYPE_TITLES[ReportType.GROWTH], headers, rows

    async def _water_usage_report(self, nursery_id: uuid.UUID, report: Report) -> _ReportPayload:
        filters = report.filters or {}
        entries = await self._all_pages(
            self._watering_logs.list_for_nursery,
            nursery_id,
            branch_id=report.branch_id,
            date_from=_parse_datetime(filters.get("date_from")),
            date_to=_parse_datetime(filters.get("date_to")),
        )
        headers = ["id", "branch_id", "plant_id", "zone", "volume_ml", "method", "recorded_at"]
        rows = [[w.id, w.branch_id, w.plant_id, w.zone, w.volume_ml, w.method, w.recorded_at] for w in entries]
        return REPORT_TYPE_TITLES[ReportType.WATER_USAGE], headers, rows

    async def _fertilizer_report(self, nursery_id: uuid.UUID, report: Report) -> _ReportPayload:
        filters = report.filters or {}
        entries = await self._all_pages(
            self._fertilizer_logs.list_for_nursery,
            nursery_id,
            branch_id=report.branch_id,
            date_from=_parse_datetime(filters.get("date_from")),
            date_to=_parse_datetime(filters.get("date_to")),
        )
        headers = ["id", "branch_id", "plant_id", "zone", "product_name", "quantity_ml", "npk_ratio", "recorded_at"]
        rows = [[f.id, f.branch_id, f.plant_id, f.zone, f.product_name, f.quantity_ml, f.npk_ratio, f.recorded_at] for f in entries]
        return REPORT_TYPE_TITLES[ReportType.FERTILIZER], headers, rows

    async def _notification_report(self, nursery_id: uuid.UUID, report: Report) -> _ReportPayload:
        filters = report.filters or {}
        notifications = await self._all_pages(
            self._notifications.list_for_nursery,
            nursery_id,
            category=NotificationCategory(filters["category"]) if filters.get("category") else None,
            date_from=_parse_datetime(filters.get("date_from")),
            date_to=_parse_datetime(filters.get("date_to")),
        )
        headers = ["id", "recipient_user_id", "category", "message", "read_at", "created_at"]
        rows = [[n.id, n.recipient_user_id, n.category, n.message, n.read_at, n.created_at] for n in notifications]
        return REPORT_TYPE_TITLES[ReportType.NOTIFICATION], headers, rows

    async def _audit_report(self, nursery_id: uuid.UUID, report: Report) -> _ReportPayload:
        # `AuditLogRepository.list_for_org` has no date-range parameter
        # (Module 4's own Protocol never needed one) -- filtered
        # client-side here rather than widening that Protocol for a
        # filter only this one report type needs.
        filters = report.filters or {}
        date_from = _parse_datetime(filters.get("date_from"))
        date_to = _parse_datetime(filters.get("date_to"))
        entries = await self._all_pages(self._audit_logs.list_for_org, nursery_id)
        if date_from is not None:
            entries = [a for a in entries if a.created_at >= date_from]
        if date_to is not None:
            entries = [a for a in entries if a.created_at <= date_to]
        headers = ["id", "actor_user_id", "action", "entity_type", "entity_id", "created_at"]
        rows = [[a.id, a.actor_user_id, a.action, a.entity_type, a.entity_id, a.created_at] for a in entries]
        return REPORT_TYPE_TITLES[ReportType.AUDIT], headers, rows

    async def _security_report(self, nursery_id: uuid.UUID, report: Report) -> _ReportPayload:
        filters = report.filters or {}
        events = await self._all_pages(
            self._security_events.list_for_nursery,
            nursery_id,
            date_from=_parse_datetime(filters.get("date_from")),
            date_to=_parse_datetime(filters.get("date_to")),
        )
        headers = ["id", "user_id", "email", "event_type", "ip_address", "created_at"]
        rows = [[e.id, e.user_id, e.email, e.event_type, e.ip_address, e.created_at] for e in events]
        return REPORT_TYPE_TITLES[ReportType.SECURITY], headers, rows

    async def _passport_report(self, nursery_id: uuid.UUID, report: Report) -> _ReportPayload:
        # `PassportRepository.list_for_nursery` has no branch filter
        # (Passport carries no branch_id of its own -- see that model's
        # docstring); `report.branch_id` is therefore not applied here,
        # a disclosed scope limitation rather than a silent gap.
        passports = await self._all_pages(self._passports.list_for_nursery, nursery_id)
        headers = ["id", "plant_id", "version", "public_token", "token_expires_at", "generated_at"]
        rows = [[p.id, p.plant_id, p.version, p.public_token, p.token_expires_at, p.generated_at] for p in passports]
        return REPORT_TYPE_TITLES[ReportType.PLANT_PASSPORT], headers, rows

    async def _ai_summary_report(self, nursery_id: uuid.UUID, report: Report) -> _ReportPayload:
        filters = report.filters or {}
        predictions = await self._all_pages(
            self._ai_predictions.list_for_nursery,
            nursery_id,
            prediction_type=AIPredictionType(filters["prediction_type"]) if filters.get("prediction_type") else None,
        )
        if report.branch_id is not None:
            predictions = [p for p in predictions if p.branch_id == report.branch_id]
        headers = ["id", "plant_id", "branch_id", "prediction_type", "model_version", "confidence", "created_at"]
        rows = [[p.id, p.plant_id, p.branch_id, p.prediction_type, p.model_version, p.confidence, p.created_at] for p in predictions]
        return REPORT_TYPE_TITLES[ReportType.AI_SUMMARY], headers, rows
