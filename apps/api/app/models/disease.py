"""
Disease & Health bounded context: DiseaseReport (lifecycle entity, unlike
its append-only siblings in digital_twin_records.py) and Treatment.

Maps to docs/architecture/02-low-level-design.md "Module: Health & Disease".
Status enum matches the lifecycle in docs/ux/03-screen-flow-diagrams.md §4
(AI Disease Detection -> Treatment flow).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Enum as PgEnum
from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPKMixin
from app.db.enums import DiseaseReportSeverity, DiseaseReportStatus, TreatmentOutcome


class DiseaseReport(UUIDPKMixin, Base):
    """
    FR-7.2. Created either manually or automatically from an AI Disease
    Detection result above the auto-flag confidence threshold
    (source_ai_prediction_id is set in the latter case — see
    docs/architecture/06-ai-architecture.md §1's Disease Detection workflow).
    """

    __tablename__ = "disease_reports"
    __table_args__ = (
        Index("ix_disease_reports_plant_id", "plant_id"),
        Index("ix_disease_reports_status_severity", "status", "severity"),
    )

    plant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plants.id", ondelete="CASCADE"), nullable=False
    )
    source_ai_prediction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_predictions.id", ondelete="SET NULL"), nullable=True
    )
    condition_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[DiseaseReportStatus] = mapped_column(
        PgEnum(DiseaseReportStatus, name="disease_report_status"),
        nullable=False,
        default=DiseaseReportStatus.DRAFT,
    )
    severity: Mapped[DiseaseReportSeverity] = mapped_column(
        PgEnum(DiseaseReportSeverity, name="disease_report_severity"), nullable=False
    )
    is_ai_sourced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ai_confidence: Mapped[Numeric | None] = mapped_column(Numeric(5, 4), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    dismissed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)

    treatments: Mapped[list["Treatment"]] = relationship(
        back_populates="disease_report", cascade="all, delete-orphan"
    )


class Treatment(UUIDPKMixin, Base):
    """
    FR-7.3. A DiseaseReport can accumulate multiple treatment attempts
    before an outcome closes it (docs/architecture/05-database-architecture.md
    §3's cardinality note).
    """

    __tablename__ = "treatments"
    __table_args__ = (Index("ix_treatments_disease_report_id", "disease_report_id"),)

    disease_report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("disease_reports.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[TreatmentOutcome] = mapped_column(
        PgEnum(TreatmentOutcome, name="treatment_outcome"),
        nullable=False,
        default=TreatmentOutcome.ONGOING,
    )
    applied_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    applied_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)

    disease_report: Mapped["DiseaseReport"] = relationship(back_populates="treatments")
