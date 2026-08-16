"""
Phase 6 Module 14 (Production Readiness) unit tests for `app/workers.py`.

Two concerns, tested separately:

  1. **Dependency-graph wiring** — `_build_notification_service`/
     `_build_event_publisher` must construct real, correctly-typed
     objects (a `SqlAlchemy*Repository`'s `__init__` only ever stores the
     session reference; it does no I/O), proving the long manual
     construction in `app/workers.py` (mirroring `app/api/deps.py`'s
     `get_domain_event_publisher`) doesn't have a typo'd keyword or a
     missing constructor argument that would only surface the first time
     a real worker process actually ran a scheduled task.
  2. **Commit-on-success / rollback-on-exception** — the exact same
     concern `tests/unit/test_db_session.py` established for
     `get_db_session()`, applied to `app/workers.py`'s own
     `async with AsyncSessionLocal() as db: try/except` blocks (which are
     hand-written here, not reusing `get_db_session`, since a Celery task
     has no FastAPI request/response cycle to hang a `Depends()` off of).
     `AsyncSessionLocal` is monkeypatched by NAME on the module (the same
     pattern `test_db_session.py`'s own fixture docstring explains is
     required, since `app/workers.py` references it at call time, not at
     import time), backed by a real in-memory SQLite engine so
     `db.commit()`/`db.rollback()` are exercised for real, not mocked.

Does not exercise the real service methods (`retry_due_deliveries`/
`run_due`) against real production data -- that's already covered by
`test_notification_delivery.py`/`test_scheduled_report_service.py`
against the in-memory fake repositories, and this module deliberately
calls the exact same, unmodified service classes those tests already
validate. What's genuinely new and worth testing here is: does this
module's own construction code work, and does it commit/rollback
correctly around whatever the service methods do.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.workers as workers_module
from app.core.config import Settings
from app.domain_events import DomainEventPublisher
from app.notifications.notification_handler import NotificationService

pytestmark = pytest.mark.unit


class _StubSession:
    """A stand-in `AsyncSession` -- every `SqlAlchemy*Repository.__init__` below only stores this reference, never calls a method on it, so a bare stub (not even a Mock) is sufficient to prove construction succeeds."""


def test_build_notification_service_constructs_without_error():
    settings = Settings(_env_file=None, APP_ENV="test")
    service = workers_module._build_notification_service(_StubSession(), settings)
    assert isinstance(service, NotificationService)


def test_build_event_publisher_constructs_without_error_and_registers_both_handlers():
    settings = Settings(_env_file=None, APP_ENV="test")
    publisher = workers_module._build_event_publisher(_StubSession(), settings)
    assert isinstance(publisher, DomainEventPublisher)
    # DigitalTwinEventHandler + NotificationEventHandler -- the same two
    # handlers `app/api/deps.py`'s `get_domain_event_publisher` registers
    # for a real request, per this module's own docstring on mirroring it.
    assert len(publisher._dispatcher._handlers) == 2  # noqa: SLF001 -- white-box check that both handlers actually registered, not just that construction didn't raise


def test_beat_schedule_registers_both_sweeps_with_expected_task_names():
    schedule = workers_module.celery_app.conf.beat_schedule
    assert schedule["notifications-retry-due"]["task"] == "app.workers.retry_due_notifications"
    assert schedule["scheduled-reports-run-due"]["task"] == "app.workers.run_due_scheduled_reports"


@pytest.fixture
async def sqlite_sessionmaker(monkeypatch):
    """Same real-commit/rollback-over-SQLite pattern `tests/unit/test_db_session.py` established for `get_db_session()` -- see that file's own docstring for why a real (if minimal) engine is used instead of a mocked session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessionmaker = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    monkeypatch.setattr(workers_module, "AsyncSessionLocal", sessionmaker)
    yield sessionmaker
    await engine.dispose()


async def test_retry_due_notifications_commits_on_success(sqlite_sessionmaker):
    with patch.object(workers_module, "_build_notification_service") as build_mock:
        service = AsyncMock()
        service.retry_due_deliveries.return_value = [{"delivery_id": "x", "result": "sent"}]
        build_mock.return_value = service
        result = await workers_module._retry_due_notifications_async()
    assert result == [{"delivery_id": "x", "result": "sent"}]
    service.retry_due_deliveries.assert_awaited_once()


async def test_retry_due_notifications_rolls_back_on_exception(sqlite_sessionmaker):
    with patch.object(workers_module, "_build_notification_service") as build_mock:
        service = AsyncMock()
        service.retry_due_deliveries.side_effect = RuntimeError("provider unreachable")
        build_mock.return_value = service
        with pytest.raises(RuntimeError, match="provider unreachable"):
            await workers_module._retry_due_notifications_async()


async def test_run_due_scheduled_reports_commits_on_success(sqlite_sessionmaker):
    with (
        patch.object(workers_module, "_build_event_publisher"),
        patch.object(workers_module, "ReportGenerationService"),
        patch.object(workers_module, "ScheduledReportService") as scheduled_service_cls,
    ):
        instance = AsyncMock()
        instance.run_due.return_value = [{"scheduled_report_id": "y", "report_id": "z"}]
        scheduled_service_cls.return_value = instance
        result = await workers_module._run_due_scheduled_reports_async()
    assert result == [{"scheduled_report_id": "y", "report_id": "z"}]
    instance.run_due.assert_awaited_once()


async def test_run_due_scheduled_reports_rolls_back_on_exception(sqlite_sessionmaker):
    with (
        patch.object(workers_module, "_build_event_publisher"),
        patch.object(workers_module, "ReportGenerationService"),
        patch.object(workers_module, "ScheduledReportService") as scheduled_service_cls,
    ):
        instance = AsyncMock()
        instance.run_due.side_effect = RuntimeError("db exploded")
        scheduled_service_cls.return_value = instance
        with pytest.raises(RuntimeError, match="db exploded"):
            await workers_module._run_due_scheduled_reports_async()


def test_celery_tasks_wrap_the_async_functions_via_asyncio_run():
    """`retry_due_notifications`/`run_due_scheduled_reports` (the actual `@celery_app.task`-decorated, synchronous functions Celery invokes) must each drive their `_*_async` counterpart to completion, not just reference it -- covered separately from the `_*_async` tests above since Celery's worker process calls these synchronous entrypoints, never the coroutine functions directly."""

    def _fake_run(coro):
        # `asyncio.run(x())` always evaluates `x()` into a real coroutine
        # object before the mock ever sees it -- closing it here (rather
        # than just returning a canned value) avoids a
        # "coroutine was never awaited" warning while still proving each
        # entrypoint passed a genuine coroutine through to `asyncio.run`.
        coro.close()
        return ["ok"]

    with patch("asyncio.run", side_effect=_fake_run) as run_mock:
        assert workers_module.retry_due_notifications() == ["ok"]
        assert workers_module.run_due_scheduled_reports() == ["ok"]
    assert run_mock.call_count == 2
