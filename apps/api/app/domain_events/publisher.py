"""
`DomainEventPublisher` -- the single place a `BaseDomainEvent` subclass
gets translated into a persisted `domain_events` row
(app/repositories/interfaces.py's `DomainEventRepository`, satisfied by
both the real SQLAlchemy repository and an in-memory fake for tests, the
same Protocol-based pattern every other repository in this codebase
follows).

Services never write to the `domain_events` table directly -- they build
an event dataclass and call `publisher.publish(event, request_id=...)`,
so "how an event gets persisted" (JSON-safety, timestamp assignment) is
defined exactly once, not re-derived per service.

`dispatcher` (optional, added by Phase 6 Module 7): if provided, every
successfully persisted event is immediately handed to `EventDispatcher.
dispatch()` -- this is the one line that turns "Module 4 built an outbox
table" into "the outbox actually drives the Digital Twin Engine's
event-driven architecture" (see app/domain_events/dispatcher.py's module
docstring for the full flow). Optional and defaulting to `None` so every
pre-Module-7 call site (`DomainEventPublisher(repo)`, positional, no
dispatcher) keeps working unchanged -- only app/api/deps.py's
`get_domain_event_publisher` wiring needed to change.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.domain_events.events import BaseDomainEvent
from app.models.events import DomainEvent as DomainEventRow
from app.repositories.interfaces import DomainEventRepository

if TYPE_CHECKING:
    from app.domain_events.dispatcher import EventDispatcher


def _json_safe(value):
    """Recursively converts UUIDs/tuples (common in event payloads) into JSON-native types."""
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    return value


class DomainEventPublisher:
    def __init__(self, repo: DomainEventRepository, dispatcher: "EventDispatcher | None" = None) -> None:
        self._repo = repo
        self._dispatcher = dispatcher

    def set_dispatcher(self, dispatcher: "EventDispatcher") -> None:
        """
        Attaches (or replaces) the dispatcher after construction. Exists
        for `tests/conftest.py`'s harness, which builds a single, shared
        `DomainEventPublisher` before every Module 6 repository (and
        therefore before `DigitalTwinService`, which depends on them)
        exists yet -- every service that already captured a reference to
        this same publisher instance sees the dispatcher the moment it's
        attached, since they all share the one object. Production wiring
        (app/api/deps.py's `get_domain_event_publisher`) never needs this;
        it builds the dispatcher first and passes it to the constructor.
        """
        self._dispatcher = dispatcher

    async def publish(self, event: BaseDomainEvent, *, request_id: str | None = None) -> DomainEventRow:
        row = DomainEventRow(
            event_type=event.event_type,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            nursery_id=event.nursery_id,
            actor_user_id=event.actor_user_id,
            payload=_json_safe(event.payload()),
            request_id=request_id,
            occurred_at=datetime.now(timezone.utc),
        )
        row = await self._repo.add(row)
        if self._dispatcher is not None:
            # `EventDispatcher.dispatch()` never raises (see its own
            # docstring) -- a Digital Twin projection failure must never
            # fail the write that emitted the event. No try/except needed
            # here; the dispatcher itself is the boundary that swallows
            # handler errors and records them to `event_dispatch_log`.
            await self._dispatcher.dispatch(row)
        return row
