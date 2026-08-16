"""
Authentication & security bounded context — added by Phase 6 Module 2.

Not part of the original Phase 5 master table list: these tables exist
because implementing the actual login/session/reset/verification flows
surfaced that the Phase 5 schema (built against the architecture docs'
*conceptual* JWT/RBAC description, not the implementation-level detail of
refresh-token rotation, replay detection, or account lockout) had nowhere
to persist any of it. See migration 0007's docstring and
docs/architecture/18-module2-authentication.md for the full justification.
Per Module 2's explicit instruction, this is a new migration on top of the
existing schema — migrations 0001-0006 are untouched.

None of these four tables carry `nursery_id`, and none are covered by the
Row-Level Security policies in migration 0003 — deliberately, for the same
reason `users`/`invites` are already RLS-exempt (migration 0003's
docstring): authentication happens before any org context is known, and a
refresh token or a password-reset token is scoped to a *user*, not an org
(the same user could, in a future multi-org-membership world, hold
sessions and reset tokens without any single org ever being "the" tenant
for them). Isolation for these tables is "a user can only act on their own
rows", enforced by every service method filtering on `user_id` from the
authenticated request, not by RLS.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum as PgEnum
from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPKMixin
from app.db.enums import SecurityEventType

if TYPE_CHECKING:
    # Phase 6 Module 14 (Production Readiness) defect fix: same ruff/mypy
    # F821/name-defined issue fixed the same way in app/models/catalog.py,
    # identity.py, organization.py, and plants.py this module -- see
    # catalog.py's TYPE_CHECKING block for the full explanation. This
    # particular occurrence had been silenced with a bare `# noqa: F821`
    # on the `relationship()` line below instead of actually being fixed
    # (satisfies ruff, since noqa comments are ruff-specific, but not
    # mypy, which doesn't recognize ruff's suppression syntax and still
    # reported "Name 'User' is not defined" -- that's what surfaced this
    # while running Module 14's full `mypy app` validation pass). Fixed
    # here the same way as the other four files, and the now-unnecessary
    # noqa comment removed below.
    from app.models.identity import User  # noqa: F401


class RefreshToken(UUIDPKMixin, Base):
    """
    One row per issued refresh token = one active session on one device.
    Deliberately doubles as the "session" concept (docs/architecture's
    Session Management requirement) rather than a separate `sessions`
    table — a session's lifetime, device info, and revocability *are*
    exactly a refresh token's lifetime, device info, and revocability in a
    JWT-based system; a parallel table would just be two rows that must
    always be kept in sync.

    Never stores the raw token — only `token_hash` (SHA-256 hex digest of
    the token the client holds), per Module 2's "refresh token hashing
    before storage" requirement: a stolen database dump cannot be replayed
    as a valid refresh token even though it reveals which sessions exist.

    `family_id` groups every token produced by one rotation chain
    (login -> refresh -> refresh -> ...). Rotation always issues a new row
    and sets `replaced_by_id` on the old one rather than mutating the old
    row's hash in place, so the chain is reconstructable. If a token is
    ever presented that has a non-null `replaced_by_id` (i.e. it was
    already rotated away), that is definitionally a replay — the
    AuthService revokes the *entire family*, not just the reused token,
    on the theory that an attacker who captured one token in the chain may
    hold others (docs/architecture/18-module2-authentication.md
    "Replay Attack Prevention").
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_family_id", "family_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    device_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6 max length
    issued_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("refresh_tokens.id", ondelete="SET NULL"), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")


class EmailVerificationToken(UUIDPKMixin, Base):
    """Single-use, expiring, hashed-at-rest token for FR-Auth's email verification flow."""

    __tablename__ = "email_verification_tokens"
    __table_args__ = (Index("ix_email_verification_tokens_user_id", "user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)


class PasswordResetToken(UUIDPKMixin, Base):
    """
    Single-use, expiring, hashed-at-rest token for the password reset flow.
    `requested_ip` is retained for security-review/abuse-investigation
    purposes (distinguishing "user reset their own password" from "someone
    is spraying reset requests at this account from an unfamiliar IP").
    """

    __tablename__ = "password_reset_tokens"
    __table_args__ = (Index("ix_password_reset_tokens_user_id", "user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(nullable=True)
    requested_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)


class SecurityEvent(UUIDPKMixin, Base):
    """
    Append-only security/auth event log — the audit trail for everything
    `audit_logs` structurally cannot record (see this module's docstring).
    `user_id` is nullable and `email` is stored redundantly alongside it
    because a failed login against an email with no matching account must
    still be logged (that's exactly the brute-force signal this table
    exists to capture) even though there is no user row to attach it to.
    """

    __tablename__ = "security_events"
    __table_args__ = (
        Index("ix_security_events_user_created", "user_id", "created_at"),
        Index("ix_security_events_email_created", "email", "created_at"),
        Index("ix_security_events_type_created", "event_type", "created_at"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    event_type: Mapped[SecurityEventType] = mapped_column(
        PgEnum(SecurityEventType, name="security_event_type"), nullable=False
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    event_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)
