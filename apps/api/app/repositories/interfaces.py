"""
Repository interfaces (structural `Protocol`s, not ABCs) for Module 2.
`AuthService` depends on these, not on SQLAlchemy directly — the real
implementations (app/repositories/sqlalchemy_repositories.py) and the
in-memory test fakes (tests/fakes/repositories.py) both satisfy the same
protocol, so the service's business logic (lockout, rotation, replay
detection) is unit-testable without a database connection while still
being the exact same code path production runs.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from app.db.enums import (
    AIPredictionType,
    AIRecommendationStatus,
    CustomerType,
    DiseaseReportSeverity,
    DiseaseReportStatus,
    EmployeeStatus,
    EventDispatchStatus,
    InvoiceStatus,
    NotificationCategory,
    NotificationChannel,
    NotificationDeliveryStatus,
    PlantStatus,
    QuotationStatus,
    RefundStatus,
    ReportScheduleFrequency,
    ReportStatus,
    ReportType,
    ReturnStatus,
    SalesOrderStatus,
    SecurityEventType,
    StockMovementType,
    StockReservationStatus,
)

from app.models.ai import AIAssistantConversation, AIAssistantMessage, AIPrediction, AIRecommendation, KnowledgeBaseChunk
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
from app.models.identity import Invite, Permission, Role, RoleAssignment, User
from app.models.inventory import Inventory, InventoryLocation, StockMovement, StockReservation
from app.models.notifications import Notification, NotificationDelivery, NotificationPreference, NotificationTemplate
from app.models.organization import Branch, Employee, Nursery
from app.models.plants import Plant, PlantImage, PlantTransfer
from app.models.platform import AuditLog, FeatureFlag, OrgSettings, SystemConfig
from app.models.purchasing import Supplier
from app.models.reports import Passport, QRScanEvent, Report, ScheduledReport
from app.models.ai import AIInferenceFailure


class UserRepository(Protocol):
    async def get_by_id(self, user_id: uuid.UUID) -> User | None: ...
    async def get_by_email(self, email: str) -> User | None: ...
    async def add(self, user: User) -> User: ...

    async def commit(self) -> None:
        """
        Persists accumulated session state *before* the caller raises.

        The request-level session (app/db/session.py's `get_db_session`)
        rolls back on any exception, which is normally exactly right --
        but `AuthService._register_failed_attempt` mutates
        `failed_login_attempts`/`locked_until` and then lets `login()`
        raise the (deliberately generic) wrong-password error. Without an
        explicit commit here that counter would be rolled back with the
        error, so the lockout threshold could never actually be reached.
        """
        ...

    # --- Added by Phase 6 Module 13 (Administration & System Management,
    # "User Administration") ---
    async def list_for_ids(self, user_ids: list[uuid.UUID]) -> list[User]:
        """
        Batch fetch, unordered. Backs `UserAdminService`'s org-scoped user
        search: `EmployeeRepository.list_for_nursery` already returns the
        page of `Employee` rows for an org (the tenant-scoping join point,
        since `users` itself carries no `nursery_id` -- see auth.py's own
        docstring on why), and this resolves their `User` records in one
        round trip rather than N+1 `get_by_id` calls.
        """
        ...

    async def set_active(self, user: User, *, is_active: bool) -> User:
        """Admin-initiated account activate/deactivate -- distinct from `Employee.status` (org membership), this flips the login-capable flag on the identity itself."""
        ...

    async def set_locked_until(self, user: User, *, locked_until: datetime | None) -> User:
        """Admin-initiated lock/unlock. `None` unlocks immediately, independent of the self-service lockout-expiry clock `AuthService._register_failed_attempt` sets."""
        ...

    async def reset_failed_login_attempts(self, user: User) -> User:
        """Zeroes the strike counter -- paired with `set_locked_until(None)` for a clean admin-initiated unlock (an unlock that left the counter primed at the lockout threshold would re-lock on the next single failed attempt)."""
        ...


class RefreshTokenRepository(Protocol):
    async def add(self, token: RefreshToken) -> RefreshToken: ...
    async def get_by_hash(self, token_hash: str) -> RefreshToken | None: ...
    async def list_active_for_user(self, user_id: uuid.UUID) -> list[RefreshToken]: ...
    async def revoke(self, token: RefreshToken, *, now: datetime) -> None: ...
    async def revoke_family(self, family_id: uuid.UUID, *, now: datetime) -> None: ...
    async def revoke_all_for_user(self, user_id: uuid.UUID, *, now: datetime) -> None: ...


class EmailVerificationTokenRepository(Protocol):
    async def add(self, token: EmailVerificationToken) -> EmailVerificationToken: ...
    async def get_by_hash(self, token_hash: str) -> EmailVerificationToken | None: ...
    async def mark_used(self, token: EmailVerificationToken, *, now: datetime) -> None: ...


class PasswordResetTokenRepository(Protocol):
    async def add(self, token: PasswordResetToken) -> PasswordResetToken: ...
    async def get_by_hash(self, token_hash: str) -> PasswordResetToken | None: ...
    async def mark_used(self, token: PasswordResetToken, *, now: datetime) -> None: ...


class SecurityEventRepository(Protocol):
    async def log(self, event: SecurityEvent) -> None: ...
    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[SecurityEvent], int]:
        """
        Added by Phase 6 Module 12 (Security Reports). `security_events`
        carries no `nursery_id` of its own -- deliberately: these rows are
        written for pre-authentication events (failed logins against an
        email with no matching account included) where no org context can
        exist yet (see that model's own docstring). Scoped here to "events
        whose `user_id` is an Employee of this nursery" (a join through
        `employees`, resolved at the `user_id` level since one user can be
        an Employee of more than one nursery) -- the closest honest
        approximation of "this org's security events" the schema supports,
        the same disclosed-limitation pattern this module's Financial
        Dashboard COGS estimate already established for an analogous gap.
        Newest first.
        """
        ...

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
        """The filterable counterpart to `list_for_nursery`, same org-scoping approximation and caveats -- see that method's own docstring."""
        ...

    async def list_all(
        self,
        *,
        offset: int,
        limit: int,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        event_type: SecurityEventType | None = None,
    ) -> tuple[list[SecurityEvent], int]:
        """
        Platform-wide, every org -- backs the `platform_admin`-only cross-
        tenant security event view (Section 8's "administrative actions"
        oversight, exercised with `target_nursery_id=None` the same way
        Module 12's report catalog route already established for a
        genuinely org-agnostic read). Never exposed to an org-scoped
        caller.
        """
        ...


class PermissionRepository(Protocol):
    """
    Backs RBAC role/permission resolution (Module 2's Authorization
    section — "permissions must come from the database, not hardcoded").
    """

    async def get_role_assignment_for_user(self, user_id: uuid.UUID) -> RoleAssignment | None: ...
    async def list_role_assignments_for_user(self, user_id: uuid.UUID) -> list[RoleAssignment]:
        """
        Every RoleAssignment a user holds (today: 0 or 1, per v1's one-org-
        per-user application-layer constraint — see RoleAssignment's
        docstring). Module 3's "multi-role support (future ready)" hook:
        the resolver already knows how to fold multiple assignments into
        one ResolvedAccess; the schema doesn't need to change for that
        future to arrive, only this method's result needs to start
        returning more than one row.
        """
        ...
    async def get_role_with_permissions(self, role_id: uuid.UUID) -> Role | None: ...
    async def get_branch_scope_ids(self, role_assignment_id: uuid.UUID) -> list[uuid.UUID]: ...

    # --- Added by Phase 6 Module 11 (Notifications) ---
    async def list_users_with_permission(
        self, nursery_id: uuid.UUID, permission_code: str, *, branch_id: uuid.UUID | None = None
    ) -> list[uuid.UUID]:
        """
        The reverse of every other lookup on this Protocol: given a
        permission code, which users in this org hold it. Backs
        `NotificationEventHandler` recipient resolution (docs/ux/14-notification-workflow.md's
        "Recipient Resolution Rules" — e.g. "notify everyone with
        `inventory:write` in this branch" for a Low Stock Alert).

        `branch_id=None` returns every user holding the permission org-wide
        (an org-wide RoleAssignment has no branch_scopes rows at all, per
        RoleAssignmentBranchScope's own "absent rows == every branch"
        docstring — those rows always match regardless of `branch_id`).
        `branch_id` set additionally includes users whose RoleAssignment is
        branch-scoped to that specific branch. A user with two qualifying
        assignments (shouldn't happen under v1's one-org-per-user
        constraint, but not schema-enforced) is returned once.
        """
        ...

    # --- Added by Phase 6 Module 4 (Nursery & Organization Management) ---
    async def get_system_role_by_code(self, code: str) -> Role | None:
        """
        Resolves one of the six seeded system roles (nursery_id IS NULL)
        by its code -- backs invite creation ("assign this role") and
        ownership transfer ("find the owner role"). v1 is staff-only,
        system-roles-only (the same scope decision Module 2 made for
        RBAC generally, docs/architecture/18-module2-authentication.md);
        custom, per-org roles (Growth/Enterprise tier, `Role`'s own
        docstring) are out of scope for this lookup.
        """
        ...

    async def create_assignment(
        self, *, user_id: uuid.UUID, nursery_id: uuid.UUID, role_id: uuid.UUID
    ) -> RoleAssignment:
        """Provisions a new RoleAssignment -- used once, at invite acceptance (an Employee gets exactly one per v1's one-org-per-user constraint)."""
        ...

    async def add_assignment_branch_scope(self, role_assignment_id: uuid.UUID, branch_id: uuid.UUID) -> None: ...

    async def replace_assignment_branch_scopes(
        self, role_assignment_id: uuid.UUID, branch_ids: list[uuid.UUID]
    ) -> None:
        """
        Atomically replaces every branch_scopes row for a RoleAssignment
        with a new set -- backs "Transfer Staff"/"Branch Reassignment".
        An empty `branch_ids` list produces zero rows, i.e. transfers the
        employee to an org-wide role scope (see `ResolvedAccess.is_org_wide()`).
        """
        ...

    async def delete_assignment(self, role_assignment_id: uuid.UUID) -> None:
        """Revokes all access -- backs "Remove Staff". Cascades to branch_scopes (ON DELETE CASCADE)."""
        ...

    # --- Added by Phase 6 Module 13 (Administration & System Management,
    # "Role & Permission Administration") ---
    async def list_roles(self, *, nursery_id: uuid.UUID | None = None) -> list[Role]:
        """
        System roles (`nursery_id IS NULL`) plus this org's own custom
        roles, if any (`Role`'s own docstring: custom roles are a Growth/
        Enterprise-tier feature this codebase has the column for but no
        creation path -- v1 never produces one, so this in practice always
        returns exactly the six seeded system roles today; the method
        still takes `nursery_id` so a future custom-role creation feature
        doesn't need a repository change, only a caller change).
        """
        ...

    async def list_permissions(self) -> list[Permission]:
        """The full, global permission catalog (`permissions` table) -- read-only reference data, never created/edited through the API (see this Protocol's own module docstring: "permissions must come from the database, not hardcoded" describes where they live, not that they're admin-editable)."""
        ...

    async def list_role_permission_codes(self, role_id: uuid.UUID) -> list[tuple[str, str]]:
        """Every `(permission_code, scope)` pair granted to one role -- the admin-facing role-permission matrix view for a single role, without loading the full `Role.permissions` relationship's ORM objects."""
        ...

    async def set_assignment_role(self, assignment: RoleAssignment, *, role_id: uuid.UUID) -> RoleAssignment:
        """
        Changes an existing RoleAssignment's role in place (its branch_scopes
        rows are left untouched) -- the "user-role assignment" edit path.
        Distinct from `delete_assignment` + `create_assignment` (which would
        also require the caller to re-supply branch scopes, and briefly
        leaves the user with zero access in between two calls); this is the
        atomic single-step equivalent Module 13 introduces because nothing
        before it ever needed to *change* an existing assignment's role,
        only create or revoke one. Takes the already-fetched ORM object
        (the caller resolved it via `get_role_assignment_for_user` to
        verify it exists and belongs to the expected org first), matching
        every other mutator on this Protocol (`add_assignment_branch_scope`,
        `replace_assignment_branch_scopes`) that operates on a live object
        or id the caller has already validated, never re-validating
        existence itself.
        """
        ...


class InviteRepository(Protocol):
    async def get_by_token(self, token: str) -> Invite | None: ...
    async def mark_accepted(self, invite: Invite, *, now: datetime) -> None: ...

    # --- Added by Phase 6 Module 4 ---
    async def add(self, invite: Invite) -> Invite: ...
    async def get_by_id(self, invite_id: uuid.UUID) -> Invite | None: ...
    async def get_pending_by_email_and_nursery(self, nursery_id: uuid.UUID, email: str) -> Invite | None:
        """An un-accepted, unexpired invite for this email in this org, if one exists -- prevents duplicate invites."""
        ...
    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[Invite], int]: ...
    async def get_branch_scope_ids(self, invite_id: uuid.UUID) -> list[uuid.UUID]: ...
    async def add_branch_scope(self, invite_id: uuid.UUID, branch_id: uuid.UUID) -> None: ...


class NurseryRepository(Protocol):
    """Backs Module 4's Organization Management (create/update/archive Nursery, settings)."""

    async def get_by_id(self, nursery_id: uuid.UUID) -> Nursery | None: ...
    async def add(self, nursery: Nursery) -> Nursery: ...
    async def get_settings(self, nursery_id: uuid.UUID) -> OrgSettings | None: ...
    async def create_settings(self, settings: OrgSettings) -> OrgSettings: ...


class BranchRepository(Protocol):
    """Backs Module 4's Branch Management (create/update/archive Branch)."""

    async def get_by_id(self, branch_id: uuid.UUID) -> Branch | None: ...
    async def get_by_name(self, nursery_id: uuid.UUID, name: str) -> Branch | None: ...
    async def add(self, branch: Branch) -> Branch: ...
    async def list_for_nursery(self, nursery_id: uuid.UUID, *, include_inactive: bool = False) -> list[Branch]: ...


class EmployeeRepository(Protocol):
    """Backs Module 4's Employee Management (profile, status, lifecycle)."""

    async def get_by_id(self, employee_id: uuid.UUID) -> Employee | None: ...
    async def get_by_user_and_nursery(self, user_id: uuid.UUID, nursery_id: uuid.UUID) -> Employee | None: ...
    async def add(self, employee: Employee) -> Employee: ...
    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int, status: EmployeeStatus | None = None
    ) -> tuple[list[Employee], int]: ...


class AuthorizationDenialRepository(Protocol):
    """Backs Module 3's authorization-failure audit trail."""

    async def log(self, denial: AuthorizationDenial) -> None: ...

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
        """Newest-first, scoped to `nursery_id` -- the read side this table never had before Module 13 (Module 3 only ever wrote to it)."""
        ...


class AuditLogRepository(Protocol):
    """
    Read-only access to Phase 5's immutable `audit_logs` table, scoped to
    a single org -- backs the `GET /api/v1/audit-log` viewer endpoint,
    which is itself the module's worked example of the full authorization
    stack (permission check + tenant isolation + caching) protecting a
    real, useful capability rather than only a synthetic test route.
    """

    async def list_for_org(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[AuditLog], int]:
        """Returns (page of rows newest-first, total matching row count)."""
        ...

    async def log(self, entry: AuditLog) -> AuditLog:
        """
        Added by Phase 6 Module 4: the write side. Module 3's route only
        ever *read* `audit_logs` (populated, until now, by nothing) --
        Module 4's Organization/Branch/Employee services are this
        codebase's first real writers of business-mutation audit rows,
        fulfilling Phase 5's FR-19 in practice, not just in schema.
        """
        ...

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
        """
        The filterable admin search behind `list_for_org` (which remains
        the simple, filterless viewer Module 3 originally built). Every
        filter is optional and AND-combined; `None` means "don't filter on
        this field". Newest first, same as `list_for_org`.
        """
        ...


class DomainEventRepository(Protocol):
    """
    Backs Module 4's `DomainEventPublisher` (app/domain_events/publisher.py)
    -- persistence for the `domain_events` outbox table.

    `get_by_id`/`list_for_aggregate` were added by Phase 6 Module 7 (Plant
    Digital Twin Engine) -- the event-driven projector and its replay
    capability are both, fundamentally, readers of this same outbox.
    `list_for_aggregate` always orders by `sequence` (the BIGSERIAL added
    by migration 0011), never `occurred_at` -- see that migration's
    docstring for why `occurred_at` alone can't be trusted as a total
    order.
    """

    async def add(self, event: DomainEvent) -> DomainEvent: ...
    async def get_by_id(self, event_id: uuid.UUID) -> DomainEvent | None: ...
    async def list_for_aggregate(
        self, aggregate_id: uuid.UUID, *, after_sequence: int | None = None
    ) -> list[DomainEvent]:
        """
        Every event ever recorded for one aggregate (e.g. one Plant),
        oldest-first by `sequence`. `after_sequence` (exclusive) lets a
        caller resume from a known point rather than always replaying from
        the beginning -- not currently used by full replay (which always
        wants the complete history), but real for a future incremental-
        catch-up path.
        """
        ...


class PlantCategoryRepository(Protocol):
    """
    Backs Module 5's read-only access to `plant_categories` -- global
    system metadata (seeded once, migration 0002), never mutated through
    the API. Exists only so `GET /plant-categories` (needed by the Species
    create/edit form's category dropdown) doesn't reach into SQLAlchemy
    directly from the route layer.
    """

    async def list_all(self) -> list[PlantCategory]: ...
    async def get_by_id(self, category_id: uuid.UUID) -> PlantCategory | None: ...


class UnitRepository(Protocol):
    """
    Backs Module 8's read-only access to `units` -- global system metadata
    (seeded once, migration 0002), never mutated through the API. Exists
    only so `GET /units` (needed by the Inventory line create form's unit
    dropdown -- a real gap found while building 7I: `CreateInventoryLineRequest.
    unit_id` had no route a frontend could call to discover valid ids,
    unlike `category_id`'s already-existing `GET /plant-categories`) doesn't
    reach into SQLAlchemy directly from the route layer. Mirrors
    `PlantCategoryRepository` exactly.
    """

    async def list_all(self) -> list[Unit]: ...
    async def get_by_id(self, unit_id: uuid.UUID) -> Unit | None: ...


class SpeciesRepository(Protocol):
    """Backs Module 5's Species Catalog (FR-4): per-Org, shared across all Branches."""

    async def get_by_id(self, species_id: uuid.UUID) -> Species | None: ...
    async def get_by_botanical_name(self, nursery_id: uuid.UUID, botanical_name: str) -> Species | None: ...
    async def add(self, species: Species) -> Species: ...
    async def delete(self, species: Species) -> None: ...
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
        """
        `search` matches against common_name/botanical_name
        (case-insensitive substring, FR-4.4's "searched ... by name").
        `category_id`/`light_requirement` are exact-match filters
        (FR-4.4's "filtered by ... category, and care attributes").
        """
        ...
    async def count_plants_referencing(self, species_id: uuid.UUID) -> int:
        """
        Backs the `DELETE /species/{id}` referential-integrity check the
        LLD requires ahead of the DB's own `ON DELETE RESTRICT` on
        `plants.species_id` -- queries the `plants` table directly (that
        table already exists as of Phase 5; its own service/API layer is
        Module 6's, not built yet, but reading its row count for this one
        check doesn't require that layer to exist).
        """
        ...


class PlantVarietyRepository(Protocol):
    """Backs Module 5's PlantVariety (cultivar) management, nested under a Species."""

    async def get_by_id(self, variety_id: uuid.UUID) -> PlantVariety | None: ...
    async def get_by_name(self, species_id: uuid.UUID, name: str) -> PlantVariety | None: ...
    async def add(self, variety: PlantVariety) -> PlantVariety: ...
    async def delete(self, variety: PlantVariety) -> None: ...
    async def list_for_species(
        self, species_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[PlantVariety], int]: ...
    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[PlantVariety], int]:
        """Backs `GET /plant-varieties` with no `species_id` filter -- every variety across the org's whole catalog."""
        ...
    async def count_plants_referencing(self, variety_id: uuid.UUID) -> int:
        """Same referential-integrity reasoning as `SpeciesRepository.count_plants_referencing`, against `plants.variety_id`."""
        ...


# ==============================================================================
# Module 6 (Plant Lifecycle Management)
# ==============================================================================


class PlantRepository(Protocol):
    """Backs Module 6's Plant Registration/Profile/Movement/Status (FR-5)."""

    async def get_by_id(self, plant_id: uuid.UUID) -> Plant | None: ...
    async def get_by_qr_token(self, qr_code_token: str) -> Plant | None:
        """Backs both QR-token uniqueness (retried on the vanishingly rare collision) and QR-scan lookup."""
        ...
    async def add(self, plant: Plant) -> Plant: ...
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
        """
        Search/Filter/Sort/Paginate, per the module's own API requirement.
        `search` matches `common_label`/`qr_code_token`/`batch_number`
        (case-insensitive substring); `sort_by` is one of "created_at",
        "planted_at", "status", "common_label" (validated at the service
        layer, not here, so the repository stays a thin query builder).
        """
        ...


class PlantImageRepository(Protocol):
    async def add(self, image: PlantImage) -> PlantImage: ...
    async def list_for_plant(self, plant_id: uuid.UUID) -> list[PlantImage]: ...


class PlantTransferRepository(Protocol):
    """Backs Plant Movement (branch transfer, zone/greenhouse/outdoor movement) with full history."""

    async def add(self, transfer: PlantTransfer) -> PlantTransfer: ...
    async def list_for_plant(self, plant_id: uuid.UUID) -> list[PlantTransfer]:
        """Full movement history, oldest first -- the Timeline and the Plant Profile's "movement history" both read this."""
        ...


class GrowthTimelineRepository(Protocol):
    async def add(self, entry: GrowthTimeline) -> GrowthTimeline: ...
    async def list_for_plant(
        self, plant_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[GrowthTimeline], int]: ...
    async def get_by_id(self, entry_id: uuid.UUID) -> GrowthTimeline | None:
        """
        Added by Module 7: `GrowthRecorded` events carry only
        `growth_entry_id` (a "thin" event, per Module 6's own design), so
        the Digital Twin projector needs this to enrich a projection
        update with the entry's actual height/growth_stage/counts. A
        read-only enrichment lookup, not a new write path.
        """
        ...
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
        """
        Added by Phase 6 Module 12 (Growth Reports) -- this table carries
        no nursery_id/branch_id of its own, so implementations resolve
        tenant scoping by joining plant_id -> plants.(nursery_id,
        branch_id), the same join-based approach
        `DiseaseReportRepository.list_for_nursery` already established.
        Newest first.
        """
        ...


class HealthHistoryRepository(Protocol):
    async def add(self, entry: HealthHistory) -> HealthHistory: ...
    async def list_for_plant(
        self, plant_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[HealthHistory], int]: ...
    async def get_by_id(self, entry_id: uuid.UUID) -> HealthHistory | None: ...


class WateringLogRepository(Protocol):
    async def add(self, entry: WateringLog) -> WateringLog: ...
    async def list_for_plant(
        self, plant_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[WateringLog], int]: ...
    async def get_by_id(self, entry_id: uuid.UUID) -> WateringLog | None: ...
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
        """
        Added by Phase 6 Module 12 (Water Usage Reports). Unlike
        `GrowthTimelineRepository.list_for_nursery`, this does NOT join
        through `Plant` -- `WateringLog` carries its own `branch_id`
        directly with a nullable `plant_id` (zone-level watering has no
        single plant to attach to), so tenant scoping resolves via
        `Branch.nursery_id` instead, or zone-level rows would be silently
        dropped.
        """
        ...


class FertilizerLogRepository(Protocol):
    async def add(self, entry: FertilizerLog) -> FertilizerLog: ...
    async def list_for_plant(
        self, plant_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[FertilizerLog], int]: ...
    async def get_by_id(self, entry_id: uuid.UUID) -> FertilizerLog | None: ...
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
        """Added by Phase 6 Module 12 (Fertilizer Reports) -- same `Branch.nursery_id` join as `WateringLogRepository.list_for_nursery` (same schema shape, same nullable-`plant_id` reasoning)."""
        ...


class EnvironmentalReadingRepository(Protocol):
    async def add(self, entry: EnvironmentalReading) -> EnvironmentalReading: ...
    async def list_for_plant(
        self, plant_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[EnvironmentalReading], int]: ...
    async def get_by_id(self, entry_id: uuid.UUID) -> EnvironmentalReading | None: ...


class DiseaseReportRepository(Protocol):
    """Backs the Health & Disease module's report lifecycle (draft -> confirmed/dismissed -> treated -> resolved)."""

    async def get_by_id(self, report_id: uuid.UUID) -> DiseaseReport | None: ...
    async def add(self, report: DiseaseReport) -> DiseaseReport: ...
    async def list_for_plant(self, plant_id: uuid.UUID) -> list[DiseaseReport]: ...
    async def list_for_nursery(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        status: DiseaseReportStatus | None = None,
        severity: DiseaseReportSeverity | None = None,
    ) -> tuple[list[DiseaseReport], int]: ...
    async def count_open_for_plant(self, plant_id: uuid.UUID) -> int:
        """Backs the status-transition guard: "no open disease report" for In Production -> Ready for Sale."""
        ...


class TreatmentRepository(Protocol):
    async def add(self, treatment: Treatment) -> Treatment: ...
    async def list_for_disease_report(self, disease_report_id: uuid.UUID) -> list[Treatment]: ...
    async def get_by_id(self, treatment_id: uuid.UUID) -> Treatment | None:
        """Added by Module 7: enriches `TreatmentApplied` projection updates -- same reasoning as `GrowthTimelineRepository.get_by_id`."""
        ...


class SupplierRepository(Protocol):
    """Read-only lookup for validating `Plant.supplier_id` on registration -- Suppliers & Purchasing owns the full CRUD surface (a later module)."""

    async def get_by_id(self, supplier_id: uuid.UUID) -> Supplier | None: ...


# --------------------------------------------------------------------------
# Module 7 (Plant Digital Twin Engine) -- the event-driven projection layer.
# See app/models/digital_twin.py's module docstring for the CQRS split
# these three repositories back.
# --------------------------------------------------------------------------


class DigitalTwinRepository(Protocol):
    """Backs the current, read-optimized projection -- one row per Plant."""

    async def get_by_plant_id(self, plant_id: uuid.UUID) -> DigitalTwin | None: ...
    async def create(self, twin: DigitalTwin) -> DigitalTwin: ...
    async def update(self, twin: DigitalTwin) -> DigitalTwin:
        """
        The *only* write path in the entire codebase that touches
        `digital_twins` -- called exclusively from `DigitalTwinService`'s
        event-projection methods, never from an API route.
        """
        ...
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
    ) -> tuple[list[DigitalTwin], int]: ...


class DigitalTwinVersionRepository(Protocol):
    """Backs the immutable, append-only version history -- see `DigitalTwinVersion`'s own docstring."""

    async def add(self, version: DigitalTwinVersion) -> DigitalTwinVersion: ...
    async def get_by_plant_and_version(self, plant_id: uuid.UUID, version: int) -> DigitalTwinVersion | None: ...
    async def get_latest_version_number(self, plant_id: uuid.UUID) -> int:
        """Returns 0 if no version exists yet -- the next version to write is always this + 1."""
        ...
    async def list_for_plant(
        self, plant_id: uuid.UUID, *, offset: int, limit: int, sort_dir: str = "desc"
    ) -> tuple[list[DigitalTwinVersion], int]:
        """Version history -- "Version comparison" reads two of these by version number; "Historical playback" reads this whole list in order."""
        ...
    async def get_as_of(self, plant_id: uuid.UUID, *, as_of: datetime) -> DigitalTwinVersion | None:
        """
        "Snapshot by date": the latest version whose `occurred_at` is
        `<= as_of` -- i.e. "what did this plant's twin look like at this
        point in time".
        """
        ...


class EventDispatchLogRepository(Protocol):
    """Backs `EventDispatcher`'s idempotency/retry-safety bookkeeping (app/domain_events/dispatcher.py)."""

    async def get(self, event_id: uuid.UUID, handler_name: str) -> EventDispatchLog | None: ...
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
        """
        Insert-or-update on the `(event_id, handler_name)` unique
        constraint -- a retry after a prior `FAILED` attempt updates the
        same row (incrementing `attempt_count`) rather than violating the
        constraint with a second insert.
        """
        ...
    async def list_failed(self, *, handler_name: str | None = None, limit: int = 100) -> list[EventDispatchLog]:
        """Backs manual/administrative recovery -- "find everything that needs a retry"."""
        ...


# --------------------------------------------------------------------------
# Module 8 (Inventory & Stock Management)
# --------------------------------------------------------------------------


class InventoryLocationRepository(Protocol):
    """Backs "Location Management" -- the sub-branch physical hierarchy."""

    async def get_by_id(self, location_id: uuid.UUID) -> InventoryLocation | None: ...
    async def add(self, location: InventoryLocation) -> InventoryLocation: ...
    async def update(self, location: InventoryLocation) -> InventoryLocation: ...
    async def list_for_branch(
        self, branch_id: uuid.UUID, *, include_inactive: bool = False
    ) -> list[InventoryLocation]: ...


class InventoryRepository(Protocol):
    """Backs the bulk stock line -- one row per (branch, SKU)."""

    async def get_by_id(self, inventory_id: uuid.UUID) -> Inventory | None: ...
    async def add(self, inventory: Inventory) -> Inventory: ...
    async def update(self, inventory: Inventory, *, expected_version: int) -> Inventory | None:
        """
        Optimistic-concurrency write path: the sole way any Inventory
        row's quantity fields are ever mutated. Implementations perform
        the update conditionally on `version == expected_version` (a
        `WHERE version = :expected_version` clause for the real SQL
        repository, an equivalent in-memory check for the fake) and
        return `None` (never raise) if no row matched -- i.e. another
        writer updated this line first. Per this codebase's convention
        (repositories are pure data access; only services raise
        `AppError` subclasses), the caller -- `InventoryService` -- is
        the one that turns a `None` result into `ConflictError` (context
        reason "version_conflict"). This is this module's "minimal
        locking" concurrency strategy: no row-level `SELECT ... FOR
        UPDATE` pessimistic lock is held for the duration of a request; a
        losing writer simply retries against the fresh row.
        """
        ...
    async def get_by_branch_and_name(self, branch_id: uuid.UUID, name: str) -> Inventory | None:
        """Find-or-create-line lookup for Receiving and the destination side of a cross-branch Transfer."""
        ...
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
        """Search/Filter/Sort/Paginate -- branch/category/species/location filtering per the module's own requirement."""
        ...


class StockMovementRepository(Protocol):
    """
    Backs the immutable, append-only movement ledger -- Movement History,
    Waste Report, Transfer Report, and Reservation Report are all derived
    from this one table. No `update`/`delete` method exists on this
    Protocol at all -- there is no legitimate write path for either.
    """

    async def add(self, movement: StockMovement) -> StockMovement: ...
    async def get_by_id(self, movement_id: uuid.UUID) -> StockMovement | None: ...
    async def list_for_inventory(
        self,
        inventory_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        movement_type: StockMovementType | None = None,
        sort_dir: str = "desc",
    ) -> tuple[list[StockMovement], int]: ...
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
        """Movement History / Waste / Transfer reports -- resolved via a JOIN to `inventory` for nursery/branch scoping (StockMovement carries no nursery_id/branch_id of its own)."""
        ...


class StockReservationRepository(Protocol):
    """Backs the Reservations workflow -- hold-without-decrementing."""

    async def get_by_id(self, reservation_id: uuid.UUID) -> StockReservation | None: ...
    async def add(self, reservation: StockReservation) -> StockReservation: ...
    async def update(self, reservation: StockReservation) -> StockReservation:
        """Status transitions (ACTIVE -> RELEASED/FULFILLED/EXPIRED) -- the only fields that ever change on an existing row."""
        ...
    async def list_for_inventory(
        self, inventory_id: uuid.UUID, *, status: StockReservationStatus | None = None
    ) -> list[StockReservation]: ...
    async def list_active_for_nursery(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int, branch_id: uuid.UUID | None = None
    ) -> tuple[list[StockReservation], int]:
        """Reservation Report."""
        ...


# =============================================================================
# Phase 6 Module 9 (Sales, CRM, Plant Passport & QR Intelligence).
# =============================================================================


class CustomerRepository(Protocol):
    async def get_by_id(self, customer_id: uuid.UUID) -> Customer | None: ...
    async def add(self, customer: Customer) -> Customer: ...
    async def update(self, customer: Customer) -> Customer: ...
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
    ) -> tuple[list[Customer], int]: ...


class CustomerContactRepository(Protocol):
    async def get_by_id(self, contact_id: uuid.UUID) -> CustomerContact | None: ...
    async def add(self, contact: CustomerContact) -> CustomerContact: ...
    async def list_for_customer(self, customer_id: uuid.UUID) -> list[CustomerContact]: ...
    async def delete(self, contact_id: uuid.UUID) -> None: ...


class CustomerAddressRepository(Protocol):
    async def get_by_id(self, address_id: uuid.UUID) -> CustomerAddress | None: ...
    async def add(self, address: CustomerAddress) -> CustomerAddress: ...
    async def list_for_customer(self, customer_id: uuid.UUID) -> list[CustomerAddress]: ...
    async def delete(self, address_id: uuid.UUID) -> None: ...


class CustomerTagRepository(Protocol):
    async def add(self, tag: CustomerTag) -> CustomerTag: ...
    async def list_for_customer(self, customer_id: uuid.UUID) -> list[CustomerTag]: ...
    async def delete(self, customer_id: uuid.UUID, tag: str) -> None: ...


class CustomerNoteRepository(Protocol):
    async def get_by_id(self, note_id: uuid.UUID) -> CustomerNote | None: ...
    async def add(self, note: CustomerNote) -> CustomerNote: ...
    async def list_for_customer(
        self, customer_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[CustomerNote], int]: ...
    async def delete(self, note_id: uuid.UUID) -> None: ...


class CustomerCommunicationRepository(Protocol):
    async def add(self, communication: CustomerCommunication) -> CustomerCommunication: ...
    async def list_for_customer(
        self, customer_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[CustomerCommunication], int]: ...


class QuotationRepository(Protocol):
    async def get_by_id(self, quotation_id: uuid.UUID) -> Quotation | None: ...
    async def add(self, quotation: Quotation) -> Quotation: ...
    async def update(self, quotation: Quotation) -> Quotation: ...
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
    ) -> tuple[list[Quotation], int]: ...


class QuotationItemRepository(Protocol):
    async def add(self, item: QuotationItem) -> QuotationItem: ...
    async def list_for_quotation(self, quotation_id: uuid.UUID) -> list[QuotationItem]: ...


class SalesOrderRepository(Protocol):
    async def get_by_id(self, order_id: uuid.UUID) -> SalesOrder | None: ...
    async def get_by_idempotency_key(self, branch_id: uuid.UUID, key: str) -> SalesOrder | None: ...
    async def add(self, order: SalesOrder) -> SalesOrder: ...
    async def update(self, order: SalesOrder) -> SalesOrder: ...
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
    ) -> tuple[list[SalesOrder], int]: ...


class OrderItemRepository(Protocol):
    async def get_by_id(self, item_id: uuid.UUID) -> OrderItem | None: ...
    async def add(self, item: OrderItem) -> OrderItem: ...
    async def update(self, item: OrderItem) -> OrderItem: ...
    async def list_for_order(self, sales_order_id: uuid.UUID) -> list[OrderItem]: ...


class SaleRepository(Protocol):
    """
    Backs the pre-existing, immutable "completed transaction" ledger
    (app/models/commerce.py's own docstring). `add` is the only write —
    a Sale is never edited in place beyond the single completed->voided
    edge, which `update` (status/void fields only) supports.
    """

    async def get_by_id(self, sale_id: uuid.UUID) -> Sale | None: ...
    async def get_by_idempotency_key(self, branch_id: uuid.UUID, key: str) -> Sale | None: ...
    async def add(self, sale: Sale) -> Sale: ...
    async def update(self, sale: Sale) -> Sale: ...
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
        """Sales Reports / Revenue Reports are built from this."""
        ...


class SaleItemRepository(Protocol):
    async def get_by_id(self, item_id: uuid.UUID) -> SaleItem | None: ...
    async def add(self, item: SaleItem) -> SaleItem: ...
    async def list_for_sale(self, sale_id: uuid.UUID) -> list[SaleItem]: ...


class InvoiceRepository(Protocol):
    async def get_by_id(self, invoice_id: uuid.UUID) -> Invoice | None: ...
    async def get_by_number(self, nursery_id: uuid.UUID, invoice_number: str) -> Invoice | None: ...
    async def add(self, invoice: Invoice) -> Invoice: ...
    async def update(self, invoice: Invoice) -> Invoice: ...
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
    ) -> tuple[list[Invoice], int]: ...


class InvoiceItemRepository(Protocol):
    async def add(self, item: InvoiceItem) -> InvoiceItem: ...
    async def list_for_invoice(self, invoice_id: uuid.UUID) -> list[InvoiceItem]: ...


class InvoiceSaleRepository(Protocol):
    """Backs the `invoice_sales` many-to-many join (a Sale may roll up into one Invoice)."""

    async def link(self, invoice_id: uuid.UUID, sale_id: uuid.UUID) -> None: ...
    async def list_sale_ids_for_invoice(self, invoice_id: uuid.UUID) -> list[uuid.UUID]: ...


class PaymentRepository(Protocol):
    """Backs Multiple/Partial Payments and Payment History — one row per tender against an Invoice."""

    async def get_by_id(self, payment_id: uuid.UUID) -> Payment | None: ...
    async def add(self, payment: Payment) -> Payment: ...
    async def list_for_invoice(self, invoice_id: uuid.UUID) -> list[Payment]: ...
    async def sum_for_invoice(self, invoice_id: uuid.UUID) -> float:
        """Total paid so far — drives the Payment Status derivation (unpaid/partial/paid)."""
        ...


class ReturnRepository(Protocol):
    async def get_by_id(self, return_id: uuid.UUID) -> Return | None: ...
    async def add(self, return_: Return) -> Return: ...
    async def update(self, return_: Return) -> Return: ...
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
    ) -> tuple[list[Return], int]: ...


class ReturnItemRepository(Protocol):
    async def add(self, item: ReturnItem) -> ReturnItem: ...
    async def list_for_return(self, return_id: uuid.UUID) -> list[ReturnItem]: ...
    async def get_by_id(self, item_id: uuid.UUID) -> ReturnItem | None:
        """
        Added alongside `DigitalTwinService._on_plant_returned`'s
        `line_refund_amount` enrichment read (Module 9) -- a single-row
        lookup by the `return_item_id` a `PlantReturned` event payload
        carries, the same shape every other enrichment-read repository
        dependency in `digital_twin_service.py` already has (e.g.
        `GrowthTimelineRepository.get_by_id`).
        """
        ...


class RefundRepository(Protocol):
    async def get_by_id(self, refund_id: uuid.UUID) -> Refund | None: ...
    async def add(self, refund: Refund) -> Refund: ...
    async def update(self, refund: Refund) -> Refund: ...
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
    ) -> tuple[list[Refund], int]: ...


class PassportRepository(Protocol):
    """
    Append-only, versioned per Plant (app/models/reports.py's own
    docstring). `get_by_token` is the ONE lookup the public,
    unauthenticated QR/passport endpoints use — everything else here is
    for internal, authenticated passport management.
    """

    async def get_by_id(self, passport_id: uuid.UUID) -> Passport | None: ...
    async def get_by_token(self, public_token: str) -> Passport | None: ...
    async def add(self, passport: Passport) -> Passport: ...
    async def get_latest_for_plant(self, plant_id: uuid.UUID) -> Passport | None: ...
    async def list_for_plant(self, plant_id: uuid.UUID) -> list[Passport]: ...
    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[Passport], int]:
        """
        Passport Reports. Passport carries no nursery_id of its own
        (deliberately — see the model's docstring), so implementations
        resolve tenant scoping by joining plant_id -> plants.nursery_id,
        the same join-based approach migration 0003 already established
        for other parent-less child tables.
        """
        ...


class QRScanEventRepository(Protocol):
    """
    Backs QR Scan Analytics. Written by the one unauthenticated endpoint
    in the system — see app/models/reports.py's QRScanEvent docstring for
    why this table carries no nursery_id/RLS policy of its own.
    """

    async def add(self, scan: QRScanEvent) -> QRScanEvent: ...
    async def count_for_passport(self, passport_id: uuid.UUID) -> int: ...
    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[QRScanEvent], int]:
        """Resolved via passport_id -> passports.plant_id -> plants.nursery_id, a two-hop join."""
        ...


# ==============================================================================
# Phase 6 Module 10 (AI Platform)
# ==============================================================================


class AIPredictionRepository(Protocol):
    """
    Backs `ai_predictions` -- FR-8.7's "no AI output without a persisted
    record" contract. `add` is called exactly once per inference, from
    `PredictionLogger.persist` (app/ai/common/prediction_logger.py), never
    from a route or any other service directly -- the same single-write-
    path discipline Module 8 established for `StockMovement` via
    `InventoryService._apply_change()`.
    """

    async def add(self, prediction: AIPrediction) -> AIPrediction: ...
    async def get_by_id(self, prediction_id: uuid.UUID) -> AIPrediction | None: ...
    async def list_for_plant(
        self, plant_id: uuid.UUID, *, prediction_type: AIPredictionType | None = None, offset: int, limit: int
    ) -> tuple[list[AIPrediction], int]:
        """`GET /plants/{id}/ai-predictions` (FR-8.8: historical, not just latest), newest first."""
        ...

    async def get_latest_for_plant(
        self, plant_id: uuid.UUID, prediction_type: AIPredictionType
    ) -> AIPrediction | None:
        """The one row each of Disease Detection/Growth/Survival/Water Recommendation actually cares about for "what does this plant need right now" callers (Recommendation Engine, QR scan's `ai_recommendations` section)."""
        ...

    async def list_for_branch(
        self, branch_id: uuid.UUID, *, prediction_type: AIPredictionType | None = None, offset: int, limit: int
    ) -> tuple[list[AIPrediction], int]:
        """Survival-risk/revenue-forecast style branch-wide reads (`GET /ai/predictions/survival-risk`, `GET /ai/predictions/revenue-forecast`)."""
        ...

    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, prediction_type: AIPredictionType | None = None, offset: int, limit: int
    ) -> tuple[list[AIPrediction], int]:
        ...

    # --- Added by Phase 6 Module 13 ("AI Administration") ---
    async def admin_stats_for_nursery(
        self, nursery_id: uuid.UUID, *, date_from: datetime | None = None, date_to: datetime | None = None
    ) -> list[dict]:
        """
        One row per `prediction_type` with `count`/`avg_latency_ms`/
        `avg_confidence` -- the "AI request statistics"/"inference latency"/
        "AI usage" admin view (Section 10). `avg_latency_ms` is `None` for
        rows where every prediction predates Module 13 (`latency_ms` is
        nullable, backfilled `NULL` on existing rows -- see migration
        0018's docstring), not zero, so an admin dashboard doesn't read a
        pre-Module-13 gap as "the model responded instantly".
        """
        ...


class AIRecommendationRepository(Protocol):
    """Backs `ai_recommendations` -- FR-8.6, mutable `status` (new/dismissed/acted_upon)."""

    async def add(self, recommendation: AIRecommendation) -> AIRecommendation: ...
    async def get_by_id(self, recommendation_id: uuid.UUID) -> AIRecommendation | None: ...
    async def update_status(
        self, recommendation: AIRecommendation, *, status: AIRecommendationStatus
    ) -> AIRecommendation: ...
    async def list_for_branch(
        self, branch_id: uuid.UUID, *, status: AIRecommendationStatus | None = None, offset: int, limit: int
    ) -> tuple[list[AIRecommendation], int]: ...
    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, status: AIRecommendationStatus | None = None, offset: int, limit: int
    ) -> tuple[list[AIRecommendation], int]: ...


class AIAssistantConversationRepository(Protocol):
    """Backs `ai_assistant_conversations` -- FR-9.4, per-user conversation threads."""

    async def add(self, conversation: AIAssistantConversation) -> AIAssistantConversation: ...
    async def get_by_id(self, conversation_id: uuid.UUID) -> AIAssistantConversation | None: ...
    async def list_for_user(
        self, user_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[AIAssistantConversation], int]: ...


class AIAssistantMessageRepository(Protocol):
    """
    Backs `ai_assistant_messages` -- append-only, except for
    `action_status` transitions (`pending_confirmation` ->
    `confirmed`/`cancelled`), which `update` exists for; every other field
    is written once at creation and never changed.
    """

    async def add(self, message: AIAssistantMessage) -> AIAssistantMessage: ...
    async def get_by_id(self, message_id: uuid.UUID) -> AIAssistantMessage | None: ...
    async def update(self, message: AIAssistantMessage) -> AIAssistantMessage: ...
    async def list_for_conversation(
        self, conversation_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[AIAssistantMessage], int]:
        """Oldest first (conversation reading order), unlike most list methods in this file."""
        ...


class KnowledgeBaseChunkRepository(Protocol):
    """
    Backs `knowledge_base_chunks` -- the Assistant's RAG grounding store
    (app/models/ai.py's own docstring on why this table is deliberately
    RLS-exempt: `search_similar` is the one place tenant scoping for
    `source_type='org_data'` rows is enforced, at the query layer, exactly
    as that docstring promises).
    """

    async def add(self, chunk: KnowledgeBaseChunk) -> KnowledgeBaseChunk: ...
    async def get_by_id(self, chunk_id: uuid.UUID) -> KnowledgeBaseChunk | None: ...
    async def search_similar(
        self, embedding: list[float], *, nursery_id: uuid.UUID | None, limit: int
    ) -> list[KnowledgeBaseChunk]:
        """
        Cosine-distance nearest-neighbor search (`embedding <=> :query`,
        pgvector's operator), filtered to `nursery_id = :nursery_id OR
        source_type = 'knowledge_article'` -- an org's own data plus every
        platform-wide curated article, never another org's data. Ordered
        nearest-first.
        """
        ...

    # --- Added by Phase 6 Module 13 ("AI Administration", RAG knowledge-base status) ---
    async def count_by_source_type(self, *, nursery_id: uuid.UUID | None = None) -> list[dict]:
        """
        `[{"source_type": ..., "count": ...}, ...]` -- the admin-facing
        "RAG knowledge-base status" view (Section 10). `nursery_id=None`
        counts every row platform-wide (the `platform_admin` view);
        `nursery_id` set counts `source_type='org_data'` rows for that org
        plus every `source_type='knowledge_article'` row (the same
        `nursery_id = :org OR source_type = 'knowledge_article'` shape
        `search_similar` already uses), for an org-scoped admin's own view
        of what's grounding their Assistant's answers.
        """
        ...


# ======================================================================
# Phase 6 Module 11 (Notifications & Communication)
# ======================================================================


class NotificationRepository(Protocol):
    """
    Backs `notifications` -- the in-app record `NotificationService`
    always creates first, regardless of which other channels a user's
    preferences enable (`Notification`'s own model docstring).
    """

    async def add(self, notification: Notification) -> Notification: ...
    async def get_by_id(self, notification_id: uuid.UUID) -> Notification | None: ...
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
        """Newest first -- notification history + unread inbox both read through this one method."""
        ...
    async def count_unread(self, user_id: uuid.UUID, nursery_id: uuid.UUID) -> int: ...
    async def mark_read(self, notification: Notification, *, now: datetime) -> None: ...
    async def mark_all_read(self, user_id: uuid.UUID, nursery_id: uuid.UUID, *, now: datetime) -> int:
        """Returns the number of previously-unread rows that were marked read."""
        ...
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
        """Added by Phase 6 Module 12 (Notification Reports) -- org-wide, unlike `list_for_user`'s per-recipient inbox view. Newest first."""
        ...


class NotificationPreferenceRepository(Protocol):
    """Backs `notification_preferences` -- one row per (user, category, channel); see that model's own docstring."""

    async def list_for_user(self, user_id: uuid.UUID) -> list[NotificationPreference]: ...
    async def get(
        self, user_id: uuid.UUID, category: NotificationCategory, channel: NotificationChannel
    ) -> NotificationPreference | None: ...
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
    ) -> NotificationPreference: ...


class NotificationTemplateRepository(Protocol):
    """Backs `notification_templates` -- see that model's own docstring for the org-override-over-global-default resolution shape `get_active` serves."""

    async def add(self, template: NotificationTemplate) -> NotificationTemplate: ...
    async def get_active(
        self,
        *,
        nursery_id: uuid.UUID | None,
        category: NotificationCategory,
        channel: NotificationChannel,
        format: str,
        locale: str,
    ) -> NotificationTemplate | None:
        """Highest `version`, `is_active=True` row for this exact key, or None if no such row exists."""
        ...
    async def list_for_org(self, nursery_id: uuid.UUID | None) -> list[NotificationTemplate]: ...


class NotificationDeliveryRepository(Protocol):
    """Backs `notification_deliveries` -- retry/DLQ/tracking/failure-log/status all folded into this one table, see that model's own docstring."""

    async def add(self, delivery: NotificationDelivery) -> NotificationDelivery: ...
    async def get_by_id(self, delivery_id: uuid.UUID) -> NotificationDelivery | None: ...
    async def list_for_notification(self, notification_id: uuid.UUID) -> list[NotificationDelivery]: ...
    async def list_due_for_retry(self, *, now: datetime, limit: int = 100) -> list[NotificationDelivery]:
        """`status='failed'` rows whose `next_retry_at <= now` and `attempt_count < max_attempts` -- the retry worker's own work queue."""
        ...
    async def list_dead_letter(
        self, nursery_id: uuid.UUID, *, limit: int = 100
    ) -> list[NotificationDelivery]:
        """Ops visibility into `status='dead_letter'` rows for this org, joined through their owning `notifications` row."""
        ...
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
    ) -> None: ...


# --------------------------------------------------------------------------
# Phase 6 Module 12 — Reports & Analytics
# --------------------------------------------------------------------------


class ReportRepository(Protocol):
    """Backs `reports` -- one row per generated report instance (Phase 5 skeleton, extended by Module 12)."""

    async def add(self, report: Report) -> Report: ...
    async def get_by_id(self, report_id: uuid.UUID) -> Report | None: ...
    async def list_for_org(
        self,
        nursery_id: uuid.UUID,
        *,
        report_type: ReportType | None = None,
        branch_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Report], int]:
        """Newest first. `branch_id` is an exact-match filter (a report generated org-wide has `branch_id=None` and is excluded when this filter is set -- it does not fall back to "show org-wide reports too")."""
        ...
    async def update_status(
        self,
        report: Report,
        *,
        status: ReportStatus,
        file_url: str | None = None,
        completed_at: datetime | None = None,
    ) -> None: ...
    async def commit(self) -> None:
        """Persist the session's pending writes. Background-task callers
        (report generation) run after the request's own session teardown
        has already committed+closed, so they must commit explicitly --
        same pattern as `UserRepository.commit`."""
        ...


class ScheduledReportRepository(Protocol):
    """Backs `scheduled_reports` -- saved recurring report definitions (FR-18.4 / this module's "Saved Reports" requirement)."""

    async def add(self, scheduled: ScheduledReport) -> ScheduledReport: ...
    async def get_by_id(self, scheduled_id: uuid.UUID) -> ScheduledReport | None: ...
    async def list_for_org(self, nursery_id: uuid.UUID) -> list[ScheduledReport]: ...
    async def list_due(self, *, now: datetime, limit: int = 100) -> list[ScheduledReport]:
        """`is_active=True` rows whose `next_run_at <= now` -- `ScheduledReportService.run_due()`'s own work queue."""
        ...
    async def update_after_run(self, scheduled: ScheduledReport, *, last_run_at: datetime, next_run_at: datetime) -> None:
        """Advances the run-tracking columns only, called from `run_due()`'s execution loop -- see `update`'s own docstring for how this differs from a caller-supplied `PATCH` update."""
        ...
    async def update(
        self,
        scheduled: ScheduledReport,
        *,
        name: str | None = None,
        filters: dict | None = None,
        frequency: ReportScheduleFrequency | None = None,
        next_run_at: datetime | None = None,
    ) -> None:
        """
        Partial field update for `PATCH /reports/scheduled/{id}` -- distinct
        from `update_after_run` (which advances the run-tracking columns
        only, called from `run_due()`'s own execution loop, never from a
        caller-supplied request body). `None` means "leave this field
        unchanged"; `report_type`/`format`/`branch_id`/`nursery_id` are
        deliberately not updatable here (an in-place type/scope change on a
        saved schedule is closer to "delete and recreate" than "edit" --
        matches `ScheduledReportUpdateRequest`'s own schema, which only
        exposes these four fields).
        """
        ...
    async def set_active(self, scheduled: ScheduledReport, *, is_active: bool) -> None: ...
    async def delete(self, scheduled: ScheduledReport) -> None: ...


class ReportingRepository(Protocol):
    """
    This module's own CQRS read side. Every method here is read-only (no
    method on this Protocol ever accepts anything but filter/id
    arguments, and none returns a mapped, session-attached ORM entity a
    caller could mutate and flush) and every implementation must reach
    its data exclusively through either (a) the materialized views/plain
    views migrations 0005 and 0017 created specifically for this purpose,
    or (b) a purpose-built aggregate query (`GROUP BY`/`COUNT`/`SUM`) --
    never a raw unfiltered table scan reused from an operational
    repository. See `app/reporting/__init__.py`'s own docstring for the
    full CQRS-separation argument.

    Deliberately scoped to what genuinely needs a *new*, cross-cutting
    aggregate query: the 9 dashboards (all fixed-shape, filterable only
    by org/branch) and the analytics endpoints. Report row-level exports
    (`ReportGenerationService`) additionally reuse each entity's own
    *existing* repository (`PlantRepository.list_for_nursery`,
    `SaleRepository.list_for_branch`, ...) for the same reason those
    repositories exist at all -- they are already the "dedicated read
    model" for their own table; duplicating their query logic here would
    violate this module's own "No duplicated reporting logic" QUALITY
    requirement, not satisfy it.
    """

    # --- Dashboards ---
    async def executive_dashboard(self, nursery_id: uuid.UUID) -> dict: ...
    async def nursery_dashboard(self, nursery_id: uuid.UUID) -> dict: ...
    async def branch_dashboard(self, nursery_id: uuid.UUID, branch_id: uuid.UUID) -> dict: ...
    async def plant_dashboard(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict: ...
    async def inventory_dashboard(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict: ...
    async def sales_dashboard(
        self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None,
        date_from: datetime | None = None, date_to: datetime | None = None,
    ) -> dict: ...
    async def customer_dashboard(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict: ...
    async def ai_dashboard(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict: ...
    async def financial_dashboard(
        self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None,
        date_from: datetime | None = None, date_to: datetime | None = None,
    ) -> dict: ...

    # --- Analytics ---
    async def kpi_summary(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict: ...
    async def revenue_trend(
        self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None, date_from: datetime, date_to: datetime
    ) -> list[dict]: ...
    async def growth_trend(
        self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None, species_id: uuid.UUID | None,
        date_from: datetime, date_to: datetime,
    ) -> list[dict]: ...
    async def inventory_trend(
        self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None, date_from: datetime, date_to: datetime
    ) -> list[dict]: ...
    async def plant_health_trend(
        self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None, date_from: datetime, date_to: datetime
    ) -> list[dict]: ...
    async def sales_forecast(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> list[dict]:
        """Reads already-persisted `revenue_forecast` `AIPrediction` rows (Module 10) -- never runs a forecast model itself, per this module's own "no duplicated logic" requirement."""
        ...
    async def disease_trend(
        self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None, date_from: datetime, date_to: datetime
    ) -> list[dict]: ...
    async def customer_analytics(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict: ...
    async def employee_productivity(
        self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None, date_from: datetime, date_to: datetime
    ) -> list[dict]: ...
    async def branch_performance(self, nursery_id: uuid.UUID) -> list[dict]: ...


# ======================================================================
# Phase 6 Module 13 (Administration & System Management)
# ======================================================================


class FeatureFlagRepository(Protocol):
    """Backs `feature_flags` -- see that model's own docstring (app/models/platform.py) for the three-tier resolution shape this Protocol's methods serve."""

    async def resolve(
        self, key: str, *, nursery_id: uuid.UUID | None, branch_id: uuid.UUID | None
    ) -> FeatureFlag | None:
        """
        The single most-specific row for this lookup, in branch -> org ->
        platform-default order, or `None` if no row exists at any tier
        (the caller -- `FeatureFlagService.is_enabled` -- treats `None`
        the same as "disabled", never raises: "feature flags must fail
        safely").
        """
        ...

    async def list_all(self, *, nursery_id: uuid.UUID | None = None) -> list[FeatureFlag]:
        """Every platform-default row plus (if `nursery_id` given) this org's own overrides -- the admin listing view, not resolution."""
        ...

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
        """Creates or updates the one row for this exact `(key, nursery_id, branch_id)` tier -- the table's own unique constraint is what makes this a true upsert rather than always-insert."""
        ...


class SystemConfigRepository(Protocol):
    """Backs `system_config` -- see that model's own docstring (app/models/platform.py) for why no secret ever lives here."""

    async def get(self, key: str) -> SystemConfig | None: ...

    async def list_all(self, *, category: str | None = None) -> list[SystemConfig]: ...

    async def upsert(
        self,
        *,
        key: str,
        value: dict,
        value_type: str,
        category: str,
        description: str | None,
        updated_by_user_id: uuid.UUID | None,
    ) -> SystemConfig: ...


class AIInferenceFailureRepository(Protocol):
    """
    Backs `ai_inference_failures` -- the failure-path counterpart to
    `AIPredictionRepository` (`InferenceBase.run()`, app/ai/common/inference_base.py,
    writes here on any exception from the predict pipeline, mirroring
    `PredictionLogger` being the one writer of `ai_predictions`).
    """

    async def add(self, failure: AIInferenceFailure) -> AIInferenceFailure: ...

    async def list_for_nursery(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int, capability: str | None = None
    ) -> tuple[list[AIInferenceFailure], int]:
        """Newest first -- the "AI failures" admin view (Section 10)."""
        ...
