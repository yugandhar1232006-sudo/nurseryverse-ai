"""
Identity & Access bounded context: Users, Roles, Permissions, and the
join tables between them.

Maps to docs/architecture/02-low-level-design.md "Module: Auth & RBAC" and
"Module: Employees", and enforces exactly the permission codes cataloged in
docs/ux/07-role-permission-matrix.md (see migration 0002_seed_rbac.py for
the system-role/permission seed data — permission codes are system
metadata, not business data, per the Phase 5 seed-data rules).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    # Same ruff F821 fix as app/models/catalog.py's own TYPE_CHECKING
    # block -- see that file's comment for the full explanation. `Employee`
    # lives in app/models/organization.py, `RefreshToken` in
    # app/models/auth.py; both are only ever referenced here as
    # `Mapped["Employee"]`/`Mapped["RefreshToken"]` forward-reference
    # strings, resolved by SQLAlchemy's mapper registry at runtime.
    from app.models.auth import RefreshToken  # noqa: F401
    from app.models.organization import Employee  # noqa: F401


class User(UUIDPKMixin, TimestampMixin, Base):
    """
    Authentication identity. A User becomes an Employee of exactly one
    Org in v1 (docs/product/02-software-requirements-specification.md
    §2.6 Assumptions) via the `employees` join below.

    `is_email_verified`/`failed_login_attempts`/`locked_until` were added
    by Phase 6 Module 2 (Authentication) — migration 0007 — once building
    the actual login flow surfaced that Phase 5's schema had no columns to
    support email verification or account lockout at all. See migration
    0007's docstring and
    docs/architecture/18-module2-authentication.md for the justification;
    per that module's explicit "never edit existing migrations" rule this
    was shipped as a new migration, not a hand-edit of migration 0001.
    """

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # server_default (not just ORM-level default=) so ADD COLUMN in
    # migration 0007 is safe even if the users table already had rows —
    # every existing row backfills to "unverified, zero strikes" rather
    # than the ALTER failing on a NOT NULL column with no way to populate
    # pre-existing rows.
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    locked_until: Mapped[datetime | None] = mapped_column(nullable=True)

    employee_profile: Mapped["Employee"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    role_assignments: Mapped[list["RoleAssignment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Role(UUIDPKMixin, TimestampMixin, Base):
    """
    System default roles (owner, org_admin, branch_manager, horticulturist,
    sales_staff, platform_admin) plus per-Org custom roles (Growth/Enterprise
    tier, FR-1.5). System roles have nursery_id = NULL; custom roles are
    scoped to the Org that created them.
    """

    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("nursery_id", "code", name="uq_roles_nursery_code"),
    )

    nursery_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nurseries.id", ondelete="CASCADE"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_system_role: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    permission_ceiling_role_code: Mapped[str] = mapped_column(
        String(50), nullable=False, default="org_admin"
    )

    permissions: Mapped[list["Permission"]] = relationship(
        secondary="role_permissions", back_populates="roles"
    )
    role_assignments: Mapped[list["RoleAssignment"]] = relationship(back_populates="role")


class Permission(UUIDPKMixin, Base):
    """
    Atomic permission codes, e.g. `plants:write`. Global, not tenant-scoped
    — the full set is exactly docs/ux/07-role-permission-matrix.md's
    permission list, seeded in migration 0002_seed_rbac.py.
    """

    __tablename__ = "permissions"
    __table_args__ = (UniqueConstraint("code", name="uq_permissions_code"),)

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    module: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)

    roles: Mapped[list["Role"]] = relationship(
        secondary="role_permissions", back_populates="permissions"
    )


class RolePermission(Base):
    """Join table: Role <-> Permission."""

    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )
    # scope is F (org-wide) or B (branch-scoped), mirroring the permission
    # matrix's legend exactly — enforced application-side per request,
    # this column is what the PermissionResolver reads.
    scope: Mapped[str] = mapped_column(String(1), nullable=False, default="B")


class RoleAssignment(UUIDPKMixin, TimestampMixin, Base):
    """
    User <-> Role, scoped to an Org and (for branch-scoped roles) a set of
    Branches via branch_scopes. One user may hold different roles across
    different Orgs in theory; v1 constrains one Org per User at the
    application layer (SRS §2.6) even though the schema doesn't hard-block
    it, since a future multi-org-membership feature shouldn't require a
    schema migration.
    """

    __tablename__ = "role_assignments"
    __table_args__ = (
        UniqueConstraint("user_id", "nursery_id", name="uq_role_assignments_user_nursery"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    nursery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nurseries.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="role_assignments")
    role: Mapped["Role"] = relationship(back_populates="role_assignments")
    branch_scopes: Mapped[list["RoleAssignmentBranchScope"]] = relationship(
        back_populates="role_assignment", cascade="all, delete-orphan"
    )


class RoleAssignmentBranchScope(Base):
    """
    Which specific Branches a branch-scoped RoleAssignment applies to.
    Absent rows for an org-wide role (Owner/Org Admin) means "all branches"
    — enforced application-side by role.permission_ceiling, not by a
    branch_scopes row per branch for org-wide roles.
    """

    __tablename__ = "role_assignment_branch_scopes"

    role_assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("role_assignments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), primary_key=True
    )

    role_assignment: Mapped["RoleAssignment"] = relationship(back_populates="branch_scopes")


class Invite(UUIDPKMixin, TimestampMixin, Base):
    """
    Pending employee invite (FR-3.1 / US-A.2). Consumed by
    POST /auth/invite/accept, which creates the User + Employee +
    RoleAssignment rows transactionally.
    """

    __tablename__ = "invites"
    __table_args__ = (UniqueConstraint("token", name="uq_invites_token"),)

    nursery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nurseries.id", ondelete="CASCADE"), nullable=False
    )
    invited_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False
    )
    token: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)

    branch_scopes: Mapped[list["InviteBranchScope"]] = relationship(
        back_populates="invite", cascade="all, delete-orphan"
    )


class InviteBranchScope(Base):
    """
    Added by Phase 6 Module 3/4's `accept_invite` completion. Module 2
    shipped `Invite` with only `role_id` (nursery_id + role, no branch
    intent) because at the time `accept_invite` only provisioned the
    `User` row — Module 4 completes that method to also provision the
    `Employee` + `RoleAssignment` (+ branch scopes) rows, and a
    branch-scoped role's *intended* branches have to be captured somewhere
    before the invite is accepted. Mirrors `RoleAssignmentBranchScope`
    exactly (same "absent rows == every branch" semantics), copied onto
    the real `RoleAssignmentBranchScope` rows at acceptance time — this
    table's rows are consumed and become irrelevant once `accepted_at` is
    set, not queried afterward.
    """

    __tablename__ = "invite_branch_scopes"

    invite_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invites.id", ondelete="CASCADE"), primary_key=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), primary_key=True
    )

    invite: Mapped["Invite"] = relationship(back_populates="branch_scopes")
