"""
Declarative base, naming convention, and shared column mixins.

Every model in app/models/ inherits from `Base` (directly or via one of the
mixins below). The naming convention is what makes Alembic autogenerate
produce stable, predictable constraint/index names across every table in
the schema instead of SQLAlchemy's default (unnamed / driver-generated)
names, which would otherwise make future migrations that ALTER or DROP a
constraint fragile and environment-dependent.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, MetaData, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Naming convention per SQLAlchemy's recommended production pattern.
# Referenced by every Alembic migration's autogenerate comparison.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Root declarative base for the entire schema."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # Production Database Readiness Review (Phase 5->6 gate) finding: every
    # `Mapped[datetime]` column was compiling to `TIMESTAMP WITHOUT TIME
    # ZONE`, SQLAlchemy's default for a bare `datetime` annotation. That's
    # wrong for a SaaS product whose nurseries/branches can legitimately
    # sit in different timezones (docs/architecture/05-database-architecture.md
    # never specified naive timestamps, and NFR expectations around
    # "revenue today" / "MTD" boundaries only make sense if `created_at` is
    # unambiguous in UTC). Registering the annotation map here, once, makes
    # every `Mapped[datetime]` column across all 49 tables resolve to
    # `TIMESTAMPTZ` without touching 42 individual column declarations —
    # fixed before Phase 6 per the readiness review's "fix before proceeding"
    # instruction. See docs/architecture/15-production-database-readiness-review.md
    # §1 (Schema Validation) for the finding this addresses.
    type_annotation_map = {datetime: DateTime(timezone=True)}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UUIDPKMixin:
    """
    Primary key strategy: UUID (via PostgreSQL's pgcrypto gen_random_uuid()),
    not sequential integers. Rationale is in
    docs/architecture/05-database-architecture.md §4 (Constraints) — avoids
    leaking record counts/creation order across tenants.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )


class TimestampMixin:
    """
    Every top-level entity carries created_at/updated_at per
    docs/ux/08-information-architecture.md §6 (Metadata Standards).
    created_by/updated_by are declared per-model (they're a FK to users,
    and a handful of system-generated tables like ai_predictions
    legitimately have no human "created_by").
    """

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=_utcnow, nullable=False
    )


class ActorStampMixin:
    """created_by / updated_by — mixed in only where a human actor applies."""

    @staticmethod
    def actor_fk():
        return mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class TenantMixin:
    """
    Every tenant-scoped table carries nursery_id, per
    docs/architecture/05-database-architecture.md §9 (Multi-Tenancy Approach).
    This column is also the leading column of every tenant-scoped table's
    composite index (§5, Indexing Strategy) and the column Row-Level
    Security policies key against (migration 0003).
    """

    nursery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nurseries.id", ondelete="RESTRICT"), nullable=False
    )


class BranchScopedMixin(TenantMixin):
    """Branch-scoped tables additionally carry branch_id (still nested under nursery_id)."""

    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False
    )
