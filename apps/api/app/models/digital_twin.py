"""
Digital Twin Engine bounded context (Phase 6 Module 7). Three tables,
migration 0011:

  - `digital_twins` -- one row per Plant, the CURRENT read-optimized
    projection. Cheap to read (O(1) row lookup), cheap to update (one
    UPDATE per event, small JSON `snapshot`).
  - `digital_twin_versions` -- append-only, one row per projection update.
    Every version carries a *complete* snapshot (not a diff) so historical
    playback/snapshot-by-date/version-comparison are all single-row reads,
    never a replay-from-scratch — see `app/services/digital_twin_service.py`
    for why full-snapshot-per-version was chosen over diffs.
  - `event_dispatch_log` -- one row per (event, handler) dispatch attempt.
    The idempotency/retry-safety/audit mechanism for `EventDispatcher`
    (app/domain_events/dispatcher.py).

Architectural split from Module 6's own tables (`plants`,
`growth_timeline`, `health_history`, ...): those are the normalized,
transactional source of truth every write path (PlantService,
GrowthService, ...) writes to directly. `digital_twins`/
`digital_twin_versions` are a *derived*, denormalized, versioned read
projection, populated exclusively by consuming the `domain_events`
those write paths already emit -- never written to by any Module 6
route or service. This is the classic CQRS split, and it's what makes
"no API route should modify the Digital Twin directly" a structural
guarantee rather than a convention: there is no `DigitalTwinRepository.
update()` call anywhere outside `DigitalTwinService`'s own event
handlers. See docs/architecture/23-module7-digital-twin-engine.md for
the full reasoning, including how this reconciles with Module 6's own
doc, which (correctly, for its own purposes) describes the Plant row
itself as "the Digital Twin" -- Module 6's tables are the write-side
source of truth; this module's tables are the read-side projection
built from it.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy import Enum as PgEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.enums import EventDispatchStatus


class DigitalTwin(UUIDPKMixin, TimestampMixin, Base):
    """
    Current projection -- exactly one row per Plant, created the moment a
    `plant.registered` event is projected (see `DigitalTwinService.
    _project_plant_registered`) and updated in place thereafter by every
    subsequent event. `snapshot` stores *latest-value summaries and
    counts*, not growing lists -- full historical timelines are served by
    querying `digital_twin_versions`/`domain_events` directly (a separate,
    indexed, paginated read path). This keeps every projection update an
    O(1)-sized write regardless of how long a plant has been alive,
    directly serving the module's "minimal write amplification"
    performance requirement.
    """

    __tablename__ = "digital_twins"
    __table_args__ = (
        UniqueConstraint("plant_id", name="uq_digital_twins_plant_id"),
        Index("ix_digital_twins_nursery_id", "nursery_id"),
        Index("ix_digital_twins_branch_id", "branch_id"),
        Index("ix_digital_twins_lifecycle_state", "lifecycle_state"),
    )

    plant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plants.id", ondelete="CASCADE"), nullable=False
    )
    nursery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nurseries.id", ondelete="CASCADE"), nullable=False
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lifecycle_state: Mapped[str] = mapped_column(String(50), nullable=False)
    operational_status: Mapped[str] = mapped_column(String(50), nullable=False)
    growth_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("domain_events.id", ondelete="SET NULL"), nullable=True
    )
    last_event_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_event_sequence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_projected_at: Mapped[datetime | None] = mapped_column(nullable=True)


class DigitalTwinVersion(UUIDPKMixin, Base):
    """
    Immutable, append-only version history -- migration 0011 also installs
    a DB-level trigger rejecting UPDATE/DELETE on this table (mirroring
    `audit_logs`' own migration-0004 immutability enforcement), because
    "No historical record may be overwritten" is a hard requirement, not
    a code-review convention.

    `snapshot` is the *complete* twin state after this event was applied
    (self-contained -- reconstructing version N never requires reading
    version N-1), which is what makes "Snapshot retrieval"/"Historical
    playback"/"Version comparison" each a single indexed row read.
    """

    __tablename__ = "digital_twin_versions"
    __table_args__ = (
        UniqueConstraint("plant_id", "version", name="uq_digital_twin_versions_plant_version"),
        Index("ix_digital_twin_versions_plant_sequence", "plant_id", "event_sequence"),
        Index("ix_digital_twin_versions_plant_occurred", "plant_id", "occurred_at"),
    )

    plant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plants.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("domain_events.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)


class EventDispatchLog(UUIDPKMixin, Base):
    """
    One row per (event_id, handler_name) dispatch attempt -- the
    idempotency/retry-safety/audit mechanism `EventDispatcher`
    (app/domain_events/dispatcher.py) depends on. Deliberately mutable
    (unlike `digital_twin_versions`): a failed attempt is upserted in
    place when retried, so `attempt_count` accumulates on the same row
    rather than growing an unbounded attempt history for a single
    (event, handler) pair -- the resulting *projection* immutability is
    what the spec actually requires, not immutability of the dispatch
    bookkeeping itself.
    """

    __tablename__ = "event_dispatch_log"
    __table_args__ = (
        UniqueConstraint("event_id", "handler_name", name="uq_event_dispatch_log_event_handler"),
        Index("ix_event_dispatch_log_handler_status", "handler_name", "status"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("domain_events.id", ondelete="CASCADE"), nullable=False
    )
    handler_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[EventDispatchStatus] = mapped_column(
        PgEnum(EventDispatchStatus, name="event_dispatch_status"), nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    resulting_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    processed_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)


__all__ = ["DigitalTwin", "DigitalTwinVersion", "EventDispatchLog"]
