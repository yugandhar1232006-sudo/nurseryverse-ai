"""
Domain events bounded context. Added by Phase 6 Module 4, whose spec
explicitly requires named domain events (NurseryCreated, BranchUpdated,
EmployeeInvited, ...) to be *generated*, not just implied by an audit-log
row. `audit_logs` (Phase 5) already records "what changed"; `domain_events`
is a distinct, append-only outbox purpose-built for "what happened,
structured for another part of the system to react to" — exactly the shape
docs/architecture/02-low-level-design.md's Notifications module already
assumes exists ("domain event -> NotificationService.create()"), and every
later module's own domain events (PlantRegistered, SaleCompleted, ...) land
in this same table rather than each module inventing its own event log.

Distinct from both existing audit tables on purpose:
  - `audit_logs` requires a human `actor_user_id`-shaped mutation record
    for compliance/who-did-what review; a domain event is a structured
    fact about the domain ("this Branch now exists") consumed by other
    code, not primarily by a human auditor.
  - `authorization_denials`/`security_events` are auth-lifecycle logs,
    unrelated to business-domain state changes.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, JSON, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPKMixin


class DomainEvent(UUIDPKMixin, Base):
    """
    One row per emitted domain event. Append-only (no `updated_at` — an
    event, once it happened, never changes) and deliberately generic
    (`event_type` + `payload` JSON) rather than one table per event type,
    the same reasoning `security_events` already applied in Module 2: a
    single, uniform log is what makes "list everything that happened to
    this Nursery, in order" a single indexed query instead of a UNION
    across a growing number of event-specific tables.

    `nursery_id` is nullable because a future platform-level event (e.g. a
    cross-tenant billing event) might legitimately have none — every
    Module 4 event populates it, since Nursery is this module's own tenant
    root.

    `sequence` was added by Phase 6 Module 7 (Plant Digital Twin Engine),
    migration 0011. `id` is a UUIDv4 (app/db/base.py's `UUIDPKMixin`) —
    deliberately non-sortable (avoids leaking row-count/creation-order
    across tenants), which is exactly right for a primary key but wrong
    for "process these events in the order they actually happened": two
    events persisted in the same microsecond can't be told apart by
    `occurred_at` alone, and the Digital Twin's event-driven projector
    needs a true, gap-tolerant total order to guarantee "Events must be
    Ordered" and to make event replay deterministic. `sequence` is a
    Postgres `BIGSERIAL` (a real auto-incrementing sequence, assigned at
    insert time, monotonically increasing across the whole table) — the
    dispatcher and `DigitalTwinService.replay_for_plant` both order by
    this column, never by `occurred_at`.
    """

    __tablename__ = "domain_events"
    __table_args__ = (
        Index("ix_domain_events_nursery_occurred", "nursery_id", "occurred_at"),
        Index("ix_domain_events_type_occurred", "event_type", "occurred_at"),
        Index("ix_domain_events_aggregate_sequence", "aggregate_id", "sequence"),
    )

    event_type: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "nursery.created"
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "Nursery"
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    nursery_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nurseries.id", ondelete="SET NULL"), nullable=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)
    # Added by migration 0011 (Module 7) -- see class docstring above.
    # `server_default` mirrors the migration's `ALTER COLUMN ... SET
    # DEFAULT nextval(...)` exactly -- without declaring it here too,
    # SQLAlchemy wouldn't know a server-side default exists and would try
    # to INSERT an explicit NULL for any ORM-constructed row that doesn't
    # set `.sequence` itself, violating the column's NOT NULL constraint
    # (the same reasoning `UUIDPKMixin.id`'s own `server_default=
    # func.gen_random_uuid()` already establishes for this codebase).
    sequence: Mapped[int] = mapped_column(
        BigInteger, server_default=text("nextval('domain_events_sequence_seq')"), nullable=False
    )
