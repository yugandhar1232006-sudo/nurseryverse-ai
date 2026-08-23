"""
Production repository implementations, backed by the real SQLAlchemy
models from Phase 5 / migration 0007. Each class satisfies the
corresponding Protocol in app/repositories/interfaces.py. No caching, no
business logic here — lockout policy, token rotation, and replay
detection all live in app/services/auth_service.py; these classes are
pure persistence.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import ColumnElement, delete, func, or_, select, text
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import (
    AIPredictionType,
    AIRecommendationStatus,
    BranchStatus,
    CustomerType,
    DiseaseReportSeverity,
    DiseaseReportStatus,
    EmployeeStatus,
    EventDispatchStatus,
    InvoiceStatus,
    NotificationCategory,
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationFrequency,
    PlantStatus,
    QuotationStatus,
    RefundStatus,
    ReportScheduleFrequency,
    ReportStatus,
    ReportType,
    ReturnStatus,
    SalesOrderStatus,
    SaleStatus,
    SecurityEventType,
    StockMovementType,
    StockReservationStatus,
)
from app.models.ai import (
    AIAssistantConversation,
    AIAssistantMessage,
    AIInferenceFailure,
    AIPrediction,
    AIRecommendation,
    KnowledgeBaseChunk,
)
from app.models.auth import EmailVerificationToken, PasswordResetToken, RefreshToken, SecurityEvent
from app.models.authorization import AuthorizationDenial
from app.models.catalog import PlantCategory, PlantVariety, Species, Unit
from app.models.commerce import (
    Customer,
    CustomerAddress,
    CustomerCommunication,
    CustomerContact,
    CustomerNote,
    CustomerTag,
    Invoice,
    InvoiceItem,
    InvoiceSale,
    OrderItem,
    Payment,
    Quotation,
    QuotationItem,
    Refund,
    Return,
    ReturnItem,
    Sale,
    SaleItem,
    SalesOrder,
)
from app.models.digital_twin import DigitalTwin, DigitalTwinVersion, EventDispatchLog
from app.models.digital_twin_records import EnvironmentalReading, FertilizerLog, GrowthTimeline, HealthHistory, WateringLog
from app.models.disease import DiseaseReport, Treatment
from app.models.events import DomainEvent
from app.models.identity import (
    Invite,
    InviteBranchScope,
    Permission,
    Role,
    RoleAssignment,
    RoleAssignmentBranchScope,
    RolePermission,
    User,
)
from app.models.inventory import Inventory, InventoryLocation, StockMovement, StockReservation
from app.models.notifications import Notification, NotificationDelivery, NotificationPreference, NotificationTemplate
from app.models.organization import Branch, Employee, Nursery
from app.models.plants import Plant, PlantImage, PlantTransfer
from app.models.platform import AuditLog, FeatureFlag, OrgSettings, SystemConfig
from app.models.purchasing import Supplier
from app.models.reports import Passport, QRScanEvent, Report, ScheduledReport


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def add(self, user: User) -> User:
        self._session.add(user)
        await self._session.flush()
        return user

    async def commit(self) -> None:
        await self._session.commit()

    # --- Added by Phase 6 Module 13 ("User Administration") ---
    async def list_for_ids(self, user_ids: list[uuid.UUID]) -> list[User]:
        if not user_ids:
            return []
        result = await self._session.execute(select(User).where(User.id.in_(user_ids)))
        return list(result.scalars().all())

    async def set_active(self, user: User, *, is_active: bool) -> User:
        user.is_active = is_active
        await self._session.flush()
        return user

    async def set_locked_until(self, user: User, *, locked_until: datetime | None) -> User:
        user.locked_until = locked_until
        await self._session.flush()
        return user

    async def reset_failed_login_attempts(self, user: User) -> User:
        user.failed_login_attempts = 0
        await self._session.flush()
        return user


class SqlAlchemyRefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, token: RefreshToken) -> RefreshToken:
        self._session.add(token)
        await self._session.flush()
        return token

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self._session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def list_active_for_user(self, user_id: uuid.UUID) -> list[RefreshToken]:
        now = datetime.now()
        result = await self._session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            )
        )
        return list(result.scalars().all())

    async def revoke(self, token: RefreshToken, *, now: datetime) -> None:
        token.revoked_at = now
        await self._session.flush()

    async def revoke_family(self, family_id: uuid.UUID, *, now: datetime) -> None:
        result = await self._session.execute(
            select(RefreshToken).where(
                RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)
            )
        )
        for token in result.scalars().all():
            token.revoked_at = now
        await self._session.flush()

    async def revoke_all_for_user(self, user_id: uuid.UUID, *, now: datetime) -> None:
        result = await self._session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
            )
        )
        for token in result.scalars().all():
            token.revoked_at = now
        await self._session.flush()


class SqlAlchemyEmailVerificationTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, token: EmailVerificationToken) -> EmailVerificationToken:
        self._session.add(token)
        await self._session.flush()
        return token

    async def get_by_hash(self, token_hash: str) -> EmailVerificationToken | None:
        result = await self._session.execute(
            select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def mark_used(self, token: EmailVerificationToken, *, now: datetime) -> None:
        token.used_at = now
        await self._session.flush()


class SqlAlchemyPasswordResetTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, token: PasswordResetToken) -> PasswordResetToken:
        self._session.add(token)
        await self._session.flush()
        return token

    async def get_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        result = await self._session.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def mark_used(self, token: PasswordResetToken, *, now: datetime) -> None:
        token.used_at = now
        await self._session.flush()


class SqlAlchemySecurityEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def log(self, event: SecurityEvent) -> None:
        self._session.add(event)
        await self._session.flush()

    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[SecurityEvent], int]:
        # `security_events` carries no `nursery_id` of its own (see that
        # model's own docstring) -- scoped via a DISTINCT join through
        # `employees.user_id`, the Protocol's own documented "closest
        # honest approximation" for Security Reports.
        filters: list[ColumnElement[bool]] = [Employee.nursery_id == nursery_id]
        if date_from is not None:
            filters.append(SecurityEvent.created_at >= date_from)
        if date_to is not None:
            filters.append(SecurityEvent.created_at <= date_to)
        base_query = (
            select(SecurityEvent).join(Employee, SecurityEvent.user_id == Employee.user_id).where(*filters).distinct()
        )
        total = (await self._session.execute(select(func.count()).select_from(base_query.subquery()))).scalar_one()
        rows = await self._session.execute(
            base_query.order_by(SecurityEvent.created_at.desc()).offset(offset).limit(limit)
        )
        return list(rows.scalars().all()), total

    # --- Added by Phase 6 Module 13 ("Audit & Security Administration") ---
    async def search_for_org(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        event_type: SecurityEventType | None = None,
        user_id: uuid.UUID | None = None,
    ) -> tuple[list[SecurityEvent], int]:
        filters: list[ColumnElement[bool]] = [Employee.nursery_id == nursery_id]
        if date_from is not None:
            filters.append(SecurityEvent.created_at >= date_from)
        if date_to is not None:
            filters.append(SecurityEvent.created_at <= date_to)
        if event_type is not None:
            filters.append(SecurityEvent.event_type == event_type)
        if user_id is not None:
            filters.append(SecurityEvent.user_id == user_id)
        base_query = (
            select(SecurityEvent).join(Employee, SecurityEvent.user_id == Employee.user_id).where(*filters).distinct()
        )
        total = (await self._session.execute(select(func.count()).select_from(base_query.subquery()))).scalar_one()
        rows = await self._session.execute(
            base_query.order_by(SecurityEvent.created_at.desc()).offset(offset).limit(limit)
        )
        return list(rows.scalars().all()), total

    async def list_all(
        self,
        *,
        offset: int,
        limit: int,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        event_type: SecurityEventType | None = None,
    ) -> tuple[list[SecurityEvent], int]:
        filters: list[ColumnElement[bool]] = []
        if date_from is not None:
            filters.append(SecurityEvent.created_at >= date_from)
        if date_to is not None:
            filters.append(SecurityEvent.created_at <= date_to)
        if event_type is not None:
            filters.append(SecurityEvent.event_type == event_type)
        base_query = select(SecurityEvent).where(*filters) if filters else select(SecurityEvent)
        total = (await self._session.execute(select(func.count()).select_from(base_query.subquery()))).scalar_one()
        rows = await self._session.execute(
            base_query.order_by(SecurityEvent.created_at.desc()).offset(offset).limit(limit)
        )
        return list(rows.scalars().all()), total


class SqlAlchemyPermissionRepository:
    """
    Backs RBAC resolution. v1 constrains one Org per User at the
    application layer (identity.py's RoleAssignment docstring), so
    `get_role_assignment_for_user` returns the single row rather than a
    list — the schema doesn't hard-block multiple, but nothing in the
    product today creates more than one.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_role_assignment_for_user(self, user_id: uuid.UUID) -> RoleAssignment | None:
        result = await self._session.execute(
            select(RoleAssignment)
            .where(RoleAssignment.user_id == user_id)
            .options(selectinload(RoleAssignment.branch_scopes))
        )
        return result.scalars().first()

    async def list_role_assignments_for_user(self, user_id: uuid.UUID) -> list[RoleAssignment]:
        result = await self._session.execute(
            select(RoleAssignment)
            .where(RoleAssignment.user_id == user_id)
            .options(selectinload(RoleAssignment.branch_scopes))
        )
        return list(result.scalars().all())

    async def get_role_with_permissions(self, role_id: uuid.UUID) -> Role | None:
        result = await self._session.execute(
            select(Role).where(Role.id == role_id).options(selectinload(Role.permissions))
        )
        return result.scalar_one_or_none()

    async def get_branch_scope_ids(self, role_assignment_id: uuid.UUID) -> list[uuid.UUID]:
        assignment = await self._session.get(
            RoleAssignment, role_assignment_id, options=[selectinload(RoleAssignment.branch_scopes)]
        )
        if assignment is None:
            return []
        return [scope.branch_id for scope in assignment.branch_scopes]

    # --- Added by Phase 6 Module 11 (Notifications) ---
    async def list_users_with_permission(
        self, nursery_id: uuid.UUID, permission_code: str, *, branch_id: uuid.UUID | None = None
    ) -> list[uuid.UUID]:
        conditions: list[ColumnElement[bool]] = [
            RoleAssignment.nursery_id == nursery_id,
            Permission.code == permission_code,
        ]
        if branch_id is not None:
            # Org-wide assignments (no branch_scopes rows at all) always
            # qualify; branch-scoped assignments qualify only if one of
            # their scope rows matches the requested branch.
            conditions.append(
                or_(
                    ~RoleAssignment.branch_scopes.any(),
                    RoleAssignment.branch_scopes.any(RoleAssignmentBranchScope.branch_id == branch_id),
                )
            )
        result = await self._session.execute(
            select(RoleAssignment.user_id)
            .join(Role, Role.id == RoleAssignment.role_id)
            .join(RolePermission, RolePermission.role_id == Role.id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .where(*conditions)
            .distinct()
        )
        return [row[0] for row in result.all()]

    # --- Added by Phase 6 Module 4 ---
    async def get_system_role_by_code(self, code: str) -> Role | None:
        result = await self._session.execute(
            select(Role).where(Role.nursery_id.is_(None), Role.code == code)
        )
        return result.scalar_one_or_none()

    async def create_assignment(
        self, *, user_id: uuid.UUID, nursery_id: uuid.UUID, role_id: uuid.UUID
    ) -> RoleAssignment:
        assignment = RoleAssignment(user_id=user_id, nursery_id=nursery_id, role_id=role_id)
        self._session.add(assignment)
        await self._session.flush()
        return assignment

    async def add_assignment_branch_scope(self, role_assignment_id: uuid.UUID, branch_id: uuid.UUID) -> None:
        self._session.add(
            RoleAssignmentBranchScope(role_assignment_id=role_assignment_id, branch_id=branch_id)
        )
        await self._session.flush()

    async def replace_assignment_branch_scopes(
        self, role_assignment_id: uuid.UUID, branch_ids: list[uuid.UUID]
    ) -> None:
        await self._session.execute(
            delete(RoleAssignmentBranchScope).where(
                RoleAssignmentBranchScope.role_assignment_id == role_assignment_id
            )
        )
        for branch_id in branch_ids:
            self._session.add(
                RoleAssignmentBranchScope(role_assignment_id=role_assignment_id, branch_id=branch_id)
            )
        await self._session.flush()

    async def delete_assignment(self, role_assignment_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(RoleAssignment).where(RoleAssignment.id == role_assignment_id)
        )
        await self._session.flush()

    # --- Added by Phase 6 Module 13 ("Role & Permission Administration") ---
    async def list_roles(self, *, nursery_id: uuid.UUID | None = None) -> list[Role]:
        condition: ColumnElement[bool] = Role.nursery_id.is_(None)
        if nursery_id is not None:
            condition = or_(condition, Role.nursery_id == nursery_id)
        result = await self._session.execute(select(Role).where(condition).order_by(Role.code))
        return list(result.scalars().all())

    async def list_permissions(self) -> list[Permission]:
        result = await self._session.execute(select(Permission).order_by(Permission.module, Permission.action))
        return list(result.scalars().all())

    async def list_role_permission_codes(self, role_id: uuid.UUID) -> list[tuple[str, str]]:
        result = await self._session.execute(
            select(Permission.code, RolePermission.scope)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
            .order_by(Permission.code)
        )
        return [(row[0], row[1]) for row in result.all()]

    async def set_assignment_role(self, assignment: RoleAssignment, *, role_id: uuid.UUID) -> RoleAssignment:
        assignment.role_id = role_id
        await self._session.flush()
        return assignment


class SqlAlchemyInviteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_token(self, token: str) -> Invite | None:
        result = await self._session.execute(select(Invite).where(Invite.token == token))
        return result.scalar_one_or_none()

    async def mark_accepted(self, invite: Invite, *, now: datetime) -> None:
        invite.accepted_at = now
        await self._session.flush()

    # --- Added by Phase 6 Module 4 ---
    async def add(self, invite: Invite) -> Invite:
        self._session.add(invite)
        await self._session.flush()
        return invite

    async def get_by_id(self, invite_id: uuid.UUID) -> Invite | None:
        return await self._session.get(Invite, invite_id)

    async def get_pending_by_email_and_nursery(self, nursery_id: uuid.UUID, email: str) -> Invite | None:
        now = datetime.now(timezone.utc)
        result = await self._session.execute(
            select(Invite).where(
                Invite.nursery_id == nursery_id,
                Invite.email == email.strip().lower(),
                Invite.accepted_at.is_(None),
                Invite.expires_at > now,
            )
        )
        return result.scalars().first()

    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[Invite], int]:
        count_result = await self._session.execute(
            select(func.count()).select_from(Invite).where(Invite.nursery_id == nursery_id)
        )
        total = count_result.scalar_one()
        rows_result = await self._session.execute(
            select(Invite)
            .where(Invite.nursery_id == nursery_id)
            .order_by(Invite.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows_result.scalars().all()), total

    async def get_branch_scope_ids(self, invite_id: uuid.UUID) -> list[uuid.UUID]:
        result = await self._session.execute(
            select(InviteBranchScope.branch_id).where(InviteBranchScope.invite_id == invite_id)
        )
        return list(result.scalars().all())

    async def add_branch_scope(self, invite_id: uuid.UUID, branch_id: uuid.UUID) -> None:
        self._session.add(InviteBranchScope(invite_id=invite_id, branch_id=branch_id))
        await self._session.flush()


class SqlAlchemyAuthorizationDenialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def log(self, denial: AuthorizationDenial) -> None:
        self._session.add(denial)
        await self._session.flush()

    # --- Added by Phase 6 Module 13 ("Audit & Security Administration") ---
    async def list_for_org(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[AuthorizationDenial], int]:
        filters: list[ColumnElement[bool]] = [AuthorizationDenial.nursery_id == nursery_id]
        if date_from is not None:
            filters.append(AuthorizationDenial.created_at >= date_from)
        if date_to is not None:
            filters.append(AuthorizationDenial.created_at <= date_to)
        total = (
            await self._session.execute(select(func.count()).select_from(AuthorizationDenial).where(*filters))
        ).scalar_one()
        rows = await self._session.execute(
            select(AuthorizationDenial)
            .where(*filters)
            .order_by(AuthorizationDenial.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows.scalars().all()), total


class SqlAlchemyAuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_org(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[AuditLog], int]:
        count_result = await self._session.execute(
            select(func.count()).select_from(AuditLog).where(AuditLog.nursery_id == nursery_id)
        )
        total = count_result.scalar_one()

        rows_result = await self._session.execute(
            select(AuditLog)
            .where(AuditLog.nursery_id == nursery_id)
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows_result.scalars().all()), total

    async def log(self, entry: AuditLog) -> AuditLog:
        self._session.add(entry)
        await self._session.flush()
        return entry

    # --- Added by Phase 6 Module 13 ("Audit & Security Administration") ---
    async def search_for_org(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        actor_user_id: uuid.UUID | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        result: str | None = None,
        branch_id: uuid.UUID | None = None,
    ) -> tuple[list[AuditLog], int]:
        filters: list[ColumnElement[bool]] = [AuditLog.nursery_id == nursery_id]
        if date_from is not None:
            filters.append(AuditLog.created_at >= date_from)
        if date_to is not None:
            filters.append(AuditLog.created_at <= date_to)
        if actor_user_id is not None:
            filters.append(AuditLog.actor_user_id == actor_user_id)
        if action is not None:
            filters.append(AuditLog.action == action)
        if entity_type is not None:
            filters.append(AuditLog.entity_type == entity_type)
        if result is not None:
            filters.append(AuditLog.result == result)
        if branch_id is not None:
            filters.append(AuditLog.branch_id == branch_id)

        total = (
            await self._session.execute(select(func.count()).select_from(AuditLog).where(*filters))
        ).scalar_one()
        rows = await self._session.execute(
            select(AuditLog).where(*filters).order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
        )
        return list(rows.scalars().all()), total


class SqlAlchemyDomainEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: DomainEvent) -> DomainEvent:
        self._session.add(event)
        await self._session.flush()
        return event

    async def get_by_id(self, event_id: uuid.UUID) -> DomainEvent | None:
        return await self._session.get(DomainEvent, event_id)

    async def list_for_aggregate(
        self, aggregate_id: uuid.UUID, *, after_sequence: int | None = None
    ) -> list[DomainEvent]:
        filters = [DomainEvent.aggregate_id == aggregate_id]
        if after_sequence is not None:
            filters.append(DomainEvent.sequence > after_sequence)
        result = await self._session.execute(
            select(DomainEvent).where(*filters).order_by(DomainEvent.sequence)
        )
        return list(result.scalars().all())


class SqlAlchemyNurseryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, nursery_id: uuid.UUID) -> Nursery | None:
        return await self._session.get(Nursery, nursery_id)

    async def add(self, nursery: Nursery) -> Nursery:
        self._session.add(nursery)
        await self._session.flush()
        return nursery

    async def get_settings(self, nursery_id: uuid.UUID) -> OrgSettings | None:
        result = await self._session.execute(
            select(OrgSettings).where(OrgSettings.nursery_id == nursery_id)
        )
        return result.scalar_one_or_none()

    async def create_settings(self, settings: OrgSettings) -> OrgSettings:
        self._session.add(settings)
        await self._session.flush()
        return settings


class SqlAlchemyBranchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, branch_id: uuid.UUID) -> Branch | None:
        return await self._session.get(Branch, branch_id)

    async def get_by_name(self, nursery_id: uuid.UUID, name: str) -> Branch | None:
        result = await self._session.execute(
            select(Branch).where(Branch.nursery_id == nursery_id, Branch.name == name)
        )
        return result.scalar_one_or_none()

    async def add(self, branch: Branch) -> Branch:
        self._session.add(branch)
        await self._session.flush()
        return branch

    async def list_for_nursery(self, nursery_id: uuid.UUID, *, include_inactive: bool = False) -> list[Branch]:
        stmt = select(Branch).where(Branch.nursery_id == nursery_id)
        if not include_inactive:
            stmt = stmt.where(Branch.status == BranchStatus.ACTIVE)
        stmt = stmt.order_by(Branch.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class SqlAlchemyEmployeeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, employee_id: uuid.UUID) -> Employee | None:
        return await self._session.get(Employee, employee_id)

    async def get_by_user_and_nursery(self, user_id: uuid.UUID, nursery_id: uuid.UUID) -> Employee | None:
        result = await self._session.execute(
            select(Employee).where(Employee.user_id == user_id, Employee.nursery_id == nursery_id)
        )
        return result.scalar_one_or_none()

    async def add(self, employee: Employee) -> Employee:
        self._session.add(employee)
        await self._session.flush()
        return employee

    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int, status: EmployeeStatus | None = None
    ) -> tuple[list[Employee], int]:
        base_filter = [Employee.nursery_id == nursery_id]
        if status is not None:
            base_filter.append(Employee.status == status)

        count_result = await self._session.execute(
            select(func.count()).select_from(Employee).where(*base_filter)
        )
        total = count_result.scalar_one()

        rows_result = await self._session.execute(
            select(Employee)
            .where(*base_filter)
            .order_by(Employee.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows_result.scalars().all()), total


class SqlAlchemyPlantCategoryRepository:
    """Module 5: read-only access to the global, system-seeded `plant_categories` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[PlantCategory]:
        result = await self._session.execute(select(PlantCategory).order_by(PlantCategory.name))
        return list(result.scalars().all())

    async def get_by_id(self, category_id: uuid.UUID) -> PlantCategory | None:
        return await self._session.get(PlantCategory, category_id)


class SqlAlchemyUnitRepository:
    """Module 8: read-only access to the global, system-seeded `units` table. Mirrors `SqlAlchemyPlantCategoryRepository` exactly."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[Unit]:
        result = await self._session.execute(select(Unit).order_by(Unit.name))
        return list(result.scalars().all())

    async def get_by_id(self, unit_id: uuid.UUID) -> Unit | None:
        return await self._session.get(Unit, unit_id)


class SqlAlchemySpeciesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, species_id: uuid.UUID) -> Species | None:
        return await self._session.get(Species, species_id)

    async def get_by_botanical_name(self, nursery_id: uuid.UUID, botanical_name: str) -> Species | None:
        result = await self._session.execute(
            select(Species).where(Species.nursery_id == nursery_id, Species.botanical_name == botanical_name)
        )
        return result.scalar_one_or_none()

    async def add(self, species: Species) -> Species:
        self._session.add(species)
        await self._session.flush()
        return species

    async def delete(self, species: Species) -> None:
        await self._session.delete(species)
        await self._session.flush()

    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        search: str | None = None,
        category_id: uuid.UUID | None = None,
        light_requirement: str | None = None,
    ) -> tuple[list[Species], int]:
        filters = [Species.nursery_id == nursery_id]
        if search:
            like = f"%{search.strip()}%"
            filters.append((Species.common_name.ilike(like)) | (Species.botanical_name.ilike(like)))
        if category_id is not None:
            filters.append(Species.category_id == category_id)
        if light_requirement is not None:
            filters.append(Species.light_requirement == light_requirement)

        count_result = await self._session.execute(select(func.count()).select_from(Species).where(*filters))
        total = count_result.scalar_one()

        rows_result = await self._session.execute(
            select(Species).where(*filters).order_by(Species.common_name).offset(offset).limit(limit)
        )
        return list(rows_result.scalars().all()), total

    async def count_plants_referencing(self, species_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(Plant).where(Plant.species_id == species_id)
        )
        return result.scalar_one()


class SqlAlchemyPlantVarietyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, variety_id: uuid.UUID) -> PlantVariety | None:
        return await self._session.get(PlantVariety, variety_id)

    async def get_by_name(self, species_id: uuid.UUID, name: str) -> PlantVariety | None:
        result = await self._session.execute(
            select(PlantVariety).where(PlantVariety.species_id == species_id, PlantVariety.name == name)
        )
        return result.scalar_one_or_none()

    async def add(self, variety: PlantVariety) -> PlantVariety:
        self._session.add(variety)
        await self._session.flush()
        return variety

    async def delete(self, variety: PlantVariety) -> None:
        await self._session.delete(variety)
        await self._session.flush()

    async def list_for_species(
        self, species_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[PlantVariety], int]:
        count_result = await self._session.execute(
            select(func.count()).select_from(PlantVariety).where(PlantVariety.species_id == species_id)
        )
        total = count_result.scalar_one()

        rows_result = await self._session.execute(
            select(PlantVariety)
            .where(PlantVariety.species_id == species_id)
            .order_by(PlantVariety.name)
            .offset(offset)
            .limit(limit)
        )
        return list(rows_result.scalars().all()), total

    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[PlantVariety], int]:
        count_result = await self._session.execute(
            select(func.count()).select_from(PlantVariety).where(PlantVariety.nursery_id == nursery_id)
        )
        total = count_result.scalar_one()

        rows_result = await self._session.execute(
            select(PlantVariety)
            .where(PlantVariety.nursery_id == nursery_id)
            .order_by(PlantVariety.name)
            .offset(offset)
            .limit(limit)
        )
        return list(rows_result.scalars().all()), total

    async def count_plants_referencing(self, variety_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(Plant).where(Plant.variety_id == variety_id)
        )
        return result.scalar_one()


# ==============================================================================
# Module 6 (Plant Lifecycle Management)
# ==============================================================================

_PLANT_SORT_COLUMNS = {
    "created_at": Plant.created_at,
    "planted_at": Plant.planted_at,
    "status": Plant.status,
    "common_label": Plant.common_label,
}


class SqlAlchemyPlantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, plant_id: uuid.UUID) -> Plant | None:
        return await self._session.get(Plant, plant_id)

    async def get_by_qr_token(self, qr_code_token: str) -> Plant | None:
        result = await self._session.execute(select(Plant).where(Plant.qr_code_token == qr_code_token))
        return result.scalar_one_or_none()

    async def add(self, plant: Plant) -> Plant:
        self._session.add(plant)
        await self._session.flush()
        return plant

    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        branch_id: uuid.UUID | None = None,
        species_id: uuid.UUID | None = None,
        status: PlantStatus | None = None,
        zone: str | None = None,
        batch_number: str | None = None,
        search: str | None = None,
        include_archived: bool = False,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> tuple[list[Plant], int]:
        filters = [Plant.nursery_id == nursery_id]
        if branch_id is not None:
            filters.append(Plant.branch_id == branch_id)
        if species_id is not None:
            filters.append(Plant.species_id == species_id)
        if status is not None:
            filters.append(Plant.status == status)
        if zone is not None:
            filters.append(Plant.zone == zone)
        if batch_number is not None:
            filters.append(Plant.batch_number == batch_number)
        if not include_archived:
            filters.append(Plant.archived_at.is_(None))
        if search:
            like = f"%{search.strip()}%"
            filters.append(
                (Plant.common_label.ilike(like))
                | (Plant.qr_code_token.ilike(like))
                | (Plant.batch_number.ilike(like))
            )

        count_result = await self._session.execute(select(func.count()).select_from(Plant).where(*filters))
        total = count_result.scalar_one()

        sort_column = _PLANT_SORT_COLUMNS.get(sort_by, Plant.created_at)
        order = sort_column.asc() if sort_dir == "asc" else sort_column.desc()
        rows_result = await self._session.execute(
            select(Plant).where(*filters).order_by(order).offset(offset).limit(limit)
        )
        return list(rows_result.scalars().all()), total


class SqlAlchemyPlantImageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, image: PlantImage) -> PlantImage:
        self._session.add(image)
        await self._session.flush()
        return image

    async def list_for_plant(self, plant_id: uuid.UUID) -> list[PlantImage]:
        result = await self._session.execute(
            select(PlantImage).where(PlantImage.plant_id == plant_id).order_by(PlantImage.captured_at)
        )
        return list(result.scalars().all())


class SqlAlchemyPlantTransferRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, transfer: PlantTransfer) -> PlantTransfer:
        self._session.add(transfer)
        await self._session.flush()
        return transfer

    async def list_for_plant(self, plant_id: uuid.UUID) -> list[PlantTransfer]:
        result = await self._session.execute(
            select(PlantTransfer).where(PlantTransfer.plant_id == plant_id).order_by(PlantTransfer.transferred_at)
        )
        return list(result.scalars().all())


class SqlAlchemyGrowthTimelineRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: GrowthTimeline) -> GrowthTimeline:
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def list_for_plant(
        self, plant_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[GrowthTimeline], int]:
        count_result = await self._session.execute(
            select(func.count()).select_from(GrowthTimeline).where(GrowthTimeline.plant_id == plant_id)
        )
        total = count_result.scalar_one()
        rows_result = await self._session.execute(
            select(GrowthTimeline)
            .where(GrowthTimeline.plant_id == plant_id)
            .order_by(GrowthTimeline.recorded_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows_result.scalars().all()), total

    async def get_by_id(self, entry_id: uuid.UUID) -> GrowthTimeline | None:
        return await self._session.get(GrowthTimeline, entry_id)

    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        branch_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[GrowthTimeline], int]:
        filters: list[ColumnElement[bool]] = [Plant.nursery_id == nursery_id]
        if branch_id is not None:
            filters.append(Plant.branch_id == branch_id)
        if date_from is not None:
            filters.append(GrowthTimeline.recorded_at >= date_from)
        if date_to is not None:
            filters.append(GrowthTimeline.recorded_at <= date_to)
        base_query = select(GrowthTimeline).join(Plant, GrowthTimeline.plant_id == Plant.id).where(*filters)
        total = (await self._session.execute(select(func.count()).select_from(base_query.subquery()))).scalar_one()
        rows = await self._session.execute(
            base_query.order_by(GrowthTimeline.recorded_at.desc()).offset(offset).limit(limit)
        )
        return list(rows.scalars().all()), total


class SqlAlchemyHealthHistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: HealthHistory) -> HealthHistory:
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def list_for_plant(
        self, plant_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[HealthHistory], int]:
        count_result = await self._session.execute(
            select(func.count()).select_from(HealthHistory).where(HealthHistory.plant_id == plant_id)
        )
        total = count_result.scalar_one()
        rows_result = await self._session.execute(
            select(HealthHistory)
            .where(HealthHistory.plant_id == plant_id)
            .order_by(HealthHistory.recorded_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows_result.scalars().all()), total

    async def get_by_id(self, entry_id: uuid.UUID) -> HealthHistory | None:
        return await self._session.get(HealthHistory, entry_id)


class SqlAlchemyWateringLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: WateringLog) -> WateringLog:
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def list_for_plant(
        self, plant_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[WateringLog], int]:
        count_result = await self._session.execute(
            select(func.count()).select_from(WateringLog).where(WateringLog.plant_id == plant_id)
        )
        total = count_result.scalar_one()
        rows_result = await self._session.execute(
            select(WateringLog)
            .where(WateringLog.plant_id == plant_id)
            .order_by(WateringLog.recorded_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows_result.scalars().all()), total

    async def get_by_id(self, entry_id: uuid.UUID) -> WateringLog | None:
        return await self._session.get(WateringLog, entry_id)

    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        branch_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[WateringLog], int]:
        # Unlike `GrowthTimeline` (FK to `plants` only), `WateringLog`
        # carries its own `branch_id` directly and a NULLABLE `plant_id`
        # (a watering pass over a whole zone has no single plant to
        # attach to) -- joining through `Plant` here would silently drop
        # every zone-level entry, so tenant scoping resolves via
        # `Branch.nursery_id` instead, and the `branch_id` filter is a
        # direct column comparison, no join needed for it at all.
        filters: list[ColumnElement[bool]] = [Branch.nursery_id == nursery_id]
        if branch_id is not None:
            filters.append(WateringLog.branch_id == branch_id)
        if date_from is not None:
            filters.append(WateringLog.recorded_at >= date_from)
        if date_to is not None:
            filters.append(WateringLog.recorded_at <= date_to)
        base_query = select(WateringLog).join(Branch, WateringLog.branch_id == Branch.id).where(*filters)
        total = (await self._session.execute(select(func.count()).select_from(base_query.subquery()))).scalar_one()
        rows = await self._session.execute(
            base_query.order_by(WateringLog.recorded_at.desc()).offset(offset).limit(limit)
        )
        return list(rows.scalars().all()), total


class SqlAlchemyFertilizerLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: FertilizerLog) -> FertilizerLog:
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def list_for_plant(
        self, plant_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[FertilizerLog], int]:
        count_result = await self._session.execute(
            select(func.count()).select_from(FertilizerLog).where(FertilizerLog.plant_id == plant_id)
        )
        total = count_result.scalar_one()
        rows_result = await self._session.execute(
            select(FertilizerLog)
            .where(FertilizerLog.plant_id == plant_id)
            .order_by(FertilizerLog.recorded_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows_result.scalars().all()), total

    async def get_by_id(self, entry_id: uuid.UUID) -> FertilizerLog | None:
        return await self._session.get(FertilizerLog, entry_id)

    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        branch_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[FertilizerLog], int]:
        # Same `Branch.nursery_id` join as `SqlAlchemyWateringLogRepository.
        # list_for_nursery` -- `FertilizerLog` also carries its own
        # `branch_id` directly with a nullable `plant_id` (zone-level
        # applications), so joining through `Plant` would drop those rows.
        filters: list[ColumnElement[bool]] = [Branch.nursery_id == nursery_id]
        if branch_id is not None:
            filters.append(FertilizerLog.branch_id == branch_id)
        if date_from is not None:
            filters.append(FertilizerLog.recorded_at >= date_from)
        if date_to is not None:
            filters.append(FertilizerLog.recorded_at <= date_to)
        base_query = select(FertilizerLog).join(Branch, FertilizerLog.branch_id == Branch.id).where(*filters)
        total = (await self._session.execute(select(func.count()).select_from(base_query.subquery()))).scalar_one()
        rows = await self._session.execute(
            base_query.order_by(FertilizerLog.recorded_at.desc()).offset(offset).limit(limit)
        )
        return list(rows.scalars().all()), total


class SqlAlchemyEnvironmentalReadingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: EnvironmentalReading) -> EnvironmentalReading:
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def list_for_plant(
        self, plant_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[EnvironmentalReading], int]:
        count_result = await self._session.execute(
            select(func.count()).select_from(EnvironmentalReading).where(EnvironmentalReading.plant_id == plant_id)
        )
        total = count_result.scalar_one()
        rows_result = await self._session.execute(
            select(EnvironmentalReading)
            .where(EnvironmentalReading.plant_id == plant_id)
            .order_by(EnvironmentalReading.recorded_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows_result.scalars().all()), total

    async def get_by_id(self, entry_id: uuid.UUID) -> EnvironmentalReading | None:
        return await self._session.get(EnvironmentalReading, entry_id)


class SqlAlchemyDiseaseReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, report_id: uuid.UUID) -> DiseaseReport | None:
        return await self._session.get(DiseaseReport, report_id)

    async def add(self, report: DiseaseReport) -> DiseaseReport:
        self._session.add(report)
        await self._session.flush()
        return report

    async def list_for_plant(self, plant_id: uuid.UUID) -> list[DiseaseReport]:
        result = await self._session.execute(
            select(DiseaseReport).where(DiseaseReport.plant_id == plant_id).order_by(DiseaseReport.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        status: DiseaseReportStatus | None = None,
        severity: DiseaseReportSeverity | None = None,
    ) -> tuple[list[DiseaseReport], int]:
        filters = [Plant.nursery_id == nursery_id]
        if status is not None:
            filters.append(DiseaseReport.status == status)
        if severity is not None:
            filters.append(DiseaseReport.severity == severity)

        base_query = select(DiseaseReport).join(Plant, DiseaseReport.plant_id == Plant.id).where(*filters)
        count_result = await self._session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()
        rows_result = await self._session.execute(
            base_query.order_by(DiseaseReport.created_at.desc()).offset(offset).limit(limit)
        )
        return list(rows_result.scalars().all()), total

    async def count_open_for_plant(self, plant_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(DiseaseReport)
            .where(
                DiseaseReport.plant_id == plant_id,
                DiseaseReport.status.in_(
                    [DiseaseReportStatus.DRAFT, DiseaseReportStatus.CONFIRMED, DiseaseReportStatus.TREATED]
                ),
            )
        )
        return result.scalar_one()


class SqlAlchemyTreatmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, treatment: Treatment) -> Treatment:
        self._session.add(treatment)
        await self._session.flush()
        return treatment

    async def list_for_disease_report(self, disease_report_id: uuid.UUID) -> list[Treatment]:
        result = await self._session.execute(
            select(Treatment)
            .where(Treatment.disease_report_id == disease_report_id)
            .order_by(Treatment.applied_at)
        )
        return list(result.scalars().all())

    async def get_by_id(self, treatment_id: uuid.UUID) -> Treatment | None:
        return await self._session.get(Treatment, treatment_id)


class SqlAlchemySupplierRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, supplier_id: uuid.UUID) -> Supplier | None:
        return await self._session.get(Supplier, supplier_id)

    async def list_for_nursery(self, nursery_id: uuid.UUID) -> list[Supplier]:
        from sqlalchemy import select
        stmt = select(Supplier).where(Supplier.nursery_id == nursery_id).order_by(Supplier.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


# --------------------------------------------------------------------------
# Module 7 (Plant Digital Twin Engine)
# --------------------------------------------------------------------------

_DIGITAL_TWIN_SORT_COLUMNS = {
    "updated_at": DigitalTwin.updated_at,
    "created_at": DigitalTwin.created_at,
    "lifecycle_state": DigitalTwin.lifecycle_state,
    "current_version": DigitalTwin.current_version,
}


class SqlAlchemyDigitalTwinRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_plant_id(self, plant_id: uuid.UUID) -> DigitalTwin | None:
        result = await self._session.execute(select(DigitalTwin).where(DigitalTwin.plant_id == plant_id))
        return result.scalar_one_or_none()

    async def create(self, twin: DigitalTwin) -> DigitalTwin:
        self._session.add(twin)
        await self._session.flush()
        return twin

    async def update(self, twin: DigitalTwin) -> DigitalTwin:
        await self._session.flush()
        return twin

    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        lifecycle_state: str | None = None,
        branch_id: uuid.UUID | None = None,
        sort_by: str = "updated_at",
        sort_dir: str = "desc",
    ) -> tuple[list[DigitalTwin], int]:
        filters = [DigitalTwin.nursery_id == nursery_id]
        if lifecycle_state is not None:
            filters.append(DigitalTwin.lifecycle_state == lifecycle_state)
        if branch_id is not None:
            filters.append(DigitalTwin.branch_id == branch_id)
        count_result = await self._session.execute(
            select(func.count()).select_from(DigitalTwin).where(*filters)
        )
        total = count_result.scalar_one()
        sort_column = _DIGITAL_TWIN_SORT_COLUMNS.get(sort_by, DigitalTwin.updated_at)
        order = sort_column.asc() if sort_dir == "asc" else sort_column.desc()
        rows_result = await self._session.execute(
            select(DigitalTwin).where(*filters).order_by(order).offset(offset).limit(limit)
        )
        return list(rows_result.scalars().all()), total


class SqlAlchemyDigitalTwinVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, version: DigitalTwinVersion) -> DigitalTwinVersion:
        self._session.add(version)
        await self._session.flush()
        return version

    async def get_by_plant_and_version(self, plant_id: uuid.UUID, version: int) -> DigitalTwinVersion | None:
        result = await self._session.execute(
            select(DigitalTwinVersion).where(
                DigitalTwinVersion.plant_id == plant_id, DigitalTwinVersion.version == version
            )
        )
        return result.scalar_one_or_none()

    async def get_latest_version_number(self, plant_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.max(DigitalTwinVersion.version)).where(DigitalTwinVersion.plant_id == plant_id)
        )
        return result.scalar_one() or 0

    async def list_for_plant(
        self, plant_id: uuid.UUID, *, offset: int, limit: int, sort_dir: str = "desc"
    ) -> tuple[list[DigitalTwinVersion], int]:
        count_result = await self._session.execute(
            select(func.count()).select_from(DigitalTwinVersion).where(DigitalTwinVersion.plant_id == plant_id)
        )
        total = count_result.scalar_one()
        order = (
            DigitalTwinVersion.version.asc() if sort_dir == "asc" else DigitalTwinVersion.version.desc()
        )
        rows_result = await self._session.execute(
            select(DigitalTwinVersion)
            .where(DigitalTwinVersion.plant_id == plant_id)
            .order_by(order)
            .offset(offset)
            .limit(limit)
        )
        return list(rows_result.scalars().all()), total

    async def get_as_of(self, plant_id: uuid.UUID, *, as_of: datetime) -> DigitalTwinVersion | None:
        result = await self._session.execute(
            select(DigitalTwinVersion)
            .where(DigitalTwinVersion.plant_id == plant_id, DigitalTwinVersion.occurred_at <= as_of)
            .order_by(DigitalTwinVersion.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


class SqlAlchemyEventDispatchLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, event_id: uuid.UUID, handler_name: str) -> EventDispatchLog | None:
        result = await self._session.execute(
            select(EventDispatchLog).where(
                EventDispatchLog.event_id == event_id, EventDispatchLog.handler_name == handler_name
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        event_id: uuid.UUID,
        handler_name: str,
        status: EventDispatchStatus,
        attempt_count: int,
        resulting_version: int | None,
        error_message: str | None,
    ) -> EventDispatchLog:
        existing = await self.get(event_id, handler_name)
        if existing is not None:
            existing.status = status
            existing.attempt_count = attempt_count
            existing.resulting_version = resulting_version
            existing.error_message = error_message
            await self._session.flush()
            return existing
        row = EventDispatchLog(
            event_id=event_id,
            handler_name=handler_name,
            status=status,
            attempt_count=attempt_count,
            resulting_version=resulting_version,
            error_message=error_message,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_failed(self, *, handler_name: str | None = None, limit: int = 100) -> list[EventDispatchLog]:
        filters = [EventDispatchLog.status == EventDispatchStatus.FAILED]
        if handler_name is not None:
            filters.append(EventDispatchLog.handler_name == handler_name)
        result = await self._session.execute(
            select(EventDispatchLog).where(*filters).order_by(EventDispatchLog.processed_at).limit(limit)
        )
        return list(result.scalars().all())


# ==============================================================================
# Module 8 (Inventory & Stock Management)
# ==============================================================================

_INVENTORY_SORT_COLUMNS = {
    "created_at": Inventory.created_at,
    "name": Inventory.name,
    "quantity": Inventory.quantity,
    "low_stock_threshold": Inventory.low_stock_threshold,
}


class SqlAlchemyInventoryLocationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, location_id: uuid.UUID) -> InventoryLocation | None:
        return await self._session.get(InventoryLocation, location_id)

    async def add(self, location: InventoryLocation) -> InventoryLocation:
        self._session.add(location)
        await self._session.flush()
        return location

    async def update(self, location: InventoryLocation) -> InventoryLocation:
        await self._session.flush()
        return location

    async def list_for_branch(
        self, branch_id: uuid.UUID, *, include_inactive: bool = False
    ) -> list[InventoryLocation]:
        filters = [InventoryLocation.branch_id == branch_id]
        if not include_inactive:
            filters.append(InventoryLocation.is_active.is_(True))
        result = await self._session.execute(
            select(InventoryLocation).where(*filters).order_by(InventoryLocation.name)
        )
        return list(result.scalars().all())


class SqlAlchemyInventoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, inventory_id: uuid.UUID) -> Inventory | None:
        return await self._session.get(Inventory, inventory_id)

    async def add(self, inventory: Inventory) -> Inventory:
        self._session.add(inventory)
        await self._session.flush()
        return inventory

    async def update(self, inventory: Inventory, *, expected_version: int) -> Inventory | None:
        """
        See InventoryRepository.update's Protocol docstring: a conditional
        UPDATE keyed on `version`, returning None (no exception) if the
        row was already changed by another writer since it was read.
        """
        stmt = (
            sa_update(Inventory)
            .where(Inventory.id == inventory.id, Inventory.version == expected_version)
            .values(
                quantity=inventory.quantity,
                reserved_quantity=inventory.reserved_quantity,
                damaged_quantity=inventory.damaged_quantity,
                disposed_quantity=inventory.disposed_quantity,
                location_id=inventory.location_id,
                unit_cost=inventory.unit_cost,
                unit_price=inventory.unit_price,
                low_stock_threshold=inventory.low_stock_threshold,
                archived_at=inventory.archived_at,
                version=expected_version + 1,
            )
        )
        result = await self._session.execute(stmt)
        if result.rowcount == 0:
            return None
        inventory.version = expected_version + 1
        await self._session.flush()
        # The bulk UPDATE above expired the ORM instance's column
        # attributes (`synchronize_session` defaults to "fetch" for a
        # bulk update). Reading e.g. `quantity` without a reload would
        # fire a synchronous lazy load -- `MissingGreenlet` in this async
        # service. Refresh explicitly so callers can read the new values.
        await self._session.refresh(inventory)
        return inventory

    async def get_by_branch_and_name(self, branch_id: uuid.UUID, name: str) -> Inventory | None:
        result = await self._session.execute(
            select(Inventory).where(Inventory.branch_id == branch_id, Inventory.name == name)
        )
        return result.scalar_one_or_none()

    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        branch_id: uuid.UUID | None = None,
        category_id: uuid.UUID | None = None,
        species_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        search: str | None = None,
        low_stock_only: bool = False,
        include_archived: bool = False,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> tuple[list[Inventory], int]:
        filters = [Inventory.nursery_id == nursery_id]
        if branch_id is not None:
            filters.append(Inventory.branch_id == branch_id)
        if category_id is not None:
            filters.append(Inventory.category_id == category_id)
        if species_id is not None:
            filters.append(Inventory.species_id == species_id)
        if location_id is not None:
            filters.append(Inventory.location_id == location_id)
        if not include_archived:
            filters.append(Inventory.archived_at.is_(None))
        if low_stock_only:
            filters.append(Inventory.quantity <= Inventory.low_stock_threshold)
        if search:
            filters.append(Inventory.name.ilike(f"%{search.strip()}%"))

        count_result = await self._session.execute(select(func.count()).select_from(Inventory).where(*filters))
        total = count_result.scalar_one()

        sort_column = _INVENTORY_SORT_COLUMNS.get(sort_by, Inventory.created_at)
        order = sort_column.asc() if sort_dir == "asc" else sort_column.desc()
        rows_result = await self._session.execute(
            select(Inventory).where(*filters).order_by(order).offset(offset).limit(limit)
        )
        return list(rows_result.scalars().all()), total


class SqlAlchemyStockMovementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, movement: StockMovement) -> StockMovement:
        self._session.add(movement)
        await self._session.flush()
        return movement

    async def get_by_id(self, movement_id: uuid.UUID) -> StockMovement | None:
        return await self._session.get(StockMovement, movement_id)

    async def list_for_inventory(
        self,
        inventory_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        movement_type: StockMovementType | None = None,
        sort_dir: str = "desc",
    ) -> tuple[list[StockMovement], int]:
        filters = [StockMovement.inventory_id == inventory_id]
        if movement_type is not None:
            filters.append(StockMovement.movement_type == movement_type)
        count_result = await self._session.execute(
            select(func.count()).select_from(StockMovement).where(*filters)
        )
        total = count_result.scalar_one()
        order = StockMovement.created_at.asc() if sort_dir == "asc" else StockMovement.created_at.desc()
        rows_result = await self._session.execute(
            select(StockMovement).where(*filters).order_by(order).offset(offset).limit(limit)
        )
        return list(rows_result.scalars().all()), total

    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        branch_id: uuid.UUID | None = None,
        movement_type: StockMovementType | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sort_dir: str = "desc",
    ) -> tuple[list[StockMovement], int]:
        inventory_filters: list[ColumnElement[bool]] = [Inventory.nursery_id == nursery_id]
        if branch_id is not None:
            inventory_filters.append(Inventory.branch_id == branch_id)
        inventory_ids_subquery = select(Inventory.id).where(*inventory_filters)

        filters: list[ColumnElement[bool]] = [StockMovement.inventory_id.in_(inventory_ids_subquery)]
        if movement_type is not None:
            filters.append(StockMovement.movement_type == movement_type)
        if date_from is not None:
            filters.append(StockMovement.created_at >= date_from)
        if date_to is not None:
            filters.append(StockMovement.created_at <= date_to)

        count_result = await self._session.execute(
            select(func.count()).select_from(StockMovement).where(*filters)
        )
        total = count_result.scalar_one()
        order = StockMovement.created_at.asc() if sort_dir == "asc" else StockMovement.created_at.desc()
        rows_result = await self._session.execute(
            select(StockMovement).where(*filters).order_by(order).offset(offset).limit(limit)
        )
        return list(rows_result.scalars().all()), total


class SqlAlchemyStockReservationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, reservation_id: uuid.UUID) -> StockReservation | None:
        return await self._session.get(StockReservation, reservation_id)

    async def add(self, reservation: StockReservation) -> StockReservation:
        self._session.add(reservation)
        await self._session.flush()
        return reservation

    async def update(self, reservation: StockReservation) -> StockReservation:
        await self._session.flush()
        return reservation

    async def list_for_inventory(
        self, inventory_id: uuid.UUID, *, status: StockReservationStatus | None = None
    ) -> list[StockReservation]:
        filters = [StockReservation.inventory_id == inventory_id]
        if status is not None:
            filters.append(StockReservation.status == status)
        result = await self._session.execute(
            select(StockReservation).where(*filters).order_by(StockReservation.reserved_at.desc())
        )
        return list(result.scalars().all())

    async def list_active_for_nursery(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int, branch_id: uuid.UUID | None = None
    ) -> tuple[list[StockReservation], int]:
        filters = [StockReservation.nursery_id == nursery_id, StockReservation.status == StockReservationStatus.ACTIVE]
        if branch_id is not None:
            filters.append(StockReservation.branch_id == branch_id)
        count_result = await self._session.execute(
            select(func.count()).select_from(StockReservation).where(*filters)
        )
        total = count_result.scalar_one()
        rows_result = await self._session.execute(
            select(StockReservation)
            .where(*filters)
            .order_by(StockReservation.reserved_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows_result.scalars().all()), total


# =============================================================================
# Phase 6 Module 9 (Sales, CRM, Plant Passport & QR Intelligence).
# =============================================================================


class SqlAlchemyCustomerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, customer_id: uuid.UUID) -> Customer | None:
        return await self._session.get(Customer, customer_id)

    async def add(self, customer: Customer) -> Customer:
        self._session.add(customer)
        await self._session.flush()
        return customer

    async def update(self, customer: Customer) -> Customer:
        await self._session.flush()
        return customer

    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        branch_id: uuid.UUID | None = None,
        customer_type: CustomerType | None = None,
        tag: str | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> tuple[list[Customer], int]:
        filters: list[ColumnElement[bool]] = [Customer.nursery_id == nursery_id]
        if branch_id is not None:
            filters.append(Customer.branch_id == branch_id)
        if customer_type is not None:
            filters.append(Customer.customer_type == customer_type)
        if search:
            needle = f"%{search.strip()}%"
            filters.append(
                Customer.name.ilike(needle) | Customer.email.ilike(needle) | Customer.phone.ilike(needle)
            )
        if tag:
            filters.append(
                Customer.id.in_(select(CustomerTag.customer_id).where(CustomerTag.tag == tag))
            )

        count_result = await self._session.execute(select(func.count()).select_from(Customer).where(*filters))
        total = count_result.scalar_one()

        sort_columns = {"created_at": Customer.created_at, "name": Customer.name}
        sort_column = sort_columns.get(sort_by, Customer.created_at)
        order = sort_column.asc() if sort_dir == "asc" else sort_column.desc()
        rows_result = await self._session.execute(
            select(Customer).where(*filters).order_by(order).offset(offset).limit(limit)
        )
        return list(rows_result.scalars().all()), total


class SqlAlchemyCustomerContactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, contact_id: uuid.UUID) -> CustomerContact | None:
        return await self._session.get(CustomerContact, contact_id)

    async def add(self, contact: CustomerContact) -> CustomerContact:
        self._session.add(contact)
        await self._session.flush()
        return contact

    async def list_for_customer(self, customer_id: uuid.UUID) -> list[CustomerContact]:
        result = await self._session.execute(
            select(CustomerContact).where(CustomerContact.customer_id == customer_id).order_by(CustomerContact.created_at)
        )
        return list(result.scalars().all())

    async def delete(self, contact_id: uuid.UUID) -> None:
        await self._session.execute(delete(CustomerContact).where(CustomerContact.id == contact_id))


class SqlAlchemyCustomerAddressRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, address_id: uuid.UUID) -> CustomerAddress | None:
        return await self._session.get(CustomerAddress, address_id)

    async def add(self, address: CustomerAddress) -> CustomerAddress:
        self._session.add(address)
        await self._session.flush()
        return address

    async def list_for_customer(self, customer_id: uuid.UUID) -> list[CustomerAddress]:
        result = await self._session.execute(
            select(CustomerAddress).where(CustomerAddress.customer_id == customer_id).order_by(CustomerAddress.created_at)
        )
        return list(result.scalars().all())

    async def delete(self, address_id: uuid.UUID) -> None:
        await self._session.execute(delete(CustomerAddress).where(CustomerAddress.id == address_id))


class SqlAlchemyCustomerTagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, tag: CustomerTag) -> CustomerTag:
        self._session.add(tag)
        await self._session.flush()
        return tag

    async def list_for_customer(self, customer_id: uuid.UUID) -> list[CustomerTag]:
        result = await self._session.execute(
            select(CustomerTag).where(CustomerTag.customer_id == customer_id).order_by(CustomerTag.tag)
        )
        return list(result.scalars().all())

    async def delete(self, customer_id: uuid.UUID, tag: str) -> None:
        await self._session.execute(
            delete(CustomerTag).where(CustomerTag.customer_id == customer_id, CustomerTag.tag == tag)
        )


class SqlAlchemyCustomerNoteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, note_id: uuid.UUID) -> CustomerNote | None:
        return await self._session.get(CustomerNote, note_id)

    async def add(self, note: CustomerNote) -> CustomerNote:
        self._session.add(note)
        await self._session.flush()
        return note

    async def list_for_customer(
        self, customer_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[CustomerNote], int]:
        filters = [CustomerNote.customer_id == customer_id]
        count_result = await self._session.execute(select(func.count()).select_from(CustomerNote).where(*filters))
        total = count_result.scalar_one()
        rows_result = await self._session.execute(
            select(CustomerNote)
            .where(*filters)
            .order_by(CustomerNote.pinned.desc(), CustomerNote.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows_result.scalars().all()), total

    async def delete(self, note_id: uuid.UUID) -> None:
        await self._session.execute(delete(CustomerNote).where(CustomerNote.id == note_id))


class SqlAlchemyCustomerCommunicationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, communication: CustomerCommunication) -> CustomerCommunication:
        self._session.add(communication)
        await self._session.flush()
        return communication

    async def list_for_customer(
        self, customer_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[CustomerCommunication], int]:
        filters = [CustomerCommunication.customer_id == customer_id]
        count_result = await self._session.execute(
            select(func.count()).select_from(CustomerCommunication).where(*filters)
        )
        total = count_result.scalar_one()
        rows_result = await self._session.execute(
            select(CustomerCommunication)
            .where(*filters)
            .order_by(CustomerCommunication.occurred_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows_result.scalars().all()), total


class SqlAlchemyQuotationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, quotation_id: uuid.UUID) -> Quotation | None:
        return await self._session.get(Quotation, quotation_id)

    async def add(self, quotation: Quotation) -> Quotation:
        self._session.add(quotation)
        await self._session.flush()
        return quotation

    async def update(self, quotation: Quotation) -> Quotation:
        await self._session.flush()
        return quotation

    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        branch_id: uuid.UUID | None = None,
        customer_id: uuid.UUID | None = None,
        status: QuotationStatus | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> tuple[list[Quotation], int]:
        filters: list[ColumnElement[bool]] = [Quotation.nursery_id == nursery_id]
        if branch_id is not None:
            filters.append(Quotation.branch_id == branch_id)
        if customer_id is not None:
            filters.append(Quotation.customer_id == customer_id)
        if status is not None:
            filters.append(Quotation.status == status)
        count_result = await self._session.execute(select(func.count()).select_from(Quotation).where(*filters))
        total = count_result.scalar_one()
        sort_column = Quotation.total_amount if sort_by == "total_amount" else Quotation.created_at
        order = sort_column.asc() if sort_dir == "asc" else sort_column.desc()
        rows_result = await self._session.execute(
            select(Quotation).where(*filters).order_by(order).offset(offset).limit(limit)
        )
        return list(rows_result.scalars().all()), total


class SqlAlchemyQuotationItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, item: QuotationItem) -> QuotationItem:
        self._session.add(item)
        await self._session.flush()
        return item

    async def list_for_quotation(self, quotation_id: uuid.UUID) -> list[QuotationItem]:
        result = await self._session.execute(
            select(QuotationItem).where(QuotationItem.quotation_id == quotation_id)
        )
        return list(result.scalars().all())


class SqlAlchemySalesOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, order_id: uuid.UUID) -> SalesOrder | None:
        return await self._session.get(SalesOrder, order_id)

    async def get_by_idempotency_key(self, branch_id: uuid.UUID, key: str) -> SalesOrder | None:
        result = await self._session.execute(
            select(SalesOrder).where(SalesOrder.branch_id == branch_id, SalesOrder.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def add(self, order: SalesOrder) -> SalesOrder:
        self._session.add(order)
        await self._session.flush()
        return order

    async def update(self, order: SalesOrder) -> SalesOrder:
        await self._session.flush()
        return order

    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        branch_id: uuid.UUID | None = None,
        customer_id: uuid.UUID | None = None,
        order_status: SalesOrderStatus | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> tuple[list[SalesOrder], int]:
        filters: list[ColumnElement[bool]] = [SalesOrder.nursery_id == nursery_id]
        if branch_id is not None:
            filters.append(SalesOrder.branch_id == branch_id)
        if customer_id is not None:
            filters.append(SalesOrder.customer_id == customer_id)
        if order_status is not None:
            filters.append(SalesOrder.order_status == order_status)
        count_result = await self._session.execute(select(func.count()).select_from(SalesOrder).where(*filters))
        total = count_result.scalar_one()
        sort_column = SalesOrder.total_amount if sort_by == "total_amount" else SalesOrder.created_at
        order_clause = sort_column.asc() if sort_dir == "asc" else sort_column.desc()
        rows_result = await self._session.execute(
            select(SalesOrder).where(*filters).order_by(order_clause).offset(offset).limit(limit)
        )
        return list(rows_result.scalars().all()), total


class SqlAlchemyOrderItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, item_id: uuid.UUID) -> OrderItem | None:
        return await self._session.get(OrderItem, item_id)

    async def add(self, item: OrderItem) -> OrderItem:
        self._session.add(item)
        await self._session.flush()
        return item

    async def update(self, item: OrderItem) -> OrderItem:
        await self._session.flush()
        return item

    async def list_for_order(self, sales_order_id: uuid.UUID) -> list[OrderItem]:
        result = await self._session.execute(
            select(OrderItem).where(OrderItem.sales_order_id == sales_order_id)
        )
        return list(result.scalars().all())


class SqlAlchemySaleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, sale_id: uuid.UUID) -> Sale | None:
        return await self._session.get(Sale, sale_id)

    async def get_by_idempotency_key(self, branch_id: uuid.UUID, key: str) -> Sale | None:
        result = await self._session.execute(
            select(Sale).where(Sale.branch_id == branch_id, Sale.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def add(self, sale: Sale) -> Sale:
        self._session.add(sale)
        await self._session.flush()
        return sale

    async def update(self, sale: Sale) -> Sale:
        await self._session.flush()
        return sale

    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        branch_id: uuid.UUID | None = None,
        customer_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> tuple[list[Sale], int]:
        filters: list[ColumnElement[bool]] = [Sale.nursery_id == nursery_id]
        if branch_id is not None:
            filters.append(Sale.branch_id == branch_id)
        if customer_id is not None:
            filters.append(Sale.customer_id == customer_id)
        if date_from is not None:
            filters.append(Sale.created_at >= date_from)
        if date_to is not None:
            filters.append(Sale.created_at <= date_to)
        count_result = await self._session.execute(select(func.count()).select_from(Sale).where(*filters))
        total = count_result.scalar_one()
        sort_column = Sale.total_amount if sort_by == "total_amount" else Sale.created_at
        order = sort_column.asc() if sort_dir == "asc" else sort_column.desc()
        rows_result = await self._session.execute(
            select(Sale).where(*filters).order_by(order).offset(offset).limit(limit)
        )
        return list(rows_result.scalars().all()), total


class SqlAlchemySaleItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, item_id: uuid.UUID) -> SaleItem | None:
        return await self._session.get(SaleItem, item_id)

    async def add(self, item: SaleItem) -> SaleItem:
        self._session.add(item)
        await self._session.flush()
        return item

    async def list_for_sale(self, sale_id: uuid.UUID) -> list[SaleItem]:
        result = await self._session.execute(select(SaleItem).where(SaleItem.sale_id == sale_id))
        return list(result.scalars().all())


class SqlAlchemyInvoiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, invoice_id: uuid.UUID) -> Invoice | None:
        return await self._session.get(Invoice, invoice_id)

    async def get_by_number(self, nursery_id: uuid.UUID, invoice_number: str) -> Invoice | None:
        result = await self._session.execute(
            select(Invoice).where(Invoice.nursery_id == nursery_id, Invoice.invoice_number == invoice_number)
        )
        return result.scalar_one_or_none()

    async def add(self, invoice: Invoice) -> Invoice:
        self._session.add(invoice)
        await self._session.flush()
        return invoice

    async def update(self, invoice: Invoice) -> Invoice:
        await self._session.flush()
        return invoice

    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        branch_id: uuid.UUID | None = None,
        customer_id: uuid.UUID | None = None,
        status: InvoiceStatus | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> tuple[list[Invoice], int]:
        filters: list[ColumnElement[bool]] = [Invoice.nursery_id == nursery_id]
        if branch_id is not None:
            filters.append(Invoice.branch_id == branch_id)
        if customer_id is not None:
            filters.append(Invoice.customer_id == customer_id)
        if status is not None:
            filters.append(Invoice.status == status)
        count_result = await self._session.execute(select(func.count()).select_from(Invoice).where(*filters))
        total = count_result.scalar_one()
        sort_column = Invoice.total_amount if sort_by == "total_amount" else Invoice.created_at
        order = sort_column.asc() if sort_dir == "asc" else sort_column.desc()
        rows_result = await self._session.execute(
            select(Invoice).where(*filters).order_by(order).offset(offset).limit(limit)
        )
        return list(rows_result.scalars().all()), total


class SqlAlchemyInvoiceItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, item: InvoiceItem) -> InvoiceItem:
        self._session.add(item)
        await self._session.flush()
        return item

    async def list_for_invoice(self, invoice_id: uuid.UUID) -> list[InvoiceItem]:
        result = await self._session.execute(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id))
        return list(result.scalars().all())


class SqlAlchemyInvoiceSaleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def link(self, invoice_id: uuid.UUID, sale_id: uuid.UUID) -> None:
        self._session.add(InvoiceSale(invoice_id=invoice_id, sale_id=sale_id))
        await self._session.flush()

    async def list_sale_ids_for_invoice(self, invoice_id: uuid.UUID) -> list[uuid.UUID]:
        result = await self._session.execute(
            select(InvoiceSale.sale_id).where(InvoiceSale.invoice_id == invoice_id)
        )
        return list(result.scalars().all())


class SqlAlchemyPaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        return await self._session.get(Payment, payment_id)

    async def add(self, payment: Payment) -> Payment:
        self._session.add(payment)
        await self._session.flush()
        return payment

    async def list_for_invoice(self, invoice_id: uuid.UUID) -> list[Payment]:
        result = await self._session.execute(
            select(Payment).where(Payment.invoice_id == invoice_id).order_by(Payment.received_at)
        )
        return list(result.scalars().all())

    async def sum_for_invoice(self, invoice_id: uuid.UUID) -> float:
        result = await self._session.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.invoice_id == invoice_id)
        )
        return float(result.scalar_one())


class SqlAlchemyReturnRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, return_id: uuid.UUID) -> Return | None:
        return await self._session.get(Return, return_id)

    async def add(self, return_: Return) -> Return:
        self._session.add(return_)
        await self._session.flush()
        return return_

    async def update(self, return_: Return) -> Return:
        await self._session.flush()
        return return_

    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        branch_id: uuid.UUID | None = None,
        status: ReturnStatus | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> tuple[list[Return], int]:
        filters: list[ColumnElement[bool]] = [Return.nursery_id == nursery_id]
        if branch_id is not None:
            filters.append(Return.branch_id == branch_id)
        if status is not None:
            filters.append(Return.status == status)
        count_result = await self._session.execute(select(func.count()).select_from(Return).where(*filters))
        total = count_result.scalar_one()
        order = Return.created_at.asc() if sort_dir == "asc" else Return.created_at.desc()
        rows_result = await self._session.execute(
            select(Return).where(*filters).order_by(order).offset(offset).limit(limit)
        )
        return list(rows_result.scalars().all()), total


class SqlAlchemyReturnItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, item: ReturnItem) -> ReturnItem:
        self._session.add(item)
        await self._session.flush()
        return item

    async def list_for_return(self, return_id: uuid.UUID) -> list[ReturnItem]:
        result = await self._session.execute(select(ReturnItem).where(ReturnItem.return_id == return_id))
        return list(result.scalars().all())

    async def get_by_id(self, item_id: uuid.UUID) -> ReturnItem | None:
        return await self._session.get(ReturnItem, item_id)


class SqlAlchemyRefundRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, refund_id: uuid.UUID) -> Refund | None:
        return await self._session.get(Refund, refund_id)

    async def add(self, refund: Refund) -> Refund:
        self._session.add(refund)
        await self._session.flush()
        return refund

    async def update(self, refund: Refund) -> Refund:
        await self._session.flush()
        return refund

    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        branch_id: uuid.UUID | None = None,
        status: RefundStatus | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> tuple[list[Refund], int]:
        filters: list[ColumnElement[bool]] = [Refund.nursery_id == nursery_id]
        if branch_id is not None:
            filters.append(Refund.branch_id == branch_id)
        if status is not None:
            filters.append(Refund.status == status)
        count_result = await self._session.execute(select(func.count()).select_from(Refund).where(*filters))
        total = count_result.scalar_one()
        order = Refund.created_at.asc() if sort_dir == "asc" else Refund.created_at.desc()
        rows_result = await self._session.execute(
            select(Refund).where(*filters).order_by(order).offset(offset).limit(limit)
        )
        return list(rows_result.scalars().all()), total


class SqlAlchemyPassportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, passport_id: uuid.UUID) -> Passport | None:
        return await self._session.get(Passport, passport_id)

    async def get_by_token(self, public_token: str) -> Passport | None:
        result = await self._session.execute(select(Passport).where(Passport.public_token == public_token))
        return result.scalar_one_or_none()

    async def add(self, passport: Passport) -> Passport:
        self._session.add(passport)
        await self._session.flush()
        return passport

    async def get_latest_for_plant(self, plant_id: uuid.UUID) -> Passport | None:
        result = await self._session.execute(
            select(Passport).where(Passport.plant_id == plant_id).order_by(Passport.version.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def list_for_plant(self, plant_id: uuid.UUID) -> list[Passport]:
        result = await self._session.execute(
            select(Passport).where(Passport.plant_id == plant_id).order_by(Passport.version.desc())
        )
        return list(result.scalars().all())

    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[Passport], int]:
        filters = [Plant.nursery_id == nursery_id]
        count_result = await self._session.execute(
            select(func.count()).select_from(Passport).join(Plant, Plant.id == Passport.plant_id).where(*filters)
        )
        total = count_result.scalar_one()
        rows_result = await self._session.execute(
            select(Passport)
            .join(Plant, Plant.id == Passport.plant_id)
            .where(*filters)
            .order_by(Passport.generated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows_result.scalars().all()), total


class SqlAlchemyQRScanEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, scan: QRScanEvent) -> QRScanEvent:
        self._session.add(scan)
        await self._session.flush()
        return scan

    async def count_for_passport(self, passport_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(QRScanEvent).where(QRScanEvent.passport_id == passport_id)
        )
        return result.scalar_one()

    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[QRScanEvent], int]:
        passport_ids_subquery = (
            select(Passport.id).join(Plant, Plant.id == Passport.plant_id).where(Plant.nursery_id == nursery_id)
        )
        filters = [QRScanEvent.passport_id.in_(passport_ids_subquery)]
        count_result = await self._session.execute(select(func.count()).select_from(QRScanEvent).where(*filters))
        total = count_result.scalar_one()
        rows_result = await self._session.execute(
            select(QRScanEvent).where(*filters).order_by(QRScanEvent.scanned_at.desc()).offset(offset).limit(limit)
        )
        return list(rows_result.scalars().all()), total


# ==============================================================================
# Phase 6 Module 10 (AI Platform)
# ==============================================================================


class SqlAlchemyAIPredictionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, prediction: AIPrediction) -> AIPrediction:
        self._session.add(prediction)
        await self._session.flush()
        return prediction

    async def get_by_id(self, prediction_id: uuid.UUID) -> AIPrediction | None:
        return await self._session.get(AIPrediction, prediction_id)

    async def list_for_plant(
        self, plant_id: uuid.UUID, *, prediction_type: AIPredictionType | None = None, offset: int, limit: int
    ) -> tuple[list[AIPrediction], int]:
        filters: list[ColumnElement[bool]] = [AIPrediction.plant_id == plant_id]
        if prediction_type is not None:
            filters.append(AIPrediction.prediction_type == prediction_type)
        count_result = await self._session.execute(select(func.count()).select_from(AIPrediction).where(*filters))
        total = count_result.scalar_one()
        rows_result = await self._session.execute(
            select(AIPrediction).where(*filters).order_by(AIPrediction.created_at.desc()).offset(offset).limit(limit)
        )
        return list(rows_result.scalars().all()), total

    async def get_latest_for_plant(
        self, plant_id: uuid.UUID, prediction_type: AIPredictionType
    ) -> AIPrediction | None:
        result = await self._session.execute(
            select(AIPrediction)
            .where(AIPrediction.plant_id == plant_id, AIPrediction.prediction_type == prediction_type)
            .order_by(AIPrediction.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_for_branch(
        self, branch_id: uuid.UUID, *, prediction_type: AIPredictionType | None = None, offset: int, limit: int
    ) -> tuple[list[AIPrediction], int]:
        filters: list[ColumnElement[bool]] = [AIPrediction.branch_id == branch_id]
        if prediction_type is not None:
            filters.append(AIPrediction.prediction_type == prediction_type)
        count_result = await self._session.execute(select(func.count()).select_from(AIPrediction).where(*filters))
        total = count_result.scalar_one()
        rows_result = await self._session.execute(
            select(AIPrediction).where(*filters).order_by(AIPrediction.created_at.desc()).offset(offset).limit(limit)
        )
        return list(rows_result.scalars().all()), total

    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, prediction_type: AIPredictionType | None = None, offset: int, limit: int
    ) -> tuple[list[AIPrediction], int]:
        filters: list[ColumnElement[bool]] = [AIPrediction.nursery_id == nursery_id]
        if prediction_type is not None:
            filters.append(AIPrediction.prediction_type == prediction_type)
        count_result = await self._session.execute(select(func.count()).select_from(AIPrediction).where(*filters))
        total = count_result.scalar_one()
        rows_result = await self._session.execute(
            select(AIPrediction).where(*filters).order_by(AIPrediction.created_at.desc()).offset(offset).limit(limit)
        )
        return list(rows_result.scalars().all()), total

    # --- Added by Phase 6 Module 13 ("AI Administration") ---
    async def admin_stats_for_nursery(
        self, nursery_id: uuid.UUID, *, date_from: datetime | None = None, date_to: datetime | None = None
    ) -> list[dict]:
        filters: list[ColumnElement[bool]] = [AIPrediction.nursery_id == nursery_id]
        if date_from is not None:
            filters.append(AIPrediction.created_at >= date_from)
        if date_to is not None:
            filters.append(AIPrediction.created_at <= date_to)
        result = await self._session.execute(
            select(
                AIPrediction.prediction_type,
                func.count().label("count"),
                func.avg(AIPrediction.latency_ms).label("avg_latency_ms"),
                func.avg(AIPrediction.confidence).label("avg_confidence"),
            )
            .where(*filters)
            .group_by(AIPrediction.prediction_type)
            .order_by(AIPrediction.prediction_type)
        )
        return [
            {
                "prediction_type": row.prediction_type,
                "count": row.count,
                "avg_latency_ms": float(row.avg_latency_ms) if row.avg_latency_ms is not None else None,
                "avg_confidence": float(row.avg_confidence) if row.avg_confidence is not None else None,
            }
            for row in result.all()
        ]


class SqlAlchemyAIRecommendationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, recommendation: AIRecommendation) -> AIRecommendation:
        self._session.add(recommendation)
        await self._session.flush()
        return recommendation

    async def get_by_id(self, recommendation_id: uuid.UUID) -> AIRecommendation | None:
        return await self._session.get(AIRecommendation, recommendation_id)

    async def update_status(
        self, recommendation: AIRecommendation, *, status: AIRecommendationStatus
    ) -> AIRecommendation:
        recommendation.status = status
        await self._session.flush()
        return recommendation

    async def list_for_branch(
        self, branch_id: uuid.UUID, *, status: AIRecommendationStatus | None = None, offset: int, limit: int
    ) -> tuple[list[AIRecommendation], int]:
        filters: list[ColumnElement[bool]] = [AIRecommendation.branch_id == branch_id]
        if status is not None:
            filters.append(AIRecommendation.status == status)
        count_result = await self._session.execute(select(func.count()).select_from(AIRecommendation).where(*filters))
        total = count_result.scalar_one()
        rows_result = await self._session.execute(
            select(AIRecommendation)
            .where(*filters)
            .order_by(AIRecommendation.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows_result.scalars().all()), total

    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, status: AIRecommendationStatus | None = None, offset: int, limit: int
    ) -> tuple[list[AIRecommendation], int]:
        filters: list[ColumnElement[bool]] = [AIRecommendation.nursery_id == nursery_id]
        if status is not None:
            filters.append(AIRecommendation.status == status)
        count_result = await self._session.execute(select(func.count()).select_from(AIRecommendation).where(*filters))
        total = count_result.scalar_one()
        rows_result = await self._session.execute(
            select(AIRecommendation)
            .where(*filters)
            .order_by(AIRecommendation.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows_result.scalars().all()), total


class SqlAlchemyAIAssistantConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, conversation: AIAssistantConversation) -> AIAssistantConversation:
        self._session.add(conversation)
        await self._session.flush()
        return conversation

    async def get_by_id(self, conversation_id: uuid.UUID) -> AIAssistantConversation | None:
        return await self._session.get(AIAssistantConversation, conversation_id)

    async def list_for_user(
        self, user_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[AIAssistantConversation], int]:
        filters: list[ColumnElement[bool]] = [AIAssistantConversation.user_id == user_id]
        count_result = await self._session.execute(
            select(func.count()).select_from(AIAssistantConversation).where(*filters)
        )
        total = count_result.scalar_one()
        rows_result = await self._session.execute(
            select(AIAssistantConversation)
            .where(*filters)
            .order_by(AIAssistantConversation.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows_result.scalars().all()), total


class SqlAlchemyAIAssistantMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, message: AIAssistantMessage) -> AIAssistantMessage:
        self._session.add(message)
        await self._session.flush()
        return message

    async def get_by_id(self, message_id: uuid.UUID) -> AIAssistantMessage | None:
        return await self._session.get(AIAssistantMessage, message_id)

    async def update(self, message: AIAssistantMessage) -> AIAssistantMessage:
        await self._session.flush()
        return message

    async def list_for_conversation(
        self, conversation_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[AIAssistantMessage], int]:
        filters: list[ColumnElement[bool]] = [AIAssistantMessage.conversation_id == conversation_id]
        count_result = await self._session.execute(select(func.count()).select_from(AIAssistantMessage).where(*filters))
        total = count_result.scalar_one()
        rows_result = await self._session.execute(
            select(AIAssistantMessage).where(*filters).order_by(AIAssistantMessage.created_at.asc()).offset(offset).limit(limit)
        )
        return list(rows_result.scalars().all()), total


class SqlAlchemyKnowledgeBaseChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, chunk: KnowledgeBaseChunk) -> KnowledgeBaseChunk:
        self._session.add(chunk)
        await self._session.flush()
        return chunk

    async def get_by_id(self, chunk_id: uuid.UUID) -> KnowledgeBaseChunk | None:
        return await self._session.get(KnowledgeBaseChunk, chunk_id)

    async def search_similar(
        self, embedding: list[float], *, nursery_id: uuid.UUID | None, limit: int
    ) -> list[KnowledgeBaseChunk]:
        tenant_filter = (
            or_(KnowledgeBaseChunk.nursery_id == nursery_id, KnowledgeBaseChunk.source_type == "knowledge_article")
            if nursery_id is not None
            else KnowledgeBaseChunk.source_type == "knowledge_article"
        )
        result = await self._session.execute(
            select(KnowledgeBaseChunk)
            .where(tenant_filter)
            .order_by(KnowledgeBaseChunk.embedding.cosine_distance(embedding))
            .limit(limit)
        )
        return list(result.scalars().all())

    # --- Added by Phase 6 Module 13 ("AI Administration", RAG knowledge-base status) ---
    async def count_by_source_type(self, *, nursery_id: uuid.UUID | None = None) -> list[dict]:
        tenant_filter = (
            or_(KnowledgeBaseChunk.nursery_id == nursery_id, KnowledgeBaseChunk.source_type == "knowledge_article")
            if nursery_id is not None
            else None
        )
        query = select(KnowledgeBaseChunk.source_type, func.count().label("count"))
        if tenant_filter is not None:
            query = query.where(tenant_filter)
        query = query.group_by(KnowledgeBaseChunk.source_type)
        result = await self._session.execute(query)
        return [{"source_type": row.source_type, "count": row.count} for row in result.all()]

    # --- Added by RAG Ingestion Pipeline (Knowledge Article management) ---
    async def delete_by_source_ref(self, source_ref: str) -> int:
        result = await self._session.execute(
            delete(KnowledgeBaseChunk).where(
                KnowledgeBaseChunk.source_type == "knowledge_article",
                KnowledgeBaseChunk.source_ref == source_ref,
            )
        )
        return result.rowcount  # type: ignore[return-value]

    async def get_by_source_ref(self, source_ref: str) -> list[KnowledgeBaseChunk]:
        result = await self._session.execute(
            select(KnowledgeBaseChunk)
            .where(
                KnowledgeBaseChunk.source_type == "knowledge_article",
                KnowledgeBaseChunk.source_ref == source_ref,
            )
            .order_by(KnowledgeBaseChunk.created_at)
        )
        return list(result.scalars().all())

    async def list_distinct_articles(self, *, offset: int = 0, limit: int = 50) -> list[dict]:
        result = await self._session.execute(
            select(
                KnowledgeBaseChunk.source_ref,
                KnowledgeBaseChunk.title,
                func.count().label("chunk_count"),
                func.min(KnowledgeBaseChunk.created_at).label("first_created"),
            )
            .where(KnowledgeBaseChunk.source_type == "knowledge_article")
            .group_by(KnowledgeBaseChunk.source_ref, KnowledgeBaseChunk.title)
            .order_by(func.min(KnowledgeBaseChunk.created_at).desc())
            .offset(offset)
            .limit(limit)
        )
        return [
            {
                "source_ref": row.source_ref,
                "title": row.title,
                "chunk_count": row.chunk_count,
                "created_at": row.first_created,
            }
            for row in result.all()
        ]


# ======================================================================
# Phase 6 Module 11 (Notifications & Communication)
# ======================================================================


class SqlAlchemyNotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, notification: Notification) -> Notification:
        self._session.add(notification)
        await self._session.flush()
        return notification

    async def get_by_id(self, notification_id: uuid.UUID) -> Notification | None:
        return await self._session.get(Notification, notification_id)

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        nursery_id: uuid.UUID,
        *,
        unread_only: bool = False,
        category: NotificationCategory | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Notification], int]:
        filters: list[ColumnElement[bool]] = [
            Notification.recipient_user_id == user_id,
            Notification.nursery_id == nursery_id,
        ]
        if unread_only:
            filters.append(Notification.read_at.is_(None))
        if category is not None:
            filters.append(Notification.category == category)
        count_result = await self._session.execute(select(func.count()).select_from(Notification).where(*filters))
        total = count_result.scalar_one()
        rows_result = await self._session.execute(
            select(Notification).where(*filters).order_by(Notification.created_at.desc()).offset(offset).limit(limit)
        )
        return list(rows_result.scalars().all()), total

    async def count_unread(self, user_id: uuid.UUID, nursery_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(Notification).where(
                Notification.recipient_user_id == user_id,
                Notification.nursery_id == nursery_id,
                Notification.read_at.is_(None),
            )
        )
        return result.scalar_one()

    async def mark_read(self, notification: Notification, *, now: datetime) -> None:
        notification.read_at = now
        await self._session.flush()

    async def mark_all_read(self, user_id: uuid.UUID, nursery_id: uuid.UUID, *, now: datetime) -> int:
        result = await self._session.execute(
            sa_update(Notification)
            .where(
                Notification.recipient_user_id == user_id,
                Notification.nursery_id == nursery_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=now)
        )
        await self._session.flush()
        return result.rowcount or 0

    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        category: NotificationCategory | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[Notification], int]:
        filters: list[ColumnElement[bool]] = [Notification.nursery_id == nursery_id]
        if category is not None:
            filters.append(Notification.category == category)
        if date_from is not None:
            filters.append(Notification.created_at >= date_from)
        if date_to is not None:
            filters.append(Notification.created_at <= date_to)
        count_result = await self._session.execute(select(func.count()).select_from(Notification).where(*filters))
        total = count_result.scalar_one()
        rows_result = await self._session.execute(
            select(Notification).where(*filters).order_by(Notification.created_at.desc()).offset(offset).limit(limit)
        )
        return list(rows_result.scalars().all()), total


class SqlAlchemyNotificationPreferenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(self, user_id: uuid.UUID) -> list[NotificationPreference]:
        result = await self._session.execute(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get(
        self, user_id: uuid.UUID, category: NotificationCategory, channel: NotificationChannel
    ) -> NotificationPreference | None:
        result = await self._session.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.category == category,
                NotificationPreference.channel == channel,
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        user_id: uuid.UUID,
        category: NotificationCategory,
        channel: NotificationChannel,
        enabled: bool,
        quiet_hours_start=None,
        quiet_hours_end=None,
        quiet_hours_timezone: str | None = None,
        frequency=None,
    ) -> NotificationPreference:
        existing = await self.get(user_id, category, channel)
        if existing is not None:
            existing.enabled = enabled
            existing.quiet_hours_start = quiet_hours_start
            existing.quiet_hours_end = quiet_hours_end
            existing.quiet_hours_timezone = quiet_hours_timezone
            if frequency is not None:
                existing.frequency = frequency
            await self._session.flush()
            return existing
        pref = NotificationPreference(
            user_id=user_id,
            category=category,
            channel=channel,
            enabled=enabled,
            quiet_hours_start=quiet_hours_start,
            quiet_hours_end=quiet_hours_end,
            quiet_hours_timezone=quiet_hours_timezone,
            frequency=frequency if frequency is not None else NotificationFrequency.IMMEDIATE,
        )
        self._session.add(pref)
        await self._session.flush()
        return pref


class SqlAlchemyNotificationTemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, template: NotificationTemplate) -> NotificationTemplate:
        self._session.add(template)
        await self._session.flush()
        return template

    async def get_active(
        self,
        *,
        nursery_id: uuid.UUID | None,
        category: NotificationCategory,
        channel: NotificationChannel,
        format: str,
        locale: str,
    ) -> NotificationTemplate | None:
        nursery_filter = (
            NotificationTemplate.nursery_id.is_(None)
            if nursery_id is None
            else NotificationTemplate.nursery_id == nursery_id
        )
        result = await self._session.execute(
            select(NotificationTemplate)
            .where(
                nursery_filter,
                NotificationTemplate.category == category,
                NotificationTemplate.channel == channel,
                NotificationTemplate.format == format,
                NotificationTemplate.locale == locale,
                NotificationTemplate.is_active.is_(True),
            )
            .order_by(NotificationTemplate.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_for_org(self, nursery_id: uuid.UUID | None) -> list[NotificationTemplate]:
        nursery_filter = (
            NotificationTemplate.nursery_id.is_(None)
            if nursery_id is None
            else NotificationTemplate.nursery_id == nursery_id
        )
        result = await self._session.execute(
            select(NotificationTemplate).where(nursery_filter).order_by(NotificationTemplate.category, NotificationTemplate.channel)
        )
        return list(result.scalars().all())


class SqlAlchemyNotificationDeliveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, delivery: NotificationDelivery) -> NotificationDelivery:
        self._session.add(delivery)
        await self._session.flush()
        return delivery

    async def get_by_id(self, delivery_id: uuid.UUID) -> NotificationDelivery | None:
        return await self._session.get(NotificationDelivery, delivery_id)

    async def list_for_notification(self, notification_id: uuid.UUID) -> list[NotificationDelivery]:
        result = await self._session.execute(
            select(NotificationDelivery).where(NotificationDelivery.notification_id == notification_id)
        )
        return list(result.scalars().all())

    async def list_due_for_retry(self, *, now: datetime, limit: int = 100) -> list[NotificationDelivery]:
        result = await self._session.execute(
            select(NotificationDelivery)
            .where(
                NotificationDelivery.status == NotificationDeliveryStatus.FAILED,
                NotificationDelivery.next_retry_at.is_not(None),
                NotificationDelivery.next_retry_at <= now,
                NotificationDelivery.attempt_count < NotificationDelivery.max_attempts,
            )
            .order_by(NotificationDelivery.next_retry_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_dead_letter(self, nursery_id: uuid.UUID, *, limit: int = 100) -> list[NotificationDelivery]:
        result = await self._session.execute(
            select(NotificationDelivery)
            .join(Notification, Notification.id == NotificationDelivery.notification_id)
            .where(
                Notification.nursery_id == nursery_id,
                NotificationDelivery.status == NotificationDeliveryStatus.DEAD_LETTER,
            )
            .order_by(NotificationDelivery.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        delivery: NotificationDelivery,
        *,
        status: NotificationDeliveryStatus,
        attempt_count: int,
        last_attempted_at: datetime,
        next_retry_at: datetime | None,
        delivered_at: datetime | None,
        error_message: str | None,
        provider_message_id: str | None,
    ) -> None:
        delivery.status = status
        delivery.attempt_count = attempt_count
        delivery.last_attempted_at = last_attempted_at
        delivery.next_retry_at = next_retry_at
        delivery.delivered_at = delivered_at
        delivery.error_message = error_message
        delivery.provider_message_id = provider_message_id
        await self._session.flush()


# --------------------------------------------------------------------------
# Phase 6 Module 12 — Reports & Analytics
# --------------------------------------------------------------------------


class SqlAlchemyReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, report: Report) -> Report:
        self._session.add(report)
        await self._session.flush()
        return report

    async def get_by_id(self, report_id: uuid.UUID) -> Report | None:
        return await self._session.get(Report, report_id)

    async def list_for_org(
        self,
        nursery_id: uuid.UUID,
        *,
        report_type: ReportType | None = None,
        branch_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Report], int]:
        filters: list[ColumnElement[bool]] = [Report.nursery_id == nursery_id]
        if report_type is not None:
            filters.append(Report.report_type == report_type)
        if branch_id is not None:
            filters.append(Report.branch_id == branch_id)
        total = (await self._session.execute(select(func.count()).select_from(Report).where(*filters))).scalar_one()
        rows = await self._session.execute(
            select(Report).where(*filters).order_by(Report.created_at.desc()).offset(offset).limit(limit)
        )
        return list(rows.scalars().all()), total

    async def update_status(
        self, report: Report, *, status: ReportStatus, file_url: str | None = None, completed_at: datetime | None = None
    ) -> None:
        report.status = status
        if file_url is not None:
            report.file_url = file_url
        if completed_at is not None:
            report.completed_at = completed_at
        await self._session.flush()

    async def commit(self) -> None:
        await self._session.commit()


class SqlAlchemyScheduledReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, scheduled: ScheduledReport) -> ScheduledReport:
        self._session.add(scheduled)
        await self._session.flush()
        return scheduled

    async def get_by_id(self, scheduled_id: uuid.UUID) -> ScheduledReport | None:
        return await self._session.get(ScheduledReport, scheduled_id)

    async def list_for_org(self, nursery_id: uuid.UUID) -> list[ScheduledReport]:
        result = await self._session.execute(
            select(ScheduledReport).where(ScheduledReport.nursery_id == nursery_id).order_by(ScheduledReport.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_due(self, *, now: datetime, limit: int = 100) -> list[ScheduledReport]:
        result = await self._session.execute(
            select(ScheduledReport)
            .where(ScheduledReport.is_active.is_(True), ScheduledReport.next_run_at <= now)
            .order_by(ScheduledReport.next_run_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_after_run(self, scheduled: ScheduledReport, *, last_run_at: datetime, next_run_at: datetime) -> None:
        scheduled.last_run_at = last_run_at
        scheduled.next_run_at = next_run_at
        await self._session.flush()

    async def update(
        self,
        scheduled: ScheduledReport,
        *,
        name: str | None = None,
        filters: dict | None = None,
        frequency: ReportScheduleFrequency | None = None,
        next_run_at: datetime | None = None,
    ) -> None:
        if name is not None:
            scheduled.name = name
        if filters is not None:
            scheduled.filters = filters
        if frequency is not None:
            scheduled.frequency = frequency
        if next_run_at is not None:
            scheduled.next_run_at = next_run_at
        await self._session.flush()

    async def set_active(self, scheduled: ScheduledReport, *, is_active: bool) -> None:
        scheduled.is_active = is_active
        await self._session.flush()

    async def delete(self, scheduled: ScheduledReport) -> None:
        await self._session.delete(scheduled)
        await self._session.flush()


class SqlAlchemyReportingRepository:
    """
    This module's CQRS read side (see `app/repositories/interfaces.py`'s
    `ReportingRepository` Protocol docstring for the full architectural
    argument). Dashboards backed by migrations 0005/0017's materialized
    views/views read through plain `text()` SELECTs (materialized views
    are not ORM-mapped entities -- there is nothing to map them to, they
    are pre-aggregated rows with no write-side counterpart); everything
    else is a purpose-built `GROUP BY`/`COUNT`/`SUM` ORM query, never a
    raw unfiltered `select(Model)` reused from an operational repository.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Dashboards
    # ------------------------------------------------------------------

    async def executive_dashboard(self, nursery_id: uuid.UUID) -> dict:
        nursery_row = (
            await self._session.execute(
                text("SELECT * FROM mv_nursery_dashboard_summary WHERE nursery_id = :nid"), {"nid": nursery_id}
            )
        ).mappings().first()
        branch_rows = (
            await self._session.execute(
                text(
                    "SELECT b.name AS branch_name, m.* FROM mv_branch_dashboard_summary m "
                    "JOIN branches b ON b.id = m.branch_id WHERE m.nursery_id = :nid "
                    "ORDER BY (m.at_risk_plant_count + m.low_stock_count + m.pending_disease_reports) DESC"
                ),
                {"nid": nursery_id},
            )
        ).mappings().all()
        revenue_trend = (
            await self._session.execute(
                text(
                    "SELECT day, revenue, sale_count FROM mv_org_revenue_rollup "
                    "WHERE nursery_id = :nid AND day >= now() - interval '30 days' ORDER BY day"
                ),
                {"nid": nursery_id},
            )
        ).mappings().all()
        return {
            "revenue_today": sum((r["revenue_today"] for r in branch_rows), 0),
            "revenue_mtd": sum((r["revenue_mtd"] for r in branch_rows), 0),
            "active_plant_count": nursery_row["active_plant_count"] if nursery_row else 0,
            "at_risk_plant_count": sum((r["at_risk_plant_count"] for r in branch_rows), 0),
            "open_disease_reports": sum((r["pending_disease_reports"] for r in branch_rows), 0),
            "branches": [dict(r) for r in branch_rows],
            "revenue_trend": [dict(r) for r in revenue_trend],
            "last_refreshed_at": nursery_row["last_refreshed_at"] if nursery_row else None,
        }

    async def nursery_dashboard(self, nursery_id: uuid.UUID) -> dict:
        row = (
            await self._session.execute(
                text("SELECT * FROM mv_nursery_dashboard_summary WHERE nursery_id = :nid"), {"nid": nursery_id}
            )
        ).mappings().first()
        return dict(row) if row else {}

    async def branch_dashboard(self, nursery_id: uuid.UUID, branch_id: uuid.UUID) -> dict:
        row = (
            await self._session.execute(
                text(
                    "SELECT b.name AS branch_name, m.* FROM mv_branch_dashboard_summary m "
                    "JOIN branches b ON b.id = m.branch_id "
                    "WHERE m.nursery_id = :nid AND m.branch_id = :bid"
                ),
                {"nid": nursery_id, "bid": branch_id},
            )
        ).mappings().first()
        return dict(row) if row else {}

    async def plant_dashboard(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict:
        filters: list[ColumnElement[bool]] = [Plant.nursery_id == nursery_id]
        if branch_id is not None:
            filters.append(Plant.branch_id == branch_id)
        by_status = await self._session.execute(
            select(Plant.status, func.count()).where(*filters).group_by(Plant.status)
        )
        by_species = await self._session.execute(
            select(Species.common_name, func.count())
            .join(Plant, Plant.species_id == Species.id)
            .where(*filters)
            .group_by(Species.common_name)
            .order_by(func.count().desc())
            .limit(10)
        )
        return {
            "by_status": {status.value: count for status, count in by_status.all()},
            "by_species": [{"species": name, "count": count} for name, count in by_species.all()],
        }

    async def inventory_dashboard(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict:
        filters: list[ColumnElement[bool]] = [Inventory.nursery_id == nursery_id]
        if branch_id is not None:
            filters.append(Inventory.branch_id == branch_id)
        totals = (
            await self._session.execute(
                select(
                    func.count(),
                    func.coalesce(func.sum(Inventory.quantity), 0),
                    func.coalesce(func.sum(Inventory.quantity * Inventory.unit_cost), 0),
                ).where(*filters)
            )
        ).one()
        low_stock = await self._session.execute(
            select(Inventory)
            .where(*filters, Inventory.quantity <= Inventory.low_stock_threshold)
            .order_by(Inventory.quantity.asc())
            .limit(20)
        )
        low_stock_rows = list(low_stock.scalars().all())
        return {
            "total_line_items": totals[0],
            "total_units_on_hand": int(totals[1]),
            "total_inventory_value": totals[2],
            "low_stock_count": len(low_stock_rows),
            "low_stock_items": [
                {"id": i.id, "name": i.name, "quantity": i.quantity, "low_stock_threshold": i.low_stock_threshold}
                for i in low_stock_rows
            ],
        }

    async def sales_dashboard(
        self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None,
        date_from: datetime | None = None, date_to: datetime | None = None,
    ) -> dict:
        filters: list[ColumnElement[bool]] = [Sale.nursery_id == nursery_id, Sale.status == SaleStatus.COMPLETED]
        if branch_id is not None:
            filters.append(Sale.branch_id == branch_id)
        if date_from is not None:
            filters.append(Sale.created_at >= date_from)
        if date_to is not None:
            filters.append(Sale.created_at <= date_to)
        result = (
            await self._session.execute(
                select(func.count(), func.coalesce(func.sum(Sale.total_amount), 0), func.coalesce(func.avg(Sale.total_amount), 0))
                .where(*filters)
            )
        ).one()
        return {
            "transaction_count": result[0],
            "total_sales": result[1],
            "average_sale_value": round(float(result[2]), 2) if result[2] else 0.0,
        }

    async def customer_dashboard(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict:
        query = "SELECT * FROM v_customer_lifetime_value WHERE nursery_id = :nid"
        params: dict = {"nid": nursery_id}
        if branch_id is not None:
            query += " AND branch_id = :bid"
            params["bid"] = branch_id
        rows = (await self._session.execute(text(query), params)).mappings().all()
        total_customers = len(rows)
        top_customers = sorted(rows, key=lambda r: r["total_spent"] or 0, reverse=True)[:10]
        repeat_customers = sum(1 for r in rows if (r["total_orders"] or 0) > 1)
        return {
            "total_customers": total_customers,
            "repeat_customer_count": repeat_customers,
            "repeat_customer_rate": round(repeat_customers / total_customers, 4) if total_customers else 0.0,
            "top_customers": [dict(r) for r in top_customers],
        }

    async def ai_dashboard(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict:
        query = (
            "SELECT ap.plant_id, p.common_label, ap.result, ap.confidence, ap.created_at "
            "FROM ai_predictions ap JOIN plants p ON p.id = ap.plant_id "
            "WHERE ap.nursery_id = :nid AND ap.prediction_type = 'survival_prediction' "
            "AND (ap.result ->> 'risk_level') IN ('high', 'critical')"
        )
        params: dict = {"nid": nursery_id}
        if branch_id is not None:
            query += " AND ap.branch_id = :bid"
            params["bid"] = branch_id
        query += " ORDER BY ap.created_at DESC LIMIT 20"
        at_risk = (await self._session.execute(text(query), params)).mappings().all()
        accuracy = (
            await self._session.execute(
                text("SELECT * FROM mv_ai_prediction_accuracy WHERE nursery_id = :nid"), {"nid": nursery_id}
            )
        ).mappings().first()
        return {
            "at_risk_plants": [dict(r) for r in at_risk],
            "prediction_accuracy": dict(accuracy) if accuracy else None,
        }

    async def financial_dashboard(
        self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None,
        date_from: datetime | None = None, date_to: datetime | None = None,
    ) -> dict:
        sale_filters: list[ColumnElement[bool]] = [Sale.nursery_id == nursery_id, Sale.status == SaleStatus.COMPLETED]
        if branch_id is not None:
            sale_filters.append(Sale.branch_id == branch_id)
        if date_from is not None:
            sale_filters.append(Sale.created_at >= date_from)
        if date_to is not None:
            sale_filters.append(Sale.created_at <= date_to)
        revenue = (
            await self._session.execute(select(func.coalesce(func.sum(Sale.total_amount), 0)).where(*sale_filters))
        ).scalar_one()
        # Estimated COGS -- only computable for bulk-inventory sale items
        # (`Inventory.unit_cost`); individually-tracked Plant sales have no
        # acquisition-cost field anywhere in this schema, so they are
        # excluded from this estimate rather than silently assumed to cost
        # nothing. Disclosed in docs/architecture/28-module12-reports-analytics.md.
        cogs_filters: list[ColumnElement[bool]] = [Sale.nursery_id == nursery_id, Sale.status == SaleStatus.COMPLETED]
        if branch_id is not None:
            cogs_filters.append(Sale.branch_id == branch_id)
        if date_from is not None:
            cogs_filters.append(Sale.created_at >= date_from)
        if date_to is not None:
            cogs_filters.append(Sale.created_at <= date_to)
        cogs = (
            await self._session.execute(
                select(func.coalesce(func.sum(SaleItem.quantity * Inventory.unit_cost), 0))
                .select_from(SaleItem)
                .join(Sale, Sale.id == SaleItem.sale_id)
                .join(Inventory, Inventory.id == SaleItem.inventory_id)
                .where(*cogs_filters, SaleItem.inventory_id.isnot(None))
            )
        ).scalar_one()
        outstanding = (
            await self._session.execute(
                select(func.count(), func.coalesce(func.sum(Invoice.total_amount), 0))
                .where(Invoice.nursery_id == nursery_id, Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE]))
            )
        ).one()
        return {
            "revenue": revenue,
            "estimated_cogs": cogs,
            "estimated_gross_profit": revenue - cogs,
            "estimated_gross_margin": round(float((revenue - cogs) / revenue), 4) if revenue else 0.0,
            "outstanding_invoice_count": outstanding[0],
            "outstanding_invoice_total": outstanding[1],
        }

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    async def kpi_summary(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict:
        executive = await self.executive_dashboard(nursery_id)
        inventory = await self.inventory_dashboard(nursery_id, branch_id)
        return {
            "revenue_mtd": executive["revenue_mtd"],
            "active_plant_count": executive["active_plant_count"],
            "at_risk_plant_count": executive["at_risk_plant_count"],
            "low_stock_count": inventory["low_stock_count"],
            "open_disease_reports": executive["open_disease_reports"],
        }

    async def revenue_trend(
        self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None, date_from: datetime, date_to: datetime
    ) -> list[dict]:
        filters: list[ColumnElement[bool]] = [
            Sale.nursery_id == nursery_id, Sale.status == SaleStatus.COMPLETED,
            Sale.created_at >= date_from, Sale.created_at <= date_to,
        ]
        if branch_id is not None:
            filters.append(Sale.branch_id == branch_id)
        day = func.date_trunc("day", Sale.created_at)
        result = await self._session.execute(
            select(day.label("day"), func.sum(Sale.total_amount), func.count())
            .where(*filters).group_by(day).order_by(day)
        )
        return [{"day": d, "revenue": revenue, "sale_count": count} for d, revenue, count in result.all()]

    async def growth_trend(
        self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None, species_id: uuid.UUID | None,
        date_from: datetime, date_to: datetime,
    ) -> list[dict]:
        filters: list[ColumnElement[bool]] = [
            Plant.nursery_id == nursery_id, GrowthTimeline.recorded_at >= date_from, GrowthTimeline.recorded_at <= date_to,
        ]
        if branch_id is not None:
            filters.append(Plant.branch_id == branch_id)
        if species_id is not None:
            filters.append(Plant.species_id == species_id)
        week = func.date_trunc("week", GrowthTimeline.recorded_at)
        result = await self._session.execute(
            select(week.label("week"), func.avg(GrowthTimeline.height_cm), func.count())
            .select_from(GrowthTimeline).join(Plant, Plant.id == GrowthTimeline.plant_id)
            .where(*filters).group_by(week).order_by(week)
        )
        return [
            {"week": w, "average_height_cm": round(float(h), 2) if h else None, "record_count": c}
            for w, h, c in result.all()
        ]

    async def inventory_trend(
        self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None, date_from: datetime, date_to: datetime
    ) -> list[dict]:
        # `StockMovement` carries no `nursery_id`/`branch_id` of its own
        # (append-only ledger keyed only to `inventory_id` -- see that
        # model's own docstring); tenant scoping joins through `Inventory`,
        # the same one-hop-further join shape migration 0003's
        # `TWO_HOP_TENANT_TABLES` already establishes for tables one join
        # away from their tenant-scoped parent.
        filters: list[ColumnElement[bool]] = [
            Inventory.nursery_id == nursery_id, StockMovement.created_at >= date_from, StockMovement.created_at <= date_to,
        ]
        if branch_id is not None:
            filters.append(Inventory.branch_id == branch_id)
        day = func.date_trunc("day", StockMovement.created_at)
        result = await self._session.execute(
            select(day.label("day"), StockMovement.movement_type, func.sum(StockMovement.quantity_delta))
            .select_from(StockMovement).join(Inventory, Inventory.id == StockMovement.inventory_id)
            .where(*filters).group_by(day, StockMovement.movement_type).order_by(day)
        )
        return [{"day": d, "movement_type": mt.value, "net_quantity_delta": q} for d, mt, q in result.all()]

    async def plant_health_trend(
        self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None, date_from: datetime, date_to: datetime
    ) -> list[dict]:
        filters: list[ColumnElement[bool]] = [
            Plant.nursery_id == nursery_id, HealthHistory.recorded_at >= date_from, HealthHistory.recorded_at <= date_to,
        ]
        if branch_id is not None:
            filters.append(Plant.branch_id == branch_id)
        week = func.date_trunc("week", HealthHistory.recorded_at)
        result = await self._session.execute(
            select(week.label("week"), HealthHistory.status_label, func.count())
            .select_from(HealthHistory).join(Plant, Plant.id == HealthHistory.plant_id)
            .where(*filters).group_by(week, HealthHistory.status_label).order_by(week)
        )
        return [{"week": w, "health_status": s, "count": c} for w, s, c in result.all()]

    async def sales_forecast(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> list[dict]:
        query = (
            "SELECT id, branch_id, result, confidence, created_at FROM ai_predictions "
            "WHERE nursery_id = :nid AND prediction_type = 'revenue_forecast'"
        )
        params: dict = {"nid": nursery_id}
        if branch_id is not None:
            query += " AND branch_id = :bid"
            params["bid"] = branch_id
        query += " ORDER BY created_at DESC LIMIT 1"
        row = (await self._session.execute(text(query), params)).mappings().first()
        return [dict(row)] if row else []

    async def disease_trend(
        self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None, date_from: datetime, date_to: datetime
    ) -> list[dict]:
        filters: list[ColumnElement[bool]] = [
            Plant.nursery_id == nursery_id, DiseaseReport.created_at >= date_from, DiseaseReport.created_at <= date_to,
        ]
        if branch_id is not None:
            filters.append(Plant.branch_id == branch_id)
        week = func.date_trunc("week", DiseaseReport.created_at)
        result = await self._session.execute(
            select(week.label("week"), DiseaseReport.severity, func.count())
            .select_from(DiseaseReport).join(Plant, Plant.id == DiseaseReport.plant_id)
            .where(*filters).group_by(week, DiseaseReport.severity).order_by(week)
        )
        return [{"week": w, "severity": sev.value, "count": c} for w, sev, c in result.all()]

    async def customer_analytics(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict:
        return await self.customer_dashboard(nursery_id, branch_id)

    async def employee_productivity(
        self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None, date_from: datetime, date_to: datetime
    ) -> list[dict]:
        # Sales attributed via `Sale.sold_by_user_id` -- the one entity
        # with a direct actor column. Broader per-employee activity
        # (plants registered, disease reports handled, ...) is available
        # through `audit_logs.actor_user_id` but is intentionally left to
        # the Employee Report's own row-level export rather than folded
        # into this summary, to keep this analytics endpoint's query
        # single-table and fast.
        filters: list[ColumnElement[bool]] = [
            Sale.nursery_id == nursery_id, Sale.status == SaleStatus.COMPLETED,
            Sale.created_at >= date_from, Sale.created_at <= date_to,
        ]
        if branch_id is not None:
            filters.append(Sale.branch_id == branch_id)
        result = await self._session.execute(
            select(Sale.sold_by_user_id, func.count(), func.coalesce(func.sum(Sale.total_amount), 0))
            .where(*filters).group_by(Sale.sold_by_user_id).order_by(func.sum(Sale.total_amount).desc())
        )
        return [
            {"user_id": uid, "sale_count": count, "total_sales": total}
            for uid, count, total in result.all()
        ]

    async def branch_performance(self, nursery_id: uuid.UUID) -> list[dict]:
        rows = (
            await self._session.execute(
                text(
                    "SELECT b.id AS branch_id, b.name AS branch_name, m.* "
                    "FROM mv_branch_dashboard_summary m JOIN branches b ON b.id = m.branch_id "
                    "WHERE m.nursery_id = :nid ORDER BY m.revenue_mtd DESC"
                ),
                {"nid": nursery_id},
            )
        ).mappings().all()
        return [dict(r) for r in rows]


# ======================================================================
# Phase 6 Module 13 (Administration & System Management)
# ======================================================================


class SqlAlchemyFeatureFlagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def resolve(
        self, key: str, *, nursery_id: uuid.UUID | None, branch_id: uuid.UUID | None
    ) -> FeatureFlag | None:
        # Branch tier, then org tier, then platform-default tier -- one
        # query per tier (three at most), stopping at the first hit. A
        # single query with a computed "specificity" ORDER BY would also
        # work, but three simple, obviously-correct queries are easier to
        # verify against the resolution order this method's Protocol
        # docstring promises than one query whose ordering logic itself
        # would need its own test coverage.
        if branch_id is not None:
            result = await self._session.execute(
                select(FeatureFlag).where(FeatureFlag.key == key, FeatureFlag.branch_id == branch_id)
            )
            row = result.scalar_one_or_none()
            if row is not None:
                return row
        if nursery_id is not None:
            result = await self._session.execute(
                select(FeatureFlag).where(
                    FeatureFlag.key == key, FeatureFlag.nursery_id == nursery_id, FeatureFlag.branch_id.is_(None)
                )
            )
            row = result.scalar_one_or_none()
            if row is not None:
                return row
        result = await self._session.execute(
            select(FeatureFlag).where(
                FeatureFlag.key == key, FeatureFlag.nursery_id.is_(None), FeatureFlag.branch_id.is_(None)
            )
        )
        return result.scalar_one_or_none()

    async def list_all(self, *, nursery_id: uuid.UUID | None = None) -> list[FeatureFlag]:
        condition: ColumnElement[bool] = FeatureFlag.nursery_id.is_(None)
        if nursery_id is not None:
            condition = or_(condition, FeatureFlag.nursery_id == nursery_id)
        result = await self._session.execute(select(FeatureFlag).where(condition).order_by(FeatureFlag.key))
        return list(result.scalars().all())

    async def upsert(
        self,
        *,
        key: str,
        nursery_id: uuid.UUID | None,
        branch_id: uuid.UUID | None,
        is_enabled: bool,
        description: str | None,
        updated_by_user_id: uuid.UUID | None,
    ) -> FeatureFlag:
        result = await self._session.execute(
            select(FeatureFlag).where(
                FeatureFlag.key == key,
                FeatureFlag.nursery_id.is_(nursery_id) if nursery_id is None else FeatureFlag.nursery_id == nursery_id,
                FeatureFlag.branch_id.is_(branch_id) if branch_id is None else FeatureFlag.branch_id == branch_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.is_enabled = is_enabled
            existing.description = description
            existing.updated_by_user_id = updated_by_user_id
            await self._session.flush()
            return existing
        flag = FeatureFlag(
            key=key,
            nursery_id=nursery_id,
            branch_id=branch_id,
            is_enabled=is_enabled,
            description=description,
            updated_by_user_id=updated_by_user_id,
        )
        self._session.add(flag)
        await self._session.flush()
        return flag


class SqlAlchemySystemConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, key: str) -> SystemConfig | None:
        result = await self._session.execute(select(SystemConfig).where(SystemConfig.key == key))
        return result.scalar_one_or_none()

    async def list_all(self, *, category: str | None = None) -> list[SystemConfig]:
        query = select(SystemConfig)
        if category is not None:
            query = query.where(SystemConfig.category == category)
        result = await self._session.execute(query.order_by(SystemConfig.category, SystemConfig.key))
        return list(result.scalars().all())

    async def upsert(
        self,
        *,
        key: str,
        value: dict,
        value_type: str,
        category: str,
        description: str | None,
        updated_by_user_id: uuid.UUID | None,
    ) -> SystemConfig:
        existing = await self.get(key)
        if existing is not None:
            existing.value = value
            existing.value_type = value_type
            existing.category = category
            existing.description = description
            existing.updated_by_user_id = updated_by_user_id
            await self._session.flush()
            return existing
        config = SystemConfig(
            key=key,
            value=value,
            value_type=value_type,
            category=category,
            description=description,
            updated_by_user_id=updated_by_user_id,
        )
        self._session.add(config)
        await self._session.flush()
        return config


class SqlAlchemyAIInferenceFailureRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, failure: AIInferenceFailure) -> AIInferenceFailure:
        self._session.add(failure)
        await self._session.flush()
        return failure

    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int, capability: str | None = None
    ) -> tuple[list[AIInferenceFailure], int]:
        filters: list[ColumnElement[bool]] = [AIInferenceFailure.nursery_id == nursery_id]
        if capability is not None:
            filters.append(AIInferenceFailure.capability == capability)
        total = (
            await self._session.execute(select(func.count()).select_from(AIInferenceFailure).where(*filters))
        ).scalar_one()
        rows = await self._session.execute(
            select(AIInferenceFailure)
            .where(*filters)
            .order_by(AIInferenceFailure.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows.scalars().all()), total
