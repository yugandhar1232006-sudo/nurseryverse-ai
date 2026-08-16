"""
Unit tests for `DashboardService`/`AnalyticsService` -- both are thin,
read-only pass-throughs onto `ReportingRepository` (see each module's own
docstring), so what's actually worth unit-testing here is (a) each method
forwards to the correct `ReportingRepository` method with the correct
arguments, unchanged, and (b) `AnalyticsService`'s one piece of real logic:
defaulting an unsupplied date range to the trailing 90 days.

Exercised against a minimal in-file recording stub rather than
`FakeReportingRepository` (that fake recomputes real aggregation math over
other fakes' data -- appropriate for integration-level dashboard/analytics
route tests, but this file's job is verifying the *pass-through wiring*
itself, independent of any particular aggregation result).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.services.analytics_service import AnalyticsService, _default_range
from app.services.dashboard_service import DashboardService

pytestmark = pytest.mark.unit


class _RecordingReportingRepo:
    """Records every call (method name + args/kwargs) and returns a canned value keyed by method name."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def _record(self, name: str, args: tuple, kwargs: dict):
        self.calls.append((name, args, kwargs))
        return {"_method": name}

    async def executive_dashboard(self, *a, **kw):
        return self._record("executive_dashboard", a, kw)

    async def nursery_dashboard(self, *a, **kw):
        return self._record("nursery_dashboard", a, kw)

    async def branch_dashboard(self, *a, **kw):
        return self._record("branch_dashboard", a, kw)

    async def plant_dashboard(self, *a, **kw):
        return self._record("plant_dashboard", a, kw)

    async def inventory_dashboard(self, *a, **kw):
        return self._record("inventory_dashboard", a, kw)

    async def sales_dashboard(self, *a, **kw):
        return self._record("sales_dashboard", a, kw)

    async def customer_dashboard(self, *a, **kw):
        return self._record("customer_dashboard", a, kw)

    async def ai_dashboard(self, *a, **kw):
        return self._record("ai_dashboard", a, kw)

    async def financial_dashboard(self, *a, **kw):
        return self._record("financial_dashboard", a, kw)

    async def kpi_summary(self, *a, **kw):
        return self._record("kpi_summary", a, kw)

    async def revenue_trend(self, *a, **kw):
        return [self._record("revenue_trend", a, kw)]

    async def growth_trend(self, *a, **kw):
        return [self._record("growth_trend", a, kw)]

    async def inventory_trend(self, *a, **kw):
        return [self._record("inventory_trend", a, kw)]

    async def plant_health_trend(self, *a, **kw):
        return [self._record("plant_health_trend", a, kw)]

    async def sales_forecast(self, *a, **kw):
        return [self._record("sales_forecast", a, kw)]

    async def disease_trend(self, *a, **kw):
        return [self._record("disease_trend", a, kw)]

    async def customer_analytics(self, *a, **kw):
        return self._record("customer_analytics", a, kw)

    async def employee_productivity(self, *a, **kw):
        return [self._record("employee_productivity", a, kw)]

    async def branch_performance(self, *a, **kw):
        return [self._record("branch_performance", a, kw)]


@pytest.fixture
def repo() -> _RecordingReportingRepo:
    return _RecordingReportingRepo()


@pytest.fixture
def dashboard_service(repo) -> DashboardService:
    return DashboardService(reporting_repo=repo)


@pytest.fixture
def analytics_service(repo) -> AnalyticsService:
    return AnalyticsService(reporting_repo=repo)


# --------------------------------------------------------------------------
# DashboardService -- pass-through wiring
# --------------------------------------------------------------------------


async def test_executive_dashboard_passes_nursery_id_only(dashboard_service, repo):
    nursery_id = uuid.uuid4()
    await dashboard_service.executive_dashboard(nursery_id)
    assert repo.calls == [("executive_dashboard", (nursery_id,), {})]


async def test_nursery_dashboard_passes_nursery_id_only(dashboard_service, repo):
    nursery_id = uuid.uuid4()
    await dashboard_service.nursery_dashboard(nursery_id)
    assert repo.calls == [("nursery_dashboard", (nursery_id,), {})]


async def test_branch_dashboard_passes_nursery_and_branch_id(dashboard_service, repo):
    nursery_id, branch_id = uuid.uuid4(), uuid.uuid4()
    await dashboard_service.branch_dashboard(nursery_id, branch_id)
    assert repo.calls == [("branch_dashboard", (nursery_id, branch_id), {})]


async def test_plant_dashboard_branch_id_defaults_to_none(dashboard_service, repo):
    nursery_id = uuid.uuid4()
    await dashboard_service.plant_dashboard(nursery_id)
    assert repo.calls == [("plant_dashboard", (nursery_id, None), {})]


async def test_inventory_dashboard_forwards_branch_id_when_supplied(dashboard_service, repo):
    nursery_id, branch_id = uuid.uuid4(), uuid.uuid4()
    await dashboard_service.inventory_dashboard(nursery_id, branch_id)
    assert repo.calls == [("inventory_dashboard", (nursery_id, branch_id), {})]


async def test_sales_dashboard_forwards_date_range(dashboard_service, repo):
    nursery_id = uuid.uuid4()
    date_from = datetime(2026, 1, 1, tzinfo=timezone.utc)
    date_to = datetime(2026, 2, 1, tzinfo=timezone.utc)
    await dashboard_service.sales_dashboard(nursery_id, None, date_from, date_to)
    assert repo.calls == [("sales_dashboard", (nursery_id, None, date_from, date_to), {})]


async def test_customer_dashboard_forwards_branch_id(dashboard_service, repo):
    nursery_id, branch_id = uuid.uuid4(), uuid.uuid4()
    await dashboard_service.customer_dashboard(nursery_id, branch_id)
    assert repo.calls == [("customer_dashboard", (nursery_id, branch_id), {})]


async def test_ai_dashboard_forwards_branch_id(dashboard_service, repo):
    nursery_id, branch_id = uuid.uuid4(), uuid.uuid4()
    await dashboard_service.ai_dashboard(nursery_id, branch_id)
    assert repo.calls == [("ai_dashboard", (nursery_id, branch_id), {})]


async def test_financial_dashboard_forwards_date_range(dashboard_service, repo):
    nursery_id = uuid.uuid4()
    date_from = datetime(2026, 1, 1, tzinfo=timezone.utc)
    await dashboard_service.financial_dashboard(nursery_id, None, date_from, None)
    assert repo.calls == [("financial_dashboard", (nursery_id, None, date_from, None), {})]


# --------------------------------------------------------------------------
# AnalyticsService -- pass-through wiring + date-range defaulting
# --------------------------------------------------------------------------


def test_default_range_fills_in_trailing_90_days_when_both_unset():
    start, end = _default_range(None, None)
    assert (end - start).days == 90


def test_default_range_preserves_explicit_bounds():
    date_from = datetime(2025, 1, 1, tzinfo=timezone.utc)
    date_to = datetime(2025, 6, 1, tzinfo=timezone.utc)
    start, end = _default_range(date_from, date_to)
    assert start == date_from
    assert end == date_to


def test_default_range_defaults_only_the_unset_side():
    date_from = datetime(2025, 1, 1, tzinfo=timezone.utc)
    start, end = _default_range(date_from, None)
    assert start == date_from
    assert end > date_from


async def test_kpi_summary_passes_branch_id(analytics_service, repo):
    nursery_id, branch_id = uuid.uuid4(), uuid.uuid4()
    await analytics_service.kpi_summary(nursery_id, branch_id)
    assert repo.calls == [("kpi_summary", (nursery_id, branch_id), {})]


async def test_revenue_trend_defaults_date_range_when_unset(analytics_service, repo):
    nursery_id = uuid.uuid4()
    await analytics_service.revenue_trend(nursery_id)
    name, args, kwargs = repo.calls[0]
    assert name == "revenue_trend"
    assert args[0] == nursery_id
    assert args[1] is None  # branch_id
    start, end = args[2], args[3]
    assert (end - start).days == 90


async def test_revenue_trend_forwards_explicit_date_range_unchanged(analytics_service, repo):
    nursery_id = uuid.uuid4()
    date_from = datetime(2026, 1, 1, tzinfo=timezone.utc)
    date_to = datetime(2026, 1, 31, tzinfo=timezone.utc)
    await analytics_service.revenue_trend(nursery_id, None, date_from, date_to)
    assert repo.calls == [("revenue_trend", (nursery_id, None, date_from, date_to), {})]


async def test_growth_trend_forwards_species_id_and_date_range(analytics_service, repo):
    nursery_id, species_id = uuid.uuid4(), uuid.uuid4()
    date_from = datetime(2026, 1, 1, tzinfo=timezone.utc)
    date_to = datetime(2026, 1, 31, tzinfo=timezone.utc)
    await analytics_service.growth_trend(nursery_id, None, species_id, date_from, date_to)
    assert repo.calls == [("growth_trend", (nursery_id, None, species_id, date_from, date_to), {})]


async def test_inventory_trend_defaults_date_range(analytics_service, repo):
    nursery_id = uuid.uuid4()
    await analytics_service.inventory_trend(nursery_id)
    _, args, _ = repo.calls[0]
    assert (args[3] - args[2]).days == 90


async def test_plant_health_trend_defaults_date_range(analytics_service, repo):
    nursery_id = uuid.uuid4()
    await analytics_service.plant_health_trend(nursery_id)
    _, args, _ = repo.calls[0]
    assert (args[3] - args[2]).days == 90


async def test_sales_forecast_takes_no_date_range(analytics_service, repo):
    """`sales_forecast` reads persisted AI predictions -- no date-range defaulting logic applies to it, unlike every other trend method."""
    nursery_id, branch_id = uuid.uuid4(), uuid.uuid4()
    await analytics_service.sales_forecast(nursery_id, branch_id)
    assert repo.calls == [("sales_forecast", (nursery_id, branch_id), {})]


async def test_disease_trend_defaults_date_range(analytics_service, repo):
    nursery_id = uuid.uuid4()
    await analytics_service.disease_trend(nursery_id)
    _, args, _ = repo.calls[0]
    assert (args[3] - args[2]).days == 90


async def test_customer_analytics_forwards_branch_id(analytics_service, repo):
    nursery_id, branch_id = uuid.uuid4(), uuid.uuid4()
    await analytics_service.customer_analytics(nursery_id, branch_id)
    assert repo.calls == [("customer_analytics", (nursery_id, branch_id), {})]


async def test_employee_productivity_defaults_date_range(analytics_service, repo):
    nursery_id = uuid.uuid4()
    await analytics_service.employee_productivity(nursery_id)
    _, args, _ = repo.calls[0]
    assert (args[3] - args[2]).days == 90


async def test_branch_performance_takes_only_nursery_id(analytics_service, repo):
    nursery_id = uuid.uuid4()
    await analytics_service.branch_performance(nursery_id)
    assert repo.calls == [("branch_performance", (nursery_id,), {})]
