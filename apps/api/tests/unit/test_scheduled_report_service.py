"""
Unit tests for `ScheduledReportService` (app/services/scheduled_report_service.py):
CRUD, pause/resume, `_advance`'s per-frequency (including month-end
rollover) arithmetic, and the `run_due`/`run_due_for_org` execution paths
-- paused schedules never execute, deleted schedules can't, a tenant-scoped
`run_due_for_org` call never touches another organization's schedules, and
re-invoking `run_due`/`run_due_for_org` against the same `now` is
idempotent (a freshly-advanced `next_run_at` is never re-selected as due
within the same sweep).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db.enums import ReportFormat, ReportScheduleFrequency, ReportStatus, ReportType
from app.services.scheduled_report_service import _advance

pytestmark = pytest.mark.unit


async def _create(harness, *, org_id, branch_id=None, frequency=ReportScheduleFrequency.DAILY, next_run_at=None):
    return await harness.scheduled_report_service.create(
        nursery_id=org_id, branch_id=branch_id, name="Nightly Sales", report_type=ReportType.SALES,
        format=ReportFormat.CSV, filters={}, frequency=frequency, created_by_user_id=uuid.uuid4(),
        next_run_at=next_run_at or (datetime.now(timezone.utc) + timedelta(days=1)),
    )


def _force_due(scheduled, *, when: datetime | None = None) -> None:
    """Bypasses the API-level "next_run_at must not be in the past" validator (`ScheduledReportCreateRequest`'s own job, not this service's) to directly simulate a schedule whose time has come -- the service layer itself has no such restriction (see `ScheduledReportService.create`'s signature, which accepts any `datetime`)."""
    scheduled.next_run_at = when or (datetime.now(timezone.utc) - timedelta(minutes=1))


# --------------------------------------------------------------------------
# _advance -- per-frequency arithmetic, including month-end rollover
# --------------------------------------------------------------------------


def test_advance_daily_adds_one_day():
    now = datetime(2026, 3, 10, 9, 0, tzinfo=timezone.utc)
    assert _advance(ReportScheduleFrequency.DAILY, now) == datetime(2026, 3, 11, 9, 0, tzinfo=timezone.utc)


def test_advance_weekly_adds_seven_days():
    now = datetime(2026, 3, 10, 9, 0, tzinfo=timezone.utc)
    assert _advance(ReportScheduleFrequency.WEEKLY, now) == datetime(2026, 3, 17, 9, 0, tzinfo=timezone.utc)


def test_advance_monthly_same_day_next_month():
    now = datetime(2026, 3, 15, 9, 0, tzinfo=timezone.utc)
    assert _advance(ReportScheduleFrequency.MONTHLY, now) == datetime(2026, 4, 15, 9, 0, tzinfo=timezone.utc)


def test_advance_monthly_rolls_december_into_next_january():
    now = datetime(2026, 12, 15, 9, 0, tzinfo=timezone.utc)
    assert _advance(ReportScheduleFrequency.MONTHLY, now) == datetime(2027, 1, 15, 9, 0, tzinfo=timezone.utc)


def test_advance_monthly_clamps_31st_to_shorter_months_last_day():
    """Jan 31 -> Feb 28 (2026 is not a leap year) -- `calendar.monthrange`-based clamping, not a naive `+relativedelta(months=1)`."""
    now = datetime(2026, 1, 31, 9, 0, tzinfo=timezone.utc)
    assert _advance(ReportScheduleFrequency.MONTHLY, now) == datetime(2026, 2, 28, 9, 0, tzinfo=timezone.utc)


def test_advance_monthly_clamps_31st_to_29th_in_a_leap_year():
    now = datetime(2028, 1, 31, 9, 0, tzinfo=timezone.utc)  # 2028 is a leap year
    assert _advance(ReportScheduleFrequency.MONTHLY, now) == datetime(2028, 2, 29, 9, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------
# CRUD
# --------------------------------------------------------------------------


async def test_create_defaults_to_active(harness):
    org_id = uuid.uuid4()
    scheduled = await _create(harness, org_id=org_id)
    assert scheduled.is_active is True
    assert scheduled.last_run_at is None


async def test_get_returns_none_for_unknown_id(harness):
    assert await harness.scheduled_report_service.get(uuid.uuid4()) is None


async def test_list_for_org_excludes_other_orgs(harness):
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    await _create(harness, org_id=org_a)
    await _create(harness, org_id=org_b)
    rows = await harness.scheduled_report_service.list_for_org(org_a)
    assert len(rows) == 1
    assert rows[0].nursery_id == org_a


async def test_update_only_changes_supplied_fields(harness):
    org_id = uuid.uuid4()
    scheduled = await _create(harness, org_id=org_id, frequency=ReportScheduleFrequency.DAILY)
    original_next_run = scheduled.next_run_at

    await harness.scheduled_report_service.update(scheduled, name="Renamed")

    assert scheduled.name == "Renamed"
    assert scheduled.frequency == ReportScheduleFrequency.DAILY  # unchanged
    assert scheduled.next_run_at == original_next_run  # unchanged


async def test_update_changes_frequency_and_next_run_at_together(harness):
    org_id = uuid.uuid4()
    scheduled = await _create(harness, org_id=org_id, frequency=ReportScheduleFrequency.DAILY)
    new_next_run = datetime.now(timezone.utc) + timedelta(days=5)

    await harness.scheduled_report_service.update(scheduled, frequency=ReportScheduleFrequency.MONTHLY, next_run_at=new_next_run)

    assert scheduled.frequency == ReportScheduleFrequency.MONTHLY
    assert scheduled.next_run_at == new_next_run


async def test_set_active_false_then_true_round_trips(harness):
    org_id = uuid.uuid4()
    scheduled = await _create(harness, org_id=org_id)

    await harness.scheduled_report_service.set_active(scheduled, is_active=False)
    assert scheduled.is_active is False

    await harness.scheduled_report_service.set_active(scheduled, is_active=True)
    assert scheduled.is_active is True


async def test_delete_removes_from_repository(harness):
    org_id = uuid.uuid4()
    scheduled = await _create(harness, org_id=org_id)

    await harness.scheduled_report_service.delete(scheduled)

    assert await harness.scheduled_report_service.get(scheduled.id) is None


# --------------------------------------------------------------------------
# run_due / run_due_for_org -- execution, idempotency, paused/deleted-never-execute
# --------------------------------------------------------------------------


async def test_run_due_for_org_executes_a_due_active_schedule(harness):
    org_id = uuid.uuid4()
    scheduled = await _create(harness, org_id=org_id, frequency=ReportScheduleFrequency.DAILY)
    _force_due(scheduled)

    results = await harness.scheduled_report_service.run_due_for_org(org_id)

    assert len(results) == 1
    assert results[0]["scheduled_report_id"] == scheduled.id
    assert results[0]["status"] == ReportStatus.COMPLETE.value
    report = await harness.reports.get_by_id(results[0]["report_id"])
    assert report is not None
    assert report.nursery_id == org_id
    assert scheduled.last_run_at is not None
    assert scheduled.next_run_at > datetime.now(timezone.utc)  # advanced into the future


async def test_run_due_for_org_never_touches_another_orgs_schedule(harness):
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    scheduled_a = await _create(harness, org_id=org_a)
    scheduled_b = await _create(harness, org_id=org_b)
    _force_due(scheduled_a)
    _force_due(scheduled_b)
    original_b_next_run = scheduled_b.next_run_at

    results = await harness.scheduled_report_service.run_due_for_org(org_a)

    assert len(results) == 1
    assert results[0]["scheduled_report_id"] == scheduled_a.id
    # org_b's due schedule is untouched -- still in the past, never advanced or executed.
    assert scheduled_b.next_run_at == original_b_next_run
    assert scheduled_b.last_run_at is None


async def test_run_due_sweeps_every_org(harness):
    """Contrast with `run_due_for_org` above -- the global `run_due` (meant for a single external cron trigger, never a tenant-scoped API caller, per its own docstring) DOES execute every organization's due schedules."""
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    scheduled_a = await _create(harness, org_id=org_a)
    scheduled_b = await _create(harness, org_id=org_b)
    _force_due(scheduled_a)
    _force_due(scheduled_b)

    results = await harness.scheduled_report_service.run_due()

    executed_ids = {r["scheduled_report_id"] for r in results}
    assert executed_ids == {scheduled_a.id, scheduled_b.id}


async def test_paused_schedule_is_never_selected_by_run_due(harness):
    org_id = uuid.uuid4()
    scheduled = await _create(harness, org_id=org_id)
    _force_due(scheduled)
    await harness.scheduled_report_service.set_active(scheduled, is_active=False)

    results = await harness.scheduled_report_service.run_due_for_org(org_id)

    assert results == []
    assert scheduled.last_run_at is None


async def test_deleted_schedule_cannot_be_executed(harness):
    org_id = uuid.uuid4()
    scheduled = await _create(harness, org_id=org_id)
    scheduled_id = scheduled.id
    _force_due(scheduled)
    await harness.scheduled_report_service.delete(scheduled)

    results = await harness.scheduled_report_service.run_due_for_org(org_id)

    assert results == []
    assert await harness.scheduled_report_service.get(scheduled_id) is None


async def test_run_due_for_org_is_idempotent_within_the_same_now(harness):
    """A second call against the exact same `now` must not re-select the row `_execute` already advanced past that `now` in the first call."""
    org_id = uuid.uuid4()
    scheduled = await _create(harness, org_id=org_id, frequency=ReportScheduleFrequency.DAILY)
    now = datetime.now(timezone.utc)
    _force_due(scheduled, when=now - timedelta(minutes=1))

    first = await harness.scheduled_report_service.run_due_for_org(org_id, now=now)
    second = await harness.scheduled_report_service.run_due_for_org(org_id, now=now)

    assert len(first) == 1
    assert second == []


async def test_run_due_for_org_advances_next_run_at_even_when_generation_fails(harness):
    """A permanently-broken schedule (bad filters) should keep advancing and keep notifying of each failure, never silently stop and vanish from view -- see `_execute`'s own docstring."""
    org_id = uuid.uuid4()
    scheduled = await harness.scheduled_report_service.create(
        nursery_id=org_id, branch_id=None, name="Broken", report_type=ReportType.PLANT, format=ReportFormat.CSV,
        filters={"status": "not-a-real-status"}, frequency=ReportScheduleFrequency.DAILY,
        created_by_user_id=uuid.uuid4(), next_run_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    _force_due(scheduled)
    original_next_run = scheduled.next_run_at

    results = await harness.scheduled_report_service.run_due_for_org(org_id)

    assert len(results) == 1
    assert results[0]["status"] == ReportStatus.FAILED.value
    assert scheduled.next_run_at > original_next_run
    assert scheduled.last_run_at is not None
    report = await harness.reports.get_by_id(results[0]["report_id"])
    assert report.status == ReportStatus.FAILED


async def test_run_due_for_org_respects_limit(harness):
    org_id = uuid.uuid4()
    for _ in range(3):
        scheduled = await _create(harness, org_id=org_id)
        _force_due(scheduled)

    results = await harness.scheduled_report_service.run_due_for_org(org_id, limit=2)

    assert len(results) == 2
