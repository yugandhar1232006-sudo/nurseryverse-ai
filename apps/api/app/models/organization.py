"""
Organization bounded context: Nursery (tenant root) and Branch (the
operational boundary), plus Employee (User <-> Nursery membership).

Maps to docs/architecture/02-low-level-design.md "Module: Organization &
Branch" and "Module: Employees".
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum as PgEnum
from sqlalchemy import ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.enums import BranchStatus, EmployeeStatus, NurseryStatus

if TYPE_CHECKING:
    # Same ruff F821 fix as app/models/catalog.py's own TYPE_CHECKING
    # block -- see that file's comment for the full explanation. `User`
    # lives in app/models/identity.py, referenced here only as the
    # `Mapped["User"]` forward-reference string SQLAlchemy's mapper
    # registry resolves at runtime.
    from app.models.identity import User  # noqa: F401


class Nursery(UUIDPKMixin, TimestampMixin, Base):
    """The tenant root. One row per paying customer Org (BRD §5/§6)."""

    __tablename__ = "nurseries"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact_email: Mapped[str] = mapped_column(String(320), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Added by Phase 6 Module 4 — see db/enums.py's NurseryStatus docstring
    # for why this was missing until now.
    status: Mapped[NurseryStatus] = mapped_column(
        PgEnum(NurseryStatus, name="nursery_status"),
        nullable=False,
        default=NurseryStatus.ACTIVE,
        server_default=NurseryStatus.ACTIVE.value,
    )

    branches: Mapped[list["Branch"]] = relationship(back_populates="nursery")


class Branch(UUIDPKMixin, TimestampMixin, Base):
    """
    A physical nursery location — the operational boundary for most roles
    (docs/ux/08-information-architecture.md §3). Soft-delete only: status
    transitions to `inactive`, never a hard DELETE (FR-2.5).
    """

    __tablename__ = "branches"
    __table_args__ = (
        UniqueConstraint("nursery_id", "name", name="uq_branches_nursery_name"),
    )

    nursery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nurseries.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False)  # ISO 3166-1 alpha-2
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)  # IANA tz name
    status: Mapped[BranchStatus] = mapped_column(
        PgEnum(BranchStatus, name="branch_status"),
        nullable=False,
        default=BranchStatus.ACTIVE,
    )

    # Operational thresholds (FR-20.2) — defaults, overridable per inventory
    # line / per plant where the domain calls for it.
    default_low_stock_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    default_watering_overdue_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=48
    )

    # Added by Phase 6 Module 4 (Nursery & Organization Management).
    # `operating_hours`: {"mon": {"open": "09:00", "close": "17:00"}, ...,
    # "sun": null} — a day key absent or null means closed. Validated at
    # the service layer (app/services/branch_service.py), not by a CHECK
    # constraint, since the exact key/value shape is an application concern
    # and JSON CHECK constraints in Postgres are painful to evolve.
    operating_hours: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    nursery: Mapped["Nursery"] = relationship(back_populates="branches")


class Employee(UUIDPKMixin, TimestampMixin, Base):
    """
    Links a User to a Nursery as staff. Branch assignment(s) live on the
    User's RoleAssignment.branch_scopes (identity.py) — Employee itself is
    the org-membership + status record, not the branch-assignment record,
    avoiding two competing places that both claim to model "which branches
    can this person work in."
    """

    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("nursery_id", "user_id", name="uq_employees_nursery_user"),
    )

    nursery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nurseries.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[EmployeeStatus] = mapped_column(
        PgEnum(EmployeeStatus, name="employee_status"),
        nullable=False,
        default=EmployeeStatus.INVITED,
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Added by Phase 6 Module 4. `department`/`position` are free-text, not
    # enums — unlike Role (which gates *access*), a department/job title is
    # descriptive metadata with no fixed, product-wide vocabulary; forcing
    # it into an enum would mean a migration every time an Org uses a title
    # this schema didn't anticipate. `hired_at` is a plain date (no time
    # component is meaningful for an employment start date).
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hired_at: Mapped[date | None] = mapped_column(nullable=True)

    user: Mapped["User"] = relationship(back_populates="employee_profile")
