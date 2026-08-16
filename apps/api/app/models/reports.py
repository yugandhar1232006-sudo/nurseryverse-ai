"""
Reports & Plant Passport bounded context.

Maps to docs/architecture/02-low-level-design.md "Module: Reports & Plant
Passport" — includes the one deliberate unauthenticated-access pattern in
the whole system (Passport.public_token), per
docs/ux/15-plant-passport-workflow.md.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Enum as PgEnum
from sqlalchemy import ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from sqlalchemy import Boolean

from app.db.base import Base, TenantMixin, UUIDPKMixin
from app.db.enums import ReportFormat, ReportScheduleFrequency, ReportStatus, ReportType


class Report(UUIDPKMixin, TenantMixin, Base):
    """FR-18.2. Async-generated report metadata; the file itself lives in Cloudinary."""

    __tablename__ = "reports"
    __table_args__ = (Index("ix_reports_nursery_created_at", "nursery_id", "created_at"),)

    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=True
    )
    report_type: Mapped[ReportType] = mapped_column(
        PgEnum(ReportType, name="report_type"), nullable=False
    )
    format: Mapped[ReportFormat] = mapped_column(
        PgEnum(ReportFormat, name="report_format"), nullable=False
    )
    status: Mapped[ReportStatus] = mapped_column(
        PgEnum(ReportStatus, name="report_status"), nullable=False, default=ReportStatus.PENDING
    )
    filters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    file_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class ScheduledReport(UUIDPKMixin, TenantMixin, Base):
    """
    Added by Phase 6 Module 12 (Reports & Analytics) — "Saved Reports /
    Scheduled Reports / Recurring Reports / Email Delivery / Notification
    Delivery". A saved *definition* ("send me the Sales report every
    Monday") distinct from `Report`, which is one *generated instance*.
    `ScheduledReportService.run_due()` finds rows whose `next_run_at` has
    passed, generates a fresh `Report` from the saved `report_type`/
    `format`/`filters`, delivers it (email via the existing `EmailSender`
    from Module 2 + an in-app `Notification` via Module 11's pipeline),
    and advances `next_run_at` by `frequency` — the same on-demand-sweep
    substitute for a real cron/Celery-Beat scheduler that
    `NotificationDeliveryService.list_due_for_retry`/`POST /notifications/
    retry-due` (Module 11) already established for this codebase's
    identical, disclosed lack of background-job infrastructure.
    """

    __tablename__ = "scheduled_reports"
    __table_args__ = (Index("ix_scheduled_reports_next_run_at", "next_run_at"),)

    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    report_type: Mapped[ReportType] = mapped_column(PgEnum(ReportType, name="report_type"), nullable=False)
    format: Mapped[ReportFormat] = mapped_column(PgEnum(ReportFormat, name="report_format"), nullable=False)
    filters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    frequency: Mapped[ReportScheduleFrequency] = mapped_column(
        PgEnum(ReportScheduleFrequency, name="report_schedule_frequency"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    next_run_at: Mapped[datetime] = mapped_column(nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)


class Passport(UUIDPKMixin, Base):
    """
    FR-18.1. Append-only, versioned (docs/ux/15-plant-passport-workflow.md
    "Versioning" — a new generation creates a new row, never overwrites).
    `public_token` is the signed, time-scoped identifier used by the one
    unauthenticated endpoint in the system (GET /passport/public/{token}).
    """

    __tablename__ = "passports"
    __table_args__ = (
        UniqueConstraint("public_token", name="uq_passports_public_token"),
        Index("ix_passports_plant_id_version", "plant_id", "version"),
    )

    plant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plants.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    public_token: Mapped[str] = mapped_column(String(128), nullable=False)
    token_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    content_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)  # frozen at generation time
    pdf_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    generated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    generated_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)


class QRScanEvent(UUIDPKMixin, Base):
    """
    Added by Phase 6 Module 9 (Sales, CRM, Plant Passport & QR
    Intelligence) — migration 0013. One row per public QR/passport scan,
    the source data for "QR Scan Analytics" reporting. No nursery_id/
    branch_id of its own, deliberately: it is written by the one
    unauthenticated endpoint in the system (no org context exists at
    scan time), and it FKs to `passports`, which is itself the one table
    exempt from Row-Level Security for the identical reason (migration
    0003's own documented exemption list). Internal reporting queries
    reach tenant scoping by joining passport_id -> passports.plant_id ->
    plants.nursery_id, the same one-hop-further join shape migration
    0003 already uses for `TWO_HOP_TENANT_TABLES` (treatments ->
    disease_reports -> plants) — access is authorized at the service
    layer, not by an RLS policy on this table.
    """

    __tablename__ = "qr_scan_events"
    __table_args__ = (Index("ix_qr_scan_events_passport_id_scanned_at", "passport_id", "scanned_at"),)

    passport_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("passports.id", ondelete="CASCADE"), nullable=False
    )
    ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    referrer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    scanned_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)
