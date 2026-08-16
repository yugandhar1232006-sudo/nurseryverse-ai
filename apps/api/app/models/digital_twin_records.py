"""
Digital Twin append-only history tables: Growth Timeline, Health History,
Environmental Readings, Watering Logs.

All four share the same architectural shape deliberately
(docs/architecture/05-database-architecture.md §3): FK to plants, no
update/delete endpoint exists for any of them (immutable once created,
per docs/architecture/02-low-level-design.md's Growth Timeline module
note — "entries are immutable once created"), and each is a primary
feature-input source for one or more AI modules
(docs/architecture/06-ai-architecture.md §4).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, JSON, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPKMixin


class GrowthTimeline(UUIDPKMixin, Base):
    """FR-6. Feeds AI Growth Prediction."""

    __tablename__ = "growth_timeline"
    __table_args__ = (Index("ix_growth_timeline_plant_id_recorded_at", "plant_id", "recorded_at"),)

    plant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plants.id", ondelete="CASCADE"), nullable=False
    )
    height_cm: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    spread_cm: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    growth_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)

    # Added by migration 0010 (Module 6) -- see that migration's docstring.
    leaf_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    flower_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fruit_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    photo_urls: Mapped[list | None] = mapped_column(JSON, nullable=True)


class HealthHistory(UUIDPKMixin, Base):
    """FR-7.1. Feeds AI Survival Prediction."""

    __tablename__ = "health_history"
    __table_args__ = (Index("ix_health_history_plant_id_recorded_at", "plant_id", "recorded_at"),)

    plant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plants.id", ondelete="CASCADE"), nullable=False
    )
    status_label: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. healthy, stressed, recovering -- also carries "Recovery status"
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)

    # Added by migration 0010 (Module 6) -- see that migration's docstring.
    # `is_ai_observation` mirrors `DiseaseReport.is_ai_sourced`'s already-
    # established manual-vs-AI distinction. "Disease history"/"Treatment
    # history" (the other two items in Module 6's Health Records list) are
    # deliberately NOT duplicated onto this table -- they're queried live
    # from `disease_reports`/`treatments` (DiseaseReportRepository.
    # list_for_plant), the same "don't create duplicate business logic"
    # instruction Module 5 already applied to Species/plants counting.
    health_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    is_ai_observation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class EnvironmentalReading(UUIDPKMixin, Base):
    """
    FR-10. Tied to a Branch (always) and optionally a specific Plant/zone.
    Also reachable via the API-key-authenticated ingest endpoint (FR-10.2)
    for third-party sensor integrations — `source` distinguishes manual
    from ingested readings.
    """

    __tablename__ = "environmental_readings"
    __table_args__ = (
        Index("ix_environmental_readings_branch_recorded_at", "branch_id", "recorded_at"),
        Index("ix_environmental_readings_plant_id", "plant_id"),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False
    )
    plant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plants.id", ondelete="CASCADE"), nullable=True
    )
    zone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    temperature_celsius: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    humidity_percent: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    soil_moisture_percent: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    light_lux: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")  # manual|ingest
    recorded_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)

    # Added by migration 0010 (Module 6) -- see that migration's docstring.
    ph_level: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    weather_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class FertilizerLog(UUIDPKMixin, Base):
    """
    Parallel structure to WateringLog, added at the Phase 5 master-table
    review (fertilizing wasn't broken out as its own workflow in Phase
    1-4's functional requirements, which folded feeding schedules under
    general "care"; it's modeled as its own append-only table here, same
    shape as WateringLog, so it can be surfaced identically in the UI and
    fed into AI Water/Growth modules as an additional feature later
    without a schema change).
    """

    __tablename__ = "fertilizer_logs"
    __table_args__ = (
        Index("ix_fertilizer_logs_plant_id_recorded_at", "plant_id", "recorded_at"),
        Index("ix_fertilizer_logs_branch_zone", "branch_id", "zone"),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False
    )
    plant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plants.id", ondelete="CASCADE"), nullable=True
    )
    zone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity_ml: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    npk_ratio: Mapped[str | None] = mapped_column(String(20), nullable=True)  # e.g. "10-10-10"
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)

    # Added by migration 0010 (Module 6) -- see that migration's docstring.
    method: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g. "soil_drench", "foliar_spray"
    schedule: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g. "weekly", "biweekly"
    next_application_date: Mapped[datetime | None] = mapped_column(nullable=True)


class WateringLog(UUIDPKMixin, Base):
    """FR-11.1. Feeds AI Water Recommendation and overdue-detection scheduling."""

    __tablename__ = "watering_logs"
    __table_args__ = (
        Index("ix_watering_logs_plant_id_recorded_at", "plant_id", "recorded_at"),
        Index("ix_watering_logs_branch_zone", "branch_id", "zone"),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False
    )
    plant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plants.id", ondelete="CASCADE"), nullable=True
    )
    zone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    volume_ml: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)

    # Added by migration 0010 (Module 6) -- see that migration's docstring.
    method: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g. "drip", "hose", "sprinkler"
