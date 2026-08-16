"""
`EventDispatcher` -- the in-process event bus that turns a persisted
`domain_events` row into calls against every interested `EventHandler`.

Architecture (Phase 6 Module 7's own diagram):

    Plant Action -> Domain Event -> Digital Twin Event Handler
                  -> Digital Twin Service -> Projection Update
                  -> Database -> API

`DomainEventPublisher.publish()` (app/domain_events/publisher.py) calls
`dispatcher.dispatch(row)` immediately after persisting the event, in the
same request -- there is no message broker or background worker in this
codebase (no prior module introduced one; inventing a fake one here would
violate the "no placeholders/mocks" instruction), so "event-driven" here
means "synchronous, in-process pub/sub", not "asynchronous, out-of-process
messaging". What still makes this a genuine event-driven architecture
rather than the write path just calling the projector directly:

  - The write path (PlantService, GrowthService, ...) has zero references
    to `DigitalTwinService` or the projector -- it only ever constructs an
    event dataclass and calls `publisher.publish()`. Coupling is entirely
    through the `domain_events` outbox and this dispatcher, exactly as the
    architecture diagram specifies -- swapping this dispatcher for a real
    message-queue consumer later requires zero changes to any Module 6
    service.
  - Dispatch failures are caught and logged (`EventDispatchLog`), never
    propagated to the caller: a Digital Twin projection bug must never
    fail a `POST /plants` request. This is the actual reason CQRS
    architectures decouple the write and read sides -- the read
    projection's health is never allowed to gate the write.
  - Idempotency, ordering, and retry-safety are handled as real
    mechanisms (see `_dispatch_to_handler` and `EventHandler` below), not
    just implied by "call it once, synchronously".
"""
from __future__ import annotations

import logging
from typing import Protocol

from app.db.enums import EventDispatchStatus
from app.models.events import DomainEvent
from app.repositories.interfaces import EventDispatchLogRepository

logger = logging.getLogger(__name__)


class EventHandler(Protocol):
    """
    `name` is the handler's identity in `event_dispatch_log` (part of the
    idempotency key `(event_id, handler_name)`) -- must be stable across
    deploys, not e.g. a class's `repr()`. `event_types` is the exact set
    of `DomainEvent.event_type` strings this handler reacts to; the
    dispatcher never invokes a handler for an event type it didn't
    declare interest in.
    """

    name: str
    event_types: frozenset[str]

    async def handle(self, event: DomainEvent) -> int | None:
        """
        Apply one event. Returns the resulting version number (recorded
        in `event_dispatch_log.resulting_version` for audit purposes) or
        `None` if the handler doesn't produce a version. Must raise on
        failure -- the dispatcher is what decides failures are swallowed,
        not the handler.
        """
        ...


class EventDispatcher:
    """
    Holds a flat list of registered handlers and, for each `dispatch()`
    call, invokes every handler whose `event_types` includes the event's
    `event_type`. One event can fan out to multiple handlers (none yet in
    this codebase beyond the Digital Twin projector, but nothing here
    assumes exactly one).
    """

    def __init__(self, dispatch_log_repo: EventDispatchLogRepository) -> None:
        self._dispatch_log_repo = dispatch_log_repo
        self._handlers: list[EventHandler] = []

    def register(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    async def dispatch(self, event: DomainEvent) -> None:
        """
        Never raises -- see module docstring's "Dispatch failures are
        caught and logged" point. Ordering: this method is always called
        synchronously, immediately after the event's own `INSERT`
        completes, in `sequence` order by construction (the caller
        publishes events one at a time); `DigitalTwinService`'s own
        per-event handlers additionally guard against ever regressing an
        already-applied projection (see `_project` there), so even a
        hypothetical future out-of-order redelivery can't corrupt state.
        """
        for handler in self._handlers:
            if event.event_type in handler.event_types:
                await self._dispatch_to_handler(event, handler)

    async def _dispatch_to_handler(self, event: DomainEvent, handler: EventHandler) -> None:
        existing = await self._dispatch_log_repo.get(event.id, handler.name)
        if existing is not None and existing.status == EventDispatchStatus.SUCCEEDED:
            # Idempotent no-op: this exact (event, handler) pair already
            # succeeded -- a duplicate `dispatch()` call (e.g. a caller
            # accidentally publishing/dispatching the same row twice)
            # must never re-apply the projection update a second time.
            return
        attempt_count = (existing.attempt_count + 1) if existing is not None else 1
        try:
            resulting_version = await handler.handle(event)
        except Exception as exc:  # noqa: BLE001 -- deliberately broad: a handler bug must never escape the dispatcher.
            logger.exception(
                "Event dispatch failed: handler=%s event_id=%s event_type=%s attempt=%d",
                handler.name, event.id, event.event_type, attempt_count,
            )
            await self._dispatch_log_repo.upsert(
                event_id=event.id,
                handler_name=handler.name,
                status=EventDispatchStatus.FAILED,
                attempt_count=attempt_count,
                resulting_version=None,
                error_message=str(exc)[:2000],
            )
            return
        await self._dispatch_log_repo.upsert(
            event_id=event.id,
            handler_name=handler.name,
            status=EventDispatchStatus.SUCCEEDED,
            attempt_count=attempt_count,
            resulting_version=resulting_version,
            error_message=None,
        )

    async def list_failed(self, *, handler_name: str | None = None, limit: int = 100) -> list:
        """
        Retry-safety's inspection path: every `FAILED` dispatch log row
        (optionally scoped to one handler), for an operator to see what
        needs recovery. The actual recovery action is
        `DigitalTwinService.replay_for_plant(plant_id)` -- a full replay
        from `domain_events` rebuilds the *entire* projection from the
        authoritative source of truth in one idempotent operation, which
        is simpler and strictly more robust than re-driving one failed
        `(event, handler)` pair at a time (a piecemeal retry risks
        re-applying events out of the order they'd have projected in on a
        clean run; a full replay never can, by construction -- see
        `replay_for_plant`'s own docstring).
        """
        return await self._dispatch_log_repo.list_failed(handler_name=handler_name, limit=limit)
