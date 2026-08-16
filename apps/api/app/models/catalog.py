"""
Species Catalog bounded context — extended to a proper 3-level hierarchy
(PlantCategory -> Species -> PlantVariety) per the Phase 5 master-table
list, plus the Unit reference table used by Inventory.

Maps to docs/architecture/02-low-level-design.md "Module: Species Catalog".
PlantCategory and Unit are system metadata (seeded in
migrations/versions/0002_seed_system_metadata.py per the Phase 5 seed-data
rules — never business data); Species and PlantVariety remain per-Org
catalog data the customer maintains themselves (FR-4).
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    # Phase 6 Module 14 (Production Readiness) defect fix: `relationship()`
    # below type-hints `Mapped["Plant"]`, a forward reference to a class
    # defined in app/models/plants.py. Under `from __future__ import
    # annotations` (above) that string is never evaluated at runtime --
    # SQLAlchemy's own declarative mapper resolves it via its class
    # registry, not Python's name resolution, which is why this worked
    # correctly at runtime across every prior module's tests. Ruff's F821
    # check, however, IS static analysis of the annotation text, and with
    # no import of `Plant` anywhere in this file it correctly flagged the
    # name as unresolvable. This import (TYPE_CHECKING-guarded, so it
    # costs nothing at runtime and creates no import cycle with
    # app/models/plants.py, which does the same back to this module for
    # `Species`/`PlantVariety`) is the fix -- see docs/architecture/
    # 30-module14-production-readiness.md's defects section.
    from app.models.plants import Plant  # noqa: F401


class PlantCategory(UUIDPKMixin, Base):
    """
    System-metadata master table (e.g. Houseplant, Succulent, Shrub, Tree,
    Annual, Perennial, Herb). Global, not tenant-scoped — every Org shares
    the same category taxonomy so cross-nursery reporting/benchmarking
    stays meaningful (a deliberate difference from Species, which IS
    per-Org, since individual species/cultivar naming legitimately varies
    by nursery but a top-level category taxonomy shouldn't).
    """

    __tablename__ = "plant_categories"
    __table_args__ = (UniqueConstraint("code", name="uq_plant_categories_code"),)

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    species: Mapped[list["Species"]] = relationship(back_populates="category")


class Unit(UUIDPKMixin, Base):
    """
    System-metadata master table for measurement/count units used by
    Inventory and (optionally) recipe-style quantities elsewhere
    (e.g. each, flat, pot, kg, liter, bag). Global, not tenant-scoped.
    """

    __tablename__ = "units"
    __table_args__ = (UniqueConstraint("code", name="uq_units_code"),)

    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    unit_type: Mapped[str] = mapped_column(String(20), nullable=False, default="count")  # count|weight|volume


class Species(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """
    Reference/classification entity (FR-4). Care-requirement fields feed
    AI Water Recommendation and Growth Prediction baselines
    (docs/architecture/06-ai-architecture.md §4); disease_susceptibility
    feeds Disease Detection's confidence-threshold adjustment.
    """

    __tablename__ = "species"
    __table_args__ = (
        UniqueConstraint("nursery_id", "botanical_name", name="uq_species_nursery_botanical"),
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plant_categories.id", ondelete="RESTRICT"), nullable=False
    )
    common_name: Mapped[str] = mapped_column(String(255), nullable=False)
    botanical_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Care requirements (FR-4.1) — numeric ranges, validated min <= max at
    # the service layer (docs/architecture/02-low-level-design.md).
    light_requirement: Mapped[str | None] = mapped_column(String(50), nullable=True)
    water_baseline_ml_per_week: Mapped[int | None] = mapped_column(nullable=True)
    soil_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # `float | None`, not `Numeric | None` -- `Numeric` is the SQLAlchemy
    # *column type* (passed to `mapped_column` below), not a Python value
    # type; the Python-side annotation should describe what the ORM
    # attribute actually holds, matching the same `Numeric(...)` column /
    # `float` attribute pattern `Branch.latitude`/`longitude`
    # (app/models/organization.py, Phase 6 Module 4) already establishes.
    temperature_min_celsius: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    temperature_max_celsius: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    # Typical growth curve baseline, used when a plant has insufficient
    # plant-specific history (docs/architecture/06-ai-architecture.md §4).
    # Stored as JSON: [{"days_since_planting": int, "expected_height_cm": float}, ...]
    growth_curve_baseline: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Known disease susceptibilities, e.g. ["root_rot", "powdery_mildew"].
    disease_susceptibility: Mapped[list | None] = mapped_column(JSON, nullable=True)

    category: Mapped["PlantCategory"] = relationship(back_populates="species")
    varieties: Mapped[list["PlantVariety"]] = relationship(back_populates="species")
    plants: Mapped[list["Plant"]] = relationship(back_populates="species")


class PlantVariety(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """
    Cultivar/variety under a Species (e.g. Species "Ficus lyrata" ->
    Variety "Bambino", "Variegata"). Optional on Plant — most nurseries
    track at the Species level; specimen/collector-grade plants track down
    to the variety, which is why Plant.variety_id is nullable rather than
    every plant being forced through a variety row.
    """

    __tablename__ = "plant_varieties"
    __table_args__ = (
        UniqueConstraint("species_id", "name", name="uq_plant_varieties_species_name"),
    )

    species_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("species.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    species: Mapped["Species"] = relationship(back_populates="varieties")
    plants: Mapped[list["Plant"]] = relationship(back_populates="variety")
