"""
Plants (Digital Twin) bounded context — the system's core entity, per
docs/ux/08-information-architecture.md §1 (Organizing Principle).

Maps to docs/architecture/02-low-level-design.md "Module: Plants".
Status lifecycle matches docs/ux/13-digital-twin-lifecycle.md exactly —
`status` is a native Postgres ENUM (app.db.enums.PlantStatus), and illegal
transitions are rejected by PlantService before they ever reach a write
(the enum only constrains *valid values*, not *valid transitions*; the
transition graph itself is enforced in the service layer per the LLD,
since expressing a full state-machine graph as a DB constraint would be
more fragile than useful here).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum as PgEnum
from sqlalchemy import ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BranchScopedMixin, Base, TimestampMixin, UUIDPKMixin
from app.db.enums import PlantStatus

if TYPE_CHECKING:
    # Same ruff F821 fix as app/models/catalog.py's own TYPE_CHECKING
    # block -- see that file's comment for the full explanation. `Species`/
    # `PlantVariety` live in app/models/catalog.py, which does the same
    # TYPE_CHECKING-guarded import back to this module for `Plant` --
    # both sides are guarded, so this is not a real circular-import
    # (runtime-evaluated) dependency.
    from app.models.catalog import PlantVariety, Species  # noqa: F401


class Plant(UUIDPKMixin, BranchScopedMixin, TimestampMixin, Base):
    """The Digital Twin root entity (FR-5)."""

    __tablename__ = "plants"
    __table_args__ = (
        UniqueConstraint("qr_code_token", name="uq_plants_qr_code_token"),
        # Leading-nursery_id-then-branch_id composite index per
        # docs/architecture/05-database-architecture.md §5 (every
        # tenant-scoped table's primary lookup pattern).
        Index("ix_plants_nursery_branch", "nursery_id", "branch_id"),
        Index("ix_plants_status", "status"),
        Index("ix_plants_species_id", "species_id"),
    )

    species_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("species.id", ondelete="RESTRICT"), nullable=False
    )
    variety_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plant_varieties.id", ondelete="RESTRICT"), nullable=True
    )
    common_label: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # optional human-friendly identifier beyond the species name
    zone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[PlantStatus] = mapped_column(
        PgEnum(PlantStatus, name="plant_status"),
        nullable=False,
        default=PlantStatus.IN_PRODUCTION,
    )
    qr_code_token: Mapped[str] = mapped_column(String(64), nullable=False)
    # `float`, not `Numeric` -- `Numeric` is the SQLAlchemy column type, not
    # a Python value type; using it as the `Mapped[...]` annotation is the
    # same latent bug Module 5 fixed on `Species.temperature_*_celsius`
    # (see that module's docs). Fixed proactively here since Module 6's
    # own service code is the first to actually read/write this field.
    price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    planted_at: Mapped[datetime] = mapped_column(nullable=False)
    sold_at: Mapped[datetime | None] = mapped_column(nullable=True)
    deceased_at: Mapped[datetime | None] = mapped_column(nullable=True)
    deceased_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Added by Phase 6 Module 6 (Plant Lifecycle Management) --
    # migration 0010. See that migration's docstring for the full
    # rationale (batch/supplier/purchase-info/ownership-tracking gap).
    batch_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True
    )
    purchase_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    purchase_date: Mapped[datetime | None] = mapped_column(nullable=True)
    registered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Administrative "Archive" action -- deliberately a nullable timestamp,
    # not a sixth PlantStatus value. Same shape as sold_at/deceased_at
    # above, not a business-lifecycle transition: hides a plant from
    # default active listings while its full history stays queryable
    # forever, same as NurseryStatus.ARCHIVED/BranchStatus.INACTIVE.
    archived_at: Mapped[datetime | None] = mapped_column(nullable=True)
    archived_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optional free-text description/notes for the plant record.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    species: Mapped["Species"] = relationship(back_populates="plants")
    variety: Mapped["PlantVariety"] = relationship(back_populates="plants")
    images: Mapped[list["PlantImage"]] = relationship(
        back_populates="plant", cascade="all, delete-orphan"
    )
    transfers: Mapped[list["PlantTransfer"]] = relationship(
        back_populates="plant", cascade="all, delete-orphan"
    )


class PlantImage(UUIDPKMixin, Base):
    """
    Append-only photo history (FR-5.1, FR-6.1, FR-7.1). No nursery_id/
    branch_id of its own — always accessed through its parent Plant, which
    is itself branch-scoped (avoids duplicating the tenant columns on every
    single history table when the parent already carries them; RLS on this
    table is expressed as a join-based policy — see migration 0003).
    """

    __tablename__ = "plant_images"
    __table_args__ = (Index("ix_plant_images_plant_id", "plant_id"),)

    plant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plants.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    caption: Mapped[str | None] = mapped_column(String(255), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    plant: Mapped["Plant"] = relationship(back_populates="images")


class PlantTransfer(UUIDPKMixin, Base):
    """
    Append-only transfer history (FR-5.5, US-C.4). Spans two branches, so
    it carries nursery_id directly rather than inheriting BranchScopedMixin
    (there's no single branch_id that correctly scopes a cross-branch event).
    """

    __tablename__ = "plant_transfers"
    __table_args__ = (Index("ix_plant_transfers_plant_id", "plant_id"),)

    nursery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nurseries.id", ondelete="CASCADE"), nullable=False
    )
    plant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plants.id", ondelete="CASCADE"), nullable=False
    )
    from_branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False
    )
    to_branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False
    )
    # Added by migration 0010 (Module 6). Nullable, and orthogonal to the
    # branch columns above: a branch transfer may leave these null; a
    # zone-only/greenhouse/outdoor movement within the *same* branch sets
    # from_branch_id == to_branch_id and populates these instead. One
    # table models every kind of Plant Movement the module requires,
    # rather than three near-duplicate history tables -- see the
    # migration's own docstring.
    from_zone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    to_zone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    transferred_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    transferred_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)

    plant: Mapped["Plant"] = relationship(back_populates="transfers")
