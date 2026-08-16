"""
KPIs / Trend Analysis / Growth / Revenue / Inventory / Plant Health /
Sales Forecast / Disease / Customer / Employee Productivity / Branch
Performance analytics. Same read-only pass-through shape as
`DashboardService` -- see that module's docstring for the CQRS reasoning;
the only logic this service owns is defaulting an unset date range (the
FILTERS requirement's "Date Range" applied consistently across every
trend endpoint) rather than pushing "what does no date range mean" into
every route handler individually.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.repositories.interfaces import ReportingRepository

_DEFAULT_TREND_WINDOW_DAYS = 90


def _default_range(date_from: datetime | None, date_to: datetime | None) -> tuple[datetime, datetime]:
    """Un-supplied bounds default to the trailing 90 days -- long enough to show a real trend, short enough to stay fast on a full-scan fake/aggregate query."""
    now = datetime.now(timezone.utc)
    return (date_from or now - timedelta(days=_DEFAULT_TREND_WINDOW_DAYS), date_to or now)


class AnalyticsService:
    def __init__(self, *, reporting_repo: ReportingRepository) -> None:
        self._reporting = reporting_repo

    async def kpi_summary(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict:
        return await self._reporting.kpi_summary(nursery_id, branch_id)

    async def revenue_trend(
        self,
        nursery_id: uuid.UUID,
        branch_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict]:
        start, end = _default_range(date_from, date_to)
        return await self._reporting.revenue_trend(nursery_id, branch_id, start, end)

    async def growth_trend(
        self,
        nursery_id: uuid.UUID,
        branch_id: uuid.UUID | None = None,
        species_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict]:
        start, end = _default_range(date_from, date_to)
        return await self._reporting.growth_trend(nursery_id, branch_id, species_id, start, end)

    async def inventory_trend(
        self,
        nursery_id: uuid.UUID,
        branch_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict]:
        start, end = _default_range(date_from, date_to)
        return await self._reporting.inventory_trend(nursery_id, branch_id, start, end)

    async def plant_health_trend(
        self,
        nursery_id: uuid.UUID,
        branch_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict]:
        start, end = _default_range(date_from, date_to)
        return await self._reporting.plant_health_trend(nursery_id, branch_id, start, end)

    async def sales_forecast(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> list[dict]:
        return await self._reporting.sales_forecast(nursery_id, branch_id)

    async def disease_trend(
        self,
        nursery_id: uuid.UUID,
        branch_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict]:
        start, end = _default_range(date_from, date_to)
        return await self._reporting.disease_trend(nursery_id, branch_id, start, end)

    async def customer_analytics(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict:
        return await self._reporting.customer_analytics(nursery_id, branch_id)

    async def employee_productivity(
        self,
        nursery_id: uuid.UUID,
        branch_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict]:
        start, end = _default_range(date_from, date_to)
        return await self._reporting.employee_productivity(nursery_id, branch_id, start, end)

    async def branch_performance(self, nursery_id: uuid.UUID) -> list[dict]:
        return await self._reporting.branch_performance(nursery_id)
