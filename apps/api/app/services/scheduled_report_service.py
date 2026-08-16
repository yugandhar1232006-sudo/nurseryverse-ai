"""
Saved Reports / Scheduled Reports / Recurring Reports (FR-18.4).

`run_due()` is the on-demand sweep substitute for a real cron/Celery-Beat
scheduler -- the identical shape `NotificationService.retry_due_deliveries`
(Module 11, reachable via `POST /notifications/retry-due`) already
established for this codebase's disclosed "no background-job
infrastructure" gap. Reachable via a future `POST /reports/scheduled/run-due`
endpoint; a real deployment would put that behind an external cron trigger
(a k8s CronJob curling the endpoint, for instance) rather than anything
running inside this API process.
"""
from __future__ import annotations

import calendar
import uuid
from datetime import datetime, timedelta, timezone

from app.db.enums import ReportFormat, ReportScheduleFrequency, ReportStatus, ReportType
from app.models.reports import Report, ScheduledReport
from app.repositories.interfaces import ReportRepository, ScheduledReportRepository
from app.services.report_generation_service import ReportGenerationService


def _advance(frequency: ReportScheduleFrequency, from_time: datetime) -> datetime:
    if frequency == ReportScheduleFrequency.DAILY:
        return from_time.replace(microsecond=0) + timedelta(days=1)
    if frequency == ReportScheduleFrequency.WEEKLY:
        return from_time.replace(microsecond=0) + timedelta(days=7)
    # MONTHLY -- same day-of-month next month, clamped to that month's
    # last day for schedules created on the 29th-31st (no `dateutil`
    # dependency in this codebase's requirements files, so this is
    # implemented with the stdlib `calendar` module rather than adding one
    # just for this).
    year = from_time.year + (1 if from_time.month == 12 else 0)
    month = 1 if from_time.month == 12 else from_time.month + 1
    day = min(from_time.day, calendar.monthrange(year, month)[1])
    return from_time.replace(year=year, month=month, day=day, microsecond=0)


class ScheduledReportService:
    def __init__(
        self,
        *,
        scheduled_repo: ScheduledReportRepository,
        report_repo: ReportRepository,
        generation_service: ReportGenerationService,
    ) -> None:
        self._scheduled = scheduled_repo
        self._reports = report_repo
        self._generation = generation_service

    async def create(
        self,
        *,
        nursery_id: uuid.UUID,
        branch_id: uuid.UUID | None,
        name: str,
        report_type: ReportType,
        format: ReportFormat,
        filters: dict | None,
        frequency: ReportScheduleFrequency,
        created_by_user_id: uuid.UUID,
        next_run_at: datetime,
    ) -> ScheduledReport:
        scheduled = ScheduledReport(
            nursery_id=nursery_id,
            branch_id=branch_id,
            name=name,
            report_type=report_type,
            format=format,
            filters=filters,
            frequency=frequency,
            is_active=True,
            created_by_user_id=created_by_user_id,
            next_run_at=next_run_at,
        )
        return await self._scheduled.add(scheduled)

    async def get(self, scheduled_id: uuid.UUID) -> ScheduledReport | None:
        return await self._scheduled.get_by_id(scheduled_id)

    async def list_for_org(self, nursery_id: uuid.UUID) -> list[ScheduledReport]:
        return await self._scheduled.list_for_org(nursery_id)

    async def update(
        self,
        scheduled: ScheduledReport,
        *,
        name: str | None = None,
        filters: dict | None = None,
        frequency: ReportScheduleFrequency | None = None,
        next_run_at: datetime | None = None,
    ) -> None:
        """Partial update -- `None` leaves a field unchanged. See `ScheduledReportRepository.update`'s own docstring for why `report_type`/`format`/`branch_id` aren't editable here."""
        await self._scheduled.update(scheduled, name=name, filters=filters, frequency=frequency, next_run_at=next_run_at)

    async def set_active(self, scheduled: ScheduledReport, *, is_active: bool) -> None:
        await self._scheduled.set_active(scheduled, is_active=is_active)

    async def delete(self, scheduled: ScheduledReport) -> None:
        await self._scheduled.delete(scheduled)

    async def run_due(self, *, now: datetime | None = None, limit: int = 100) -> list[dict]:
        """
        Global sweep across every organization's due schedules -- meant to
        be driven by a single external, org-agnostic cron trigger in a
        real deployment (see this module's own docstring), NOT something
        an authenticated API caller should ever invoke directly: a
        tenant-scoped caller triggering this would execute (and advance
        the `next_run_at` of) every OTHER organization's due schedules too
        as a side effect, a cross-tenant violation. `app/api/routes/
        reports.py`'s `POST /reports/scheduled/run-due` route calls
        `run_due_for_org` below instead, never this method, for exactly
        that reason.
        """
        now = now or datetime.now(timezone.utc)
        due = await self._scheduled.list_due(now=now, limit=limit)
        return await self._execute(due, now=now)

    async def run_due_for_org(self, nursery_id: uuid.UUID, *, now: datetime | None = None, limit: int = 100) -> list[dict]:
        """
        The tenant-scoped counterpart to `run_due` -- executes only the
        calling organization's own due, active schedules, never another
        organization's. Fetches the full globally-due set (there is no
        `ScheduledReportRepository.list_due` org filter -- see that
        Protocol method's own docstring on why it's meant for a global
        cron sweep) and narrows to `nursery_id` in-process before
        executing anything, so nothing outside the caller's own org is
        ever touched.
        """
        now = now or datetime.now(timezone.utc)
        due = [s for s in await self._scheduled.list_due(now=now, limit=1000) if s.nursery_id == nursery_id]
        return await self._execute(due[:limit], now=now)

    async def _execute(self, due: list[ScheduledReport], *, now: datetime) -> list[dict]:
        """
        For each due row: generates one `Report` from the saved
        `report_type`/`format`/`filters` (delegating the actual build to
        `ReportGenerationService.generate`, never duplicating its
        provider registry here), then advances `next_run_at` by
        `frequency` regardless of whether that generation succeeded or
        failed -- a permanently-broken schedule (e.g. filters referencing
        a deleted branch) should keep notifying its owner of each failure
        via `ReportFailed`, not silently stop advancing and vanish from
        view. A paused (`is_active=False`) row is never returned by
        `list_due` in the first place (see that method's own docstring),
        and a deleted row can't be either (it no longer exists to be
        fetched) -- both "paused/deleted schedules never execute"
        requirements are therefore satisfied one layer down, at the
        repository query itself, not by a check in this loop. Idempotent
        per invocation: each call only ever processes rows whose
        `next_run_at <= now` *at fetch time*; `update_after_run` advances
        `next_run_at` into the future before this method returns, so an
        immediate second call against the same `now` will not re-select
        the row it just processed.
        """
        results: list[dict] = []
        for scheduled in due:
            report = Report(
                nursery_id=scheduled.nursery_id,
                branch_id=scheduled.branch_id,
                report_type=scheduled.report_type,
                format=scheduled.format,
                filters=scheduled.filters,
                status=ReportStatus.PENDING,
                requested_by_user_id=scheduled.created_by_user_id,
            )
            report = await self._reports.add(report)
            await self._generation.generate(report)
            next_run_at = _advance(scheduled.frequency, now)
            await self._scheduled.update_after_run(scheduled, last_run_at=now, next_run_at=next_run_at)
            results.append(
                {
                    "scheduled_report_id": scheduled.id,
                    "report_id": report.id,
                    "status": report.status.value,
                    "next_run_at": next_run_at,
                }
            )
        return results
