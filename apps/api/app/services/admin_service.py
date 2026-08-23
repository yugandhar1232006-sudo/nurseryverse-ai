"""
Phase 6 Module 13 (Administration & System Management) business logic.

Eight services, one per bounded concern, sharing this file because each is
genuinely small (a handful of methods, most of them thin org-scoping +
audit-logging wrappers around a repository call) -- the same "several
related service classes in one module" shape Module 9's sales_service.py
already established for PaymentService/QuotationService/RefundService/
ReturnService, rather than eight near-empty files:

  - RoleAdminService        -- Section 1 (Role & Permission Administration)
  - UserAdminService        -- Section 2 (User Administration)
  - FeatureFlagService      -- Section 7 (Feature Flags)
  - SystemConfigService     -- Section 6 (System Configuration)
  - AuditAdminService       -- Section 8 (Audit & Security Administration)
  - HealthCheckService      -- Section 9 (System Health)
  - AIAdminService          -- Section 10 (AI Administration)
  - DataManagementService   -- Section 11 (Data Management)

Sections 3/4/5 (Employee/Nursery/Branch Administration) are deliberately
NOT reimplemented here -- `EmployeeService`/`OrganizationService`/
`BranchService` (Module 4) already cover every capability those sections
ask for (see `docs/architecture/29-module13-administration.md` for the
full mapping); `app/api/routes/admin.py` calls those existing services
directly. Per the standing "do not modify completed modules unless a
genuine dependency or defect requires it" instruction, the one exception
is `EmployeeService.reactivate_employee` (added directly to that file,
not duplicated here) -- a genuinely missing capability Module 4 never
built, not a rebuild of anything that already existed.

Platform-wide actions (System Configuration, Feature Flags' platform-
default tier, AI Administration, System Health, Data Management) are
gated by the `admin:read`/`admin:manage` permissions (migration 0018),
checked with `target_nursery_id=None` -- the same org-agnostic
`AuthorizationService.authorize()` shape Module 12's report catalog route
already established. `audit_logs.nursery_id` is NOT NULL (Phase 5's
original schema), so a platform-wide action still needs *some* value for
that column; every method here that performs one logs it against the
*caller's own home organization* (the org their RoleAssignment happens to
belong to, per v1's one-org-per-user constraint) -- documented here, once,
rather than re-derived at each call site: "Organization" in the audit
trail for a platform-wide action means "who the actor is affiliated with",
not "which org this action affected" (there may be no single such org).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.ai.common.model_registry import ModelRegistry
from app.core.cache import Cache
from app.core.config import Settings
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.db.enums import SecurityEventType
from app.models.auth import RefreshToken, SecurityEvent
from app.models.identity import Permission, Role, RoleAssignment, User
from app.models.organization import Employee
from app.models.platform import AuditLog, FeatureFlag, SystemConfig
from app.repositories.interfaces import (
    AIInferenceFailureRepository,
    AIPredictionRepository,
    AuditLogRepository,
    AuthorizationDenialRepository,
    EmployeeRepository,
    FeatureFlagRepository,
    KnowledgeBaseChunkRepository,
    PermissionRepository,
    SecurityEventRepository,
    SystemConfigRepository,
    UserRepository,
)
from app.services.auth_service import AuthService
from app.services.permission_service import PermissionService

_VALID_CONFIG_CATEGORIES = {"application", "feature", "notification", "ai", "report"}
_VALID_CONFIG_VALUE_TYPES = {"bool", "int", "str", "json"}
_AI_CAPABILITIES = (
    "disease_detection",
    "growth_prediction",
    "survival_prediction",
    "water_recommendation",
    "revenue_forecast",
    "recommendation_engine",
)


async def _log_admin_audit(
    audit_repo: AuditLogRepository,
    *,
    nursery_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    diff: dict,
    request_id: str | None,
    branch_id: uuid.UUID | None = None,
    result: str = "success",
) -> None:
    """Shared by every service in this file -- the one place Module 13's admin actions become `AuditLog` rows, mirroring every earlier module's own per-service `_log_audit` helper."""
    await audit_repo.log(
        AuditLog(
            nursery_id=nursery_id,
            branch_id=branch_id,
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            diff=diff,
            result=result,
            request_id=request_id,
            created_at=datetime.now(timezone.utc),
        )
    )


class RoleAdminService:
    """Section 1: Role & Permission Administration."""

    def __init__(
        self,
        *,
        permission_repo: PermissionRepository,
        permission_service: PermissionService,
        audit_repo: AuditLogRepository,
    ) -> None:
        self._permissions = permission_repo
        self._permission_service = permission_service
        self._audit = audit_repo

    async def list_roles(self, *, nursery_id: uuid.UUID | None = None) -> list[Role]:
        return await self._permissions.list_roles(nursery_id=nursery_id)

    async def list_permissions(self) -> list[Permission]:
        return await self._permissions.list_permissions()

    async def get_role_permissions(self, role_id: uuid.UUID) -> list[tuple[str, str]]:
        return await self._permissions.list_role_permission_codes(role_id)

    async def get_effective_permissions(self, user_id: uuid.UUID):
        """"Effective-permission inspection" -- delegates straight to the Module 3 resolver, which is already the single source of truth for "what can this user do right now"."""
        return await self._permission_service.resolve_for_user(user_id)

    async def change_user_role(
        self,
        *,
        actor_user_id: uuid.UUID,
        nursery_id: uuid.UUID,
        target_user_id: uuid.UUID,
        new_role_code: str,
        request_id: str | None = None,
    ) -> RoleAssignment:
        """
        Changes an already-employed user's role in place. Two protections
        satisfy Section 1's "system-level roles must be protected from
        unauthorized modification" / Section 12's "privilege escalation
        prevention":

          1. Neither the *current* nor the *new* role may be `owner` --
             ownership is transferred exclusively through
             `EmployeeService.transfer_ownership` (Module 4), which
             enforces its own single-owner invariant this method does not
             duplicate.
          2. The target must already hold a RoleAssignment in exactly this
             org (never resolved by user id alone) -- a cross-tenant
             target is a 403, not a 404, matching every other cross-tenant
             check in this codebase (Module 12's own established pattern).
        """
        assignment = await self._permissions.get_role_assignment_for_user(target_user_id)
        if assignment is None or assignment.nursery_id != nursery_id:
            raise PermissionDeniedError("This user does not hold a role assignment in your organization.")

        current_role = await self._permissions.get_role_with_permissions(assignment.role_id)
        if current_role is not None and current_role.code == "owner":
            raise ValidationError(
                "The organization owner's role cannot be changed here -- use ownership transfer instead."
            )
        if new_role_code == "owner":
            raise ValidationError("Ownership can only be granted via ownership transfer, not a role change.")

        new_role = await self._permissions.get_system_role_by_code(new_role_code)
        if new_role is None:
            raise ValidationError(f"Unknown role code: {new_role_code!r}.")

        before_code = current_role.code if current_role is not None else None
        await self._permissions.set_assignment_role(assignment, role_id=new_role.id)
        await self._permission_service.invalidate_user(target_user_id)

        await _log_admin_audit(
            self._audit,
            nursery_id=nursery_id,
            actor_user_id=actor_user_id,
            action="admin.role_assignment_changed",
            entity_type="RoleAssignment",
            entity_id=assignment.id,
            diff={"before": {"role_code": before_code}, "after": {"role_code": new_role_code}},
            request_id=request_id,
        )
        return assignment


class UserAdminService:
    """
    Section 2: User Administration. Org-scoped: every method verifies the
    target user is an Employee of the caller's own org before touching
    anything (`users` carries no `nursery_id` of its own -- see
    app/models/auth.py's docstring -- so `employees` is the only tenant-
    scoping join point available). A user with no Employee row in this org
    gets a 403 (`PermissionDeniedError`), never a 404 -- the same
    cross-tenant-must-not-leak-existence pattern this codebase has used
    since Module 8.

    Session management, password reset, and email verification delegate
    to the existing `AuthService` (Module 2) rather than reimplementing
    token issuance -- this class adds only the org-scoping check, the
    admin-initiated security event, and the audit trail around each call.
    """

    def __init__(
        self,
        *,
        user_repo: UserRepository,
        employee_repo: EmployeeRepository,
        permission_repo: PermissionRepository,
        auth_service: AuthService,
        security_event_repo: SecurityEventRepository,
        audit_repo: AuditLogRepository,
    ) -> None:
        self._users = user_repo
        self._employees = employee_repo
        self._permissions = permission_repo
        self._auth = auth_service
        self._security_events = security_event_repo
        self._audit = audit_repo

    async def _resolve(self, *, nursery_id: uuid.UUID, target_user_id: uuid.UUID) -> tuple[Employee, User]:
        employee = await self._employees.get_by_user_and_nursery(target_user_id, nursery_id)
        if employee is None:
            raise PermissionDeniedError("This user is not a member of your organization.")
        user = await self._users.get_by_id(target_user_id)
        if user is None:
            raise NotFoundError("User not found.")
        return employee, user

    async def _assert_not_owner(self, *, actor_user_id: uuid.UUID, employee: Employee) -> None:
        """Refuses to let anyone but the owner themself act on the owner's own account -- the same "owner is untouchable via generic admin actions" invariant `RoleAdminService.change_user_role` enforces."""
        assignment = await self._permissions.get_role_assignment_for_user(employee.user_id)
        if assignment is None:
            return
        role = await self._permissions.get_role_with_permissions(assignment.role_id)
        if role is not None and role.code == "owner" and employee.user_id != actor_user_id:
            raise PermissionDeniedError("The organization owner's account cannot be administered by another user.")

    async def search_users(
        self, *, nursery_id: uuid.UUID, offset: int, limit: int
    ) -> tuple[list[tuple[Employee, User]], int]:
        employees, total = await self._employees.list_for_nursery(nursery_id, offset=offset, limit=limit)
        users = await self._users.list_for_ids([e.user_id for e in employees])
        by_id = {u.id: u for u in users}
        return [(e, by_id[e.user_id]) for e in employees if e.user_id in by_id], total

    async def get_user_detail(self, *, nursery_id: uuid.UUID, target_user_id: uuid.UUID) -> tuple[Employee, User]:
        return await self._resolve(nursery_id=nursery_id, target_user_id=target_user_id)

    async def set_account_active(
        self,
        *,
        actor_user_id: uuid.UUID,
        nursery_id: uuid.UUID,
        target_user_id: uuid.UUID,
        is_active: bool,
        request_id: str | None = None,
    ) -> User:
        employee, user = await self._resolve(nursery_id=nursery_id, target_user_id=target_user_id)
        await self._assert_not_owner(actor_user_id=actor_user_id, employee=employee)
        before = user.is_active
        user = await self._users.set_active(user, is_active=is_active)
        event_type = (
            SecurityEventType.ACCOUNT_ACTIVATED_BY_ADMIN if is_active else SecurityEventType.ACCOUNT_DEACTIVATED_BY_ADMIN
        )
        await self._security_events.log(
            SecurityEvent(
                user_id=user.id, email=user.email, event_type=event_type,
                event_metadata={"initiated_by": "admin", "admin_user_id": str(actor_user_id)},
                created_at=datetime.now(timezone.utc),
            )
        )
        await _log_admin_audit(
            self._audit, nursery_id=nursery_id, actor_user_id=actor_user_id,
            action="admin.user.account_active_changed", entity_type="User", entity_id=user.id,
            diff={"before": {"is_active": before}, "after": {"is_active": is_active}}, request_id=request_id,
        )
        return user

    async def lock_account(
        self,
        *,
        actor_user_id: uuid.UUID,
        nursery_id: uuid.UUID,
        target_user_id: uuid.UUID,
        duration_minutes: int,
        request_id: str | None = None,
    ) -> User:
        employee, user = await self._resolve(nursery_id=nursery_id, target_user_id=target_user_id)
        await self._assert_not_owner(actor_user_id=actor_user_id, employee=employee)
        locked_until = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
        user = await self._users.set_locked_until(user, locked_until=locked_until)
        await self._security_events.log(
            SecurityEvent(
                user_id=user.id, email=user.email, event_type=SecurityEventType.ACCOUNT_LOCKED,
                event_metadata={"initiated_by": "admin", "admin_user_id": str(actor_user_id)},
                created_at=datetime.now(timezone.utc),
            )
        )
        await _log_admin_audit(
            self._audit, nursery_id=nursery_id, actor_user_id=actor_user_id,
            action="admin.user.locked", entity_type="User", entity_id=user.id,
            diff={"after": {"locked_until": locked_until.isoformat()}}, request_id=request_id,
        )
        return user

    async def unlock_account(
        self,
        *,
        actor_user_id: uuid.UUID,
        nursery_id: uuid.UUID,
        target_user_id: uuid.UUID,
        request_id: str | None = None,
    ) -> User:
        employee, user = await self._resolve(nursery_id=nursery_id, target_user_id=target_user_id)
        await self._assert_not_owner(actor_user_id=actor_user_id, employee=employee)
        user = await self._users.set_locked_until(user, locked_until=None)
        # Clears the strike counter too -- an unlock that left it primed at
        # the lockout threshold would re-lock on the next single failed
        # attempt (see UserRepository.reset_failed_login_attempts's docstring).
        user = await self._users.reset_failed_login_attempts(user)
        await self._security_events.log(
            SecurityEvent(
                user_id=user.id, email=user.email, event_type=SecurityEventType.ACCOUNT_UNLOCKED,
                event_metadata={"initiated_by": "admin", "admin_user_id": str(actor_user_id)},
                created_at=datetime.now(timezone.utc),
            )
        )
        await _log_admin_audit(
            self._audit, nursery_id=nursery_id, actor_user_id=actor_user_id,
            action="admin.user.unlocked", entity_type="User", entity_id=user.id,
            diff={"after": {"locked_until": None}}, request_id=request_id,
        )
        return user

    async def list_sessions(self, *, nursery_id: uuid.UUID, target_user_id: uuid.UUID) -> list[RefreshToken]:
        await self._resolve(nursery_id=nursery_id, target_user_id=target_user_id)
        return await self._auth.list_sessions(user_id=target_user_id)

    async def revoke_session(
        self,
        *,
        actor_user_id: uuid.UUID,
        nursery_id: uuid.UUID,
        target_user_id: uuid.UUID,
        session_id: uuid.UUID,
        request_id: str | None = None,
    ) -> None:
        employee, _user = await self._resolve(nursery_id=nursery_id, target_user_id=target_user_id)
        await self._assert_not_owner(actor_user_id=actor_user_id, employee=employee)
        await self._auth.revoke_session(user_id=target_user_id, session_id=session_id)
        await _log_admin_audit(
            self._audit, nursery_id=nursery_id, actor_user_id=actor_user_id,
            action="admin.user.session_revoked", entity_type="RefreshToken", entity_id=session_id,
            diff={}, request_id=request_id,
        )

    async def force_logout(
        self,
        *,
        actor_user_id: uuid.UUID,
        nursery_id: uuid.UUID,
        target_user_id: uuid.UUID,
        request_id: str | None = None,
    ) -> None:
        employee, _user = await self._resolve(nursery_id=nursery_id, target_user_id=target_user_id)
        await self._assert_not_owner(actor_user_id=actor_user_id, employee=employee)
        await self._auth.logout_all(user_id=target_user_id)
        await _log_admin_audit(
            self._audit, nursery_id=nursery_id, actor_user_id=actor_user_id,
            action="admin.user.force_logout", entity_type="User", entity_id=target_user_id,
            diff={}, request_id=request_id,
        )

    async def request_password_reset(
        self,
        *,
        actor_user_id: uuid.UUID,
        nursery_id: uuid.UUID,
        target_user_id: uuid.UUID,
        request_id: str | None = None,
    ) -> None:
        employee, user = await self._resolve(nursery_id=nursery_id, target_user_id=target_user_id)
        await self._assert_not_owner(actor_user_id=actor_user_id, employee=employee)
        await self._auth.request_password_reset(email=user.email, ip_address=None)
        await _log_admin_audit(
            self._audit, nursery_id=nursery_id, actor_user_id=actor_user_id,
            action="admin.user.password_reset_requested", entity_type="User", entity_id=user.id,
            diff={}, request_id=request_id,
        )

    async def request_email_verification(
        self,
        *,
        actor_user_id: uuid.UUID,
        nursery_id: uuid.UUID,
        target_user_id: uuid.UUID,
        request_id: str | None = None,
    ) -> None:
        employee, user = await self._resolve(nursery_id=nursery_id, target_user_id=target_user_id)
        await self._assert_not_owner(actor_user_id=actor_user_id, employee=employee)
        await self._auth.request_email_verification(user_id=user.id)
        await _log_admin_audit(
            self._audit, nursery_id=nursery_id, actor_user_id=actor_user_id,
            action="admin.user.email_verification_requested", entity_type="User", entity_id=user.id,
            diff={}, request_id=request_id,
        )


class FeatureFlagService:
    """Section 7: Feature Flags. See `FeatureFlag`'s own model docstring for the three-tier resolution shape."""

    def __init__(self, *, flag_repo: FeatureFlagRepository, audit_repo: AuditLogRepository) -> None:
        self._flags = flag_repo
        self._audit = audit_repo

    async def is_enabled(self, key: str, *, nursery_id: uuid.UUID | None = None, branch_id: uuid.UUID | None = None) -> bool:
        """"Feature flags must fail safely": a key with no row at any tier resolves to `False`, never raises."""
        flag = await self._flags.resolve(key, nursery_id=nursery_id, branch_id=branch_id)
        return flag.is_enabled if flag is not None else False

    async def list_flags(self, *, nursery_id: uuid.UUID | None = None) -> list[FeatureFlag]:
        return await self._flags.list_all(nursery_id=nursery_id)

    async def set_flag(
        self,
        *,
        actor_user_id: uuid.UUID,
        audit_nursery_id: uuid.UUID,
        key: str,
        target_nursery_id: uuid.UUID | None,
        branch_id: uuid.UUID | None,
        is_enabled: bool,
        description: str | None,
        request_id: str | None = None,
    ) -> FeatureFlag:
        """
        `audit_nursery_id` (always the caller's own org) and
        `target_nursery_id` (the tier being written -- `None` for a
        platform-wide default) are deliberately separate parameters: a
        `platform_admin` setting the platform-wide default for a key has
        no single "affected org", but `audit_logs.nursery_id` still needs
        a value (this module's own docstring explains why).
        """
        if branch_id is not None and target_nursery_id is None:
            raise ValidationError("A branch-scoped flag override requires an organization.")
        flag = await self._flags.upsert(
            key=key, nursery_id=target_nursery_id, branch_id=branch_id, is_enabled=is_enabled,
            description=description, updated_by_user_id=actor_user_id,
        )
        await _log_admin_audit(
            self._audit, nursery_id=audit_nursery_id, actor_user_id=actor_user_id,
            action="admin.feature_flag_set", entity_type="FeatureFlag", entity_id=flag.id,
            diff={"after": {"key": key, "is_enabled": is_enabled, "nursery_id": str(target_nursery_id) if target_nursery_id else None, "branch_id": str(branch_id) if branch_id else None}},
            request_id=request_id,
        )
        return flag


class SystemConfigService:
    """Section 6: System Configuration. Never accepts or exposes a secret -- see `SystemConfig`'s own model docstring."""

    def __init__(self, *, config_repo: SystemConfigRepository, audit_repo: AuditLogRepository) -> None:
        self._configs = config_repo
        self._audit = audit_repo

    async def list_configs(self, *, category: str | None = None) -> list[SystemConfig]:
        return await self._configs.list_all(category=category)

    async def get_config(self, key: str) -> SystemConfig:
        config = await self._configs.get(key)
        if config is None:
            raise NotFoundError(f"No system configuration exists for key {key!r}.")
        return config

    async def set_config(
        self,
        *,
        actor_user_id: uuid.UUID,
        audit_nursery_id: uuid.UUID,
        key: str,
        value: Any,
        value_type: str,
        category: str,
        description: str | None,
        request_id: str | None = None,
    ) -> SystemConfig:
        if category not in _VALID_CONFIG_CATEGORIES:
            raise ValidationError(f"Invalid category {category!r}; must be one of {sorted(_VALID_CONFIG_CATEGORIES)}.")
        if value_type not in _VALID_CONFIG_VALUE_TYPES:
            raise ValidationError(f"Invalid value_type {value_type!r}; must be one of {sorted(_VALID_CONFIG_VALUE_TYPES)}.")
        before = await self._configs.get(key)
        # Snapshot the pre-update value as a deep copy, NOT a reference to
        # `before` itself, before calling `upsert`. Regression: both
        # `FakeSystemConfigRepository.upsert` and
        # `SqlAlchemySystemConfigRepository.upsert` mutate the existing
        # row's `.value` attribute IN PLACE on an update (rather than
        # returning a new object) -- `SqlAlchemySystemConfigRepository`
        # additionally relies on SQLAlchemy's identity map, which
        # guarantees `get(key)` returns the exact same Python object
        # `upsert` then mutates. Capturing `before.value` by reference
        # here meant that by the time this diff was built, `before.value`
        # and `config.value` were the SAME (already-mutated) dict --
        # every "before" ever logged for a config update silently equaled
        # "after", making the audit trail useless for exactly the changes
        # it exists to record. Caught by
        # tests/unit/test_admin_service.py::test_set_config_round_trips_value_and_audits_before_after.
        before_value = dict(before.value) if before is not None else None
        config = await self._configs.upsert(
            key=key, value={"value": value}, value_type=value_type, category=category,
            description=description, updated_by_user_id=actor_user_id,
        )
        await _log_admin_audit(
            self._audit, nursery_id=audit_nursery_id, actor_user_id=actor_user_id,
            action="admin.system_config_set", entity_type="SystemConfig", entity_id=config.id,
            diff={
                "before": {"value": before_value} if before_value is not None else None,
                "after": {"value": config.value, "category": category},
            },
            request_id=request_id,
        )
        return config


class AuditAdminService:
    """Section 8: Audit & Security Administration -- the filterable search layer over `audit_logs`/`security_events`/`authorization_denials` this module adds on top of Module 3's original filterless viewer."""

    def __init__(
        self,
        *,
        audit_repo: AuditLogRepository,
        security_event_repo: SecurityEventRepository,
        denial_repo: AuthorizationDenialRepository,
    ) -> None:
        self._audit = audit_repo
        self._security_events = security_event_repo
        self._denials = denial_repo

    async def search_audit_logs(self, nursery_id: uuid.UUID, *, offset: int, limit: int, **filters) -> tuple[list[AuditLog], int]:
        return await self._audit.search_for_org(nursery_id, offset=offset, limit=limit, **filters)

    async def search_security_events(self, nursery_id: uuid.UUID, *, offset: int, limit: int, **filters) -> tuple[list[SecurityEvent], int]:
        return await self._security_events.search_for_org(nursery_id, offset=offset, limit=limit, **filters)

    async def platform_security_events(self, *, offset: int, limit: int, **filters) -> tuple[list[SecurityEvent], int]:
        """`platform_admin`-only cross-tenant view -- authorization for this is enforced at the route layer (`admin:read`, `target_nursery_id=None`), not here."""
        return await self._security_events.list_all(offset=offset, limit=limit, **filters)

    async def search_authorization_denials(self, nursery_id: uuid.UUID, *, offset: int, limit: int, **filters):
        return await self._denials.list_for_org(nursery_id, offset=offset, limit=limit, **filters)


@dataclass(frozen=True)
class HealthReport:
    api: str
    database_reachable: bool
    cache_reachable: bool
    cache_backend: str
    storage_configured: bool
    ai_anthropic_configured: bool
    ai_model_artifacts_configured: bool
    notifications_email_configured: bool
    notifications_sms_configured: bool
    notifications_push_configured: bool
    background_processing_configured: bool


class HealthCheckService:
    """
    Section 9: System Health. Every field is a boolean or a short label --
    "expose safe health information only... never secrets, credentials,
    internal tokens" is satisfied structurally: nothing on `HealthReport`
    is capable of holding a secret value, since every check here reduces
    to either a live round-trip (database, cache) or a `bool(setting)`
    presence check (storage/AI/notifications/background), never the
    setting's actual value.
    """

    def __init__(self, *, db_session, cache: Cache, settings: Settings) -> None:
        self._db = db_session
        self._cache = cache
        self._settings = settings

    async def check(self) -> HealthReport:
        database_reachable = await self._check_database()
        cache_reachable = await self._check_cache()
        return HealthReport(
            api="ok",
            database_reachable=database_reachable,
            cache_reachable=cache_reachable,
            cache_backend=type(self._cache).__name__,
            storage_configured=bool(self._settings.CLOUDINARY_CLOUD_NAME),
            ai_anthropic_configured=bool(self._settings.ANTHROPIC_API_KEY) or self._settings.LLM_PROVIDER == "ollama",
            ai_model_artifacts_configured=bool(self._settings.MODEL_ARTIFACT_BASE_PATH),
            notifications_email_configured=bool(self._settings.SMTP_HOST),
            notifications_sms_configured=bool(self._settings.SMS_PROVIDER_API_KEY),
            notifications_push_configured=bool(self._settings.PUSH_PROVIDER_API_KEY),
            background_processing_configured=bool(self._settings.CELERY_BROKER_URL),
        )

    async def _check_database(self) -> bool:
        try:
            from sqlalchemy import text

            await self._db.execute(text("SELECT 1"))
            return True
        except Exception:  # noqa: BLE001 -- any failure means "not reachable", mirrors /readyz's own broad catch
            return False

    async def _check_cache(self) -> bool:
        # A real round-trip through the app's own cache abstraction
        # (Module 3, app/core/cache.py) rather than reaching into a
        # provider-specific client -- exercises the exact code path the
        # rest of the application uses, works identically whether the
        # active backend is `RedisCache` or the documented `InMemoryCache`
        # fallback, and needs no change to Module 3's Cache Protocol.
        try:
            probe_key, probe_value = "admin:health:probe", "1"
            await self._cache.set(probe_key, probe_value, ttl_seconds=5)
            return await self._cache.get(probe_key) == probe_value
        except Exception:  # noqa: BLE001
            return False


class AIAdminService:
    """Section 10: AI Administration."""

    def __init__(
        self,
        *,
        prediction_repo: AIPredictionRepository,
        failure_repo: AIInferenceFailureRepository,
        knowledge_repo: KnowledgeBaseChunkRepository,
        model_registry: ModelRegistry,
    ) -> None:
        self._predictions = prediction_repo
        self._failures = failure_repo
        self._knowledge = knowledge_repo
        self._registry = model_registry

    def model_status(self) -> list[dict]:
        """
        "Model status/model configuration" without an arbitrary-change
        path: `is_configured()` is a read-only check against
        `Settings.MODEL_ARTIFACT_BASE_PATH` (an environment variable, not
        a database row) -- there is no method on this service that writes
        a model configuration, which is how Section 10's "do not allow
        arbitrary model configuration changes without appropriate
        authorization" is satisfied: the capability simply does not exist
        in the application layer at all, not merely gated.
        """
        return [{"capability": c, "configured": self._registry.is_configured(c)} for c in _AI_CAPABILITIES]

    async def usage_stats(
        self, nursery_id: uuid.UUID, *, date_from: datetime | None = None, date_to: datetime | None = None
    ) -> list[dict]:
        return await self._predictions.admin_stats_for_nursery(nursery_id, date_from=date_from, date_to=date_to)

    async def list_failures(
        self, nursery_id: uuid.UUID, *, offset: int, limit: int, capability: str | None = None
    ):
        return await self._failures.list_for_nursery(nursery_id, offset=offset, limit=limit, capability=capability)

    async def knowledge_base_status(self, *, nursery_id: uuid.UUID | None = None) -> list[dict]:
        return await self._knowledge.count_by_source_type(nursery_id=nursery_id)


class DataManagementService:
    """
    Section 11: Data Management. Deliberately read-only: "never provide
    unrestricted destructive database operations through the application"
    rules out a generic purge/delete endpoint, so this service offers
    retention *visibility* (a dry-run count of rows older than a
    threshold) rather than a deletion path. Export reuses
    `AuditAdminService`'s search methods plus `app/reporting/exporters.py`
    (Module 12) at the route layer -- no duplicate export logic here.
    Soft deletion/restoration for the entities this codebase actually
    supports it for (Employees, Branches) are Section 3/5 concerns,
    covered by `EmployeeService`/`BranchService` directly.
    """

    def __init__(
        self,
        *,
        audit_repo: AuditLogRepository,
        security_event_repo: SecurityEventRepository,
        prediction_repo: AIPredictionRepository,
        failure_repo: AIInferenceFailureRepository,
    ) -> None:
        self._audit = audit_repo
        self._security_events = security_event_repo
        self._predictions = prediction_repo
        self._failures = failure_repo

    async def retention_summary(self, nursery_id: uuid.UUID, *, older_than_days: int) -> dict:
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        _, audit_count = await self._audit.search_for_org(nursery_id, offset=0, limit=1, date_to=cutoff)
        _, failure_count = await self._failures.list_for_nursery(nursery_id, offset=0, limit=1)
        return {
            "cutoff": cutoff.isoformat(),
            "audit_logs_older_than_cutoff": audit_count,
            "ai_inference_failures_older_than_cutoff": failure_count,
            # AIPredictionRepository has no date-filtered count method
            # (Module 10 never needed one) -- reported as "not available"
            # rather than silently returning an unfiltered total that
            # would misrepresent what's actually eligible for retention.
            "ai_predictions_older_than_cutoff": None,
            "note": "Read-only visibility. No deletion is performed by this endpoint.",
        }
