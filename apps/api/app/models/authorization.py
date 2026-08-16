"""
Authorization audit trail — added by Phase 6 Module 3.

Not part of Phase 5's master table list, and deliberately not merged into
`security_events` (Module 2): that table is authentication/session
lifecycle (login, tokens, password/email flows), scoped to a user before
any resource-level context necessarily exists. `authorization_denials` is
the opposite shape — it always has a specific permission, and usually a
specific resource and org, being checked against an already-authenticated
user. Splitting them keeps each table's queries simple (a security review
of "who tried to log in and failed" vs. "who tried to do something they
weren't allowed to do" are different investigations with different shapes)
rather than one wide table with half its columns null depending on event
type.

Per Module 3's requirement that every authorization *failure* generate an
auditable record with user, permission, resource, request, IP, timestamp,
and reason — this table is that record. Successful authorization checks
are NOT logged here (would be an enormous, low-value volume of rows for
every permitted API call); only denials.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Enum as PgEnum
from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPKMixin
from app.db.enums import AuthorizationDenialReason


class AuthorizationDenial(UUIDPKMixin, Base):
    __tablename__ = "authorization_denials"
    __table_args__ = (
        Index("ix_authorization_denials_user_created", "user_id", "created_at"),
        Index("ix_authorization_denials_nursery_created", "nursery_id", "created_at"),
        Index("ix_authorization_denials_reason_created", "reason", "created_at"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    permission_code: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    nursery_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nurseries.id", ondelete="SET NULL"), nullable=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[AuthorizationDenialReason] = mapped_column(
        PgEnum(AuthorizationDenialReason, name="authorization_denial_reason"), nullable=False
    )
    explanation: Mapped[str] = mapped_column(String(500), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)
