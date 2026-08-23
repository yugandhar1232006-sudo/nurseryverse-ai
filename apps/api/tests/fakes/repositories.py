"""
In-memory fakes satisfying app/repositories/interfaces.py's Protocols.
Not mocks of AuthService's own logic — these are real, if simplified,
alternate implementations of the persistence boundary, which is what lets
tests exercise AuthService's actual lockout/rotation/replay-detection code
paths without a live database. Production always runs against
app/repositories/sqlalchemy_repositories.py; these exist only under tests/.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.db.enums import (
    AIPredictionType,
    AIRecommendationStatus,
    BranchStatus,
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
    SaleStatus,
    SalesOrderStatus,
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
from app.models.identity import Invite, RoleAssignment, User
from app.models.inventory import Inventory, InventoryLocation, StockMovement, StockReservation
from app.models.notifications import Notification, NotificationDelivery, NotificationPreference, NotificationTemplate
from app.models.organization import Branch, Employee, Nursery
from app.models.plants import Plant, PlantImage, PlantTransfer
from app.models.platform import FeatureFlag, OrgSettings, SystemConfig
from app.models.purchasing import Supplier
from app.models.reports import Passport, QRScanEvent, Report, ScheduledReport


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[uuid.UUID, User] = {}

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.users.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        for user in self.users.values():
            if user.email == email.strip().lower():
                return user
        return None

    async def add(self, user: User) -> User:
        if user.id is None:
            user.id = uuid.uuid4()
        self.users[user.id] = user
        return user

    async def commit(self) -> None:
        # In-memory fake: mutations are immediately visible, nothing to persist.
        pass

    # --- Added by Phase 6 Module 13 ("User Administration") ---
    async def list_for_ids(self, user_ids: list[uuid.UUID]) -> list[User]:
        return [self.users[uid] for uid in user_ids if uid in self.users]

    async def set_active(self, user: User, *, is_active: bool) -> User:
        user.is_active = is_active
        return user

    async def set_locked_until(self, user: User, *, locked_until: datetime | None) -> User:
        user.locked_until = locked_until
        return user

    async def reset_failed_login_attempts(self, user: User) -> User:
        user.failed_login_attempts = 0
        return user


class FakeRefreshTokenRepository:
    def __init__(self) -> None:
        self.tokens: dict[uuid.UUID, RefreshToken] = {}

    async def add(self, token: RefreshToken) -> RefreshToken:
        if token.id is None:
            token.id = uuid.uuid4()
        # Regression (Phase 6 Module 13): `issued_at` is a DB
        # `server_default="now()"` -- `AuthService._issue_token_pair`
        # never sets it explicitly (the same "let the database populate
        # this" pattern `id`/`created_at` use elsewhere), so it only ever
        # populates on a real flush. No route serialized a `RefreshToken`
        # back out through a Pydantic model requiring `issued_at` until
        # Module 13's `SessionResponse` (`GET /admin/users/{id}/sessions`)
        # did -- every session obtained through a real `harness.service.login(...)`
        # call in a test would otherwise 500 on that route. Backfilling
        # here mirrors the exact same precedent `FakeAuditLogRepository.log`/
        # `FakeSecurityEventRepository.log` already established for their
        # own `id`/`created_at` server defaults.
        if token.issued_at is None:
            token.issued_at = datetime.now(timezone.utc)
        self.tokens[token.id] = token
        return token

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        for token in self.tokens.values():
            if token.token_hash == token_hash:
                return token
        return None

    async def list_active_for_user(self, user_id: uuid.UUID) -> list[RefreshToken]:
        now = datetime.now(timezone.utc)
        return [
            t
            for t in self.tokens.values()
            if t.user_id == user_id and t.revoked_at is None and _aware(t.expires_at) > now
        ]

    async def revoke(self, token: RefreshToken, *, now: datetime) -> None:
        token.revoked_at = now

    async def revoke_family(self, family_id: uuid.UUID, *, now: datetime) -> None:
        for token in self.tokens.values():
            if token.family_id == family_id and token.revoked_at is None:
                token.revoked_at = now

    async def revoke_all_for_user(self, user_id: uuid.UUID, *, now: datetime) -> None:
        for token in self.tokens.values():
            if token.user_id == user_id and token.revoked_at is None:
                token.revoked_at = now


class FakeEmailVerificationTokenRepository:
    def __init__(self) -> None:
        self.tokens: dict[uuid.UUID, EmailVerificationToken] = {}

    async def add(self, token: EmailVerificationToken) -> EmailVerificationToken:
        if token.id is None:
            token.id = uuid.uuid4()
        self.tokens[token.id] = token
        return token

    async def get_by_hash(self, token_hash: str) -> EmailVerificationToken | None:
        for token in self.tokens.values():
            if token.token_hash == token_hash:
                return token
        return None

    async def mark_used(self, token: EmailVerificationToken, *, now: datetime) -> None:
        token.used_at = now


class FakePasswordResetTokenRepository:
    def __init__(self) -> None:
        self.tokens: dict[uuid.UUID, PasswordResetToken] = {}

    async def add(self, token: PasswordResetToken) -> PasswordResetToken:
        if token.id is None:
            token.id = uuid.uuid4()
        self.tokens[token.id] = token
        return token

    async def get_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        for token in self.tokens.values():
            if token.token_hash == token_hash:
                return token
        return None

    async def mark_used(self, token: PasswordResetToken, *, now: datetime) -> None:
        token.used_at = now


class FakeSecurityEventRepository:
    """
    `employee_repo` (optional, Phase 6 Module 12 addition) is the same
    constructor-injection precedent as `FakeDiseaseReportRepository
    (plant_repo)` -- `list_for_nursery` resolves each event's `user_id`
    back to "is this user an Employee of this nursery" (`security_events`
    carries no `nursery_id` of its own; see that Protocol method's own
    docstring for why), by scanning the shared `FakeEmployeeRepository`
    the harness already populates.
    """

    def __init__(self, employee_repo: "FakeEmployeeRepository | None" = None) -> None:
        self.events: list[SecurityEvent] = []
        self._employee_repo = employee_repo

    async def log(self, event: SecurityEvent) -> None:
        # Regression (Phase 6 Module 13): `id`/`created_at` are DB
        # `server_default`s (UUIDPKMixin/`server_default="now()"`), which
        # only populate on a real flush -- every pre-Module-13 caller
        # (`AuthService._log_event`) constructs a `SecurityEvent` without
        # setting either explicitly, and no route ever serialized a
        # `SecurityEvent` back out through a Pydantic model that required
        # `id` until Module 13's `SecurityEventResponse`
        # (`GET /admin/security-events`) did -- so this gap in the fake
        # (unlike `FakeAuditLogRepository.log`, which already backfills
        # both) went unnoticed until then. Backfilling here now matches
        # that established precedent instead of only papering over it at
        # each individual call site.
        if event.id is None:
            event.id = uuid.uuid4()
        if event.created_at is None:
            event.created_at = datetime.now(timezone.utc)
        self.events.append(event)

    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[SecurityEvent], int]:
        employee_user_ids = {
            e.user_id for e in self._employee_repo.employees.values() if e.nursery_id == nursery_id
        }
        matching = [e for e in self.events if e.user_id in employee_user_ids]
        if date_from is not None:
            matching = [e for e in matching if _aware(e.created_at) >= _aware(date_from)]
        if date_to is not None:
            matching = [e for e in matching if _aware(e.created_at) <= _aware(date_to)]
        matching.sort(key=lambda e: e.created_at, reverse=True)
        total = len(matching)
        return matching[offset : offset + limit], total

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
        employee_user_ids = {
            e.user_id for e in self._employee_repo.employees.values() if e.nursery_id == nursery_id
        }
        matching = [e for e in self.events if e.user_id in employee_user_ids]
        if date_from is not None:
            matching = [e for e in matching if _aware(e.created_at) >= _aware(date_from)]
        if date_to is not None:
            matching = [e for e in matching if _aware(e.created_at) <= _aware(date_to)]
        if event_type is not None:
            matching = [e for e in matching if e.event_type == event_type]
        if user_id is not None:
            matching = [e for e in matching if e.user_id == user_id]
        matching.sort(key=lambda e: e.created_at, reverse=True)
        total = len(matching)
        return matching[offset : offset + limit], total

    async def list_all(
        self,
        *,
        offset: int,
        limit: int,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        event_type: SecurityEventType | None = None,
    ) -> tuple[list[SecurityEvent], int]:
        matching = list(self.events)
        if date_from is not None:
            matching = [e for e in matching if _aware(e.created_at) >= _aware(date_from)]
        if date_to is not None:
            matching = [e for e in matching if _aware(e.created_at) <= _aware(date_to)]
        if event_type is not None:
            matching = [e for e in matching if e.event_type == event_type]
        matching.sort(key=lambda e: e.created_at, reverse=True)
        total = len(matching)
        return matching[offset : offset + limit], total


class FakePermissionRepository:
    """
    Seeded directly by tests with whatever role-assignment/role/permission
    graph a given test needs, rather than reconstructing the real RBAC
    seed data (migration 0002) in memory.
    """

    def __init__(self) -> None:
        self.role_assignments: dict[uuid.UUID, object] = {}  # user_id -> RoleAssignment
        self.roles: dict[uuid.UUID, object] = {}  # role_id -> Role
        self.branch_scopes: dict[uuid.UUID, list[uuid.UUID]] = {}  # role_assignment_id -> [branch_id]

    async def get_role_assignment_for_user(self, user_id: uuid.UUID):
        return self.role_assignments.get(user_id)

    async def list_role_assignments_for_user(self, user_id: uuid.UUID) -> list:
        assignment = self.role_assignments.get(user_id)
        return [assignment] if assignment is not None else []

    async def get_role_with_permissions(self, role_id: uuid.UUID):
        return self.roles.get(role_id)

    async def get_branch_scope_ids(self, role_assignment_id: uuid.UUID) -> list[uuid.UUID]:
        return self.branch_scopes.get(role_assignment_id, [])

    # --- Added by Phase 6 Module 11 (Notifications) ---
    async def list_users_with_permission(
        self, nursery_id: uuid.UUID, permission_code: str, *, branch_id: uuid.UUID | None = None
    ) -> list[uuid.UUID]:
        matches: list[uuid.UUID] = []
        for user_id, assignment in self.role_assignments.items():
            if assignment.nursery_id != nursery_id:
                continue
            role = self.roles.get(assignment.role_id)
            if role is None:
                continue
            if permission_code not in {p.code for p in role.permissions}:
                continue
            if branch_id is not None:
                scoped_branches = self.branch_scopes.get(assignment.id, [])
                if scoped_branches and branch_id not in scoped_branches:
                    continue
            matches.append(user_id)
        return matches

    # --- Added by Phase 6 Module 4 ---
    async def get_system_role_by_code(self, code: str):
        for role in self.roles.values():
            if getattr(role, "nursery_id", "unset") is None and role.code == code:
                return role
        return None

    async def create_assignment(
        self, *, user_id: uuid.UUID, nursery_id: uuid.UUID, role_id: uuid.UUID
    ) -> RoleAssignment:
        assignment = RoleAssignment(id=uuid.uuid4(), user_id=user_id, nursery_id=nursery_id, role_id=role_id)
        self.role_assignments[user_id] = assignment
        return assignment

    async def add_assignment_branch_scope(self, role_assignment_id: uuid.UUID, branch_id: uuid.UUID) -> None:
        self.branch_scopes.setdefault(role_assignment_id, []).append(branch_id)

    async def replace_assignment_branch_scopes(
        self, role_assignment_id: uuid.UUID, branch_ids: list[uuid.UUID]
    ) -> None:
        self.branch_scopes[role_assignment_id] = list(branch_ids)

    async def delete_assignment(self, role_assignment_id: uuid.UUID) -> None:
        for user_id, assignment in list(self.role_assignments.items()):
            if assignment.id == role_assignment_id:
                del self.role_assignments[user_id]
        self.branch_scopes.pop(role_assignment_id, None)

    # --- Added by Phase 6 Module 13 ("Role & Permission Administration") ---
    async def list_roles(self, *, nursery_id: uuid.UUID | None = None):
        return [
            r for r in self.roles.values()
            if r.nursery_id is None or (nursery_id is not None and r.nursery_id == nursery_id)
        ]

    async def list_permissions(self):
        """
        No standalone catalog list is seeded in the fake (unlike production,
        where `permissions` is a real, always-populated table) -- derives
        the catalog from every permission ever granted to a role in this
        test's harness, deduped by code. Good enough for admin-catalog-
        viewing tests, which only need "the permissions this test set up
        exist", not the full 60+ row production seed.
        """
        seen: dict[str, object] = {}
        for role in self.roles.values():
            for permission in getattr(role, "permissions", []):
                seen.setdefault(permission.code, permission)
        return list(seen.values())

    async def list_role_permission_codes(self, role_id: uuid.UUID) -> list[tuple[str, str]]:
        """Scope is not modeled per-permission in this fake (see `FakePermissionRepository`'s own docstring) -- every pair is reported with a fixed `"F"` scope, sufficient for admin-catalog-viewing assertions that only check *which* permissions a role has, not scope."""
        role = self.roles.get(role_id)
        if role is None:
            return []
        return [(p.code, "F") for p in getattr(role, "permissions", [])]

    async def set_assignment_role(self, assignment, *, role_id: uuid.UUID):
        assignment.role_id = role_id
        return assignment


class FakeInviteRepository:
    def __init__(self) -> None:
        self.invites: dict[str, Invite] = {}  # token -> Invite
        self.branch_scopes: dict[uuid.UUID, list[uuid.UUID]] = {}  # invite_id -> [branch_id]

    async def get_by_token(self, token: str) -> Invite | None:
        return self.invites.get(token)

    async def mark_accepted(self, invite: Invite, *, now: datetime) -> None:
        invite.accepted_at = now

    # --- Added by Phase 6 Module 4 ---
    async def add(self, invite: Invite) -> Invite:
        if invite.id is None:
            invite.id = uuid.uuid4()
        _backfill_timestamps(invite)
        self.invites[invite.token] = invite
        return invite

    async def get_by_id(self, invite_id: uuid.UUID) -> Invite | None:
        for invite in self.invites.values():
            if invite.id == invite_id:
                return invite
        return None

    async def get_pending_by_email_and_nursery(self, nursery_id: uuid.UUID, email: str) -> Invite | None:
        now = datetime.now(timezone.utc)
        normalized = email.strip().lower()
        for invite in self.invites.values():
            if (
                invite.nursery_id == nursery_id
                and invite.email == normalized
                and invite.accepted_at is None
                and _aware(invite.expires_at) > now
            ):
                return invite
        return None

    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[Invite], int]:
        matching = [i for i in self.invites.values() if i.nursery_id == nursery_id]
        # Production rows populate created_at from the DB's server_default
        # on flush; a fake-constructed Invite that never went through a
        # real flush may still have created_at=None, so the sort key
        # falls back to the epoch rather than raising a None-comparison
        # TypeError.
        matching.sort(key=lambda i: i.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return matching[offset : offset + limit], len(matching)

    async def get_branch_scope_ids(self, invite_id: uuid.UUID) -> list[uuid.UUID]:
        return self.branch_scopes.get(invite_id, [])

    async def add_branch_scope(self, invite_id: uuid.UUID, branch_id: uuid.UUID) -> None:
        self.branch_scopes.setdefault(invite_id, []).append(branch_id)


class FakeEmailSender:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, *, to: str, subject: str, body_text: str) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body_text})


class FakeAuthorizationDenialRepository:
    def __init__(self) -> None:
        self.denials: list = []

    async def log(self, denial) -> None:
        self.denials.append(denial)

    # --- Added by Phase 6 Module 13 ("Audit & Security Administration") ---
    async def list_for_org(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list, int]:
        matching = [d for d in self.denials if d.nursery_id == nursery_id]
        if date_from is not None:
            matching = [d for d in matching if _aware(d.created_at) >= _aware(date_from)]
        if date_to is not None:
            matching = [d for d in matching if _aware(d.created_at) <= _aware(date_to)]
        matching.sort(key=lambda d: d.created_at, reverse=True)
        return matching[offset : offset + limit], len(matching)


class FakeAuditLogRepository:
    """Seeded directly by tests with whatever AuditLog rows a scenario needs."""

    def __init__(self) -> None:
        self.rows: list = []  # list of AuditLog instances

    async def list_for_org(self, nursery_id: uuid.UUID, *, offset: int, limit: int):
        matching = [r for r in self.rows if r.nursery_id == nursery_id]
        matching.sort(key=lambda r: r.created_at, reverse=True)
        return matching[offset : offset + limit], len(matching)

    async def log(self, entry):
        if entry.id is None:
            entry.id = uuid.uuid4()
        if entry.created_at is None:
            entry.created_at = datetime.now(timezone.utc)
        # Regression (Phase 6 Module 13): `result` (migration 0018) is a
        # DB `server_default="success"` column -- every `_log_audit`
        # helper written before that migration (Modules 4-12's
        # Organization/Branch/Employee/Inventory/... services) constructs
        # `AuditLog` without setting it at all, since the column didn't
        # exist yet when those call sites were written, and relies on
        # Postgres to supply "success" at INSERT time in production. No
        # route ever serialized `AuditLog.result` back out through a
        # required-string Pydantic field until Module 13's
        # `AdminAuditLogEntryResponse` (`GET /admin/audit-logs`) did --
        # searching audit history that includes rows written by any
        # earlier module's own helper would otherwise 500. Backfilling
        # here mirrors the same `id`/`created_at` precedent immediately
        # above.
        if entry.result is None:
            entry.result = "success"
        self.rows.append(entry)
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
    ):
        matching = [r for r in self.rows if r.nursery_id == nursery_id]
        if date_from is not None:
            matching = [r for r in matching if _aware(r.created_at) >= _aware(date_from)]
        if date_to is not None:
            matching = [r for r in matching if _aware(r.created_at) <= _aware(date_to)]
        if actor_user_id is not None:
            matching = [r for r in matching if r.actor_user_id == actor_user_id]
        if action is not None:
            matching = [r for r in matching if r.action == action]
        if entity_type is not None:
            matching = [r for r in matching if r.entity_type == entity_type]
        if result is not None:
            matching = [r for r in matching if getattr(r, "result", "success") == result]
        if branch_id is not None:
            matching = [r for r in matching if getattr(r, "branch_id", None) == branch_id]
        matching.sort(key=lambda r: r.created_at, reverse=True)
        return matching[offset : offset + limit], len(matching)


class FakeDomainEventRepository:
    """
    Added by Phase 6 Module 4. Records every published event for
    assertion in tests. `_next_sequence` mirrors the real
    `domain_events_sequence_seq` BIGSERIAL (migration 0011) -- a simple
    monotonically-increasing counter, assigned at `add()` time, giving the
    fake the same total-order guarantee production gets from Postgres.
    """

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []
        self._next_sequence = 1

    async def add(self, event: DomainEvent) -> DomainEvent:
        if event.id is None:
            event.id = uuid.uuid4()
        if event.sequence is None:
            event.sequence = self._next_sequence
            self._next_sequence += 1
        self.events.append(event)
        return event

    async def get_by_id(self, event_id: uuid.UUID) -> DomainEvent | None:
        for event in self.events:
            if event.id == event_id:
                return event
        return None

    async def list_for_aggregate(
        self, aggregate_id: uuid.UUID, *, after_sequence: int | None = None
    ) -> list[DomainEvent]:
        matching = [e for e in self.events if e.aggregate_id == aggregate_id]
        if after_sequence is not None:
            matching = [e for e in matching if e.sequence > after_sequence]
        matching.sort(key=lambda e: e.sequence)
        return matching


class FakeNurseryRepository:
    def __init__(self) -> None:
        self.nurseries: dict[uuid.UUID, Nursery] = {}
        self.settings: dict[uuid.UUID, OrgSettings] = {}  # nursery_id -> OrgSettings

    async def get_by_id(self, nursery_id: uuid.UUID) -> Nursery | None:
        return self.nurseries.get(nursery_id)

    async def add(self, nursery: Nursery) -> Nursery:
        if nursery.id is None:
            nursery.id = uuid.uuid4()
        _backfill_timestamps(nursery)
        self.nurseries[nursery.id] = nursery
        return nursery

    async def get_settings(self, nursery_id: uuid.UUID) -> OrgSettings | None:
        return self.settings.get(nursery_id)

    async def create_settings(self, settings: OrgSettings) -> OrgSettings:
        if settings.id is None:
            settings.id = uuid.uuid4()
        # Mirrors the real SqlAlchemyNurseryRepository.create_settings's
        # `session.flush()`: against a real DB, OrgSettings.default_currency/
        # default_timezone/sms_enabled's Python-side `default=`
        # (app/models/platform.py) is applied by SQLAlchemy's unit-of-work
        # at flush time, populating the attribute on the object without a
        # round-trip. This fake has no flush to do that for us, so it
        # applies the same defaults explicitly -- otherwise a fake-backed
        # test would see `None` where production always sees "INR"/"UTC"/
        # `False`, same class of gap as `_backfill_timestamps` above.
        if settings.default_currency is None:
            settings.default_currency = "INR"
        if settings.default_timezone is None:
            settings.default_timezone = "UTC"
        if settings.sms_enabled is None:
            settings.sms_enabled = False
        self.settings[settings.nursery_id] = settings
        return settings


class FakeBranchRepository:
    def __init__(self) -> None:
        self.branches: dict[uuid.UUID, Branch] = {}

    async def get_by_id(self, branch_id: uuid.UUID) -> Branch | None:
        return self.branches.get(branch_id)

    async def get_by_name(self, nursery_id: uuid.UUID, name: str) -> Branch | None:
        for branch in self.branches.values():
            if branch.nursery_id == nursery_id and branch.name == name:
                return branch
        return None

    async def add(self, branch: Branch) -> Branch:
        if branch.id is None:
            branch.id = uuid.uuid4()
        _backfill_timestamps(branch)
        self.branches[branch.id] = branch
        return branch

    async def list_for_nursery(self, nursery_id: uuid.UUID, *, include_inactive: bool = False) -> list[Branch]:
        matching = [b for b in self.branches.values() if b.nursery_id == nursery_id]
        if not include_inactive:
            matching = [b for b in matching if b.status == BranchStatus.ACTIVE]
        matching.sort(key=lambda b: b.name)
        return matching


class FakeEmployeeRepository:
    def __init__(self) -> None:
        self.employees: dict[uuid.UUID, Employee] = {}

    async def get_by_id(self, employee_id: uuid.UUID) -> Employee | None:
        return self.employees.get(employee_id)

    async def get_by_user_and_nursery(self, user_id: uuid.UUID, nursery_id: uuid.UUID) -> Employee | None:
        for employee in self.employees.values():
            if employee.user_id == user_id and employee.nursery_id == nursery_id:
                return employee
        return None

    async def add(self, employee: Employee) -> Employee:
        if employee.id is None:
            employee.id = uuid.uuid4()
        _backfill_timestamps(employee)
        self.employees[employee.id] = employee
        return employee

    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int, status: EmployeeStatus | None = None
    ) -> tuple[list[Employee], int]:
        matching = [e for e in self.employees.values() if e.nursery_id == nursery_id]
        if status is not None:
            matching = [e for e in matching if e.status == status]
        matching.sort(key=lambda e: e.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return matching[offset : offset + limit], len(matching)


class FakePlantCategoryRepository:
    def __init__(self) -> None:
        self.categories: dict[uuid.UUID, PlantCategory] = {}

    async def list_all(self) -> list[PlantCategory]:
        return sorted(self.categories.values(), key=lambda c: c.name)

    async def get_by_id(self, category_id: uuid.UUID) -> PlantCategory | None:
        return self.categories.get(category_id)


class FakeUnitRepository:
    def __init__(self) -> None:
        self.units: dict[uuid.UUID, Unit] = {}

    async def list_all(self) -> list[Unit]:
        return sorted(self.units.values(), key=lambda u: u.name)

    async def get_by_id(self, unit_id: uuid.UUID) -> Unit | None:
        return self.units.get(unit_id)


class FakeSpeciesRepository:
    """
    Module 5. `plant_species_ids` is a test-seedable list simulating "a
    Plant row references this species" -- standing in for Module 6's
    (not-yet-built) Plant repository, since `count_plants_referencing`
    only needs a count, not a real Plant aggregate, to exercise
    `SpeciesService.delete_species`'s referential-integrity check.
    """

    def __init__(self) -> None:
        self.species: dict[uuid.UUID, Species] = {}
        self.plant_species_ids: list[uuid.UUID] = []

    async def get_by_id(self, species_id: uuid.UUID) -> Species | None:
        return self.species.get(species_id)

    async def get_by_botanical_name(self, nursery_id: uuid.UUID, botanical_name: str) -> Species | None:
        for s in self.species.values():
            if s.nursery_id == nursery_id and s.botanical_name == botanical_name:
                return s
        return None

    async def add(self, species: Species) -> Species:
        if species.id is None:
            species.id = uuid.uuid4()
        _backfill_timestamps(species)
        self.species[species.id] = species
        return species

    async def delete(self, species: Species) -> None:
        self.species.pop(species.id, None)

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
        matching = [s for s in self.species.values() if s.nursery_id == nursery_id]
        if search:
            needle = search.strip().lower()
            matching = [
                s for s in matching if needle in s.common_name.lower() or needle in s.botanical_name.lower()
            ]
        if category_id is not None:
            matching = [s for s in matching if s.category_id == category_id]
        if light_requirement is not None:
            matching = [s for s in matching if s.light_requirement == light_requirement]
        matching.sort(key=lambda s: s.common_name)
        return matching[offset : offset + limit], len(matching)

    async def count_plants_referencing(self, species_id: uuid.UUID) -> int:
        return self.plant_species_ids.count(species_id)


class FakePlantVarietyRepository:
    """Module 5. `plant_variety_ids` mirrors `FakeSpeciesRepository.plant_species_ids` -- see that class's docstring."""

    def __init__(self) -> None:
        self.varieties: dict[uuid.UUID, PlantVariety] = {}
        self.plant_variety_ids: list[uuid.UUID] = []

    async def get_by_id(self, variety_id: uuid.UUID) -> PlantVariety | None:
        return self.varieties.get(variety_id)

    async def get_by_name(self, species_id: uuid.UUID, name: str) -> PlantVariety | None:
        for v in self.varieties.values():
            if v.species_id == species_id and v.name == name:
                return v
        return None

    async def add(self, variety: PlantVariety) -> PlantVariety:
        if variety.id is None:
            variety.id = uuid.uuid4()
        _backfill_timestamps(variety)
        self.varieties[variety.id] = variety
        return variety

    async def delete(self, variety: PlantVariety) -> None:
        self.varieties.pop(variety.id, None)

    async def list_for_species(
        self, species_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[PlantVariety], int]:
        matching = sorted(
            (v for v in self.varieties.values() if v.species_id == species_id), key=lambda v: v.name
        )
        return matching[offset : offset + limit], len(matching)

    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[PlantVariety], int]:
        matching = sorted(
            (v for v in self.varieties.values() if v.nursery_id == nursery_id), key=lambda v: v.name
        )
        return matching[offset : offset + limit], len(matching)

    async def count_plants_referencing(self, variety_id: uuid.UUID) -> int:
        return self.plant_variety_ids.count(variety_id)


# ==============================================================================
# Module 6 (Plant Lifecycle Management)
# ==============================================================================


class FakePlantRepository:
    def __init__(self) -> None:
        self.plants: dict[uuid.UUID, Plant] = {}

    async def get_by_id(self, plant_id: uuid.UUID) -> Plant | None:
        return self.plants.get(plant_id)

    async def get_by_qr_token(self, qr_code_token: str) -> Plant | None:
        for plant in self.plants.values():
            if plant.qr_code_token == qr_code_token:
                return plant
        return None

    async def add(self, plant: Plant) -> Plant:
        if plant.id is None:
            plant.id = uuid.uuid4()
        _backfill_timestamps(plant)
        self.plants[plant.id] = plant
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
        matching = [p for p in self.plants.values() if p.nursery_id == nursery_id]
        if branch_id is not None:
            matching = [p for p in matching if p.branch_id == branch_id]
        if species_id is not None:
            matching = [p for p in matching if p.species_id == species_id]
        if status is not None:
            matching = [p for p in matching if p.status == status]
        if zone is not None:
            matching = [p for p in matching if p.zone == zone]
        if batch_number is not None:
            matching = [p for p in matching if p.batch_number == batch_number]
        if not include_archived:
            matching = [p for p in matching if p.archived_at is None]
        if search:
            needle = search.strip().lower()
            matching = [
                p
                for p in matching
                if needle in (p.common_label or "").lower()
                or needle in (p.qr_code_token or "").lower()
                or needle in (p.batch_number or "").lower()
            ]

        def _key(p: Plant):
            value = getattr(p, sort_by, None) or getattr(p, "created_at", None)
            if value is None:
                return datetime.min.replace(tzinfo=timezone.utc)
            if isinstance(value, str):
                return value
            return value

        matching.sort(key=_key, reverse=(sort_dir != "asc"))
        return matching[offset : offset + limit], len(matching)


class FakePlantImageRepository:
    def __init__(self) -> None:
        self.images: dict[uuid.UUID, PlantImage] = {}

    async def add(self, image: PlantImage) -> PlantImage:
        if image.id is None:
            image.id = uuid.uuid4()
        if image.captured_at is None:
            image.captured_at = datetime.now(timezone.utc)
        self.images[image.id] = image
        return image

    async def list_for_plant(self, plant_id: uuid.UUID) -> list[PlantImage]:
        matching = [i for i in self.images.values() if i.plant_id == plant_id]
        matching.sort(key=lambda i: i.captured_at)
        return matching


class FakePlantTransferRepository:
    def __init__(self) -> None:
        self.transfers: dict[uuid.UUID, PlantTransfer] = {}

    async def add(self, transfer: PlantTransfer) -> PlantTransfer:
        if transfer.id is None:
            transfer.id = uuid.uuid4()
        if transfer.transferred_at is None:
            transfer.transferred_at = datetime.now(timezone.utc)
        self.transfers[transfer.id] = transfer
        return transfer

    async def list_for_plant(self, plant_id: uuid.UUID) -> list[PlantTransfer]:
        matching = [t for t in self.transfers.values() if t.plant_id == plant_id]
        matching.sort(key=lambda t: t.transferred_at)
        return matching


class _FakeTimestampedLogRepository:
    """
    Shared base for the four near-identical append-only log fakes
    (Growth/Health/Watering/Fertilizer/Environmental) -- each production
    table has its own real model with its own domain columns, but the
    fake's storage/list-for-plant/paginate shape is identical across all
    five, so this avoids five copy-pasted classes differing only in the
    `recorded_at` attribute name (always `recorded_at` here, matching the
    real tables' own shared naming).

    `plant_repo` (optional, matching `FakeCustomerRepository`'s own
    optional `tag_repo` precedent) is only supplied by the harness for the
    three subclasses whose Protocol grew a Phase 6 Module 12
    `list_for_nursery` (Growth/Water Usage/Fertilizer Reports) -- it
    resolves each row's `plant_id` back to a `nursery_id`/`branch_id` the
    same join-through-`FakePlantRepository` way `FakeDiseaseReportRepository`
    already does, since none of these tables carry tenant columns of their
    own.
    """

    def __init__(self, plant_repo: "FakePlantRepository | None" = None) -> None:
        self.rows: dict[uuid.UUID, object] = {}
        self._plant_repo = plant_repo

    async def add(self, entry) -> object:
        if entry.id is None:
            entry.id = uuid.uuid4()
        if getattr(entry, "recorded_at", None) is None:
            entry.recorded_at = datetime.now(timezone.utc)
        self.rows[entry.id] = entry
        return entry

    async def list_for_plant(self, plant_id: uuid.UUID, *, offset: int, limit: int):
        matching = [r for r in self.rows.values() if r.plant_id == plant_id]
        matching.sort(key=lambda r: r.recorded_at, reverse=True)
        return matching[offset : offset + limit], len(matching)

    async def get_by_id(self, entry_id: uuid.UUID):
        return self.rows.get(entry_id)

    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        branch_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ):
        plants = self._plant_repo.plants
        matching = []
        for r in self.rows.values():
            plant = plants.get(r.plant_id)
            if plant is None or plant.nursery_id != nursery_id:
                continue
            if branch_id is not None and plant.branch_id != branch_id:
                continue
            if date_from is not None and _aware(r.recorded_at) < _aware(date_from):
                continue
            if date_to is not None and _aware(r.recorded_at) > _aware(date_to):
                continue
            matching.append(r)
        matching.sort(key=lambda r: r.recorded_at, reverse=True)
        return matching[offset : offset + limit], len(matching)


class FakeGrowthTimelineRepository(_FakeTimestampedLogRepository):
    rows: dict[uuid.UUID, GrowthTimeline]


class FakeHealthHistoryRepository(_FakeTimestampedLogRepository):
    rows: dict[uuid.UUID, HealthHistory]


class _FakeBranchScopedLogRepository(_FakeTimestampedLogRepository):
    """
    `WateringLog`/`FertilizerLog` diverge from the base class's
    plant-join `list_for_nursery` (used by `FakeGrowthTimelineRepository`)
    because both tables carry their own `branch_id` directly alongside a
    NULLABLE `plant_id` (a zone-level watering/fertilizing pass has no
    single plant to attach to -- see `WateringLog`'s own model docstring).
    Resolving tenant scope via `self._plant_repo.plants[r.plant_id]` would
    silently drop every such zone-level row, exactly the bug the real
    `SqlAlchemyWateringLogRepository.list_for_nursery`/
    `SqlAlchemyFertilizerLogRepository.list_for_nursery` were caught and
    fixed for -- this override keeps the fake matching that same
    corrected join-through-`Branch` shape instead.
    """

    def __init__(self, branch_repo: "FakeBranchRepository") -> None:
        super().__init__()
        self._branch_repo = branch_repo

    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        branch_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ):
        branches = self._branch_repo.branches
        matching = []
        for r in self.rows.values():
            branch = branches.get(r.branch_id)
            if branch is None or branch.nursery_id != nursery_id:
                continue
            if branch_id is not None and r.branch_id != branch_id:
                continue
            if date_from is not None and _aware(r.recorded_at) < _aware(date_from):
                continue
            if date_to is not None and _aware(r.recorded_at) > _aware(date_to):
                continue
            matching.append(r)
        matching.sort(key=lambda r: r.recorded_at, reverse=True)
        return matching[offset : offset + limit], len(matching)


class FakeWateringLogRepository(_FakeBranchScopedLogRepository):
    rows: dict[uuid.UUID, WateringLog]


class FakeFertilizerLogRepository(_FakeBranchScopedLogRepository):
    rows: dict[uuid.UUID, FertilizerLog]


class FakeEnvironmentalReadingRepository(_FakeTimestampedLogRepository):
    rows: dict[uuid.UUID, EnvironmentalReading]


class FakeDiseaseReportRepository:
    """
    Takes the same `FakePlantRepository` instance the harness wires into
    `PlantService` -- `list_for_nursery` needs to resolve each report's
    `plant_id` back to a `nursery_id` (DiseaseReport carries no nursery_id
    column of its own; the real SQL repository does this with a JOIN),
    and sharing the live dict is simpler and less error-prone than
    duplicating a plant_id->nursery_id index that could drift out of sync.
    """

    def __init__(self, plant_repo: "FakePlantRepository") -> None:
        self.reports: dict[uuid.UUID, DiseaseReport] = {}
        self._plant_repo = plant_repo

    async def get_by_id(self, report_id: uuid.UUID) -> DiseaseReport | None:
        return self.reports.get(report_id)

    async def add(self, report: DiseaseReport) -> DiseaseReport:
        if report.id is None:
            report.id = uuid.uuid4()
        if report.created_at is None:
            report.created_at = datetime.now(timezone.utc)
        self.reports[report.id] = report
        return report

    async def list_for_plant(self, plant_id: uuid.UUID) -> list[DiseaseReport]:
        matching = [r for r in self.reports.values() if r.plant_id == plant_id]
        matching.sort(key=lambda r: r.created_at, reverse=True)
        return matching

    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        status: DiseaseReportStatus | None = None,
        severity: DiseaseReportSeverity | None = None,
    ) -> tuple[list[DiseaseReport], int]:
        plants = self._plant_repo.plants
        matching = [
            r
            for r in self.reports.values()
            if plants.get(r.plant_id) is not None and plants[r.plant_id].nursery_id == nursery_id
        ]
        if status is not None:
            matching = [r for r in matching if r.status == status]
        if severity is not None:
            matching = [r for r in matching if r.severity == severity]
        matching.sort(key=lambda r: r.created_at, reverse=True)
        return matching[offset : offset + limit], len(matching)

    async def count_open_for_plant(self, plant_id: uuid.UUID) -> int:
        open_statuses = {DiseaseReportStatus.DRAFT, DiseaseReportStatus.CONFIRMED, DiseaseReportStatus.TREATED}
        return sum(1 for r in self.reports.values() if r.plant_id == plant_id and r.status in open_statuses)


class FakeTreatmentRepository:
    def __init__(self) -> None:
        self.treatments: dict[uuid.UUID, Treatment] = {}

    async def add(self, treatment: Treatment) -> Treatment:
        if treatment.id is None:
            treatment.id = uuid.uuid4()
        if treatment.applied_at is None:
            treatment.applied_at = datetime.now(timezone.utc)
        self.treatments[treatment.id] = treatment
        return treatment

    async def list_for_disease_report(self, disease_report_id: uuid.UUID) -> list[Treatment]:
        matching = [t for t in self.treatments.values() if t.disease_report_id == disease_report_id]
        matching.sort(key=lambda t: t.applied_at)
        return matching

    async def get_by_id(self, treatment_id: uuid.UUID) -> Treatment | None:
        return self.treatments.get(treatment_id)


class FakeSupplierRepository:
    def __init__(self) -> None:
        self.suppliers: dict[uuid.UUID, Supplier] = {}

    async def get_by_id(self, supplier_id: uuid.UUID) -> Supplier | None:
        return self.suppliers.get(supplier_id)

    async def list_for_nursery(self, nursery_id: uuid.UUID) -> list[Supplier]:
        return sorted(
            [s for s in self.suppliers.values() if s.nursery_id == nursery_id],
            key=lambda s: s.name,
        )


# --------------------------------------------------------------------------
# Module 7 (Plant Digital Twin Engine)
# --------------------------------------------------------------------------


class FakeDigitalTwinRepository:
    def __init__(self) -> None:
        self.twins: dict[uuid.UUID, DigitalTwin] = {}  # keyed by twin id
        self._by_plant: dict[uuid.UUID, uuid.UUID] = {}  # plant_id -> twin id

    async def get_by_plant_id(self, plant_id: uuid.UUID) -> DigitalTwin | None:
        twin_id = self._by_plant.get(plant_id)
        return self.twins.get(twin_id) if twin_id else None

    async def create(self, twin: DigitalTwin) -> DigitalTwin:
        if twin.id is None:
            twin.id = uuid.uuid4()
        _backfill_timestamps(twin)
        self.twins[twin.id] = twin
        self._by_plant[twin.plant_id] = twin.id
        return twin

    async def update(self, twin: DigitalTwin) -> DigitalTwin:
        twin.updated_at = datetime.now(timezone.utc)
        self.twins[twin.id] = twin
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
        matching = [t for t in self.twins.values() if t.nursery_id == nursery_id]
        if lifecycle_state is not None:
            matching = [t for t in matching if t.lifecycle_state == lifecycle_state]
        if branch_id is not None:
            matching = [t for t in matching if t.branch_id == branch_id]
        reverse = sort_dir != "asc"
        matching.sort(key=lambda t: getattr(t, sort_by, t.updated_at) or t.updated_at, reverse=reverse)
        return matching[offset : offset + limit], len(matching)


class FakeDigitalTwinVersionRepository:
    def __init__(self) -> None:
        self.versions: list[DigitalTwinVersion] = []

    async def add(self, version: DigitalTwinVersion) -> DigitalTwinVersion:
        if version.id is None:
            version.id = uuid.uuid4()
        if version.created_at is None:
            version.created_at = datetime.now(timezone.utc)
        self.versions.append(version)
        return version

    async def get_by_plant_and_version(self, plant_id: uuid.UUID, version: int) -> DigitalTwinVersion | None:
        for v in self.versions:
            if v.plant_id == plant_id and v.version == version:
                return v
        return None

    async def get_latest_version_number(self, plant_id: uuid.UUID) -> int:
        matching = [v.version for v in self.versions if v.plant_id == plant_id]
        return max(matching) if matching else 0

    async def list_for_plant(
        self, plant_id: uuid.UUID, *, offset: int, limit: int, sort_dir: str = "desc"
    ) -> tuple[list[DigitalTwinVersion], int]:
        matching = [v for v in self.versions if v.plant_id == plant_id]
        matching.sort(key=lambda v: v.version, reverse=(sort_dir != "asc"))
        return matching[offset : offset + limit], len(matching)

    async def get_as_of(self, plant_id: uuid.UUID, *, as_of: datetime) -> DigitalTwinVersion | None:
        as_of = _aware(as_of)
        matching = [v for v in self.versions if v.plant_id == plant_id and _aware(v.occurred_at) <= as_of]
        if not matching:
            return None
        return max(matching, key=lambda v: v.version)


class FakeEventDispatchLogRepository:
    def __init__(self) -> None:
        self.rows: dict[tuple[uuid.UUID, str], EventDispatchLog] = {}

    async def get(self, event_id: uuid.UUID, handler_name: str) -> EventDispatchLog | None:
        return self.rows.get((event_id, handler_name))

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
        key = (event_id, handler_name)
        existing = self.rows.get(key)
        if existing is not None:
            existing.status = status
            existing.attempt_count = attempt_count
            existing.resulting_version = resulting_version
            existing.error_message = error_message
            existing.processed_at = datetime.now(timezone.utc)
            return existing
        row = EventDispatchLog(
            id=uuid.uuid4(),
            event_id=event_id,
            handler_name=handler_name,
            status=status,
            attempt_count=attempt_count,
            resulting_version=resulting_version,
            error_message=error_message,
            processed_at=datetime.now(timezone.utc),
        )
        self.rows[key] = row
        return row

    async def list_failed(self, *, handler_name: str | None = None, limit: int = 100) -> list[EventDispatchLog]:
        matching = [r for r in self.rows.values() if r.status == EventDispatchStatus.FAILED]
        if handler_name is not None:
            matching = [r for r in matching if r.handler_name == handler_name]
        matching.sort(key=lambda r: r.processed_at)
        return matching[:limit]


# ==============================================================================
# Module 8 (Inventory & Stock Management)
# ==============================================================================


class FakeInventoryLocationRepository:
    def __init__(self) -> None:
        self.locations: dict[uuid.UUID, InventoryLocation] = {}

    async def get_by_id(self, location_id: uuid.UUID) -> InventoryLocation | None:
        return self.locations.get(location_id)

    async def add(self, location: InventoryLocation) -> InventoryLocation:
        if location.id is None:
            location.id = uuid.uuid4()
        if location.is_active is None:
            location.is_active = True
        _backfill_timestamps(location)
        self.locations[location.id] = location
        return location

    async def update(self, location: InventoryLocation) -> InventoryLocation:
        self.locations[location.id] = location
        return location

    async def list_for_branch(
        self, branch_id: uuid.UUID, *, include_inactive: bool = False
    ) -> list[InventoryLocation]:
        matching = [loc for loc in self.locations.values() if loc.branch_id == branch_id]
        if not include_inactive:
            matching = [loc for loc in matching if loc.is_active]
        matching.sort(key=lambda loc: loc.name)
        return matching


class FakeInventoryRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, Inventory] = {}

    async def get_by_id(self, inventory_id: uuid.UUID) -> Inventory | None:
        return self.items.get(inventory_id)

    async def add(self, inventory: Inventory) -> Inventory:
        if inventory.id is None:
            inventory.id = uuid.uuid4()
        if inventory.reserved_quantity is None:
            inventory.reserved_quantity = 0
        if inventory.damaged_quantity is None:
            inventory.damaged_quantity = 0
        if inventory.disposed_quantity is None:
            inventory.disposed_quantity = 0
        if inventory.version is None:
            inventory.version = 1
        _backfill_timestamps(inventory)
        self.items[inventory.id] = inventory
        return inventory

    async def update(self, inventory: Inventory, *, expected_version: int) -> Inventory | None:
        """
        Optimistic-lock check against the *value* of `expected_version`
        the caller captured at read time, not against Python object
        identity -- correct even though these fakes hand back the same
        live reference from `get_by_id` (see this method's Protocol
        docstring for why a real concurrent-write race still can't be
        reproduced against a single-threaded fake, only the version-
        mismatch *logic* itself).
        """
        current = self.items.get(inventory.id)
        if current is None or current.version != expected_version:
            return None
        current.quantity = inventory.quantity
        current.reserved_quantity = inventory.reserved_quantity
        current.damaged_quantity = inventory.damaged_quantity
        current.disposed_quantity = inventory.disposed_quantity
        current.location_id = inventory.location_id
        current.unit_cost = inventory.unit_cost
        current.unit_price = inventory.unit_price
        current.low_stock_threshold = inventory.low_stock_threshold
        current.archived_at = inventory.archived_at
        current.version = expected_version + 1
        return current

    async def get_by_branch_and_name(self, branch_id: uuid.UUID, name: str) -> Inventory | None:
        for item in self.items.values():
            if item.branch_id == branch_id and item.name == name:
                return item
        return None

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
        matching = [item for item in self.items.values() if item.nursery_id == nursery_id]
        if branch_id is not None:
            matching = [item for item in matching if item.branch_id == branch_id]
        if category_id is not None:
            matching = [item for item in matching if item.category_id == category_id]
        if species_id is not None:
            matching = [item for item in matching if item.species_id == species_id]
        if location_id is not None:
            matching = [item for item in matching if item.location_id == location_id]
        if not include_archived:
            matching = [item for item in matching if item.archived_at is None]
        if low_stock_only:
            matching = [item for item in matching if item.quantity <= item.low_stock_threshold]
        if search:
            needle = search.strip().lower()
            matching = [item for item in matching if needle in item.name.lower()]

        sort_key = {
            "name": lambda item: item.name,
            "quantity": lambda item: item.quantity,
            "low_stock_threshold": lambda item: item.low_stock_threshold,
        }.get(sort_by, lambda item: item.created_at)
        matching.sort(key=sort_key, reverse=(sort_dir != "asc"))

        total = len(matching)
        return matching[offset : offset + limit], total


class FakeStockMovementRepository:
    """
    Takes the same `FakeInventoryRepository` instance the harness wires
    into `InventoryService` -- `list_for_nursery` needs to resolve each
    movement's `inventory_id` back to a `nursery_id`/`branch_id`
    (StockMovement carries neither column of its own; the real SQL
    repository does this with a JOIN), matching the
    `FakeDiseaseReportRepository` precedent above.
    """

    def __init__(self, inventory_repo: "FakeInventoryRepository") -> None:
        self.movements: dict[uuid.UUID, StockMovement] = {}
        self._inventory_repo = inventory_repo

    async def add(self, movement: StockMovement) -> StockMovement:
        if movement.id is None:
            movement.id = uuid.uuid4()
        if movement.created_at is None:
            movement.created_at = datetime.now(timezone.utc)
        self.movements[movement.id] = movement
        return movement

    async def get_by_id(self, movement_id: uuid.UUID) -> StockMovement | None:
        return self.movements.get(movement_id)

    async def list_for_inventory(
        self,
        inventory_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        movement_type: StockMovementType | None = None,
        sort_dir: str = "desc",
    ) -> tuple[list[StockMovement], int]:
        matching = [m for m in self.movements.values() if m.inventory_id == inventory_id]
        if movement_type is not None:
            matching = [m for m in matching if m.movement_type == movement_type]
        matching.sort(key=lambda m: m.created_at, reverse=(sort_dir != "asc"))
        total = len(matching)
        return matching[offset : offset + limit], total

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
        matching = []
        for m in self.movements.values():
            inv = self._inventory_repo.items.get(m.inventory_id)
            if inv is None or inv.nursery_id != nursery_id:
                continue
            if branch_id is not None and inv.branch_id != branch_id:
                continue
            if movement_type is not None and m.movement_type != movement_type:
                continue
            if date_from is not None and _aware(m.created_at) < _aware(date_from):
                continue
            if date_to is not None and _aware(m.created_at) > _aware(date_to):
                continue
            matching.append(m)
        matching.sort(key=lambda m: m.created_at, reverse=(sort_dir != "asc"))
        total = len(matching)
        return matching[offset : offset + limit], total


class FakeStockReservationRepository:
    def __init__(self) -> None:
        self.reservations: dict[uuid.UUID, StockReservation] = {}

    async def get_by_id(self, reservation_id: uuid.UUID) -> StockReservation | None:
        return self.reservations.get(reservation_id)

    async def add(self, reservation: StockReservation) -> StockReservation:
        if reservation.id is None:
            reservation.id = uuid.uuid4()
        if reservation.status is None:
            reservation.status = StockReservationStatus.ACTIVE
        if reservation.reserved_at is None:
            reservation.reserved_at = datetime.now(timezone.utc)
        self.reservations[reservation.id] = reservation
        return reservation

    async def update(self, reservation: StockReservation) -> StockReservation:
        self.reservations[reservation.id] = reservation
        return reservation

    async def list_for_inventory(
        self, inventory_id: uuid.UUID, *, status: StockReservationStatus | None = None
    ) -> list[StockReservation]:
        matching = [r for r in self.reservations.values() if r.inventory_id == inventory_id]
        if status is not None:
            matching = [r for r in matching if r.status == status]
        matching.sort(key=lambda r: r.reserved_at, reverse=True)
        return matching

    async def list_active_for_nursery(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int, branch_id: uuid.UUID | None = None
    ) -> tuple[list[StockReservation], int]:
        matching = [
            r
            for r in self.reservations.values()
            if r.nursery_id == nursery_id and r.status == StockReservationStatus.ACTIVE
        ]
        if branch_id is not None:
            matching = [r for r in matching if r.branch_id == branch_id]
        matching.sort(key=lambda r: r.reserved_at, reverse=True)
        total = len(matching)
        return matching[offset : offset + limit], total


def _aware(value: datetime) -> datetime:
    import datetime as dt

    return value if value.tzinfo is not None else value.replace(tzinfo=dt.timezone.utc)


def _backfill_timestamps(entity) -> None:
    """
    `TimestampMixin` (app/db/base.py) populates `created_at`/`updated_at`
    via `server_default=func.now()`, not a Python-side `default=` --
    against a real Postgres/asyncpg session, SQLAlchemy's implicit
    RETURNING support fetches those server-generated values back onto the
    object as part of `session.flush()`, so production code never sees
    `None` there once a row has been added. These fakes have no flush (and
    no database) to do that, so `add()` backfills both fields itself --
    otherwise an HTTP-level integration test serializing a fake-backed
    `Nursery`/`Branch`/`Employee`/`Invite` straight into its Pydantic
    response schema (all of which declare `created_at: datetime`, not
    `datetime | None`) would fail with a spurious validation error that
    has nothing to do with the route or schema being tested.
    """
    now = datetime.now(timezone.utc)
    if getattr(entity, "created_at", "unset") is None:
        entity.created_at = now
    if getattr(entity, "updated_at", "unset") is None:
        entity.updated_at = now


# ==============================================================================
# Module 9 (Sales, CRM, Plant Passport & QR Intelligence)
# ==============================================================================


class FakeCustomerRepository:
    """
    `tag_repo` is an optional reference to the harness's
    `FakeCustomerTagRepository`, wired at construction time (same
    constructor-injection precedent `FakeStockMovementRepository` already
    established for resolving a join through another fake) — needed
    because `list_for_nursery`'s `tag` filter has no other way to see
    `customer_tags` rows without it (the real SQL repository does this
    with a `WHERE id IN (SELECT customer_id FROM customer_tags ...)`
    subquery instead).
    """

    def __init__(self, tag_repo: "FakeCustomerTagRepository | None" = None) -> None:
        self.customers: dict[uuid.UUID, Customer] = {}
        self._tag_repo = tag_repo

    async def get_by_id(self, customer_id: uuid.UUID) -> Customer | None:
        return self.customers.get(customer_id)

    async def add(self, customer: Customer) -> Customer:
        if customer.id is None:
            customer.id = uuid.uuid4()
        _backfill_timestamps(customer)
        self.customers[customer.id] = customer
        return customer

    async def update(self, customer: Customer) -> Customer:
        self.customers[customer.id] = customer
        return customer

    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        branch_id: uuid.UUID | None = None,
        customer_type=None,
        tag: str | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> tuple[list[Customer], int]:
        matching = [c for c in self.customers.values() if c.nursery_id == nursery_id]
        if branch_id is not None:
            matching = [c for c in matching if c.branch_id == branch_id]
        if customer_type is not None:
            matching = [c for c in matching if c.customer_type == customer_type]
        if search:
            needle = search.strip().lower()
            matching = [
                c
                for c in matching
                if needle in c.name.lower()
                or (c.email and needle in c.email.lower())
                or (c.phone and needle in c.phone.lower())
            ]
        if tag and self._tag_repo is not None:
            tagged_customer_ids = {t.customer_id for t in self._tag_repo.tags.values() if t.tag == tag}
            matching = [c for c in matching if c.id in tagged_customer_ids]
        sort_key = {"name": lambda c: c.name}.get(sort_by, lambda c: c.created_at)
        matching.sort(key=sort_key, reverse=(sort_dir != "asc"))
        total = len(matching)
        return matching[offset : offset + limit], total


class FakeCustomerContactRepository:
    def __init__(self) -> None:
        self.contacts: dict[uuid.UUID, CustomerContact] = {}

    async def get_by_id(self, contact_id: uuid.UUID) -> CustomerContact | None:
        return self.contacts.get(contact_id)

    async def add(self, contact: CustomerContact) -> CustomerContact:
        if contact.id is None:
            contact.id = uuid.uuid4()
        if contact.is_primary is None:
            contact.is_primary = False
        _backfill_timestamps(contact)
        self.contacts[contact.id] = contact
        return contact

    async def list_for_customer(self, customer_id: uuid.UUID) -> list[CustomerContact]:
        matching = [c for c in self.contacts.values() if c.customer_id == customer_id]
        matching.sort(key=lambda c: c.created_at)
        return matching

    async def delete(self, contact_id: uuid.UUID) -> None:
        self.contacts.pop(contact_id, None)


class FakeCustomerAddressRepository:
    def __init__(self) -> None:
        self.addresses: dict[uuid.UUID, CustomerAddress] = {}

    async def get_by_id(self, address_id: uuid.UUID) -> CustomerAddress | None:
        return self.addresses.get(address_id)

    async def add(self, address: CustomerAddress) -> CustomerAddress:
        if address.id is None:
            address.id = uuid.uuid4()
        if address.is_default is None:
            address.is_default = False
        _backfill_timestamps(address)
        self.addresses[address.id] = address
        return address

    async def list_for_customer(self, customer_id: uuid.UUID) -> list[CustomerAddress]:
        matching = [a for a in self.addresses.values() if a.customer_id == customer_id]
        matching.sort(key=lambda a: a.created_at)
        return matching

    async def delete(self, address_id: uuid.UUID) -> None:
        self.addresses.pop(address_id, None)


class FakeCustomerTagRepository:
    def __init__(self) -> None:
        self.tags: dict[uuid.UUID, CustomerTag] = {}

    async def add(self, tag: CustomerTag) -> CustomerTag:
        if tag.id is None:
            tag.id = uuid.uuid4()
        self.tags[tag.id] = tag
        return tag

    async def list_for_customer(self, customer_id: uuid.UUID) -> list[CustomerTag]:
        matching = [t for t in self.tags.values() if t.customer_id == customer_id]
        matching.sort(key=lambda t: t.tag)
        return matching

    async def delete(self, customer_id: uuid.UUID, tag: str) -> None:
        match = next(
            (t for t in self.tags.values() if t.customer_id == customer_id and t.tag == tag), None
        )
        if match is not None:
            self.tags.pop(match.id, None)


class FakeCustomerNoteRepository:
    def __init__(self) -> None:
        self.notes: dict[uuid.UUID, CustomerNote] = {}

    async def get_by_id(self, note_id: uuid.UUID) -> CustomerNote | None:
        return self.notes.get(note_id)

    async def add(self, note: CustomerNote) -> CustomerNote:
        if note.id is None:
            note.id = uuid.uuid4()
        if note.pinned is None:
            note.pinned = False
        if note.created_at is None:
            note.created_at = datetime.now(timezone.utc)
        self.notes[note.id] = note
        return note

    async def list_for_customer(
        self, customer_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[CustomerNote], int]:
        matching = [n for n in self.notes.values() if n.customer_id == customer_id]
        matching.sort(key=lambda n: (not n.pinned, -_aware(n.created_at).timestamp()))
        total = len(matching)
        return matching[offset : offset + limit], total

    async def delete(self, note_id: uuid.UUID) -> None:
        self.notes.pop(note_id, None)


class FakeCustomerCommunicationRepository:
    def __init__(self) -> None:
        self.communications: dict[uuid.UUID, CustomerCommunication] = {}

    async def add(self, communication: CustomerCommunication) -> CustomerCommunication:
        if communication.id is None:
            communication.id = uuid.uuid4()
        if communication.occurred_at is None:
            communication.occurred_at = datetime.now(timezone.utc)
        self.communications[communication.id] = communication
        return communication

    async def list_for_customer(
        self, customer_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[CustomerCommunication], int]:
        matching = [c for c in self.communications.values() if c.customer_id == customer_id]
        matching.sort(key=lambda c: c.occurred_at, reverse=True)
        total = len(matching)
        return matching[offset : offset + limit], total


class FakeQuotationRepository:
    def __init__(self) -> None:
        self.quotations: dict[uuid.UUID, Quotation] = {}

    async def get_by_id(self, quotation_id: uuid.UUID) -> Quotation | None:
        return self.quotations.get(quotation_id)

    async def add(self, quotation: Quotation) -> Quotation:
        if quotation.id is None:
            quotation.id = uuid.uuid4()
        if quotation.status is None:
            quotation.status = QuotationStatus.DRAFT
        _backfill_timestamps(quotation)
        self.quotations[quotation.id] = quotation
        return quotation

    async def update(self, quotation: Quotation) -> Quotation:
        self.quotations[quotation.id] = quotation
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
        matching = [q for q in self.quotations.values() if q.nursery_id == nursery_id]
        if branch_id is not None:
            matching = [q for q in matching if q.branch_id == branch_id]
        if customer_id is not None:
            matching = [q for q in matching if q.customer_id == customer_id]
        if status is not None:
            matching = [q for q in matching if q.status == status]
        sort_key = {"total_amount": lambda q: q.total_amount}.get(sort_by, lambda q: q.created_at)
        matching.sort(key=sort_key, reverse=(sort_dir != "asc"))
        total = len(matching)
        return matching[offset : offset + limit], total


class FakeQuotationItemRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, QuotationItem] = {}

    async def add(self, item: QuotationItem) -> QuotationItem:
        if item.id is None:
            item.id = uuid.uuid4()
        self.items[item.id] = item
        return item

    async def list_for_quotation(self, quotation_id: uuid.UUID) -> list[QuotationItem]:
        return [i for i in self.items.values() if i.quotation_id == quotation_id]


class FakeSalesOrderRepository:
    def __init__(self) -> None:
        self.orders: dict[uuid.UUID, SalesOrder] = {}

    async def get_by_id(self, order_id: uuid.UUID) -> SalesOrder | None:
        return self.orders.get(order_id)

    async def get_by_idempotency_key(self, branch_id: uuid.UUID, key: str) -> SalesOrder | None:
        for order in self.orders.values():
            if order.branch_id == branch_id and order.idempotency_key == key:
                return order
        return None

    async def add(self, order: SalesOrder) -> SalesOrder:
        if order.id is None:
            order.id = uuid.uuid4()
        if order.order_status is None:
            order.order_status = SalesOrderStatus.DRAFT
        _backfill_timestamps(order)
        self.orders[order.id] = order
        return order

    async def update(self, order: SalesOrder) -> SalesOrder:
        self.orders[order.id] = order
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
        matching = [o for o in self.orders.values() if o.nursery_id == nursery_id]
        if branch_id is not None:
            matching = [o for o in matching if o.branch_id == branch_id]
        if customer_id is not None:
            matching = [o for o in matching if o.customer_id == customer_id]
        if order_status is not None:
            matching = [o for o in matching if o.order_status == order_status]
        sort_key = {"total_amount": lambda o: o.total_amount}.get(sort_by, lambda o: o.created_at)
        matching.sort(key=sort_key, reverse=(sort_dir != "asc"))
        total = len(matching)
        return matching[offset : offset + limit], total


class FakeOrderItemRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, OrderItem] = {}

    async def get_by_id(self, item_id: uuid.UUID) -> OrderItem | None:
        return self.items.get(item_id)

    async def add(self, item: OrderItem) -> OrderItem:
        if item.id is None:
            item.id = uuid.uuid4()
        self.items[item.id] = item
        return item

    async def update(self, item: OrderItem) -> OrderItem:
        self.items[item.id] = item
        return item

    async def list_for_order(self, sales_order_id: uuid.UUID) -> list[OrderItem]:
        return [i for i in self.items.values() if i.sales_order_id == sales_order_id]


class FakeSaleRepository:
    def __init__(self) -> None:
        self.sales: dict[uuid.UUID, Sale] = {}

    async def get_by_id(self, sale_id: uuid.UUID) -> Sale | None:
        return self.sales.get(sale_id)

    async def get_by_idempotency_key(self, branch_id: uuid.UUID, key: str) -> Sale | None:
        for sale in self.sales.values():
            if sale.branch_id == branch_id and sale.idempotency_key == key:
                return sale
        return None

    async def add(self, sale: Sale) -> Sale:
        if sale.id is None:
            sale.id = uuid.uuid4()
        if sale.tax_amount is None:
            sale.tax_amount = 0
        if sale.created_at is None:
            sale.created_at = datetime.now(timezone.utc)
        self.sales[sale.id] = sale
        return sale

    async def update(self, sale: Sale) -> Sale:
        self.sales[sale.id] = sale
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
        matching = [s for s in self.sales.values() if s.nursery_id == nursery_id]
        if branch_id is not None:
            matching = [s for s in matching if s.branch_id == branch_id]
        if customer_id is not None:
            matching = [s for s in matching if s.customer_id == customer_id]
        if date_from is not None:
            matching = [s for s in matching if _aware(s.created_at) >= _aware(date_from)]
        if date_to is not None:
            matching = [s for s in matching if _aware(s.created_at) <= _aware(date_to)]
        sort_key = {"total_amount": lambda s: s.total_amount}.get(sort_by, lambda s: s.created_at)
        matching.sort(key=sort_key, reverse=(sort_dir != "asc"))
        total = len(matching)
        return matching[offset : offset + limit], total


class FakeSaleItemRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, SaleItem] = {}

    async def get_by_id(self, item_id: uuid.UUID) -> SaleItem | None:
        return self.items.get(item_id)

    async def add(self, item: SaleItem) -> SaleItem:
        if item.id is None:
            item.id = uuid.uuid4()
        self.items[item.id] = item
        return item

    async def list_for_sale(self, sale_id: uuid.UUID) -> list[SaleItem]:
        return [i for i in self.items.values() if i.sale_id == sale_id]


class FakeInvoiceRepository:
    def __init__(self) -> None:
        self.invoices: dict[uuid.UUID, Invoice] = {}

    async def get_by_id(self, invoice_id: uuid.UUID) -> Invoice | None:
        return self.invoices.get(invoice_id)

    async def get_by_number(self, nursery_id: uuid.UUID, invoice_number: str) -> Invoice | None:
        for inv in self.invoices.values():
            if inv.nursery_id == nursery_id and inv.invoice_number == invoice_number:
                return inv
        return None

    async def add(self, invoice: Invoice) -> Invoice:
        if invoice.id is None:
            invoice.id = uuid.uuid4()
        _backfill_timestamps(invoice)
        self.invoices[invoice.id] = invoice
        return invoice

    async def update(self, invoice: Invoice) -> Invoice:
        self.invoices[invoice.id] = invoice
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
        matching = [i for i in self.invoices.values() if i.nursery_id == nursery_id]
        if branch_id is not None:
            matching = [i for i in matching if i.branch_id == branch_id]
        if customer_id is not None:
            matching = [i for i in matching if i.customer_id == customer_id]
        if status is not None:
            matching = [i for i in matching if i.status == status]
        sort_key = {"total_amount": lambda i: i.total_amount}.get(sort_by, lambda i: i.created_at)
        matching.sort(key=sort_key, reverse=(sort_dir != "asc"))
        total = len(matching)
        return matching[offset : offset + limit], total


class FakeInvoiceItemRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, InvoiceItem] = {}

    async def add(self, item: InvoiceItem) -> InvoiceItem:
        if item.id is None:
            item.id = uuid.uuid4()
        self.items[item.id] = item
        return item

    async def list_for_invoice(self, invoice_id: uuid.UUID) -> list[InvoiceItem]:
        return [i for i in self.items.values() if i.invoice_id == invoice_id]


class FakeInvoiceSaleRepository:
    def __init__(self) -> None:
        self.links: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def link(self, invoice_id: uuid.UUID, sale_id: uuid.UUID) -> None:
        self.links.append((invoice_id, sale_id))

    async def list_sale_ids_for_invoice(self, invoice_id: uuid.UUID) -> list[uuid.UUID]:
        return [sale_id for inv_id, sale_id in self.links if inv_id == invoice_id]


class FakePaymentRepository:
    def __init__(self) -> None:
        self.payments: dict[uuid.UUID, Payment] = {}

    async def get_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        return self.payments.get(payment_id)

    async def add(self, payment: Payment) -> Payment:
        if payment.id is None:
            payment.id = uuid.uuid4()
        if payment.received_at is None:
            payment.received_at = datetime.now(timezone.utc)
        self.payments[payment.id] = payment
        return payment

    async def list_for_invoice(self, invoice_id: uuid.UUID) -> list[Payment]:
        matching = [p for p in self.payments.values() if p.invoice_id == invoice_id]
        matching.sort(key=lambda p: p.received_at)
        return matching

    async def sum_for_invoice(self, invoice_id: uuid.UUID) -> float:
        return float(sum(float(p.amount) for p in self.payments.values() if p.invoice_id == invoice_id))


class FakeReturnRepository:
    def __init__(self) -> None:
        self.returns: dict[uuid.UUID, Return] = {}

    async def get_by_id(self, return_id: uuid.UUID) -> Return | None:
        return self.returns.get(return_id)

    async def add(self, return_: Return) -> Return:
        if return_.id is None:
            return_.id = uuid.uuid4()
        if return_.status is None:
            return_.status = ReturnStatus.REQUESTED
        _backfill_timestamps(return_)
        self.returns[return_.id] = return_
        return return_

    async def update(self, return_: Return) -> Return:
        self.returns[return_.id] = return_
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
        matching = [r for r in self.returns.values() if r.nursery_id == nursery_id]
        if branch_id is not None:
            matching = [r for r in matching if r.branch_id == branch_id]
        if status is not None:
            matching = [r for r in matching if r.status == status]
        matching.sort(key=lambda r: r.created_at, reverse=(sort_dir != "asc"))
        total = len(matching)
        return matching[offset : offset + limit], total


class FakeReturnItemRepository:
    def __init__(self) -> None:
        self.items: dict[uuid.UUID, ReturnItem] = {}

    async def add(self, item: ReturnItem) -> ReturnItem:
        if item.id is None:
            item.id = uuid.uuid4()
        self.items[item.id] = item
        return item

    async def list_for_return(self, return_id: uuid.UUID) -> list[ReturnItem]:
        return [i for i in self.items.values() if i.return_id == return_id]

    async def get_by_id(self, item_id: uuid.UUID) -> ReturnItem | None:
        return self.items.get(item_id)


class FakeRefundRepository:
    def __init__(self) -> None:
        self.refunds: dict[uuid.UUID, Refund] = {}

    async def get_by_id(self, refund_id: uuid.UUID) -> Refund | None:
        return self.refunds.get(refund_id)

    async def add(self, refund: Refund) -> Refund:
        if refund.id is None:
            refund.id = uuid.uuid4()
        if refund.status is None:
            refund.status = RefundStatus.PENDING
        if refund.created_at is None:
            refund.created_at = datetime.now(timezone.utc)
        self.refunds[refund.id] = refund
        return refund

    async def update(self, refund: Refund) -> Refund:
        self.refunds[refund.id] = refund
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
        matching = [r for r in self.refunds.values() if r.nursery_id == nursery_id]
        if branch_id is not None:
            matching = [r for r in matching if r.branch_id == branch_id]
        if status is not None:
            matching = [r for r in matching if r.status == status]
        matching.sort(key=lambda r: r.created_at, reverse=(sort_dir != "asc"))
        total = len(matching)
        return matching[offset : offset + limit], total


class FakePassportRepository:
    """`plant_repo` resolves nursery scoping for `list_for_nursery` — Passport carries no nursery_id of its own (see the model's docstring)."""

    def __init__(self, plant_repo=None) -> None:
        self.passports: dict[uuid.UUID, Passport] = {}
        self._plant_repo = plant_repo

    async def get_by_id(self, passport_id: uuid.UUID) -> Passport | None:
        return self.passports.get(passport_id)

    async def get_by_token(self, public_token: str) -> Passport | None:
        for p in self.passports.values():
            if p.public_token == public_token:
                return p
        return None

    async def add(self, passport: Passport) -> Passport:
        if passport.id is None:
            passport.id = uuid.uuid4()
        if passport.version is None:
            passport.version = 1
        if passport.generated_at is None:
            passport.generated_at = datetime.now(timezone.utc)
        self.passports[passport.id] = passport
        return passport

    async def get_latest_for_plant(self, plant_id: uuid.UUID) -> Passport | None:
        matching = [p for p in self.passports.values() if p.plant_id == plant_id]
        if not matching:
            return None
        return max(matching, key=lambda p: p.version)

    async def list_for_plant(self, plant_id: uuid.UUID) -> list[Passport]:
        matching = [p for p in self.passports.values() if p.plant_id == plant_id]
        matching.sort(key=lambda p: p.version, reverse=True)
        return matching

    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[Passport], int]:
        plants = getattr(self._plant_repo, "plants", {}) if self._plant_repo else {}
        matching = [
            p for p in self.passports.values() if (plant := plants.get(p.plant_id)) and plant.nursery_id == nursery_id
        ]
        matching.sort(key=lambda p: p.generated_at, reverse=True)
        total = len(matching)
        return matching[offset : offset + limit], total


class FakeQRScanEventRepository:
    def __init__(self, passport_repo: "FakePassportRepository", plant_repo=None) -> None:
        self.scans: dict[uuid.UUID, QRScanEvent] = {}
        self._passport_repo = passport_repo
        self._plant_repo = plant_repo

    async def add(self, scan: QRScanEvent) -> QRScanEvent:
        if scan.id is None:
            scan.id = uuid.uuid4()
        if scan.scanned_at is None:
            scan.scanned_at = datetime.now(timezone.utc)
        self.scans[scan.id] = scan
        return scan

    async def count_for_passport(self, passport_id: uuid.UUID) -> int:
        return len([s for s in self.scans.values() if s.passport_id == passport_id])

    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[QRScanEvent], int]:
        plants = getattr(self._plant_repo, "plants", {}) if self._plant_repo else {}
        matching = []
        for scan in self.scans.values():
            passport = self._passport_repo.passports.get(scan.passport_id)
            if passport is None:
                continue
            plant = plants.get(passport.plant_id)
            if plant is None or plant.nursery_id != nursery_id:
                continue
            matching.append(scan)
        matching.sort(key=lambda s: s.scanned_at, reverse=True)
        total = len(matching)
        return matching[offset : offset + limit], total


# ==============================================================================
# Phase 6 Module 10 (AI Platform)
# ==============================================================================


class FakeAIPredictionRepository:
    def __init__(self) -> None:
        self.predictions: dict[uuid.UUID, AIPrediction] = {}

    async def add(self, prediction: AIPrediction) -> AIPrediction:
        if prediction.id is None:
            prediction.id = uuid.uuid4()
        if prediction.created_at is None:
            prediction.created_at = datetime.now(timezone.utc)
        self.predictions[prediction.id] = prediction
        return prediction

    async def get_by_id(self, prediction_id: uuid.UUID) -> AIPrediction | None:
        return self.predictions.get(prediction_id)

    async def list_for_plant(
        self, plant_id: uuid.UUID, *, prediction_type: AIPredictionType | None = None, offset: int, limit: int
    ) -> tuple[list[AIPrediction], int]:
        matching = [p for p in self.predictions.values() if p.plant_id == plant_id]
        if prediction_type is not None:
            matching = [p for p in matching if p.prediction_type == prediction_type]
        matching.sort(key=lambda p: p.created_at, reverse=True)
        total = len(matching)
        return matching[offset : offset + limit], total

    async def get_latest_for_plant(
        self, plant_id: uuid.UUID, prediction_type: AIPredictionType
    ) -> AIPrediction | None:
        matching = [
            p for p in self.predictions.values() if p.plant_id == plant_id and p.prediction_type == prediction_type
        ]
        if not matching:
            return None
        return max(matching, key=lambda p: p.created_at)

    async def list_for_branch(
        self, branch_id: uuid.UUID, *, prediction_type: AIPredictionType | None = None, offset: int, limit: int
    ) -> tuple[list[AIPrediction], int]:
        matching = [p for p in self.predictions.values() if p.branch_id == branch_id]
        if prediction_type is not None:
            matching = [p for p in matching if p.prediction_type == prediction_type]
        matching.sort(key=lambda p: p.created_at, reverse=True)
        total = len(matching)
        return matching[offset : offset + limit], total

    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, prediction_type: AIPredictionType | None = None, offset: int, limit: int
    ) -> tuple[list[AIPrediction], int]:
        matching = [p for p in self.predictions.values() if p.nursery_id == nursery_id]
        if prediction_type is not None:
            matching = [p for p in matching if p.prediction_type == prediction_type]
        matching.sort(key=lambda p: p.created_at, reverse=True)
        total = len(matching)
        return matching[offset : offset + limit], total

    # --- Added by Phase 6 Module 13 ("AI Administration") ---
    async def admin_stats_for_nursery(
        self, nursery_id: uuid.UUID, *, date_from: datetime | None = None, date_to: datetime | None = None
    ) -> list[dict]:
        matching = [p for p in self.predictions.values() if p.nursery_id == nursery_id]
        if date_from is not None:
            matching = [p for p in matching if _aware(p.created_at) >= _aware(date_from)]
        if date_to is not None:
            matching = [p for p in matching if _aware(p.created_at) <= _aware(date_to)]

        by_type: dict[AIPredictionType, list[AIPrediction]] = {}
        for p in matching:
            by_type.setdefault(p.prediction_type, []).append(p)

        stats = []
        for prediction_type in sorted(by_type, key=lambda t: t.value):
            rows = by_type[prediction_type]
            latencies = [r.latency_ms for r in rows if r.latency_ms is not None]
            confidences = [float(r.confidence) for r in rows if r.confidence is not None]
            stats.append(
                {
                    "prediction_type": prediction_type,
                    "count": len(rows),
                    "avg_latency_ms": (sum(latencies) / len(latencies)) if latencies else None,
                    "avg_confidence": (sum(confidences) / len(confidences)) if confidences else None,
                }
            )
        return stats


class FakeAIRecommendationRepository:
    def __init__(self) -> None:
        self.recommendations: dict[uuid.UUID, AIRecommendation] = {}

    async def add(self, recommendation: AIRecommendation) -> AIRecommendation:
        if recommendation.id is None:
            recommendation.id = uuid.uuid4()
        if recommendation.created_at is None:
            recommendation.created_at = datetime.now(timezone.utc)
        if recommendation.status is None:
            recommendation.status = AIRecommendationStatus.NEW
        self.recommendations[recommendation.id] = recommendation
        return recommendation

    async def get_by_id(self, recommendation_id: uuid.UUID) -> AIRecommendation | None:
        return self.recommendations.get(recommendation_id)

    async def update_status(
        self, recommendation: AIRecommendation, *, status: AIRecommendationStatus
    ) -> AIRecommendation:
        recommendation.status = status
        self.recommendations[recommendation.id] = recommendation
        return recommendation

    async def list_for_branch(
        self, branch_id: uuid.UUID, *, status: AIRecommendationStatus | None = None, offset: int, limit: int
    ) -> tuple[list[AIRecommendation], int]:
        matching = [r for r in self.recommendations.values() if r.branch_id == branch_id]
        if status is not None:
            matching = [r for r in matching if r.status == status]
        matching.sort(key=lambda r: r.created_at, reverse=True)
        total = len(matching)
        return matching[offset : offset + limit], total

    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, status: AIRecommendationStatus | None = None, offset: int, limit: int
    ) -> tuple[list[AIRecommendation], int]:
        matching = [r for r in self.recommendations.values() if r.nursery_id == nursery_id]
        if status is not None:
            matching = [r for r in matching if r.status == status]
        matching.sort(key=lambda r: r.created_at, reverse=True)
        total = len(matching)
        return matching[offset : offset + limit], total


class FakeAIAssistantConversationRepository:
    def __init__(self) -> None:
        self.conversations: dict[uuid.UUID, AIAssistantConversation] = {}

    async def add(self, conversation: AIAssistantConversation) -> AIAssistantConversation:
        if conversation.id is None:
            conversation.id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        if conversation.created_at is None:
            conversation.created_at = now
        if conversation.updated_at is None:
            conversation.updated_at = now
        self.conversations[conversation.id] = conversation
        return conversation

    async def get_by_id(self, conversation_id: uuid.UUID) -> AIAssistantConversation | None:
        return self.conversations.get(conversation_id)

    async def list_for_user(
        self, user_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[AIAssistantConversation], int]:
        matching = [c for c in self.conversations.values() if c.user_id == user_id]
        matching.sort(key=lambda c: c.updated_at, reverse=True)
        total = len(matching)
        return matching[offset : offset + limit], total


class FakeAIAssistantMessageRepository:
    def __init__(self) -> None:
        self.messages: dict[uuid.UUID, AIAssistantMessage] = {}

    async def add(self, message: AIAssistantMessage) -> AIAssistantMessage:
        if message.id is None:
            message.id = uuid.uuid4()
        if message.created_at is None:
            message.created_at = datetime.now(timezone.utc)
        self.messages[message.id] = message
        return message

    async def get_by_id(self, message_id: uuid.UUID) -> AIAssistantMessage | None:
        return self.messages.get(message_id)

    async def update(self, message: AIAssistantMessage) -> AIAssistantMessage:
        self.messages[message.id] = message
        return message

    async def list_for_conversation(
        self, conversation_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[AIAssistantMessage], int]:
        matching = [m for m in self.messages.values() if m.conversation_id == conversation_id]
        matching.sort(key=lambda m: m.created_at)
        total = len(matching)
        return matching[offset : offset + limit], total


class FakeKnowledgeBaseChunkRepository:
    """
    `search_similar` computes cosine similarity in pure Python -- the same
    ranking `.cosine_distance()` produces against real pgvector, just
    without the database extension, matching every other Fake repo's
    "real logic, in-memory storage" contract (this file's own module
    docstring).
    """

    def __init__(self) -> None:
        self.chunks: dict[uuid.UUID, KnowledgeBaseChunk] = {}

    async def add(self, chunk: KnowledgeBaseChunk) -> KnowledgeBaseChunk:
        if chunk.id is None:
            chunk.id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        if chunk.created_at is None:
            chunk.created_at = now
        if chunk.updated_at is None:
            chunk.updated_at = now
        self.chunks[chunk.id] = chunk
        return chunk

    async def get_by_id(self, chunk_id: uuid.UUID) -> KnowledgeBaseChunk | None:
        return self.chunks.get(chunk_id)

    async def search_similar(
        self, embedding: list[float], *, nursery_id: uuid.UUID | None, limit: int
    ) -> list[KnowledgeBaseChunk]:
        def cosine_distance(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b, strict=False))
            norm_a = sum(x * x for x in a) ** 0.5
            norm_b = sum(y * y for y in b) ** 0.5
            if norm_a == 0 or norm_b == 0:
                return 1.0
            return 1.0 - (dot / (norm_a * norm_b))

        candidates = [
            c
            for c in self.chunks.values()
            if c.source_type == "knowledge_article" or (nursery_id is not None and c.nursery_id == nursery_id)
        ]
        candidates.sort(key=lambda c: cosine_distance(embedding, c.embedding))
        return candidates[:limit]

    # --- Added by Phase 6 Module 13 ("AI Administration", RAG knowledge-base status) ---
    async def count_by_source_type(self, *, nursery_id: uuid.UUID | None = None) -> list[dict]:
        if nursery_id is not None:
            candidates = [
                c for c in self.chunks.values()
                if c.source_type == "knowledge_article" or c.nursery_id == nursery_id
            ]
        else:
            candidates = list(self.chunks.values())
        counts: dict[str, int] = {}
        for c in candidates:
            counts[c.source_type] = counts.get(c.source_type, 0) + 1
        return [{"source_type": st, "count": n} for st, n in counts.items()]

    # --- Added by RAG Ingestion Pipeline (Knowledge Article management) ---
    async def delete_by_source_ref(self, source_ref: str) -> int:
        to_delete = [
            cid for cid, c in self.chunks.items()
            if c.source_type == "knowledge_article" and c.source_ref == source_ref
        ]
        for cid in to_delete:
            del self.chunks[cid]
        return len(to_delete)

    async def get_by_source_ref(self, source_ref: str) -> list[KnowledgeBaseChunk]:
        chunks = [
            c for c in self.chunks.values()
            if c.source_type == "knowledge_article" and c.source_ref == source_ref
        ]
        chunks.sort(key=lambda c: c.created_at or datetime.min.replace(tzinfo=timezone.utc))
        return chunks

    async def list_distinct_articles(self, *, offset: int = 0, limit: int = 50) -> list[dict]:
        article_map: dict[str, dict] = {}
        for c in self.chunks.values():
            if c.source_type != "knowledge_article":
                continue
            ref = c.source_ref
            if ref not in article_map:
                article_map[ref] = {
                    "source_ref": ref,
                    "title": c.title,
                    "chunk_count": 0,
                    "created_at": c.created_at,
                }
            article_map[ref]["chunk_count"] += 1
            if c.created_at and (article_map[ref]["created_at"] is None or c.created_at < article_map[ref]["created_at"]):
                article_map[ref]["created_at"] = c.created_at
        articles = sorted(
            article_map.values(),
            key=lambda a: a["created_at"] or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return articles[offset : offset + limit]


# ======================================================================
# Phase 6 Module 11 (Notifications & Communication)
# ======================================================================


class FakeNotificationRepository:
    def __init__(self) -> None:
        self.notifications: dict[uuid.UUID, Notification] = {}

    async def add(self, notification: Notification) -> Notification:
        if notification.id is None:
            notification.id = uuid.uuid4()
        if notification.created_at is None:
            notification.created_at = datetime.now(timezone.utc)
        self.notifications[notification.id] = notification
        return notification

    async def get_by_id(self, notification_id: uuid.UUID) -> Notification | None:
        return self.notifications.get(notification_id)

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
        matching = [
            n
            for n in self.notifications.values()
            if n.recipient_user_id == user_id
            and n.nursery_id == nursery_id
            and (not unread_only or n.read_at is None)
            and (category is None or n.category == category)
        ]
        matching.sort(key=lambda n: n.created_at, reverse=True)
        total = len(matching)
        return matching[offset : offset + limit], total

    async def count_unread(self, user_id: uuid.UUID, nursery_id: uuid.UUID) -> int:
        return sum(
            1
            for n in self.notifications.values()
            if n.recipient_user_id == user_id and n.nursery_id == nursery_id and n.read_at is None
        )

    async def mark_read(self, notification: Notification, *, now: datetime) -> None:
        notification.read_at = now

    async def mark_all_read(self, user_id: uuid.UUID, nursery_id: uuid.UUID, *, now: datetime) -> int:
        count = 0
        for n in self.notifications.values():
            if n.recipient_user_id == user_id and n.nursery_id == nursery_id and n.read_at is None:
                n.read_at = now
                count += 1
        return count

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
        matching = [
            n
            for n in self.notifications.values()
            if n.nursery_id == nursery_id
            and (category is None or n.category == category)
            and (date_from is None or _aware(n.created_at) >= _aware(date_from))
            and (date_to is None or _aware(n.created_at) <= _aware(date_to))
        ]
        matching.sort(key=lambda n: n.created_at, reverse=True)
        total = len(matching)
        return matching[offset : offset + limit], total


class FakeNotificationPreferenceRepository:
    def __init__(self) -> None:
        self.preferences: dict[tuple[uuid.UUID, NotificationCategory, NotificationChannel], NotificationPreference] = {}

    async def list_for_user(self, user_id: uuid.UUID) -> list[NotificationPreference]:
        return [p for p in self.preferences.values() if p.user_id == user_id]

    async def get(
        self, user_id: uuid.UUID, category: NotificationCategory, channel: NotificationChannel
    ) -> NotificationPreference | None:
        return self.preferences.get((user_id, category, channel))

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
        key = (user_id, category, channel)
        existing = self.preferences.get(key)
        if existing is not None:
            existing.enabled = enabled
            existing.quiet_hours_start = quiet_hours_start
            existing.quiet_hours_end = quiet_hours_end
            existing.quiet_hours_timezone = quiet_hours_timezone
            if frequency is not None:
                existing.frequency = frequency
            return existing
        pref = NotificationPreference(
            id=uuid.uuid4(),
            user_id=user_id,
            category=category,
            channel=channel,
            enabled=enabled,
            quiet_hours_start=quiet_hours_start,
            quiet_hours_end=quiet_hours_end,
            quiet_hours_timezone=quiet_hours_timezone,
            frequency=frequency if frequency is not None else NotificationFrequency.IMMEDIATE,
        )
        self.preferences[key] = pref
        return pref


class FakeNotificationTemplateRepository:
    def __init__(self) -> None:
        self.templates: dict[uuid.UUID, NotificationTemplate] = {}

    async def add(self, template: NotificationTemplate) -> NotificationTemplate:
        if template.id is None:
            template.id = uuid.uuid4()
        _backfill_timestamps(template)
        self.templates[template.id] = template
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
        candidates = [
            t
            for t in self.templates.values()
            if t.nursery_id == nursery_id
            and t.category == category
            and t.channel == channel
            and t.format == format
            and t.locale == locale
            and t.is_active
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda t: t.version)

    async def list_for_org(self, nursery_id: uuid.UUID | None) -> list[NotificationTemplate]:
        return [t for t in self.templates.values() if t.nursery_id == nursery_id]


class FakeNotificationDeliveryRepository:
    def __init__(self) -> None:
        self.deliveries: dict[uuid.UUID, NotificationDelivery] = {}

    async def add(self, delivery: NotificationDelivery) -> NotificationDelivery:
        if delivery.id is None:
            delivery.id = uuid.uuid4()
        _backfill_timestamps(delivery)
        self.deliveries[delivery.id] = delivery
        return delivery

    async def get_by_id(self, delivery_id: uuid.UUID) -> NotificationDelivery | None:
        return self.deliveries.get(delivery_id)

    async def list_for_notification(self, notification_id: uuid.UUID) -> list[NotificationDelivery]:
        return [d for d in self.deliveries.values() if d.notification_id == notification_id]

    async def list_due_for_retry(self, *, now: datetime, limit: int = 100) -> list[NotificationDelivery]:
        due = [
            d
            for d in self.deliveries.values()
            if d.status == NotificationDeliveryStatus.FAILED
            and d.next_retry_at is not None
            and d.next_retry_at <= now
            and d.attempt_count < d.max_attempts
        ]
        due.sort(key=lambda d: d.next_retry_at)
        return due[:limit]

    async def list_dead_letter(self, nursery_id: uuid.UUID, *, limit: int = 100) -> list[NotificationDelivery]:
        # This fake has no join to `notifications`; callers in tests pass a
        # `nursery_id` that's only meaningful against the real repo -- unit
        # tests exercising this path seed `self.deliveries` with rows whose
        # notification is already known to belong to that org, so an
        # unfiltered dead-letter scan is equivalent for fake purposes.
        dead = [d for d in self.deliveries.values() if d.status == NotificationDeliveryStatus.DEAD_LETTER]
        return dead[:limit]

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


# --------------------------------------------------------------------------
# Phase 6 Module 12 — Reports & Analytics
# --------------------------------------------------------------------------


class FakeReportRepository:
    def __init__(self) -> None:
        self.reports: dict[uuid.UUID, Report] = {}

    async def add(self, report: Report) -> Report:
        if report.id is None:
            report.id = uuid.uuid4()
        if report.created_at is None:
            report.created_at = datetime.now(timezone.utc)
        self.reports[report.id] = report
        return report

    async def get_by_id(self, report_id: uuid.UUID) -> Report | None:
        return self.reports.get(report_id)

    async def list_for_org(
        self,
        nursery_id: uuid.UUID,
        *,
        report_type: ReportType | None = None,
        branch_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Report], int]:
        matching = [r for r in self.reports.values() if r.nursery_id == nursery_id]
        if report_type is not None:
            matching = [r for r in matching if r.report_type == report_type]
        if branch_id is not None:
            matching = [r for r in matching if r.branch_id == branch_id]
        matching.sort(key=lambda r: r.created_at, reverse=True)
        total = len(matching)
        return matching[offset : offset + limit], total

    async def update_status(
        self,
        report: Report,
        *,
        status: ReportStatus,
        file_url: str | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        report.status = status
        if file_url is not None:
            report.file_url = file_url
        if completed_at is not None:
            report.completed_at = completed_at

    async def commit(self) -> None:
        pass


class FakeScheduledReportRepository:
    def __init__(self) -> None:
        self.scheduled: dict[uuid.UUID, ScheduledReport] = {}

    async def add(self, scheduled: ScheduledReport) -> ScheduledReport:
        if scheduled.id is None:
            scheduled.id = uuid.uuid4()
        if scheduled.created_at is None:
            scheduled.created_at = datetime.now(timezone.utc)
        self.scheduled[scheduled.id] = scheduled
        return scheduled

    async def get_by_id(self, scheduled_id: uuid.UUID) -> ScheduledReport | None:
        return self.scheduled.get(scheduled_id)

    async def list_for_org(self, nursery_id: uuid.UUID) -> list[ScheduledReport]:
        matching = [s for s in self.scheduled.values() if s.nursery_id == nursery_id]
        matching.sort(key=lambda s: s.created_at, reverse=True)
        return matching

    async def list_due(self, *, now: datetime, limit: int = 100) -> list[ScheduledReport]:
        due = [s for s in self.scheduled.values() if s.is_active and _aware(s.next_run_at) <= _aware(now)]
        due.sort(key=lambda s: s.next_run_at)
        return due[:limit]

    async def update_after_run(self, scheduled: ScheduledReport, *, last_run_at: datetime, next_run_at: datetime) -> None:
        scheduled.last_run_at = last_run_at
        scheduled.next_run_at = next_run_at

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

    async def set_active(self, scheduled: ScheduledReport, *, is_active: bool) -> None:
        scheduled.is_active = is_active

    async def delete(self, scheduled: ScheduledReport) -> None:
        self.scheduled.pop(scheduled.id, None)


class FakeReportingRepository:
    """
    This module's CQRS read side, faked. The real `SqlAlchemyReportingRepository`
    reads pre-aggregated rows straight out of migrations 0005/0017's
    materialized views/views (`mv_branch_dashboard_summary`,
    `mv_org_revenue_rollup`, `mv_nursery_dashboard_summary`,
    `mv_ai_prediction_accuracy`, `v_customer_lifetime_value`) or runs a
    purpose-built `GROUP BY` aggregate against the operational tables --
    there is no equivalent view to "SELECT * FROM" against an in-memory
    fake, so every dashboard/analytics method here recomputes the same
    aggregation in pure Python against the *other* fakes' live dicts.

    Takes constructor references to every other fake repository whose data
    it needs to aggregate over, extending the same precedent
    `FakeGrowthTimelineRepository(plant_repo)` / `FakeStockMovementRepository
    (inventory_repo)` / `FakeDiseaseReportRepository(plant_repo)` already
    established above: sharing the live dict the harness already populates
    is simpler and less error-prone than this fake maintaining its own
    duplicate copy that could drift out of sync with what a test actually
    seeded into `FakePlantRepository.plants`, `FakeSaleRepository.sales`, etc.
    """

    def __init__(
        self,
        *,
        plant_repo: "FakePlantRepository",
        species_repo: "FakeSpeciesRepository",
        inventory_repo: "FakeInventoryRepository",
        stock_movement_repo: "FakeStockMovementRepository",
        sale_repo: "FakeSaleRepository",
        sale_item_repo: "FakeSaleItemRepository",
        invoice_repo: "FakeInvoiceRepository",
        customer_repo: "FakeCustomerRepository",
        branch_repo: "FakeBranchRepository",
        nursery_repo: "FakeNurseryRepository",
        employee_repo: "FakeEmployeeRepository",
        growth_timeline_repo: "FakeGrowthTimelineRepository",
        health_history_repo: "FakeHealthHistoryRepository",
        disease_report_repo: "FakeDiseaseReportRepository",
        ai_prediction_repo: "FakeAIPredictionRepository",
    ) -> None:
        self._plant_repo = plant_repo
        self._species_repo = species_repo
        self._inventory_repo = inventory_repo
        self._stock_movement_repo = stock_movement_repo
        self._sale_repo = sale_repo
        self._sale_item_repo = sale_item_repo
        self._invoice_repo = invoice_repo
        self._customer_repo = customer_repo
        self._branch_repo = branch_repo
        self._nursery_repo = nursery_repo
        self._employee_repo = employee_repo
        self._growth_timeline_repo = growth_timeline_repo
        self._health_history_repo = health_history_repo
        self._disease_report_repo = disease_report_repo
        self._ai_prediction_repo = ai_prediction_repo

    # ------------------------------------------------------------------
    # Internal aggregation helpers -- mirror the CTEs in migrations
    # 0005/0017's materialized view definitions exactly, so a test
    # asserting against this fake and a (hypothetical) real-Postgres run
    # would see the same numbers.
    # ------------------------------------------------------------------

    @staticmethod
    def _day_start(value: datetime) -> datetime:
        value = _aware(value)
        return value.replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def _week_start(value: datetime) -> datetime:
        # Postgres date_trunc('week', ...) truncates to the Monday of the
        # ISO week containing the value -- `weekday()` is already
        # Monday=0, so this matches without needing the `isocalendar()`
        # machinery.
        day = FakeReportingRepository._day_start(value)
        return day - timedelta(days=day.weekday())

    def _plants_for(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> list[Plant]:
        return [
            p
            for p in self._plant_repo.plants.values()
            if p.nursery_id == nursery_id and (branch_id is None or p.branch_id == branch_id)
        ]

    def _inventory_for(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> list[Inventory]:
        return [
            i
            for i in self._inventory_repo.items.values()
            if i.nursery_id == nursery_id and (branch_id is None or i.branch_id == branch_id)
        ]

    def _completed_sales(
        self,
        nursery_id: uuid.UUID,
        branch_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[Sale]:
        matching = [
            s
            for s in self._sale_repo.sales.values()
            if s.nursery_id == nursery_id and s.status == SaleStatus.COMPLETED
        ]
        if branch_id is not None:
            matching = [s for s in matching if s.branch_id == branch_id]
        if date_from is not None:
            matching = [s for s in matching if _aware(s.created_at) >= _aware(date_from)]
        if date_to is not None:
            matching = [s for s in matching if _aware(s.created_at) <= _aware(date_to)]
        return matching

    def _latest_survival_prediction_per_plant(self) -> dict[uuid.UUID, AIPrediction]:
        latest: dict[uuid.UUID, AIPrediction] = {}
        for pred in self._ai_prediction_repo.predictions.values():
            if pred.prediction_type != AIPredictionType.SURVIVAL_PREDICTION or pred.plant_id is None:
                continue
            existing = latest.get(pred.plant_id)
            if existing is None or _aware(pred.created_at) > _aware(existing.created_at):
                latest[pred.plant_id] = pred
        return latest

    def _open_disease_report_count(self, plant_ids: set[uuid.UUID]) -> int:
        open_statuses = {DiseaseReportStatus.DRAFT, DiseaseReportStatus.CONFIRMED}
        return sum(
            1
            for r in self._disease_report_repo.reports.values()
            if r.plant_id in plant_ids and r.status in open_statuses
        )

    def _branch_summary(self, branch: Branch) -> dict:
        now = datetime.now(timezone.utc)
        today_sales = self._completed_sales(branch.nursery_id, branch.id, self._day_start(now), None)
        mtd_sales = self._completed_sales(
            branch.nursery_id, branch.id, now.replace(day=1, hour=0, minute=0, second=0, microsecond=0), None
        )
        latest_predictions = self._latest_survival_prediction_per_plant()
        at_risk = sum(
            1
            for pred in latest_predictions.values()
            if pred.branch_id == branch.id and (pred.result or {}).get("risk_level") in ("high", "critical")
        )
        low_stock = sum(1 for i in self._inventory_for(branch.nursery_id, branch.id) if i.quantity <= i.low_stock_threshold)
        branch_plant_ids = {p.id for p in self._plants_for(branch.nursery_id, branch.id)}
        pending_disease = self._open_disease_report_count(branch_plant_ids)
        return {
            "branch_id": branch.id,
            "nursery_id": branch.nursery_id,
            "branch_name": branch.name,
            "revenue_today": sum((s.total_amount for s in today_sales), 0),
            "revenue_mtd": sum((s.total_amount for s in mtd_sales), 0),
            "at_risk_plant_count": at_risk,
            "low_stock_count": low_stock,
            "pending_disease_reports": pending_disease,
            "last_refreshed_at": now,
        }

    def _nursery_summary(self, nursery_id: uuid.UUID) -> dict:
        now = datetime.now(timezone.utc)
        plants = self._plants_for(nursery_id)
        active_plants = [p for p in plants if p.status not in (PlantStatus.DECEASED, PlantStatus.SOLD)]
        active_branches = [
            b for b in self._branch_repo.branches.values() if b.nursery_id == nursery_id and b.status == BranchStatus.ACTIVE
        ]
        active_employees = [
            e for e in self._employee_repo.employees.values() if e.nursery_id == nursery_id and e.status == EmployeeStatus.ACTIVE
        ]
        low_stock = sum(1 for i in self._inventory_for(nursery_id) if i.quantity <= i.low_stock_threshold)
        plant_ids = {p.id for p in plants}
        pending_disease = self._open_disease_report_count(plant_ids)
        return {
            "nursery_id": nursery_id,
            "total_plants": len(plants),
            "active_plant_count": len(active_plants),
            "branch_count": len(active_branches),
            "employee_count": len(active_employees),
            "low_stock_count": low_stock,
            "pending_disease_reports": pending_disease,
            "last_refreshed_at": now,
        }

    def _customer_lifetime_rows(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> list[dict]:
        customers = [
            c
            for c in self._customer_repo.customers.values()
            if c.nursery_id == nursery_id and (branch_id is None or c.branch_id == branch_id)
        ]
        rows = []
        for c in customers:
            orders = [
                s for s in self._sale_repo.sales.values() if s.customer_id == c.id and s.status == SaleStatus.COMPLETED
            ]
            rows.append(
                {
                    "customer_id": c.id,
                    "nursery_id": c.nursery_id,
                    "branch_id": c.branch_id,
                    "customer_name": c.name,
                    "total_orders": len(orders),
                    "total_spent": sum((s.total_amount for s in orders), 0),
                    "first_purchase_at": min((s.created_at for s in orders), default=None),
                    "last_purchase_at": max((s.created_at for s in orders), default=None),
                }
            )
        return rows

    # ------------------------------------------------------------------
    # Dashboards
    # ------------------------------------------------------------------

    async def executive_dashboard(self, nursery_id: uuid.UUID) -> dict:
        nursery_row = self._nursery_summary(nursery_id)
        branch_rows = [
            self._branch_summary(b)
            for b in self._branch_repo.branches.values()
            if b.nursery_id == nursery_id and b.status == BranchStatus.ACTIVE
        ]
        branch_rows.sort(
            key=lambda r: r["at_risk_plant_count"] + r["low_stock_count"] + r["pending_disease_reports"], reverse=True
        )
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)
        recent_sales = self._completed_sales(nursery_id, None, thirty_days_ago, None)
        by_day: dict[datetime, dict] = {}
        for s in recent_sales:
            day = self._day_start(s.created_at)
            entry = by_day.setdefault(day, {"day": day, "revenue": 0, "sale_count": 0})
            entry["revenue"] += s.total_amount
            entry["sale_count"] += 1
        revenue_trend = [by_day[d] for d in sorted(by_day)]
        return {
            "revenue_today": sum((r["revenue_today"] for r in branch_rows), 0),
            "revenue_mtd": sum((r["revenue_mtd"] for r in branch_rows), 0),
            "active_plant_count": nursery_row["active_plant_count"],
            "at_risk_plant_count": sum((r["at_risk_plant_count"] for r in branch_rows), 0),
            "open_disease_reports": sum((r["pending_disease_reports"] for r in branch_rows), 0),
            "branches": branch_rows,
            "revenue_trend": revenue_trend,
            "last_refreshed_at": nursery_row["last_refreshed_at"],
        }

    async def nursery_dashboard(self, nursery_id: uuid.UUID) -> dict:
        return self._nursery_summary(nursery_id)

    async def branch_dashboard(self, nursery_id: uuid.UUID, branch_id: uuid.UUID) -> dict:
        branch = self._branch_repo.branches.get(branch_id)
        if branch is None or branch.nursery_id != nursery_id:
            return {}
        return self._branch_summary(branch)

    async def plant_dashboard(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict:
        plants = self._plants_for(nursery_id, branch_id)
        by_status: dict[str, int] = {}
        for p in plants:
            by_status[p.status.value] = by_status.get(p.status.value, 0) + 1
        by_species_counts: dict[uuid.UUID, int] = {}
        for p in plants:
            by_species_counts[p.species_id] = by_species_counts.get(p.species_id, 0) + 1
        ranked = sorted(by_species_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
        by_species = [
            {"species": self._species_repo.species[sid].common_name if sid in self._species_repo.species else None, "count": c}
            for sid, c in ranked
        ]
        return {"by_status": by_status, "by_species": by_species}

    async def inventory_dashboard(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict:
        items = self._inventory_for(nursery_id, branch_id)
        total_units = sum((i.quantity for i in items), 0)
        total_value = sum((i.quantity * (i.unit_cost or 0) for i in items), 0)
        low_stock_items = sorted(
            (i for i in items if i.quantity <= i.low_stock_threshold), key=lambda i: i.quantity
        )[:20]
        return {
            "total_line_items": len(items),
            "total_units_on_hand": int(total_units),
            "total_inventory_value": total_value,
            "low_stock_count": len(low_stock_items),
            "low_stock_items": [
                {"id": i.id, "name": i.name, "quantity": i.quantity, "low_stock_threshold": i.low_stock_threshold}
                for i in low_stock_items
            ],
        }

    async def sales_dashboard(
        self,
        nursery_id: uuid.UUID,
        branch_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict:
        sales = self._completed_sales(nursery_id, branch_id, date_from, date_to)
        total = sum((s.total_amount for s in sales), 0)
        return {
            "transaction_count": len(sales),
            "total_sales": total,
            "average_sale_value": round(float(total) / len(sales), 2) if sales else 0.0,
        }

    async def customer_dashboard(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict:
        rows = self._customer_lifetime_rows(nursery_id, branch_id)
        total_customers = len(rows)
        top_customers = sorted(rows, key=lambda r: r["total_spent"] or 0, reverse=True)[:10]
        repeat_customers = sum(1 for r in rows if (r["total_orders"] or 0) > 1)
        return {
            "total_customers": total_customers,
            "repeat_customer_count": repeat_customers,
            "repeat_customer_rate": round(repeat_customers / total_customers, 4) if total_customers else 0.0,
            "top_customers": top_customers,
        }

    async def ai_dashboard(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict:
        predictions = [
            p
            for p in self._ai_prediction_repo.predictions.values()
            if p.nursery_id == nursery_id
            and p.prediction_type == AIPredictionType.SURVIVAL_PREDICTION
            and (p.result or {}).get("risk_level") in ("high", "critical")
            and (branch_id is None or p.branch_id == branch_id)
        ]
        predictions.sort(key=lambda p: p.created_at, reverse=True)
        at_risk = []
        for p in predictions[:20]:
            plant = self._plant_repo.plants.get(p.plant_id)
            at_risk.append(
                {
                    "plant_id": p.plant_id,
                    "common_label": plant.common_label if plant else None,
                    "result": p.result,
                    "confidence": p.confidence,
                    "created_at": p.created_at,
                }
            )
        accuracy = self._ai_prediction_accuracy(nursery_id)
        return {"at_risk_plants": at_risk, "prediction_accuracy": accuracy}

    def _ai_prediction_accuracy(self, nursery_id: uuid.UUID) -> dict | None:
        scored = 0
        correct = 0
        for pred in self._ai_prediction_repo.predictions.values():
            if pred.prediction_type != AIPredictionType.SURVIVAL_PREDICTION or pred.plant_id is None:
                continue
            if pred.nursery_id != nursery_id:
                continue
            plant = self._plant_repo.plants.get(pred.plant_id)
            if plant is None:
                continue
            risk = (pred.result or {}).get("risk_level")
            is_deceased = plant.status == PlantStatus.DECEASED
            if is_deceased or risk in ("low", "medium"):
                scored += 1
                if (risk in ("high", "critical") and is_deceased) or (risk in ("low", "medium") and not is_deceased):
                    correct += 1
        if scored == 0:
            return None
        return {
            "nursery_id": nursery_id,
            "prediction_type": "survival_prediction",
            "scored_prediction_count": scored,
            "correct_prediction_count": correct,
            "last_refreshed_at": datetime.now(timezone.utc),
        }

    async def financial_dashboard(
        self,
        nursery_id: uuid.UUID,
        branch_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict:
        sales = self._completed_sales(nursery_id, branch_id, date_from, date_to)
        revenue = sum((s.total_amount for s in sales), 0)
        sale_ids = {s.id for s in sales}
        cogs = 0
        for item in self._sale_item_repo.items.values():
            if item.sale_id not in sale_ids or item.inventory_id is None:
                continue
            inv = self._inventory_repo.items.get(item.inventory_id)
            if inv is None:
                continue
            cogs += item.quantity * (inv.unit_cost or 0)
        outstanding_invoices = [
            i
            for i in self._invoice_repo.invoices.values()
            if i.nursery_id == nursery_id and i.status in (InvoiceStatus.SENT, InvoiceStatus.OVERDUE)
        ]
        return {
            "revenue": revenue,
            "estimated_cogs": cogs,
            "estimated_gross_profit": revenue - cogs,
            "estimated_gross_margin": round(float(revenue - cogs) / float(revenue), 4) if revenue else 0.0,
            "outstanding_invoice_count": len(outstanding_invoices),
            "outstanding_invoice_total": sum((i.total_amount for i in outstanding_invoices), 0),
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
        sales = self._completed_sales(nursery_id, branch_id, date_from, date_to)
        by_day: dict[datetime, dict] = {}
        for s in sales:
            day = self._day_start(s.created_at)
            entry = by_day.setdefault(day, {"day": day, "revenue": 0, "sale_count": 0})
            entry["revenue"] += s.total_amount
            entry["sale_count"] += 1
        return [by_day[d] for d in sorted(by_day)]

    async def growth_trend(
        self,
        nursery_id: uuid.UUID,
        branch_id: uuid.UUID | None,
        species_id: uuid.UUID | None,
        date_from: datetime,
        date_to: datetime,
    ) -> list[dict]:
        plant_ids = {
            p.id
            for p in self._plants_for(nursery_id, branch_id)
            if species_id is None or p.species_id == species_id
        }
        rows = [
            r
            for r in self._growth_timeline_repo.rows.values()
            if r.plant_id in plant_ids and _aware(date_from) <= _aware(r.recorded_at) <= _aware(date_to)
        ]
        by_week: dict[datetime, list] = {}
        for r in rows:
            week = self._week_start(r.recorded_at)
            by_week.setdefault(week, []).append(r)
        result = []
        for week in sorted(by_week):
            entries = by_week[week]
            heights = [float(e.height_cm) for e in entries if e.height_cm is not None]
            result.append(
                {
                    "week": week,
                    "average_height_cm": round(sum(heights) / len(heights), 2) if heights else None,
                    "record_count": len(entries),
                }
            )
        return result

    async def inventory_trend(
        self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None, date_from: datetime, date_to: datetime
    ) -> list[dict]:
        inventory_ids = {i.id for i in self._inventory_for(nursery_id, branch_id)}
        movements = [
            m
            for m in self._stock_movement_repo.movements.values()
            if m.inventory_id in inventory_ids and _aware(date_from) <= _aware(m.created_at) <= _aware(date_to)
        ]
        by_key: dict[tuple[datetime, str], int] = {}
        for m in movements:
            day = self._day_start(m.created_at)
            key = (day, m.movement_type)
            by_key[key] = by_key.get(key, 0) + m.quantity_delta
        result = [
            {"day": day, "movement_type": mt.value, "net_quantity_delta": qty}
            for (day, mt), qty in sorted(by_key.items(), key=lambda kv: kv[0][0])
        ]
        return result

    async def plant_health_trend(
        self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None, date_from: datetime, date_to: datetime
    ) -> list[dict]:
        plant_ids = {p.id for p in self._plants_for(nursery_id, branch_id)}
        rows = [
            r
            for r in self._health_history_repo.rows.values()
            if r.plant_id in plant_ids and _aware(date_from) <= _aware(r.recorded_at) <= _aware(date_to)
        ]
        by_key: dict[tuple[datetime, str], int] = {}
        for r in rows:
            week = self._week_start(r.recorded_at)
            key = (week, r.status_label)
            by_key[key] = by_key.get(key, 0) + 1
        return [
            {"week": week, "health_status": status, "count": count}
            for (week, status), count in sorted(by_key.items(), key=lambda kv: kv[0][0])
        ]

    async def sales_forecast(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> list[dict]:
        matching = [
            p
            for p in self._ai_prediction_repo.predictions.values()
            if p.nursery_id == nursery_id
            and p.prediction_type == AIPredictionType.REVENUE_FORECAST
            and (branch_id is None or p.branch_id == branch_id)
        ]
        if not matching:
            return []
        latest = max(matching, key=lambda p: p.created_at)
        return [
            {
                "id": latest.id,
                "branch_id": latest.branch_id,
                "result": latest.result,
                "confidence": latest.confidence,
                "created_at": latest.created_at,
            }
        ]

    async def disease_trend(
        self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None, date_from: datetime, date_to: datetime
    ) -> list[dict]:
        plant_ids = {p.id for p in self._plants_for(nursery_id, branch_id)}
        rows = [
            r
            for r in self._disease_report_repo.reports.values()
            if r.plant_id in plant_ids and _aware(date_from) <= _aware(r.created_at) <= _aware(date_to)
        ]
        by_key: dict[tuple[datetime, str], int] = {}
        for r in rows:
            week = self._week_start(r.created_at)
            key = (week, r.severity)
            by_key[key] = by_key.get(key, 0) + 1
        return [
            {"week": week, "severity": severity.value, "count": count}
            for (week, severity), count in sorted(by_key.items(), key=lambda kv: kv[0][0])
        ]

    async def customer_analytics(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict:
        return await self.customer_dashboard(nursery_id, branch_id)

    async def employee_productivity(
        self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None, date_from: datetime, date_to: datetime
    ) -> list[dict]:
        sales = self._completed_sales(nursery_id, branch_id, date_from, date_to)
        by_user: dict[uuid.UUID, dict] = {}
        for s in sales:
            entry = by_user.setdefault(s.sold_by_user_id, {"user_id": s.sold_by_user_id, "sale_count": 0, "total_sales": 0})
            entry["sale_count"] += 1
            entry["total_sales"] += s.total_amount
        return sorted(by_user.values(), key=lambda e: e["total_sales"], reverse=True)

    async def branch_performance(self, nursery_id: uuid.UUID) -> list[dict]:
        rows = [
            self._branch_summary(b)
            for b in self._branch_repo.branches.values()
            if b.nursery_id == nursery_id
        ]
        rows.sort(key=lambda r: r["revenue_mtd"], reverse=True)
        return rows


# ======================================================================
# Phase 6 Module 13 (Administration & System Management)
# ======================================================================


class FakeFeatureFlagRepository:
    def __init__(self) -> None:
        self.flags: dict[uuid.UUID, FeatureFlag] = {}

    async def resolve(
        self, key: str, *, nursery_id: uuid.UUID | None, branch_id: uuid.UUID | None
    ) -> FeatureFlag | None:
        if branch_id is not None:
            for f in self.flags.values():
                if f.key == key and f.branch_id == branch_id:
                    return f
        if nursery_id is not None:
            for f in self.flags.values():
                if f.key == key and f.nursery_id == nursery_id and f.branch_id is None:
                    return f
        for f in self.flags.values():
            if f.key == key and f.nursery_id is None and f.branch_id is None:
                return f
        return None

    async def list_all(self, *, nursery_id: uuid.UUID | None = None) -> list[FeatureFlag]:
        return [
            f for f in self.flags.values()
            if f.nursery_id is None or (nursery_id is not None and f.nursery_id == nursery_id)
        ]

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
        for f in self.flags.values():
            if f.key == key and f.nursery_id == nursery_id and f.branch_id == branch_id:
                f.is_enabled = is_enabled
                f.description = description
                f.updated_by_user_id = updated_by_user_id
                return f
        flag = FeatureFlag(
            id=uuid.uuid4(),
            key=key,
            nursery_id=nursery_id,
            branch_id=branch_id,
            is_enabled=is_enabled,
            description=description,
            updated_by_user_id=updated_by_user_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.flags[flag.id] = flag
        return flag


class FakeSystemConfigRepository:
    def __init__(self) -> None:
        self.configs: dict[str, SystemConfig] = {}  # key -> SystemConfig

    async def get(self, key: str) -> SystemConfig | None:
        return self.configs.get(key)

    async def list_all(self, *, category: str | None = None) -> list[SystemConfig]:
        rows = list(self.configs.values())
        if category is not None:
            rows = [r for r in rows if r.category == category]
        return sorted(rows, key=lambda r: (r.category, r.key))

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
        existing = self.configs.get(key)
        if existing is not None:
            existing.value = value
            existing.value_type = value_type
            existing.category = category
            existing.description = description
            existing.updated_by_user_id = updated_by_user_id
            return existing
        config = SystemConfig(
            id=uuid.uuid4(),
            key=key,
            value=value,
            value_type=value_type,
            category=category,
            description=description,
            updated_by_user_id=updated_by_user_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.configs[key] = config
        return config


class FakeAIInferenceFailureRepository:
    def __init__(self) -> None:
        self.failures: list[AIInferenceFailure] = []

    async def add(self, failure: AIInferenceFailure) -> AIInferenceFailure:
        if failure.id is None:
            failure.id = uuid.uuid4()
        if failure.created_at is None:
            failure.created_at = datetime.now(timezone.utc)
        self.failures.append(failure)
        return failure

    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int, capability: str | None = None
    ) -> tuple[list[AIInferenceFailure], int]:
        matching = [f for f in self.failures if f.nursery_id == nursery_id]
        if capability is not None:
            matching = [f for f in matching if f.capability == capability]
        matching.sort(key=lambda f: f.created_at, reverse=True)
        return matching[offset : offset + limit], len(matching)
