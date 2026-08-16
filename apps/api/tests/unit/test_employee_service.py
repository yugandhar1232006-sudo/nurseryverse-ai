"""
Module 4 unit tests: EmployeeService -- invite/accept, profile, branch
transfer, removal, and ownership transfer -- against in-memory fakes.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest

from app.core.cache import InMemoryCache
from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.enums import BranchStatus, EmployeeStatus
from app.domain_events import DomainEventPublisher
from app.models.identity import Permission, Role, User
from app.models.organization import Branch, Employee
from app.services.employee_service import EmployeeService
from app.services.permission_service import PermissionService
from tests.fakes.repositories import (
    FakeAuditLogRepository,
    FakeBranchRepository,
    FakeDomainEventRepository,
    FakeEmailSender,
    FakeEmployeeRepository,
    FakeInviteRepository,
    FakePermissionRepository,
    FakeUserRepository,
)


@dataclass
class EmployeeTestHarness:
    service: EmployeeService
    users: FakeUserRepository
    permissions: FakePermissionRepository
    invites: FakeInviteRepository
    branches: FakeBranchRepository
    employees: FakeEmployeeRepository
    email_sender: FakeEmailSender
    permission_service: PermissionService
    nursery_id: uuid.UUID
    branch_id: uuid.UUID

    def seed_system_role(self, code: str, permission_codes: list[str]) -> Role:
        role = Role(id=uuid.uuid4(), nursery_id=None, code=code, name=code, is_system_role=True)
        role.permissions = [
            Permission(id=uuid.uuid4(), code=c, module=c.split(":")[0], action=c.split(":")[1], description=c)
            for c in permission_codes
        ]
        self.permissions.roles[role.id] = role
        return role

    async def add_user(self, email: str = "person@example.com") -> User:
        user = User(id=uuid.uuid4(), email=email, password_hash="x", full_name="Test Person", is_active=True)
        return await self.users.add(user)


@pytest.fixture
async def harness() -> EmployeeTestHarness:
    settings = Settings(_env_file=None, APP_ENV="test")
    users = FakeUserRepository()
    permissions = FakePermissionRepository()
    invites = FakeInviteRepository()
    branches = FakeBranchRepository()
    employees = FakeEmployeeRepository()
    audit = FakeAuditLogRepository()
    events = DomainEventPublisher(FakeDomainEventRepository())
    email_sender = FakeEmailSender()
    cache = InMemoryCache()
    permission_service = PermissionService(permissions, cache=cache)

    nursery_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    branches.branches[branch_id] = Branch(
        id=branch_id,
        nursery_id=nursery_id,
        name="Main",
        address_line1="1 St",
        city="Austin",
        country="US",
        timezone="America/Chicago",
        status=BranchStatus.ACTIVE,
    )

    service = EmployeeService(
        settings=settings,
        employee_repo=employees,
        invite_repo=invites,
        branch_repo=branches,
        user_repo=users,
        permission_repo=permissions,
        permission_service=permission_service,
        audit_repo=audit,
        event_publisher=events,
        email_sender=email_sender,
    )
    return EmployeeTestHarness(
        service=service,
        users=users,
        permissions=permissions,
        invites=invites,
        branches=branches,
        employees=employees,
        email_sender=email_sender,
        permission_service=permission_service,
        nursery_id=nursery_id,
        branch_id=branch_id,
    )


class TestInviteEmployee:
    async def test_sends_invite_and_email(self, harness: EmployeeTestHarness) -> None:
        harness.seed_system_role("branch_manager", ["branch:read"])
        invite = await harness.service.invite_employee(
            nursery_id=harness.nursery_id,
            email="New.Hire@Example.com",
            role_code="branch_manager",
            invited_by_user_id=uuid.uuid4(),
            branch_ids=[harness.branch_id],
        )
        assert invite.email == "new.hire@example.com"
        assert invite.expires_at is not None
        assert len(harness.email_sender.sent) == 1
        assert harness.email_sender.sent[0]["to"] == "new.hire@example.com"
        assert await harness.invites.get_branch_scope_ids(invite.id) == [harness.branch_id]

    async def test_unknown_role_rejected(self, harness: EmployeeTestHarness) -> None:
        with pytest.raises(ValidationError):
            await harness.service.invite_employee(
                nursery_id=harness.nursery_id,
                email="a@b.com",
                role_code="not_a_real_role",
                invited_by_user_id=uuid.uuid4(),
            )

    async def test_branch_outside_org_rejected(self, harness: EmployeeTestHarness) -> None:
        harness.seed_system_role("branch_manager", ["branch:read"])
        foreign_branch_id = uuid.uuid4()
        harness.branches.branches[foreign_branch_id] = Branch(
            id=foreign_branch_id,
            nursery_id=uuid.uuid4(),  # different org
            name="Foreign",
            address_line1="2 St",
            city="Dallas",
            country="US",
            timezone="America/Chicago",
            status=BranchStatus.ACTIVE,
        )
        with pytest.raises(ValidationError):
            await harness.service.invite_employee(
                nursery_id=harness.nursery_id,
                email="a@b.com",
                role_code="branch_manager",
                invited_by_user_id=uuid.uuid4(),
                branch_ids=[foreign_branch_id],
            )

    async def test_duplicate_pending_invite_conflicts(self, harness: EmployeeTestHarness) -> None:
        harness.seed_system_role("branch_manager", ["branch:read"])
        await harness.service.invite_employee(
            nursery_id=harness.nursery_id,
            email="dup@example.com",
            role_code="branch_manager",
            invited_by_user_id=uuid.uuid4(),
        )
        with pytest.raises(ConflictError):
            await harness.service.invite_employee(
                nursery_id=harness.nursery_id,
                email="dup@example.com",
                role_code="branch_manager",
                invited_by_user_id=uuid.uuid4(),
            )

    async def test_already_active_member_conflicts(self, harness: EmployeeTestHarness) -> None:
        harness.seed_system_role("branch_manager", ["branch:read"])
        existing_user = await harness.add_user(email="member@example.com")
        owner_role = harness.seed_system_role("owner", ["org:read"])
        await harness.permissions.create_assignment(
            user_id=existing_user.id, nursery_id=harness.nursery_id, role_id=owner_role.id
        )
        existing_employee = Employee(
            id=uuid.uuid4(), user_id=existing_user.id, nursery_id=harness.nursery_id, status=EmployeeStatus.ACTIVE
        )
        harness.employees.employees[existing_employee.id] = existing_employee
        with pytest.raises(ConflictError):
            await harness.service.invite_employee(
                nursery_id=harness.nursery_id,
                email="member@example.com",
                role_code="branch_manager",
                invited_by_user_id=uuid.uuid4(),
            )


class TestProvisionOwner:
    async def test_provisions_owner_org_wide(self, harness: EmployeeTestHarness) -> None:
        harness.seed_system_role("owner", ["org:read", "org:write", "org:delete"])
        user = await harness.add_user()
        employee = await harness.service.provision_owner(nursery_id=harness.nursery_id, user_id=user.id)
        assert employee.status == EmployeeStatus.ACTIVE

        access = await harness.permission_service.resolve_for_user(user.id)
        assert access.org_id == harness.nursery_id
        assert access.role_code == "owner"
        assert access.is_org_wide()

    async def test_missing_owner_role_conflicts(self, harness: EmployeeTestHarness) -> None:
        user = await harness.add_user()
        with pytest.raises(ConflictError):
            await harness.service.provision_owner(nursery_id=harness.nursery_id, user_id=user.id)

    async def test_double_provisioning_conflicts(self, harness: EmployeeTestHarness) -> None:
        harness.seed_system_role("owner", ["org:read"])
        user = await harness.add_user()
        await harness.service.provision_owner(nursery_id=harness.nursery_id, user_id=user.id)
        with pytest.raises(ConflictError):
            await harness.service.provision_owner(nursery_id=harness.nursery_id, user_id=user.id)


class TestProvisionFromInvite:
    async def test_provisions_branch_scoped_employee(self, harness: EmployeeTestHarness) -> None:
        harness.seed_system_role("branch_manager", ["branch:read"])
        invited_user = await harness.add_user(email="invitee@example.com")
        invite = await harness.service.invite_employee(
            nursery_id=harness.nursery_id,
            email="invitee@example.com",
            role_code="branch_manager",
            invited_by_user_id=uuid.uuid4(),
            branch_ids=[harness.branch_id],
        )
        employee = await harness.service.provision_from_invite(invite=invite, user=invited_user)
        assert employee.status == EmployeeStatus.ACTIVE

        access = await harness.permission_service.resolve_for_user(invited_user.id)
        assert access.branch_ids == [harness.branch_id]
        assert not access.is_org_wide()


class TestTransferBranches:
    async def test_transfers_active_employee(self, harness: EmployeeTestHarness) -> None:
        role = harness.seed_system_role("branch_manager", ["branch:read"])
        user = await harness.add_user()
        assignment = await harness.permissions.create_assignment(
            user_id=user.id, nursery_id=harness.nursery_id, role_id=role.id
        )
        await harness.permissions.add_assignment_branch_scope(assignment.id, harness.branch_id)
        employee = Employee(id=uuid.uuid4(), user_id=user.id, nursery_id=harness.nursery_id, status=EmployeeStatus.ACTIVE)
        harness.employees.employees[employee.id] = employee

        new_branch_id = uuid.uuid4()
        harness.branches.branches[new_branch_id] = Branch(
            id=new_branch_id,
            nursery_id=harness.nursery_id,
            name="Second",
            address_line1="3 St",
            city="Waco",
            country="US",
            timezone="America/Chicago",
            status=BranchStatus.ACTIVE,
        )

        result = await harness.service.transfer_branches(
            employee_id=employee.id, new_branch_ids=[new_branch_id], actor_user_id=uuid.uuid4()
        )
        assert result.id == employee.id
        access = await harness.permission_service.resolve_for_user(user.id)
        assert access.branch_ids == [new_branch_id]

    async def test_inactive_employee_rejected(self, harness: EmployeeTestHarness) -> None:
        employee = Employee(
            id=uuid.uuid4(), user_id=uuid.uuid4(), nursery_id=harness.nursery_id, status=EmployeeStatus.DEACTIVATED
        )
        harness.employees.employees[employee.id] = employee
        with pytest.raises(ConflictError):
            await harness.service.transfer_branches(
                employee_id=employee.id, new_branch_ids=[], actor_user_id=uuid.uuid4()
            )

    async def test_employee_not_found(self, harness: EmployeeTestHarness) -> None:
        with pytest.raises(NotFoundError):
            await harness.service.transfer_branches(
                employee_id=uuid.uuid4(), new_branch_ids=[], actor_user_id=uuid.uuid4()
            )


class TestRemoveEmployee:
    async def test_deactivates_and_revokes_access(self, harness: EmployeeTestHarness) -> None:
        role = harness.seed_system_role("sales_staff", ["sales:read"])
        user = await harness.add_user()
        await harness.permissions.create_assignment(user_id=user.id, nursery_id=harness.nursery_id, role_id=role.id)
        employee = Employee(
            id=uuid.uuid4(), user_id=user.id, nursery_id=harness.nursery_id, status=EmployeeStatus.ACTIVE, deactivated_at=None
        )
        harness.employees.employees[employee.id] = employee

        result = await harness.service.remove_employee(employee_id=employee.id, actor_user_id=uuid.uuid4(), reason="left company")
        assert result.status == EmployeeStatus.DEACTIVATED
        assert result.deactivated_at is not None

        access = await harness.permission_service.resolve_for_user(user.id)
        assert access.org_id is None  # role assignment deleted -> no access

    async def test_double_removal_conflicts(self, harness: EmployeeTestHarness) -> None:
        employee = Employee(
            id=uuid.uuid4(), user_id=uuid.uuid4(), nursery_id=harness.nursery_id, status=EmployeeStatus.DEACTIVATED, deactivated_at=None
        )
        harness.employees.employees[employee.id] = employee
        with pytest.raises(ConflictError):
            await harness.service.remove_employee(employee_id=employee.id, actor_user_id=uuid.uuid4())


class TestTransferOwnership:
    async def test_transfers_owner_role(self, harness: EmployeeTestHarness) -> None:
        owner_role = harness.seed_system_role("owner", ["org:read", "org:write", "org:delete"])
        admin_role = harness.seed_system_role("org_admin", ["org:read", "org:write"])

        current_owner = await harness.add_user(email="owner@example.com")
        new_owner = await harness.add_user(email="new-owner@example.com")

        current_assignment = await harness.permissions.create_assignment(
            user_id=current_owner.id, nursery_id=harness.nursery_id, role_id=owner_role.id
        )
        new_assignment = await harness.permissions.create_assignment(
            user_id=new_owner.id, nursery_id=harness.nursery_id, role_id=admin_role.id
        )

        await harness.service.transfer_ownership(
            nursery_id=harness.nursery_id,
            current_owner_user_id=current_owner.id,
            new_owner_user_id=new_owner.id,
            actor_user_id=current_owner.id,
        )

        assert current_assignment.role_id == admin_role.id
        assert new_assignment.role_id == owner_role.id

    async def test_same_user_rejected(self, harness: EmployeeTestHarness) -> None:
        user_id = uuid.uuid4()
        with pytest.raises(ValidationError):
            await harness.service.transfer_ownership(
                nursery_id=harness.nursery_id,
                current_owner_user_id=user_id,
                new_owner_user_id=user_id,
                actor_user_id=user_id,
            )

    async def test_new_owner_must_already_be_employee(self, harness: EmployeeTestHarness) -> None:
        owner_role = harness.seed_system_role("owner", ["org:read"])
        harness.seed_system_role("org_admin", ["org:read"])
        current_owner = await harness.add_user(email="owner2@example.com")
        await harness.permissions.create_assignment(
            user_id=current_owner.id, nursery_id=harness.nursery_id, role_id=owner_role.id
        )
        with pytest.raises(ValidationError):
            await harness.service.transfer_ownership(
                nursery_id=harness.nursery_id,
                current_owner_user_id=current_owner.id,
                new_owner_user_id=uuid.uuid4(),  # not an employee at all
                actor_user_id=current_owner.id,
            )

    async def test_current_owner_mismatch_rejected(self, harness: EmployeeTestHarness) -> None:
        harness.seed_system_role("owner", ["org:read"])
        harness.seed_system_role("org_admin", ["org:read"])
        not_the_owner = await harness.add_user(email="imposter@example.com")
        # not_the_owner has no role assignment at all
        with pytest.raises(ValidationError):
            await harness.service.transfer_ownership(
                nursery_id=harness.nursery_id,
                current_owner_user_id=not_the_owner.id,
                new_owner_user_id=uuid.uuid4(),
                actor_user_id=not_the_owner.id,
            )
