"""
Module 4 (Nursery & Organization Management) — Employee Management +
Organization Membership: invite an employee, complete the deferred
Employee/RoleAssignment provisioning Module 2's `AuthService.accept_invite`
left for this module (see that method's docstring), employee profile/
status, branch (re)assignment, removal, and ownership transfer.

Deliberately does *not* hardcode which role codes are "org-wide" vs
"branch-scoped" anywhere in this file (Module 3's RBAC principle: "no
hardcoded role names in business logic"). `branch_ids` is accepted exactly
as given by the caller -- zero branch ids means an org-wide grant for
whatever the role's permissions are (per `ResolvedAccess.is_org_wide()`'s
"absent rows == every branch" semantics, Module 3), one or more means a
branch-scoped grant. Which shape is "correct" for a given role is a
product/UI-level convention the inviting admin follows, not something this
service enforces by name-matching "owner" or "branch_manager" strings.
"""
from __future__ import annotations

import secrets
import uuid
from datetime import date, datetime, timedelta, timezone

from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.enums import EmployeeStatus
from app.domain_events import (
    DomainEventPublisher,
    EmployeeActivated,
    EmployeeInvited,
    EmployeeRemoved,
    EmployeeTransferred,
)
from app.models.identity import Invite, User
from app.models.organization import Employee
from app.models.platform import AuditLog
from app.repositories.interfaces import (
    AuditLogRepository,
    BranchRepository,
    EmployeeRepository,
    InviteRepository,
    PermissionRepository,
    UserRepository,
)
from app.services.email_sender import EmailSender
from app.services.permission_service import PermissionService


class EmployeeService:
    def __init__(
        self,
        *,
        settings: Settings,
        employee_repo: EmployeeRepository,
        invite_repo: InviteRepository,
        branch_repo: BranchRepository,
        user_repo: UserRepository,
        permission_repo: PermissionRepository,
        permission_service: PermissionService,
        audit_repo: AuditLogRepository,
        event_publisher: DomainEventPublisher,
        email_sender: EmailSender,
    ) -> None:
        self._settings = settings
        self._employees = employee_repo
        self._invites = invite_repo
        self._branches = branch_repo
        self._users = user_repo
        self._permissions = permission_repo
        self._permission_service = permission_service
        self._audit = audit_repo
        self._events = event_publisher
        self._email_sender = email_sender

    # ------------------------------------------------------------------
    # Add Staff / Invitation Workflow
    # ------------------------------------------------------------------
    async def invite_employee(
        self,
        *,
        nursery_id: uuid.UUID,
        email: str,
        role_code: str,
        invited_by_user_id: uuid.UUID,
        branch_ids: list[uuid.UUID] | None = None,
        request_id: str | None = None,
    ) -> Invite:
        normalized_email = email.strip().lower()
        branch_ids = branch_ids or []

        role = await self._permissions.get_system_role_by_code(role_code)
        if role is None:
            raise ValidationError(f"'{role_code}' is not a recognized role.")

        for branch_id in branch_ids:
            branch = await self._branches.get_by_id(branch_id)
            if branch is None or branch.nursery_id != nursery_id:
                raise ValidationError(f"Branch {branch_id} does not belong to this organization.")

        existing_user = await self._users.get_by_email(normalized_email)
        if existing_user is not None:
            existing_employee = await self._employees.get_by_user_and_nursery(existing_user.id, nursery_id)
            if existing_employee is not None and existing_employee.status != EmployeeStatus.DEACTIVATED:
                raise ConflictError("This person is already a member of this organization.")

        if await self._invites.get_pending_by_email_and_nursery(nursery_id, normalized_email) is not None:
            raise ConflictError("There is already a pending invitation for this email address.")

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(days=self._settings.AUTH_INVITE_EXPIRE_DAYS)
        invite = Invite(
            nursery_id=nursery_id,
            invited_by_user_id=invited_by_user_id,
            email=normalized_email,
            role_id=role.id,
            token=token,
            expires_at=expires_at,
        )
        await self._invites.add(invite)
        for branch_id in branch_ids:
            await self._invites.add_branch_scope(invite.id, branch_id)

        await self._log_audit(
            nursery_id=nursery_id,
            actor_user_id=invited_by_user_id,
            action="employee.invited",
            entity_id=invite.id,
            diff={"after": {"email": normalized_email, "role_code": role_code}},
            request_id=request_id,
        )
        await self._events.publish(
            EmployeeInvited(
                aggregate_id=invite.id,
                nursery_id=nursery_id,
                actor_user_id=invited_by_user_id,
                email=normalized_email,
                role_code=role_code,
                branch_ids=tuple(branch_ids),
            ),
            request_id=request_id,
        )

        invite_url = f"{self._settings.FRONTEND_BASE_URL}/accept-invite?token={token}"
        await self._email_sender.send(
            to=normalized_email,
            subject="You've been invited to join NurseryVerse AI",
            body_text=(
                f"You've been invited to join as a {role.name}.\n\n"
                f"Accept your invitation: {invite_url}\n\n"
                f"This link expires in {self._settings.AUTH_INVITE_EXPIRE_DAYS} days."
            ),
        )
        return invite

    async def list_invites(
        self, *, nursery_id: uuid.UUID, offset: int, limit: int
    ) -> tuple[list[Invite], int]:
        return await self._invites.list_for_nursery(nursery_id, offset=offset, limit=limit)

    # ------------------------------------------------------------------
    # Accept Invitation (completes what AuthService.accept_invite defers)
    # ------------------------------------------------------------------
    async def provision_from_invite(
        self, *, invite: Invite, user: User, request_id: str | None = None
    ) -> Employee:
        """
        Called by the `/auth/invite/accept` route immediately after
        `AuthService.accept_invite` creates the `User` row -- both run
        against the same request-scoped DB session, so a failure here
        rolls back the User creation too (see app/db/session.py's
        `get_db_session` fix): invite acceptance is all-or-nothing.
        """
        branch_ids = await self._invites.get_branch_scope_ids(invite.id)
        return await self._provision_employee(
            nursery_id=invite.nursery_id,
            user_id=user.id,
            role_id=invite.role_id,
            branch_ids=branch_ids,
            request_id=request_id,
        )

    async def provision_owner(
        self, *, nursery_id: uuid.UUID, user_id: uuid.UUID, request_id: str | None = None
    ) -> Employee:
        """
        Called by `POST /orgs` (app/api/routes/organizations.py)
        immediately after `OrganizationService.create_nursery` -- the
        creator of a new organization becomes its Owner, org-wide (no
        branch scope rows: see `ResolvedAccess.is_org_wide()`), in the
        same request/transaction as the Nursery itself.
        """
        owner_role = await self._permissions.get_system_role_by_code("owner")
        if owner_role is None:
            raise ConflictError("The 'owner' system role is not provisioned.")
        return await self._provision_employee(
            nursery_id=nursery_id,
            user_id=user_id,
            role_id=owner_role.id,
            branch_ids=[],
            request_id=request_id,
        )

    async def _provision_employee(
        self,
        *,
        nursery_id: uuid.UUID,
        user_id: uuid.UUID,
        role_id: uuid.UUID,
        branch_ids: list[uuid.UUID],
        request_id: str | None,
    ) -> Employee:
        existing = await self._employees.get_by_user_and_nursery(user_id, nursery_id)
        if existing is not None:
            raise ConflictError("This user is already an employee of this organization.")

        employee = Employee(
            nursery_id=nursery_id,
            user_id=user_id,
            status=EmployeeStatus.ACTIVE,
            hired_at=date.today(),
        )
        await self._employees.add(employee)

        assignment = await self._permissions.create_assignment(
            user_id=user_id, nursery_id=nursery_id, role_id=role_id
        )
        for branch_id in branch_ids:
            await self._permissions.add_assignment_branch_scope(assignment.id, branch_id)

        role = await self._permissions.get_role_with_permissions(role_id)
        role_code = role.code if role is not None else "unknown"

        await self._log_audit(
            nursery_id=nursery_id,
            actor_user_id=user_id,
            action="employee.activated",
            entity_id=employee.id,
            diff={"after": {"role_code": role_code, "branch_ids": [str(b) for b in branch_ids]}},
            request_id=request_id,
        )
        await self._events.publish(
            EmployeeActivated(
                aggregate_id=employee.id,
                nursery_id=nursery_id,
                actor_user_id=user_id,
                employee_id=employee.id,
                role_code=role_code,
            ),
            request_id=request_id,
        )
        return employee

    # ------------------------------------------------------------------
    # Employee Profile / Status
    # ------------------------------------------------------------------
    async def get_employee(self, employee_id: uuid.UUID) -> Employee:
        employee = await self._employees.get_by_id(employee_id)
        if employee is None:
            raise NotFoundError("Employee not found.")
        return employee

    async def list_employees(
        self,
        *,
        nursery_id: uuid.UUID,
        offset: int,
        limit: int,
        status: EmployeeStatus | None = None,
    ) -> tuple[list[Employee], int]:
        return await self._employees.list_for_nursery(nursery_id, offset=offset, limit=limit, status=status)

    async def update_profile(
        self,
        *,
        employee_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        department: str | None = None,
        position: str | None = None,
        request_id: str | None = None,
    ) -> Employee:
        employee = await self.get_employee(employee_id)
        before = {"department": employee.department, "position": employee.position}
        changed: list[str] = []

        if department is not None and department != employee.department:
            employee.department = department
            changed.append("department")
        if position is not None and position != employee.position:
            employee.position = position
            changed.append("position")

        if not changed:
            return employee

        await self._log_audit(
            nursery_id=employee.nursery_id,
            actor_user_id=actor_user_id,
            action="employee.profile_updated",
            entity_id=employee.id,
            diff={"before": before, "after": {"department": employee.department, "position": employee.position}},
            request_id=request_id,
        )
        return employee

    # ------------------------------------------------------------------
    # Branch Reassignment / Transfer Staff
    # ------------------------------------------------------------------
    async def transfer_branches(
        self,
        *,
        employee_id: uuid.UUID,
        new_branch_ids: list[uuid.UUID],
        actor_user_id: uuid.UUID,
        request_id: str | None = None,
    ) -> Employee:
        employee = await self.get_employee(employee_id)
        if employee.status != EmployeeStatus.ACTIVE:
            raise ConflictError("Only an active employee can be transferred.")

        for branch_id in new_branch_ids:
            branch = await self._branches.get_by_id(branch_id)
            if branch is None or branch.nursery_id != employee.nursery_id:
                raise ValidationError(f"Branch {branch_id} does not belong to this organization.")

        assignment = await self._permissions.get_role_assignment_for_user(employee.user_id)
        if assignment is None:
            raise ConflictError("This employee has no active role assignment to transfer.")

        old_branch_ids = await self._permissions.get_branch_scope_ids(assignment.id)
        await self._permissions.replace_assignment_branch_scopes(assignment.id, new_branch_ids)
        # Immediate revocation/grant of the new branch scope -- without
        # this, the old scope would remain effective for up to the
        # permission cache's TTL (app/services/permission_service.py).
        await self._permission_service.invalidate_user(employee.user_id)

        await self._log_audit(
            nursery_id=employee.nursery_id,
            actor_user_id=actor_user_id,
            action="employee.transferred",
            entity_id=employee.id,
            diff={
                "before": {"branch_ids": [str(b) for b in old_branch_ids]},
                "after": {"branch_ids": [str(b) for b in new_branch_ids]},
            },
            request_id=request_id,
        )
        await self._events.publish(
            EmployeeTransferred(
                aggregate_id=employee.id,
                nursery_id=employee.nursery_id,
                actor_user_id=actor_user_id,
                employee_id=employee.id,
                from_branch_ids=tuple(old_branch_ids),
                to_branch_ids=tuple(new_branch_ids),
            ),
            request_id=request_id,
        )
        return employee

    # ------------------------------------------------------------------
    # Remove Staff
    # ------------------------------------------------------------------
    async def remove_employee(
        self,
        *,
        employee_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        reason: str | None = None,
        request_id: str | None = None,
    ) -> Employee:
        employee = await self.get_employee(employee_id)
        if employee.status == EmployeeStatus.DEACTIVATED:
            raise ConflictError("This employee has already been removed.")

        assignment = await self._permissions.get_role_assignment_for_user(employee.user_id)
        if assignment is not None:
            await self._permissions.delete_assignment(assignment.id)

        employee.status = EmployeeStatus.DEACTIVATED
        employee.deactivated_at = datetime.now(timezone.utc)
        # Revoked access must take effect immediately, not after the
        # permission cache's TTL -- see PermissionService.invalidate_user's
        # own docstring for why this call is what makes revocation real.
        await self._permission_service.invalidate_user(employee.user_id)

        await self._log_audit(
            nursery_id=employee.nursery_id,
            actor_user_id=actor_user_id,
            action="employee.removed",
            entity_id=employee.id,
            diff={"before": {"status": "active"}, "after": {"status": "deactivated", "reason": reason}},
            request_id=request_id,
        )
        await self._events.publish(
            EmployeeRemoved(
                aggregate_id=employee.id,
                nursery_id=employee.nursery_id,
                actor_user_id=actor_user_id,
                employee_id=employee.id,
                reason=reason,
            ),
            request_id=request_id,
        )
        return employee

    # ------------------------------------------------------------------
    # Reactivation -- added by Phase 6 Module 13 (Administration &
    # System Management, "Employee Administration: reactivation")
    # ------------------------------------------------------------------
    async def reactivate_employee(
        self,
        *,
        employee_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        role_code: str,
        branch_ids: list[uuid.UUID] | None = None,
        request_id: str | None = None,
    ) -> Employee:
        """
        The counterpart `remove_employee` never had: Module 4 shipped
        deactivation (a RoleAssignment revocation + status flip) but no
        way back, since nothing before Module 13 needed one. Deactivation
        deletes the RoleAssignment entirely (`remove_employee`'s own
        implementation, `PermissionRepository.delete_assignment`) rather
        than merely disabling it, so reactivation cannot simply "undo" a
        flag -- it must provision a brand-new RoleAssignment, exactly the
        same `create_assignment` + `add_assignment_branch_scope` sequence
        `_provision_employee` uses at invite-acceptance time. That's why
        the caller must supply a `role_code`: the employee's original role
        is not recoverable from a deleted row, and re-granting access
        without an explicit admin decision about *what* access to restore
        would itself be a privilege-escalation risk this module's Section
        12 requirements exist to prevent.
        """
        employee = await self.get_employee(employee_id)
        if employee.status != EmployeeStatus.DEACTIVATED:
            raise ConflictError("Only a deactivated employee can be reactivated.")

        role = await self._permissions.get_system_role_by_code(role_code)
        if role is None:
            raise ValidationError(f"Unknown role code: {role_code!r}.")

        existing_assignment = await self._permissions.get_role_assignment_for_user(employee.user_id)
        if existing_assignment is not None:
            # Shouldn't happen (deactivation always deletes the
            # assignment), but if this employee's user somehow already
            # holds a RoleAssignment (e.g. a concurrent invite to another
            # branch of the same org), refuse rather than silently
            # overwriting an assignment this method didn't create.
            raise ConflictError("This user already holds an active role assignment.")

        assignment = await self._permissions.create_assignment(
            user_id=employee.user_id, nursery_id=employee.nursery_id, role_id=role.id
        )
        for branch_id in branch_ids or []:
            await self._permissions.add_assignment_branch_scope(assignment.id, branch_id)

        employee.status = EmployeeStatus.ACTIVE
        employee.deactivated_at = None
        await self._permission_service.invalidate_user(employee.user_id)

        await self._log_audit(
            nursery_id=employee.nursery_id,
            actor_user_id=actor_user_id,
            action="employee.reactivated",
            entity_id=employee.id,
            diff={"before": {"status": "deactivated"}, "after": {"status": "active", "role_code": role_code}},
            request_id=request_id,
        )
        await self._events.publish(
            EmployeeActivated(
                aggregate_id=employee.id,
                nursery_id=employee.nursery_id,
                actor_user_id=actor_user_id,
                employee_id=employee.id,
                role_code=role_code,
            ),
            request_id=request_id,
        )
        return employee

    # ------------------------------------------------------------------
    # Ownership Transfer
    # ------------------------------------------------------------------
    async def transfer_ownership(
        self,
        *,
        nursery_id: uuid.UUID,
        current_owner_user_id: uuid.UUID,
        new_owner_user_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        request_id: str | None = None,
    ) -> None:
        """
        Owner is "exactly one per Org ... cannot be deleted, only
        transferred" (docs/ux/07-role-permission-matrix.md). The outgoing
        owner is demoted to `org_admin` (the next-highest system role,
        same permission ceiling minus billing/deletion per that doc) --
        not removed -- since an ownership transfer is a handoff, not an
        offboarding; `remove_employee` is the separate operation for that.
        """
        if current_owner_user_id == new_owner_user_id:
            raise ValidationError("Cannot transfer ownership to the current owner.")

        owner_role = await self._permissions.get_system_role_by_code("owner")
        org_admin_role = await self._permissions.get_system_role_by_code("org_admin")
        if owner_role is None or org_admin_role is None:
            raise ConflictError("Required system roles are not provisioned.")

        current_assignment = await self._permissions.get_role_assignment_for_user(current_owner_user_id)
        if (
            current_assignment is None
            or current_assignment.nursery_id != nursery_id
            or current_assignment.role_id != owner_role.id
        ):
            raise ValidationError("The specified current owner does not hold the owner role in this organization.")

        new_assignment = await self._permissions.get_role_assignment_for_user(new_owner_user_id)
        if new_assignment is None or new_assignment.nursery_id != nursery_id:
            raise ValidationError("The new owner must already be an employee of this organization.")

        current_assignment.role_id = org_admin_role.id
        new_assignment.role_id = owner_role.id

        await self._permission_service.invalidate_user(current_owner_user_id)
        await self._permission_service.invalidate_user(new_owner_user_id)

        await self._log_audit(
            nursery_id=nursery_id,
            actor_user_id=actor_user_id,
            action="employee.ownership_transferred",
            entity_id=nursery_id,
            diff={
                "before": {"owner_user_id": str(current_owner_user_id)},
                "after": {"owner_user_id": str(new_owner_user_id)},
            },
            request_id=request_id,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    async def _log_audit(
        self,
        *,
        nursery_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        action: str,
        entity_id: uuid.UUID,
        diff: dict,
        request_id: str | None,
    ) -> None:
        await self._audit.log(
            AuditLog(
                nursery_id=nursery_id,
                actor_user_id=actor_user_id,
                action=action,
                entity_type="Employee",
                entity_id=entity_id,
                diff=diff,
                request_id=request_id,
                created_at=datetime.now(timezone.utc),
            )
        )
