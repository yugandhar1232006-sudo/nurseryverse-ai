"""
Unit tests for `EventDispatcher` in isolation (app/domain_events/
dispatcher.py) -- idempotency, retry-safety, and "only invoke interested
handlers" behavior, independent of the Digital Twin projector itself
(that integration is covered by test_digital_twin_service.py's own
idempotency/ordering tests).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.db.enums import EventDispatchStatus
from app.domain_events.dispatcher import EventDispatcher
from app.models.events import DomainEvent
from tests.fakes.repositories import FakeEventDispatchLogRepository

pytestmark = pytest.mark.unit


def _event(event_type: str = "plant.registered", *, sequence: int = 1) -> DomainEvent:
    return DomainEvent(
        id=uuid.uuid4(), event_type=event_type, aggregate_type="Plant", aggregate_id=uuid.uuid4(),
        nursery_id=uuid.uuid4(), actor_user_id=None, payload={}, occurred_at=datetime.now(timezone.utc),
        sequence=sequence,
    )


class _RecordingHandler:
    """A minimal, real `EventHandler` implementation -- not a mock -- for isolating dispatcher behavior."""

    def __init__(self, name: str, event_types: frozenset[str], *, fail_times: int = 0) -> None:
        self.name = name
        self.event_types = event_types
        self.calls: list[DomainEvent] = []
        self._fail_times = fail_times

    async def handle(self, event: DomainEvent) -> int:
        self.calls.append(event)
        if len(self.calls) <= self._fail_times:
            raise RuntimeError("simulated handler failure")
        return len(self.calls)


async def test_dispatch_invokes_a_registered_handler_for_a_matching_event_type():
    dispatch_log = FakeEventDispatchLogRepository()
    dispatcher = EventDispatcher(dispatch_log)
    handler = _RecordingHandler("test_handler", frozenset({"plant.registered"}))
    dispatcher.register(handler)

    await dispatcher.dispatch(_event("plant.registered"))

    assert len(handler.calls) == 1


async def test_dispatch_skips_a_handler_not_interested_in_the_event_type():
    dispatch_log = FakeEventDispatchLogRepository()
    dispatcher = EventDispatcher(dispatch_log)
    handler = _RecordingHandler("test_handler", frozenset({"plant.watering_recorded"}))
    dispatcher.register(handler)

    await dispatcher.dispatch(_event("plant.registered"))

    assert handler.calls == []


async def test_dispatch_fans_out_to_every_interested_handler():
    dispatch_log = FakeEventDispatchLogRepository()
    dispatcher = EventDispatcher(dispatch_log)
    handler_a = _RecordingHandler("handler_a", frozenset({"plant.registered"}))
    handler_b = _RecordingHandler("handler_b", frozenset({"plant.registered"}))
    dispatcher.register(handler_a)
    dispatcher.register(handler_b)

    event = _event("plant.registered")
    await dispatcher.dispatch(event)

    assert len(handler_a.calls) == 1
    assert len(handler_b.calls) == 1


async def test_duplicate_dispatch_of_the_same_event_id_is_idempotent():
    dispatch_log = FakeEventDispatchLogRepository()
    dispatcher = EventDispatcher(dispatch_log)
    handler = _RecordingHandler("test_handler", frozenset({"plant.registered"}))
    dispatcher.register(handler)
    event = _event("plant.registered")

    await dispatcher.dispatch(event)
    await dispatcher.dispatch(event)  # exact same event row, dispatched twice

    assert len(handler.calls) == 1  # handler only actually ran once
    log_row = await dispatch_log.get(event.id, "test_handler")
    assert log_row.status == EventDispatchStatus.SUCCEEDED
    assert log_row.attempt_count == 1


async def test_failed_handler_is_logged_and_does_not_raise():
    dispatch_log = FakeEventDispatchLogRepository()
    dispatcher = EventDispatcher(dispatch_log)
    handler = _RecordingHandler("flaky_handler", frozenset({"plant.registered"}), fail_times=99)
    dispatcher.register(handler)
    event = _event("plant.registered")

    await dispatcher.dispatch(event)  # must not raise -- see EventDispatcher.dispatch's own docstring

    log_row = await dispatch_log.get(event.id, "flaky_handler")
    assert log_row.status == EventDispatchStatus.FAILED
    assert "simulated handler failure" in log_row.error_message
    assert log_row.attempt_count == 1


async def test_retry_after_failure_increments_attempt_count_and_can_succeed():
    dispatch_log = FakeEventDispatchLogRepository()
    dispatcher = EventDispatcher(dispatch_log)
    handler = _RecordingHandler("flaky_handler", frozenset({"plant.registered"}), fail_times=1)
    dispatcher.register(handler)
    event = _event("plant.registered")

    await dispatcher.dispatch(event)  # fails (1st call)
    first_log = await dispatch_log.get(event.id, "flaky_handler")
    assert first_log.status == EventDispatchStatus.FAILED
    assert first_log.attempt_count == 1

    await dispatcher.dispatch(event)  # retried -- succeeds (2nd call)
    second_log = await dispatch_log.get(event.id, "flaky_handler")
    assert second_log.status == EventDispatchStatus.SUCCEEDED
    assert second_log.attempt_count == 2
    assert len(handler.calls) == 2


async def test_list_failed_returns_only_failed_rows_optionally_scoped_to_a_handler():
    dispatch_log = FakeEventDispatchLogRepository()
    dispatcher = EventDispatcher(dispatch_log)
    always_fails = _RecordingHandler("always_fails", frozenset({"plant.registered"}), fail_times=99)
    always_succeeds = _RecordingHandler("always_succeeds", frozenset({"plant.registered"}))
    dispatcher.register(always_fails)
    dispatcher.register(always_succeeds)

    await dispatcher.dispatch(_event("plant.registered"))

    all_failed = await dispatcher.list_failed()
    assert len(all_failed) == 1
    assert all_failed[0].handler_name == "always_fails"

    scoped = await dispatcher.list_failed(handler_name="always_succeeds")
    assert scoped == []
