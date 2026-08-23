"""
Shared FastAPI dependencies. Module 1 provided `get_db` and pagination
parsing. Module 2 (Authentication) adds: constructing an `AuthService`
wired to real SQLAlchemy repositories, decoding the bearer JWT into
`get_current_user`, and capturing per-request device context (IP/user
agent) for session tracking. Every later module imports
`get_current_user` from here rather than re-implementing token decoding,
so authentication is enforced identically everywhere.

Module 3 (Authorization) adds the enforcement layer that was deliberately
left out of Module 2: `get_tenant_context` resolves the caller's org/branch
scope once per request (and populates app/core/context.py's contextvars for
structured logging); `get_scoped_db` wires that org id into Postgres as the
`app.current_org_id` session variable the RLS policies
(migrations/versions/0003_row_level_security.py) key against; and
`require_permission` / `require_org_match` / `require_branch_match` /
`require_ownership_or_permission` are dependency *factories* — each call
returns a fresh FastAPI dependency closed over the specific permission code
and path-param names a given route needs — that all funnel through
`AuthorizationService.authorize()` (app/services/authorization_service.py),
so there is exactly one place that decides "is this allowed" and exactly
one place that writes the authorization-denial audit trail.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass

from fastapi import Depends, Query, Request, WebSocket
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import Cache
from app.core.config import Settings, get_settings
from app.core.context import current_branch_ids_var, current_org_id_var, current_user_id_var
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.rate_limit import RateLimiter
from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.models.identity import User
from app.repositories.interfaces import AuditLogRepository, InviteRepository
from app.repositories.sqlalchemy_repositories import (
    SqlAlchemyAIAssistantConversationRepository,
    SqlAlchemyAIAssistantMessageRepository,
    SqlAlchemyAIInferenceFailureRepository,
    SqlAlchemyAIPredictionRepository,
    SqlAlchemyAIRecommendationRepository,
    SqlAlchemyAuditLogRepository,
    SqlAlchemyAuthorizationDenialRepository,
    SqlAlchemyBranchRepository,
    SqlAlchemyFeatureFlagRepository,
    SqlAlchemySystemConfigRepository,
    SqlAlchemyCustomerAddressRepository,
    SqlAlchemyCustomerCommunicationRepository,
    SqlAlchemyCustomerContactRepository,
    SqlAlchemyCustomerNoteRepository,
    SqlAlchemyCustomerRepository,
    SqlAlchemyCustomerTagRepository,
    SqlAlchemyDigitalTwinRepository,
    SqlAlchemyDigitalTwinVersionRepository,
    SqlAlchemyDiseaseReportRepository,
    SqlAlchemyDomainEventRepository,
    SqlAlchemyEmailVerificationTokenRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyEnvironmentalReadingRepository,
    SqlAlchemyEventDispatchLogRepository,
    SqlAlchemyFertilizerLogRepository,
    SqlAlchemyGrowthTimelineRepository,
    SqlAlchemyHealthHistoryRepository,
    SqlAlchemyInventoryLocationRepository,
    SqlAlchemyInventoryRepository,
    SqlAlchemyInviteRepository,
    SqlAlchemyInvoiceItemRepository,
    SqlAlchemyInvoiceRepository,
    SqlAlchemyInvoiceSaleRepository,
    SqlAlchemyKnowledgeBaseChunkRepository,
    SqlAlchemyNotificationDeliveryRepository,
    SqlAlchemyNotificationPreferenceRepository,
    SqlAlchemyNotificationRepository,
    SqlAlchemyNotificationTemplateRepository,
    SqlAlchemyNurseryRepository,
    SqlAlchemyOrderItemRepository,
    SqlAlchemyPassportRepository,
    SqlAlchemyPasswordResetTokenRepository,
    SqlAlchemyPaymentRepository,
    SqlAlchemyPermissionRepository,
    SqlAlchemyPlantCategoryRepository,
    SqlAlchemyUnitRepository,
    SqlAlchemyPlantImageRepository,
    SqlAlchemyPlantRepository,
    SqlAlchemyPlantTransferRepository,
    SqlAlchemyPlantVarietyRepository,
    SqlAlchemyQRScanEventRepository,
    SqlAlchemyQuotationItemRepository,
    SqlAlchemyQuotationRepository,
    SqlAlchemyRefreshTokenRepository,
    SqlAlchemyRefundRepository,
    SqlAlchemyReportingRepository,
    SqlAlchemyReportRepository,
    SqlAlchemyReturnItemRepository,
    SqlAlchemyReturnRepository,
    SqlAlchemyScheduledReportRepository,
    SqlAlchemySaleItemRepository,
    SqlAlchemySaleRepository,
    SqlAlchemySalesOrderRepository,
    SqlAlchemySecurityEventRepository,
    SqlAlchemySpeciesRepository,
    SqlAlchemyStockMovementRepository,
    SqlAlchemyStockReservationRepository,
    SqlAlchemySupplierRepository,
    SqlAlchemyTreatmentRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyWateringLogRepository,
)
from app.ai.assistant.knowledge_retrieval import KnowledgeRetrievalService
from app.services.knowledge_article_service import KnowledgeArticleService
from app.ai.assistant.orchestrator import AssistantOrchestrator
from app.ai.assistant.tool_registry import AssistantToolRegistry
from app.ai.common import FeatureStore, ModelRegistry, PredictionLogger
from app.ai.disease_detection.inference import DiseaseDetectionInference
from app.ai.growth_prediction.inference import GrowthPredictionInference
from app.ai.recommendation_engine.engine import RecommendationEngine
from app.ai.revenue_forecast.inference import RevenueForecastInference
from app.ai.survival_prediction.inference import SurvivalPredictionInference
from app.ai.water_recommendation.inference import WaterRecommendationInference
from app.domain_events import DomainEventPublisher, EventDispatcher
from app.notifications.delivery import NotificationDeliveryService
from app.notifications.hub import NotificationHub
from app.notifications.notification_handler import NotificationEventHandler, NotificationService
from app.notifications.preferences import PreferenceService
from app.notifications.providers import (
    EmailProvider,
    LoggingPushProvider,
    LoggingSmsProvider,
    PushProvider,
    SmsProvider,
    SmtpEmailProvider,
)
from app.notifications.templates import TemplateService
from app.reporting.file_storage import FileStorage
from app.reporting.file_storage import get_file_storage as _build_file_storage
from app.services.admin_service import (
    AIAdminService,
    AuditAdminService,
    DataManagementService,
    FeatureFlagService,
    HealthCheckService,
    RoleAdminService,
    SystemConfigService,
    UserAdminService,
)
from app.services.analytics_service import AnalyticsService
from app.services.assistant_conversation_service import AssistantConversationService
from app.services.auth_service import AuthService, DeviceContext
from app.services.authorization_service import (
    AuthorizationDecision,
    AuthorizationService,
    RequestContext,
)
from app.services.branch_service import BranchService
from app.services.customer_service import CustomerService
from app.services.digital_twin_service import DigitalTwinEventHandler, DigitalTwinService
from app.services.disease_service import DiseaseReportService, TreatmentService
from app.services.email_sender import EmailSender, SmtpEmailSender
from app.services.employee_service import EmployeeService
from app.services.inventory_service import InventoryLocationService, InventoryService
from app.services.organization_service import OrganizationService
from app.services.passport_service import PassportService, QRService, resolve_passport_token_secret
from app.services.permission_service import PermissionService
from app.services.plant_records_service import (
    EnvironmentalService,
    FertilizerService,
    GrowthService,
    HealthService,
    WateringService,
)
from app.services.plant_service import PlantService
from app.services.plant_timeline_service import PlantTimelineService
from app.services.plant_variety_service import PlantVarietyService
from app.services.qr_code_service import QRCodeService
from app.services.report_generation_service import ReportGenerationService
from app.services.dashboard_service import DashboardService
from app.services.sales_service import (
    PaymentService,
    QuotationService,
    RefundService,
    ReturnService,
    SalesOrderService,
    SalesReportingService,
)
from app.services.scheduled_report_service import ScheduledReportService
from app.services.species_service import SpeciesService

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session


class PageParams:
    """Shared `?page=&page_size=` parsing, capped to keep list endpoints bounded."""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="1-indexed page number"),
        page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    ) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def get_rate_limiter(request: Request) -> RateLimiter:
    """
    Reads the limiter off `app.state` (set once in `create_app`'s lifespan,
    app/main.py) rather than a module-level global — a module-level
    singleton would be shared across every FastAPI app instance in the
    same process, which is exactly wrong in tests: each test constructs
    its own app via `create_app()` and expects its own, independent rate
    limit budget, not one bled over from whichever test ran first.
    """
    return request.app.state.rate_limiter


def get_email_sender(settings: Settings = Depends(get_settings)) -> EmailSender:
    return SmtpEmailSender(settings)


def _resolve_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    return (forwarded_for.split(",")[0].strip() if forwarded_for else None) or (
        request.client.host if request.client else None
    )


def get_device_context(request: Request) -> DeviceContext:
    return DeviceContext(
        device_name=request.headers.get("x-device-name"),
        user_agent=request.headers.get("user-agent"),
        ip_address=_resolve_client_ip(request),
    )


def _request_context(request: Request) -> RequestContext:
    """
    Shared by every Module 3 `require_*` dependency to build the
    RequestContext (request_id/ip) AuthorizationService needs to satisfy
    "every authorization failure must generate: ... Request ID, IP,
    Timestamp" — reuses `request.state.request_id`, the same
    middleware-populated value app/core/error_handlers.py's `_envelope()`
    prefers (see that module's docstring for why request.state, not the
    request_id_var contextvar, is the reliable source here).
    """
    return RequestContext(
        request_id=getattr(request.state, "request_id", None),
        ip_address=_resolve_client_ip(request),
    )


def get_auth_service(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    email_sender: EmailSender = Depends(get_email_sender),
) -> AuthService:
    return AuthService(
        settings=settings,
        user_repo=SqlAlchemyUserRepository(db),
        refresh_token_repo=SqlAlchemyRefreshTokenRepository(db),
        email_verification_repo=SqlAlchemyEmailVerificationTokenRepository(db),
        password_reset_repo=SqlAlchemyPasswordResetTokenRepository(db),
        security_event_repo=SqlAlchemySecurityEventRepository(db),
        permission_repo=SqlAlchemyPermissionRepository(db),
        invite_repo=SqlAlchemyInviteRepository(db),
        email_sender=email_sender,
    )


def get_cache(request: Request) -> Cache:
    """
    Mirrors `get_rate_limiter`: reads the cache off `app.state` (set to an
    `InMemoryCache` immediately in `create_app`, optionally upgraded to a
    `RedisCache` during `lifespan` if Redis is reachable — see
    `app/main.py`'s `_try_upgrade_to_redis_cache`) rather than a
    module-level singleton, for the exact same test-isolation reason
    `get_rate_limiter` gives.
    """
    return request.app.state.cache


def get_permission_service(
    db: AsyncSession = Depends(get_db), cache: Cache = Depends(get_cache)
) -> PermissionService:
    """
    Split out from `get_auth_service` so routes that only need role/
    permission resolution (GET /me) — and tests that only want to
    override *that* — don't have to construct a whole AuthService (and
    its email sender, invite repo, etc.) just to answer "what can this
    user do". Module 3 onward: always passes a cache (Module 2 callers
    that stubbed a bare `PermissionService(repo)` in tests still work —
    the cache argument is optional on the class itself).
    """
    return PermissionService(SqlAlchemyPermissionRepository(db), cache=cache)


def get_authorization_service(
    permission_service: PermissionService = Depends(get_permission_service),
    db: AsyncSession = Depends(get_db),
) -> AuthorizationService:
    return AuthorizationService(
        permission_service=permission_service,
        denial_repo=SqlAlchemyAuthorizationDenialRepository(db),
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise AuthenticationError("Missing bearer token.")
    payload = decode_access_token(credentials.credentials, settings=settings)
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("Malformed access token.") from exc

    user = await SqlAlchemyUserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Account no longer exists or is inactive.")
    return user


async def get_current_token_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Raw decoded claims (org_id/branch_ids/role/permissions), for routes
    that need the token's authorization context without a second DB
    round-trip to reload the user.
    """
    if credentials is None:
        raise AuthenticationError("Missing bearer token.")
    return decode_access_token(credentials.credentials, settings=settings)


# --------------------------------------------------------------------------
# Module 3 — Authorization & multi-tenancy enforcement
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class TenantContext:
    """
    A request's resolved org/branch scope — the "Nursery -> Branch"
    portion of the module's required "Nursery -> Branch -> Resource"
    enforcement chain. `org_id=None` means the caller has no
    RoleAssignment yet (see PermissionService._resolve_from_database);
    routes that require org membership must go through `require_org_match`
    / `require_permission`, which reject that case explicitly rather than
    silently treating "no org" as "any org".
    """

    org_id: uuid.UUID | None
    branch_ids: tuple[uuid.UUID, ...]
    role_code: str | None
    permissions: tuple[str, ...]

    def is_org_wide(self) -> bool:
        return len(self.branch_ids) == 0


async def get_tenant_context(
    user: User = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
) -> TenantContext:
    """
    Resolves the caller's effective access exactly once per request
    (PermissionService caches this, so concurrent dependencies resolving
    it within the same request/process still only hit Redis/Postgres
    once per cache TTL, not once per dependency). Also populates
    app/core/context.py's contextvars so structured logs emitted anywhere
    in this request automatically carry user/org/branch context, per that
    module's docstring.
    """
    access = await permission_service.resolve_for_user(user.id)
    current_user_id_var.set(user.id)
    current_org_id_var.set(access.org_id)
    current_branch_ids_var.set(tuple(access.branch_ids))
    return TenantContext(
        org_id=access.org_id,
        branch_ids=tuple(access.branch_ids),
        role_code=access.role_code,
        permissions=tuple(access.permissions),
    )


async def get_scoped_db(
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
) -> AsyncGenerator[AsyncSession, None]:
    """
    Issues `SELECT set_config('app.current_org_id', ..., true)` at the
    start of the request's transaction — the session variable
    migrations/versions/0003_row_level_security.py's RLS policies key
    against via `current_setting('app.current_org_id', true)::uuid`. Uses
    `set_config` with a bound parameter rather than a raw `SET LOCAL
    app.current_org_id = '<value>'` string, since `SET` does not accept
    bind parameters in Postgres and string-formatting a session variable
    is an injection risk even for a value we control — `set_config` is
    the parameterized equivalent, and the `true` third argument makes it
    transaction-local (`is_local`), matching `SET LOCAL` semantics so the
    value never leaks to a pooled connection's next transaction.

    Routes that must enforce row-level tenant isolation depend on this
    instead of the bare `get_db` — cross-tenant access becomes impossible
    at the database layer, not just the application layer, satisfying the
    module's "cross-tenant access must be impossible" requirement even if
    an application-layer check is ever missed.

    A caller with no org membership yet (`tenant.org_id is None`) simply
    gets a session with no session variable set — RLS policies compare
    against `current_setting(..., true)`'s `true` missing-ok flag, which
    resolves to NULL, and every policy's `nursery_id = NULL` comparison
    is false, so an org-less caller sees zero rows rather than an error.
    That fits routes like `GET /me` that use `get_scoped_db` defensively
    without themselves requiring org membership.
    """
    if tenant.org_id is not None:
        await db.execute(text("SELECT set_config('app.current_org_id', :val, true)"), {"val": str(tenant.org_id)})
    yield db


def get_audit_log_repository(db: AsyncSession = Depends(get_scoped_db)) -> AuditLogRepository:
    """
    Injectable rather than routes constructing `SqlAlchemyAuditLogRepository`
    inline — same reasoning as every other `get_*_repository`-shaped
    dependency in this module: production always gets the real SQLAlchemy
    implementation, but `tests/integration/test_audit_routes.py` can
    override this one dependency with `FakeAuditLogRepository`
    (tests/fakes/repositories.py) to integration-test the route's
    permission/tenant-scoping/pagination wiring without a live database.
    """
    return SqlAlchemyAuditLogRepository(db)


def _permission_denied(decision: AuthorizationDecision) -> PermissionDeniedError:
    return PermissionDeniedError(
        decision.explanation,
        context={
            "permission": decision.permission,
            "reason": decision.reason.value if decision.reason else None,
            "resource_type": decision.resource_type,
            "resource_id": str(decision.resource_id) if decision.resource_id else None,
        },
    )


def require_permission(
    permission: str, *, resource_type: str | None = None
) -> Callable[..., Awaitable[AuthorizationDecision]]:
    """
    Dependency factory for the common case: "this route requires
    `<module>:<action>`, no path-scoped nursery/branch, no ownership
    fallback." Usage: `Depends(require_permission("audit:read"))`. Each
    call returns a fresh closure (not a shared dependency instance), so
    two routes requiring different permissions never collide.
    """

    async def _dependency(
        request: Request,
        user: User = Depends(get_current_user),
        authz: AuthorizationService = Depends(get_authorization_service),
    ) -> AuthorizationDecision:
        decision = await authz.authorize(
            user=user,
            permission=permission,
            resource_type=resource_type,
            context=_request_context(request),
        )
        if not decision.allowed:
            raise _permission_denied(decision)
        return decision

    return _dependency


def require_org_match(
    permission: str, *, nursery_id_param: str = "nursery_id", resource_type: str | None = None
) -> Callable[..., Awaitable[AuthorizationDecision]]:
    """
    For routes shaped like `/nurseries/{nursery_id}/...`: requires the
    permission *and* that the path's `nursery_id` matches the caller's
    own org (`AuthorizationDenialReason.CROSS_TENANT_ORG` otherwise).
    `nursery_id_param` lets a route rename the path parameter (e.g.
    `org_id`) without needing its own bespoke dependency.
    """

    async def _dependency(
        request: Request,
        user: User = Depends(get_current_user),
        authz: AuthorizationService = Depends(get_authorization_service),
    ) -> AuthorizationDecision:
        raw = request.path_params.get(nursery_id_param)
        target_nursery_id = uuid.UUID(str(raw)) if raw is not None else None
        decision = await authz.authorize(
            user=user,
            permission=permission,
            resource_type=resource_type,
            target_nursery_id=target_nursery_id,
            context=_request_context(request),
        )
        if not decision.allowed:
            raise _permission_denied(decision)
        return decision

    return _dependency


def require_branch_match(
    permission: str,
    *,
    nursery_id_param: str = "nursery_id",
    branch_id_param: str = "branch_id",
    resource_type: str | None = None,
) -> Callable[..., Awaitable[AuthorizationDecision]]:
    """
    For routes shaped like `/nurseries/{nursery_id}/branches/{branch_id}/...`:
    requires the permission, org match, *and* (for role assignments scoped
    to specific branches — see `ResolvedAccess.is_org_wide()`) that the
    path's `branch_id` is one of the caller's assigned branches.
    """

    async def _dependency(
        request: Request,
        user: User = Depends(get_current_user),
        authz: AuthorizationService = Depends(get_authorization_service),
    ) -> AuthorizationDecision:
        raw_nursery = request.path_params.get(nursery_id_param)
        raw_branch = request.path_params.get(branch_id_param)
        decision = await authz.authorize(
            user=user,
            permission=permission,
            resource_type=resource_type,
            target_nursery_id=uuid.UUID(str(raw_nursery)) if raw_nursery is not None else None,
            target_branch_id=uuid.UUID(str(raw_branch)) if raw_branch is not None else None,
            context=_request_context(request),
        )
        if not decision.allowed:
            raise _permission_denied(decision)
        return decision

    return _dependency


def require_ownership_or_permission(
    permission: str,
    *,
    resolve_owner_id: Callable[[Request], Awaitable[uuid.UUID | None]] | None = None,
    resource_type: str | None = None,
) -> Callable[..., Awaitable[AuthorizationDecision]]:
    """
    For routes where a caller should be able to act on their *own*
    resource even without the blanket permission (e.g. a customer reading
    their own order) — allowed if either the permission is granted, or
    `resolve_owner_id(request)` returns the caller's own user id.
    `resolve_owner_id` is intentionally a caller-supplied async lookup
    (typically a small repository call keyed off a path param) rather
    than a fixed path-param name, since "who owns this resource" is a
    per-resource-type question this module — which owns no business
    resources of its own — can't hardcode; later modules (e.g. Module 6+)
    pass their own resolver when they wire this up for a real resource.
    """

    async def _dependency(
        request: Request,
        user: User = Depends(get_current_user),
        authz: AuthorizationService = Depends(get_authorization_service),
    ) -> AuthorizationDecision:
        owner_id = await resolve_owner_id(request) if resolve_owner_id is not None else None
        decision = await authz.authorize(
            user=user,
            permission=permission,
            resource_type=resource_type,
            resource_owner_user_id=owner_id,
            context=_request_context(request),
        )
        if not decision.allowed:
            raise _permission_denied(decision)
        return decision

    return _dependency


# Public aliases of the module-private helpers above, for routes that need
# a *manual* `AuthorizationService.authorize()` call outside the
# `require_*` dependency factories -- e.g. a flat `/branches/{id}` route
# (Module 4) with no `nursery_id` in its path, which must fetch the
# resource first to learn which org it belongs to before a cross-tenant
# check is even possible. The `require_*` factories assume the tenant id
# is already sitting in `request.path_params`, which a flat resource route
# doesn't have.
request_context = _request_context
raise_if_denied = _permission_denied


# --------------------------------------------------------------------------
# Module 4 — Nursery & Organization Management
# --------------------------------------------------------------------------


def get_domain_event_publisher(
    request: Request, db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)
) -> DomainEventPublisher:
    """
    Added by Phase 6 Module 7: every publisher now carries a fully-wired
    `EventDispatcher` with the Digital Twin projector registered, so
    every event any module's service publishes through this dependency
    automatically reaches `DigitalTwinService.project()` -- exactly the
    architecture diagram's "Domain Event -> Digital Twin Event Handler"
    step, with zero changes needed in any Module 4/5/6 service's own code
    (they only ever called `publisher.publish(event)`).

    Phase 6 Module 11 extends this the identical way: `NotificationEventHandler`
    is registered alongside `DigitalTwinEventHandler` on the same
    dispatcher, so "Domain Event -> Notification Event Handler" (this
    module's own ARCHITECTURE diagram) is likewise automatic for every
    Module 4-11 service with zero change to any of their own code -- the
    concrete structural proof of "no business module may send
    notifications directly."

    Builds every repository directly from `db` here (not via other
    `Depends(get_*_repository)` functions) deliberately: this function is
    defined early in the file (Module 4 was the first to need it) but the
    Digital Twin's own repositories are defined later, alongside the rest
    of Module 6/7's dependencies -- referencing those functions by name in
    a `Depends(...)` default here would be a forward reference Python
    can't resolve at function-definition time. Instantiating the classes
    directly sidesteps that ordering constraint entirely; every instance
    still shares this same request's `db` session, so it's transactionally
    identical to going through the usual per-repository dependency
    functions. `get_digital_twin_service`/`get_notification_service` below
    are the separate, `Depends()`-based dependencies the read-only/REST
    routes use.
    """
    dispatch_log_repo = SqlAlchemyEventDispatchLogRepository(db)
    digital_twin_service = DigitalTwinService(
        twin_repo=SqlAlchemyDigitalTwinRepository(db),
        version_repo=SqlAlchemyDigitalTwinVersionRepository(db),
        domain_event_repo=SqlAlchemyDomainEventRepository(db),
        plant_repo=SqlAlchemyPlantRepository(db),
        growth_repo=SqlAlchemyGrowthTimelineRepository(db),
        health_repo=SqlAlchemyHealthHistoryRepository(db),
        watering_repo=SqlAlchemyWateringLogRepository(db),
        fertilizer_repo=SqlAlchemyFertilizerLogRepository(db),
        environmental_repo=SqlAlchemyEnvironmentalReadingRepository(db),
        disease_repo=SqlAlchemyDiseaseReportRepository(db),
        treatment_repo=SqlAlchemyTreatmentRepository(db),
        return_item_repo=SqlAlchemyReturnItemRepository(db),
    )
    notification_service = NotificationService(
        notification_repo=SqlAlchemyNotificationRepository(db),
        delivery_service=NotificationDeliveryService(
            delivery_repo=SqlAlchemyNotificationDeliveryRepository(db),
            email_provider=SmtpEmailProvider(settings),
            sms_provider=LoggingSmsProvider(settings),
            push_provider=LoggingPushProvider(settings),
        ),
        preference_service=PreferenceService(SqlAlchemyNotificationPreferenceRepository(db)),
        template_service=TemplateService(SqlAlchemyNotificationTemplateRepository(db)),
        hub=request.app.state.notification_hub,
        user_repo=SqlAlchemyUserRepository(db),
    )
    notification_handler = NotificationEventHandler(
        notification_service=notification_service,
        permission_repo=SqlAlchemyPermissionRepository(db),
        plant_repo=SqlAlchemyPlantRepository(db),
        inventory_repo=SqlAlchemyInventoryRepository(db),
        invoice_repo=SqlAlchemyInvoiceRepository(db),
        sales_order_repo=SqlAlchemySalesOrderRepository(db),
        employee_repo=SqlAlchemyEmployeeRepository(db),
    )
    dispatcher = EventDispatcher(dispatch_log_repo)
    dispatcher.register(DigitalTwinEventHandler(digital_twin_service))
    dispatcher.register(notification_handler)
    return DomainEventPublisher(SqlAlchemyDomainEventRepository(db), dispatcher)


def get_nursery_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyNurseryRepository(db)


def get_branch_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyBranchRepository(db)


def get_employee_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyEmployeeRepository(db)


def get_invite_repository(db: AsyncSession = Depends(get_db)) -> InviteRepository:
    return SqlAlchemyInviteRepository(db)


def get_organization_service(
    nursery_repo=Depends(get_nursery_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
) -> OrganizationService:
    return OrganizationService(nursery_repo=nursery_repo, audit_repo=audit_repo, event_publisher=event_publisher)


def get_branch_service(
    branch_repo=Depends(get_branch_repository),
    nursery_repo=Depends(get_nursery_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
) -> BranchService:
    return BranchService(
        branch_repo=branch_repo,
        nursery_repo=nursery_repo,
        audit_repo=audit_repo,
        event_publisher=event_publisher,
    )


def get_employee_service(
    settings: Settings = Depends(get_settings),
    employee_repo=Depends(get_employee_repository),
    invite_repo: InviteRepository = Depends(get_invite_repository),
    branch_repo=Depends(get_branch_repository),
    db: AsyncSession = Depends(get_db),
    permission_service: PermissionService = Depends(get_permission_service),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
    email_sender: EmailSender = Depends(get_email_sender),
) -> EmployeeService:
    return EmployeeService(
        settings=settings,
        employee_repo=employee_repo,
        invite_repo=invite_repo,
        branch_repo=branch_repo,
        user_repo=SqlAlchemyUserRepository(db),
        permission_repo=SqlAlchemyPermissionRepository(db),
        permission_service=permission_service,
        audit_repo=audit_repo,
        event_publisher=event_publisher,
        email_sender=email_sender,
    )


# --------------------------------------------------------------------------
# Module 5 — Species Catalog
# --------------------------------------------------------------------------


def get_plant_category_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyPlantCategoryRepository(db)


def get_species_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemySpeciesRepository(db)


def get_plant_variety_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyPlantVarietyRepository(db)


def get_species_service(
    species_repo=Depends(get_species_repository),
    category_repo=Depends(get_plant_category_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
) -> SpeciesService:
    return SpeciesService(
        species_repo=species_repo,
        category_repo=category_repo,
        audit_repo=audit_repo,
        event_publisher=event_publisher,
    )


def get_plant_variety_service(
    variety_repo=Depends(get_plant_variety_repository),
    species_repo=Depends(get_species_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
) -> PlantVarietyService:
    return PlantVarietyService(
        variety_repo=variety_repo,
        species_repo=species_repo,
        audit_repo=audit_repo,
        event_publisher=event_publisher,
    )


# --------------------------------------------------------------------------
# Module 6 — Plant Lifecycle Management
# --------------------------------------------------------------------------


def get_plant_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyPlantRepository(db)


def get_plant_image_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyPlantImageRepository(db)


def get_plant_transfer_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyPlantTransferRepository(db)


def get_growth_timeline_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyGrowthTimelineRepository(db)


def get_health_history_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyHealthHistoryRepository(db)


def get_watering_log_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyWateringLogRepository(db)


def get_fertilizer_log_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyFertilizerLogRepository(db)


def get_environmental_reading_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyEnvironmentalReadingRepository(db)


def get_disease_report_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyDiseaseReportRepository(db)


def get_treatment_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyTreatmentRepository(db)


def get_supplier_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemySupplierRepository(db)


def get_qr_code_service(plant_repo=Depends(get_plant_repository)) -> QRCodeService:
    return QRCodeService(plant_repo)


def get_plant_service(
    plant_repo=Depends(get_plant_repository),
    image_repo=Depends(get_plant_image_repository),
    transfer_repo=Depends(get_plant_transfer_repository),
    species_repo=Depends(get_species_repository),
    variety_repo=Depends(get_plant_variety_repository),
    branch_repo=Depends(get_branch_repository),
    supplier_repo=Depends(get_supplier_repository),
    disease_repo=Depends(get_disease_report_repository),
    treatment_repo=Depends(get_treatment_repository),
    qr_service: QRCodeService = Depends(get_qr_code_service),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
) -> PlantService:
    return PlantService(
        plant_repo=plant_repo,
        image_repo=image_repo,
        transfer_repo=transfer_repo,
        species_repo=species_repo,
        variety_repo=variety_repo,
        branch_repo=branch_repo,
        supplier_repo=supplier_repo,
        disease_repo=disease_repo,
        treatment_repo=treatment_repo,
        qr_service=qr_service,
        audit_repo=audit_repo,
        event_publisher=event_publisher,
    )


def get_growth_service(
    growth_repo=Depends(get_growth_timeline_repository),
    plant_repo=Depends(get_plant_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
) -> GrowthService:
    return GrowthService(growth_repo=growth_repo, plant_repo=plant_repo, audit_repo=audit_repo, event_publisher=event_publisher)


def get_health_service(
    health_repo=Depends(get_health_history_repository),
    plant_repo=Depends(get_plant_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
) -> HealthService:
    return HealthService(health_repo=health_repo, plant_repo=plant_repo, audit_repo=audit_repo, event_publisher=event_publisher)


def get_watering_service(
    watering_repo=Depends(get_watering_log_repository),
    plant_repo=Depends(get_plant_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
) -> WateringService:
    return WateringService(watering_repo=watering_repo, plant_repo=plant_repo, audit_repo=audit_repo, event_publisher=event_publisher)


def get_fertilizer_service(
    fertilizer_repo=Depends(get_fertilizer_log_repository),
    plant_repo=Depends(get_plant_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
) -> FertilizerService:
    return FertilizerService(
        fertilizer_repo=fertilizer_repo, plant_repo=plant_repo, audit_repo=audit_repo, event_publisher=event_publisher
    )


def get_environmental_service(
    environmental_repo=Depends(get_environmental_reading_repository),
    plant_repo=Depends(get_plant_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
) -> EnvironmentalService:
    return EnvironmentalService(
        environmental_repo=environmental_repo, plant_repo=plant_repo, audit_repo=audit_repo, event_publisher=event_publisher
    )


def get_disease_report_service(
    disease_repo=Depends(get_disease_report_repository),
    plant_service: PlantService = Depends(get_plant_service),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
) -> DiseaseReportService:
    return DiseaseReportService(
        disease_repo=disease_repo, plant_service=plant_service, audit_repo=audit_repo, event_publisher=event_publisher
    )


def get_treatment_service(
    treatment_repo=Depends(get_treatment_repository),
    disease_repo=Depends(get_disease_report_repository),
    plant_service: PlantService = Depends(get_plant_service),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
) -> TreatmentService:
    return TreatmentService(
        treatment_repo=treatment_repo, disease_repo=disease_repo, plant_service=plant_service,
        audit_repo=audit_repo, event_publisher=event_publisher,
    )


def get_plant_timeline_service(
    plant_repo=Depends(get_plant_repository),
    transfer_repo=Depends(get_plant_transfer_repository),
    image_repo=Depends(get_plant_image_repository),
    growth_repo=Depends(get_growth_timeline_repository),
    health_repo=Depends(get_health_history_repository),
    watering_repo=Depends(get_watering_log_repository),
    fertilizer_repo=Depends(get_fertilizer_log_repository),
    disease_repo=Depends(get_disease_report_repository),
    treatment_repo=Depends(get_treatment_repository),
) -> PlantTimelineService:
    return PlantTimelineService(
        plant_repo=plant_repo, transfer_repo=transfer_repo, image_repo=image_repo, growth_repo=growth_repo,
        health_repo=health_repo, watering_repo=watering_repo, fertilizer_repo=fertilizer_repo,
        disease_repo=disease_repo, treatment_repo=treatment_repo,
    )


# --------------------------------------------------------------------------
# Module 7 — Plant Digital Twin Engine
# --------------------------------------------------------------------------


def get_domain_event_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyDomainEventRepository(db)


def get_digital_twin_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyDigitalTwinRepository(db)


def get_digital_twin_version_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyDigitalTwinVersionRepository(db)


def get_event_dispatch_log_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyEventDispatchLogRepository(db)


def get_return_item_repository(db: AsyncSession = Depends(get_db)):
    """
    Defined ahead of `get_return_repository`/the rest of Module 9's
    repository factories (down by `get_return_repository` further below,
    which conceptually reads more naturally) for the same reason
    `get_passport_service` was moved earlier in this file: `get_digital_
    twin_service`'s own `Depends(get_return_item_repository)` default is
    resolved by name at module-import time, and `get_return_item_
    repository` must already exist by then.
    """
    return SqlAlchemyReturnItemRepository(db)


def get_digital_twin_service(
    twin_repo=Depends(get_digital_twin_repository),
    version_repo=Depends(get_digital_twin_version_repository),
    domain_event_repo=Depends(get_domain_event_repository),
    plant_repo=Depends(get_plant_repository),
    growth_repo=Depends(get_growth_timeline_repository),
    health_repo=Depends(get_health_history_repository),
    watering_repo=Depends(get_watering_log_repository),
    fertilizer_repo=Depends(get_fertilizer_log_repository),
    environmental_repo=Depends(get_environmental_reading_repository),
    disease_repo=Depends(get_disease_report_repository),
    treatment_repo=Depends(get_treatment_repository),
    return_item_repo=Depends(get_return_item_repository),
) -> DigitalTwinService:
    """
    The read-facing dependency `app/api/routes/digital_twin.py` uses for
    every query endpoint. Distinct from the `DigitalTwinService` instance
    `get_domain_event_publisher` builds internally to wire the dispatcher
    -- both are constructed the same way, from the same repositories,
    against the same request-scoped `db` session, so a query issued
    immediately after a write in the same request sees that write's
    projected result. `return_item_repo` (Module 9) backs
    `_on_plant_returned`'s `line_refund_amount` enrichment read -- see
    digital_twin_service.py's own PROJECTED_EVENT_TYPES comment.
    """
    return DigitalTwinService(
        twin_repo=twin_repo, version_repo=version_repo, domain_event_repo=domain_event_repo, plant_repo=plant_repo,
        growth_repo=growth_repo, health_repo=health_repo, watering_repo=watering_repo,
        fertilizer_repo=fertilizer_repo, environmental_repo=environmental_repo, disease_repo=disease_repo,
        treatment_repo=treatment_repo, return_item_repo=return_item_repo,
    )


# --------------------------------------------------------------------------
# Module 8 — Inventory & Stock Management
# --------------------------------------------------------------------------


def get_inventory_location_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyInventoryLocationRepository(db)


def get_unit_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyUnitRepository(db)


def get_inventory_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyInventoryRepository(db)


def get_stock_movement_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyStockMovementRepository(db)


def get_stock_reservation_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyStockReservationRepository(db)


def get_inventory_location_service(
    location_repo=Depends(get_inventory_location_repository),
    unit_repo=Depends(get_unit_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
) -> InventoryLocationService:
    return InventoryLocationService(
        location_repo=location_repo, unit_repo=unit_repo, audit_repo=audit_repo, event_publisher=event_publisher
    )


def get_inventory_service(
    inventory_repo=Depends(get_inventory_repository),
    location_repo=Depends(get_inventory_location_repository),
    movement_repo=Depends(get_stock_movement_repository),
    reservation_repo=Depends(get_stock_reservation_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
) -> InventoryService:
    """
    `event_publisher` is the same fully-wired-with-dispatcher instance
    every other module's service receives (see `get_domain_event_publisher`'s
    own docstring) -- when `InventoryService` publishes
    `InventoryMovementRecorded` (the one narrow Digital Twin coupling
    point, see app/services/inventory_service.py's module docstring),
    it reaches the existing `DigitalTwinEventHandler` through this exact
    same path, with zero new plumbing beyond adding that event type to
    `DigitalTwinService.PROJECTED_EVENT_TYPES`.
    """
    return InventoryService(
        inventory_repo=inventory_repo, location_repo=location_repo, movement_repo=movement_repo,
        reservation_repo=reservation_repo, audit_repo=audit_repo, event_publisher=event_publisher,
    )


# --------------------------------------------------------------------------
# Module 9 — Sales, CRM, Plant Passport & QR Intelligence
# --------------------------------------------------------------------------


def get_customer_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyCustomerRepository(db)


def get_customer_contact_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyCustomerContactRepository(db)


def get_customer_address_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyCustomerAddressRepository(db)


def get_customer_tag_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyCustomerTagRepository(db)


def get_customer_note_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyCustomerNoteRepository(db)


def get_customer_communication_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyCustomerCommunicationRepository(db)


def get_quotation_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyQuotationRepository(db)


def get_quotation_item_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyQuotationItemRepository(db)


def get_sales_order_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemySalesOrderRepository(db)


def get_order_item_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyOrderItemRepository(db)


def get_sale_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemySaleRepository(db)


def get_sale_item_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemySaleItemRepository(db)


def get_invoice_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyInvoiceRepository(db)


def get_invoice_item_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyInvoiceItemRepository(db)


def get_invoice_sale_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyInvoiceSaleRepository(db)


def get_payment_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyPaymentRepository(db)


def get_return_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyReturnRepository(db)


def get_refund_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyRefundRepository(db)


def get_passport_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyPassportRepository(db)


def get_qr_scan_event_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyQRScanEventRepository(db)


def get_customer_service(
    customer_repo=Depends(get_customer_repository),
    contact_repo=Depends(get_customer_contact_repository),
    address_repo=Depends(get_customer_address_repository),
    tag_repo=Depends(get_customer_tag_repository),
    note_repo=Depends(get_customer_note_repository),
    communication_repo=Depends(get_customer_communication_repository),
    sale_repo=Depends(get_sale_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
) -> CustomerService:
    return CustomerService(
        customer_repo=customer_repo, contact_repo=contact_repo, address_repo=address_repo, tag_repo=tag_repo,
        note_repo=note_repo, communication_repo=communication_repo, sale_repo=sale_repo, audit_repo=audit_repo,
        event_publisher=event_publisher,
    )


def get_passport_token_secret(settings: Settings = Depends(get_settings)) -> bytes:
    return resolve_passport_token_secret(settings)


def get_passport_service(
    passport_repo=Depends(get_passport_repository),
    plant_repo=Depends(get_plant_repository),
    species_repo=Depends(get_species_repository),
    variety_repo=Depends(get_plant_variety_repository),
    nursery_repo=Depends(get_nursery_repository),
    branch_repo=Depends(get_branch_repository),
    growth_repo=Depends(get_growth_timeline_repository),
    health_repo=Depends(get_health_history_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
    token_secret: bytes = Depends(get_passport_token_secret),
) -> PassportService:
    """
    `event_publisher` is the same dispatcher-wired instance every other
    module's service receives -- `PassportGenerated`/`QRGenerated` reach
    the Digital Twin projector's new Sales/Ownership/Revenue timeline
    handlers through this exact same path, zero new plumbing beyond
    registering those event types (see digital_twin_service.py). Defined
    ahead of `get_sales_order_service` in this file (rather than down by
    `get_qr_service`, where it conceptually reads more naturally) because
    `get_sales_order_service`'s own `Depends(get_passport_service)`
    default is resolved by name at module-import time, not lazily --
    Python raises `NameError` on a forward reference in a default
    argument, so definition order here is a real constraint, not just
    style.
    """
    return PassportService(
        passport_repo=passport_repo, plant_repo=plant_repo, species_repo=species_repo, variety_repo=variety_repo,
        nursery_repo=nursery_repo, branch_repo=branch_repo, growth_repo=growth_repo, health_repo=health_repo,
        audit_repo=audit_repo, event_publisher=event_publisher, token_secret=token_secret,
    )


def get_quotation_service(
    quotation_repo=Depends(get_quotation_repository),
    quotation_item_repo=Depends(get_quotation_item_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
) -> QuotationService:
    return QuotationService(
        quotation_repo=quotation_repo, quotation_item_repo=quotation_item_repo, audit_repo=audit_repo,
        event_publisher=event_publisher,
    )


def get_sales_order_service(
    order_repo=Depends(get_sales_order_repository),
    order_item_repo=Depends(get_order_item_repository),
    sale_repo=Depends(get_sale_repository),
    sale_item_repo=Depends(get_sale_item_repository),
    invoice_repo=Depends(get_invoice_repository),
    invoice_item_repo=Depends(get_invoice_item_repository),
    invoice_sale_repo=Depends(get_invoice_sale_repository),
    inventory_service: InventoryService = Depends(get_inventory_service),
    passport_service: PassportService = Depends(get_passport_service),
    plant_repo=Depends(get_plant_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
) -> SalesOrderService:
    """
    `inventory_service` is the same real `InventoryService` (Module 8)
    every inventory route uses -- `confirm_order`/`checkout` call its
    public `reserve_stock`/`fulfill_reservation`/`sell_stock_direct`
    methods directly (a legitimate in-request cross-context service call,
    not the forbidden Plant-Lifecycle coupling -- see
    app/services/sales_service.py's module docstring). `passport_service`
    is wired here (rather than only reachable from app/api/routes/
    passport.py) so `checkout()` can generate each sold plant's Passport
    synchronously, in the same request -- see `checkout()`'s own comment
    for why this isn't the forbidden coupling either (Passport is this
    same module's own bounded context).
    """
    return SalesOrderService(
        order_repo=order_repo, order_item_repo=order_item_repo, sale_repo=sale_repo, sale_item_repo=sale_item_repo,
        invoice_repo=invoice_repo, invoice_item_repo=invoice_item_repo, invoice_sale_repo=invoice_sale_repo,
        inventory_service=inventory_service, passport_service=passport_service, plant_repo=plant_repo,
        audit_repo=audit_repo, event_publisher=event_publisher,
    )


def get_payment_service(
    payment_repo=Depends(get_payment_repository),
    invoice_repo=Depends(get_invoice_repository),
    order_repo=Depends(get_sales_order_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
) -> PaymentService:
    return PaymentService(
        payment_repo=payment_repo, invoice_repo=invoice_repo, order_repo=order_repo, audit_repo=audit_repo,
        event_publisher=event_publisher,
    )


def get_return_service(
    return_repo=Depends(get_return_repository),
    return_item_repo=Depends(get_return_item_repository),
    sale_item_repo=Depends(get_sale_item_repository),
    inventory_service: InventoryService = Depends(get_inventory_service),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
) -> ReturnService:
    return ReturnService(
        return_repo=return_repo, return_item_repo=return_item_repo, sale_item_repo=sale_item_repo,
        inventory_service=inventory_service, audit_repo=audit_repo, event_publisher=event_publisher,
    )


def get_refund_service(
    refund_repo=Depends(get_refund_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
) -> RefundService:
    return RefundService(refund_repo=refund_repo, audit_repo=audit_repo, event_publisher=event_publisher)


def get_sales_reporting_service(sale_repo=Depends(get_sale_repository)) -> SalesReportingService:
    return SalesReportingService(sale_repo=sale_repo)


def get_unscoped_audit_log_repository(db: AsyncSession = Depends(get_db)) -> AuditLogRepository:
    """
    Same repository class as `get_audit_log_repository`, but built off
    plain `get_db` instead of `get_scoped_db` -- i.e. with NO
    `app.current_org_id` session variable set, and therefore no
    transitive `get_tenant_context`/`get_current_user` dependency.

    Exists for exactly one caller: `get_public_passport_service` below.
    `PassportService.__init__` requires an `audit_repo` (its
    `generate_passport` method writes an audit row), but the public,
    unauthenticated `get_passport_by_token`/`QRService.scan` methods
    NEVER call `generate_passport` and never touch `self._audit` at all
    (see app/services/passport_service.py) -- so this repo is
    constructed to satisfy the constructor's type but is provably dead
    weight on every code path this dependency graph is actually used
    for. Using the real `get_audit_log_repository` here instead would be
    the bug this function exists to avoid: that factory's `get_scoped_db`
    forces `get_tenant_context` -> `get_current_user`, which raises
    `AuthenticationError("Missing bearer token.")` for a request that
    never sent one -- exactly what broke `GET /public/passport/{token}`/
    `GET /public/qr/{token}` before this fix (caught by this module's own
    live-uvicorn smoke test, not by the unit/integration suite, since
    those override every service factory directly and never exercise the
    *real* dependency graph in `deps.py`).
    """
    return SqlAlchemyAuditLogRepository(db)


def get_public_passport_service(
    passport_repo=Depends(get_passport_repository),
    plant_repo=Depends(get_plant_repository),
    species_repo=Depends(get_species_repository),
    variety_repo=Depends(get_plant_variety_repository),
    nursery_repo=Depends(get_nursery_repository),
    branch_repo=Depends(get_branch_repository),
    growth_repo=Depends(get_growth_timeline_repository),
    health_repo=Depends(get_health_history_repository),
    audit_repo: AuditLogRepository = Depends(get_unscoped_audit_log_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
    token_secret: bytes = Depends(get_passport_token_secret),
) -> PassportService:
    """
    The public-route counterpart to `get_passport_service` -- identical
    wiring except `audit_repo` (see `get_unscoped_audit_log_repository`'s
    docstring for why that one substitution is what makes this factory
    safe to resolve with zero `Authorization` header). Used exclusively
    by `app/api/routes/passport.py`'s `public_router` (`get_public_passport`)
    and by `get_public_qr_service` below -- never by the internal,
    authenticated `router`, which keeps using `get_passport_service`
    unchanged (that route legitimately has an authenticated actor and
    wants `generate_passport`'s audit-logged, tenant-scoped write path).
    """
    return PassportService(
        passport_repo=passport_repo, plant_repo=plant_repo, species_repo=species_repo, variety_repo=variety_repo,
        nursery_repo=nursery_repo, branch_repo=branch_repo, growth_repo=growth_repo, health_repo=health_repo,
        audit_repo=audit_repo, event_publisher=event_publisher, token_secret=token_secret,
    )


def get_qr_service(
    passport_service: PassportService = Depends(get_public_passport_service),
    scan_repo=Depends(get_qr_scan_event_repository),
    plant_repo=Depends(get_plant_repository),
    growth_repo=Depends(get_growth_timeline_repository),
    health_repo=Depends(get_health_history_repository),
    fertilizer_repo=Depends(get_fertilizer_log_repository),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> QRService:
    """
    Public, unauthenticated QR Intelligence scan path -- depends on
    `get_public_passport_service` (not `get_passport_service`), which is
    what actually keeps this whole dependency graph free of
    `get_current_user`; see that function's docstring and
    `get_unscoped_audit_log_repository`'s for the bug this avoids.

    `db` is threaded through (unused for any query here) so `QRService`
    can issue the narrow, token-verification-gated RLS scoping call
    described in migration 0014's docstring immediately after a token
    resolves to a specific `plant_id`, before reading
    `plants`/`growth_timeline`/`health_history`/`fertilizer_logs` (all
    RLS-protected per migration 0003 -- the previous version of this
    docstring's claim that "nothing this service touches is an
    RLS-protected table" was wrong; those four tables are exactly the
    ones migration 0003 already covers under DIRECT_TENANT_TABLES/
    JOIN_TENANT_TABLES). Without that scoping call, a real Postgres
    deployment's RLS policies would silently return zero rows for all
    four reads (RLS filters, it doesn't error), degrading `health_status`/
    `growth_timeline`/`fertilizer_schedule` to always-null for every
    public QR scan -- unverifiable in this sandbox (no live Postgres),
    but a live-Postgres-shaped bug worth fixing at the code+migration
    level now rather than leaving undiscovered until a real deployment.
    """
    return QRService(
        passport_service=passport_service, scan_repo=scan_repo, plant_repo=plant_repo, growth_repo=growth_repo,
        health_repo=health_repo, fertilizer_repo=fertilizer_repo, frontend_base_url=settings.FRONTEND_BASE_URL,
        db=db,
    )


# --------------------------------------------------------------------------
# Module 10 — AI Platform
# --------------------------------------------------------------------------


def get_ai_prediction_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyAIPredictionRepository(db)


def get_ai_inference_failure_repository(db: AsyncSession = Depends(get_db)):
    """
    Defined here (Module 10's section), not down in Module 13's own
    section below, because `get_disease_detection_inference` and its four
    siblings (a few dozen lines down, still in this section) reference it
    as a `Depends()` default -- a default argument value is evaluated at
    `def` time, so the referenced factory must already be a bound name at
    that point in the file, not merely defined later in module.
    """
    return SqlAlchemyAIInferenceFailureRepository(db)


def get_ai_recommendation_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyAIRecommendationRepository(db)


def get_ai_assistant_conversation_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyAIAssistantConversationRepository(db)


def get_ai_assistant_message_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyAIAssistantMessageRepository(db)


def get_knowledge_base_chunk_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyKnowledgeBaseChunkRepository(db)


def get_model_registry(settings: Settings = Depends(get_settings)) -> ModelRegistry:
    return ModelRegistry(settings=settings)


def get_prediction_logger(
    prediction_repo=Depends(get_ai_prediction_repository),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
) -> PredictionLogger:
    return PredictionLogger(prediction_repo=prediction_repo, event_publisher=event_publisher)


def get_feature_store(
    species_repo=Depends(get_species_repository),
    growth_repo=Depends(get_growth_timeline_repository),
    health_repo=Depends(get_health_history_repository),
    watering_repo=Depends(get_watering_log_repository),
    fertilizer_repo=Depends(get_fertilizer_log_repository),
    environmental_repo=Depends(get_environmental_reading_repository),
    disease_repo=Depends(get_disease_report_repository),
    sale_repo=Depends(get_sale_repository),
) -> FeatureStore:
    return FeatureStore(
        species_repo=species_repo, growth_repo=growth_repo, health_repo=health_repo, watering_repo=watering_repo,
        fertilizer_repo=fertilizer_repo, environmental_repo=environmental_repo, disease_repo=disease_repo,
        sale_repo=sale_repo,
    )


def get_disease_detection_inference(
    prediction_logger: PredictionLogger = Depends(get_prediction_logger),
    model_registry: ModelRegistry = Depends(get_model_registry),
    failure_repo=Depends(get_ai_inference_failure_repository),
) -> DiseaseDetectionInference:
    return DiseaseDetectionInference(
        prediction_logger=prediction_logger, model_registry=model_registry, failure_repo=failure_repo
    )


def get_growth_prediction_inference(
    prediction_logger: PredictionLogger = Depends(get_prediction_logger),
    failure_repo=Depends(get_ai_inference_failure_repository),
) -> GrowthPredictionInference:
    return GrowthPredictionInference(prediction_logger=prediction_logger, failure_repo=failure_repo)


def get_survival_prediction_inference(
    prediction_logger: PredictionLogger = Depends(get_prediction_logger),
    failure_repo=Depends(get_ai_inference_failure_repository),
) -> SurvivalPredictionInference:
    return SurvivalPredictionInference(prediction_logger=prediction_logger, failure_repo=failure_repo)


def get_water_recommendation_inference(
    prediction_logger: PredictionLogger = Depends(get_prediction_logger),
    failure_repo=Depends(get_ai_inference_failure_repository),
) -> WaterRecommendationInference:
    return WaterRecommendationInference(prediction_logger=prediction_logger, failure_repo=failure_repo)


def get_revenue_forecast_inference(
    prediction_logger: PredictionLogger = Depends(get_prediction_logger),
    failure_repo=Depends(get_ai_inference_failure_repository),
) -> RevenueForecastInference:
    return RevenueForecastInference(prediction_logger=prediction_logger, failure_repo=failure_repo)


def get_recommendation_engine() -> RecommendationEngine:
    return RecommendationEngine()


def get_knowledge_retrieval_service(
    settings: Settings = Depends(get_settings),
    chunk_repo=Depends(get_knowledge_base_chunk_repository),
) -> KnowledgeRetrievalService:
    return KnowledgeRetrievalService(settings=settings, chunk_repo=chunk_repo)


def get_assistant_orchestrator(settings: Settings = Depends(get_settings)) -> AssistantOrchestrator:
    return AssistantOrchestrator(settings=settings)


def get_assistant_tool_registry(
    request: Request,
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    authz: AuthorizationService = Depends(get_authorization_service),
    plant_repo=Depends(get_plant_repository),
    plant_service: PlantService = Depends(get_plant_service),
    inventory_service: InventoryService = Depends(get_inventory_service),
    sales_reporting_service: SalesReportingService = Depends(get_sales_reporting_service),
    ai_prediction_repo=Depends(get_ai_prediction_repository),
    watering_service: WateringService = Depends(get_watering_service),
    health_service: HealthService = Depends(get_health_service),
) -> AssistantToolRegistry:
    """
    Constructed fresh per-request (see `AssistantToolRegistry`'s own
    docstring on why) -- every dependency here is the SAME factory a
    native route for that resource already depends on
    (`get_plant_service`, `get_inventory_service`,
    `get_sales_reporting_service`, `get_watering_service`,
    `get_health_service`), so a tool call goes through identical
    service-layer logic to its equivalent page, never a parallel
    assistant-only code path.
    """
    return AssistantToolRegistry(
        user=user, org_id=tenant.org_id, authz=authz, request_context=_request_context(request),
        plant_repo=plant_repo, plant_service=plant_service, inventory_service=inventory_service,
        sales_reporting_service=sales_reporting_service, ai_prediction_repo=ai_prediction_repo,
        watering_service=watering_service, health_service=health_service,
    )


def get_assistant_conversation_service(
    conversation_repo=Depends(get_ai_assistant_conversation_repository),
    message_repo=Depends(get_ai_assistant_message_repository),
    orchestrator: AssistantOrchestrator = Depends(get_assistant_orchestrator),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
    knowledge_retrieval: KnowledgeRetrievalService = Depends(get_knowledge_retrieval_service),
) -> AssistantConversationService:
    return AssistantConversationService(
        conversation_repo=conversation_repo, message_repo=message_repo, orchestrator=orchestrator,
        event_publisher=event_publisher, knowledge_retrieval=knowledge_retrieval,
    )


# --------------------------------------------------------------------------
# Module 11 — Notifications & Communication
# --------------------------------------------------------------------------


def get_notification_hub(request: Request) -> NotificationHub:
    """Reads the shared connection registry off `app.state` (set once in `create_app`, app/main.py) -- same test-isolation reasoning as `get_rate_limiter`/`get_cache`."""
    return request.app.state.notification_hub


def get_notification_hub_ws(websocket: WebSocket) -> NotificationHub:
    """
    The WebSocket-route equivalent of `get_notification_hub` above --
    FastAPI's dependency solver only fills a `Request`-typed parameter when
    the connection actually `isinstance`-checks as `Request` (see
    `fastapi/dependencies/utils.py`'s `solve_dependencies`); a WebSocket
    connection never satisfies that check, so `app/api/routes/
    notifications.py`'s `notifications_websocket` route cannot reuse
    `get_notification_hub` directly and needs its own `WebSocket`-typed
    twin instead. Both read the exact same `app.state.notification_hub`
    in production; `tests/conftest.py`'s `_apply_common_overrides`
    overrides both to `harness.notification_hub` for the same reason it
    overrides every other `app.state`-backed dependency -- a route that
    quietly bypassed this (reading `websocket.app.state.notification_hub`
    directly, as an earlier version of this route did) would connect to a
    completely different, harness-invisible hub instance under tests,
    silently dropping every push and hanging any test waiting on one.
    """
    return websocket.app.state.notification_hub


def get_email_provider(settings: Settings = Depends(get_settings)) -> EmailProvider:
    return SmtpEmailProvider(settings)


def get_sms_provider(settings: Settings = Depends(get_settings)) -> SmsProvider:
    return LoggingSmsProvider(settings)


def get_push_provider(settings: Settings = Depends(get_settings)) -> PushProvider:
    return LoggingPushProvider(settings)


def get_permission_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyPermissionRepository(db)


def get_user_repository(db: AsyncSession = Depends(get_db)):
    """
    A standalone, overridable `Depends(get_db)`-based user-lookup
    dependency -- introduced for `app/api/routes/notifications.py`'s
    WebSocket route, which previously opened its own raw
    `get_db_session()` generator directly (bypassing FastAPI's `Depends`
    graph entirely) to resolve the token's `sub` claim to a `User` row.
    That worked in production but was untestable: `app.dependency_
    overrides` can only intercept dependencies FastAPI actually resolves
    through `Depends(...)`, so a hand-rolled `async for db in
    get_db_session()` inside a route body always hit a real database,
    even under `auth_client`/`authenticated_client`'s in-memory harness.
    Making this its own top-level `Depends(...)` function lets
    `tests/conftest.py`'s `_apply_common_overrides` override it directly
    to `harness.users` (the same fake `UserRepository` every other test
    already seeds users into via `harness.create_user()`), the same
    "override the repository, not the raw session" pattern every other
    entry in that function already follows -- fixing testability without
    changing production behavior at all.
    """
    return SqlAlchemyUserRepository(db)


def get_notification_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyNotificationRepository(db)


def get_notification_preference_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyNotificationPreferenceRepository(db)


def get_notification_template_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyNotificationTemplateRepository(db)


def get_notification_delivery_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyNotificationDeliveryRepository(db)


def get_template_service(
    template_repo=Depends(get_notification_template_repository),
) -> TemplateService:
    return TemplateService(template_repo)


def get_preference_service(
    preference_repo=Depends(get_notification_preference_repository),
) -> PreferenceService:
    return PreferenceService(preference_repo)


def get_notification_delivery_service(
    delivery_repo=Depends(get_notification_delivery_repository),
    email_provider: EmailProvider = Depends(get_email_provider),
    sms_provider: SmsProvider = Depends(get_sms_provider),
    push_provider: PushProvider = Depends(get_push_provider),
) -> NotificationDeliveryService:
    return NotificationDeliveryService(
        delivery_repo=delivery_repo, email_provider=email_provider, sms_provider=sms_provider, push_provider=push_provider
    )


def get_notification_service(
    db: AsyncSession = Depends(get_db),
    notification_repo=Depends(get_notification_repository),
    delivery_service: NotificationDeliveryService = Depends(get_notification_delivery_service),
    preference_service: PreferenceService = Depends(get_preference_service),
    template_service: TemplateService = Depends(get_template_service),
    hub: NotificationHub = Depends(get_notification_hub),
) -> NotificationService:
    """The Depends()-based dependency `app/api/routes/notifications.py` uses for every REST/WebSocket route -- constructed the same way `get_domain_event_publisher` builds its own internal `NotificationService` instance, against the same request-scoped `db` session."""
    return NotificationService(
        notification_repo=notification_repo, delivery_service=delivery_service, preference_service=preference_service,
        template_service=template_service, hub=hub, user_repo=SqlAlchemyUserRepository(db),
    )


# --------------------------------------------------------------------------
# Module 12 — Reports & Analytics
# --------------------------------------------------------------------------


def get_security_event_repository(db: AsyncSession = Depends(get_db)):
    """
    Not needed until now -- Module 2's `get_auth_service` has always
    constructed its own `SqlAlchemySecurityEventRepository(db)` inline
    (see that factory above) rather than through a standalone `Depends()`
    function, since no route ever needed the repository on its own before
    `ReportGenerationService`'s Security Report provider (Module 12).
    Mirrors every other single-argument `get_*_repository` factory in this
    file exactly.
    """
    return SqlAlchemySecurityEventRepository(db)


def get_report_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyReportRepository(db)


def get_scheduled_report_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyScheduledReportRepository(db)


def get_reporting_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyReportingRepository(db)


def get_file_storage(settings: Settings = Depends(get_settings)) -> FileStorage:
    """
    Thin `Depends()` wrapper around `app.reporting.file_storage.get_file_storage`
    (imported here as `_build_file_storage` to avoid shadowing this
    function's own name) -- picks `CloudinaryFileStorage` when
    `CLOUDINARY_CLOUD_NAME`/`API_KEY`/`API_SECRET` are all configured,
    otherwise `LocalFileStorage`; see that factory's own docstring for the
    full "real implementation + local graceful-degradation fallback"
    reasoning.
    """
    return _build_file_storage(settings)


def get_dashboard_service(reporting_repo=Depends(get_reporting_repository)) -> DashboardService:
    return DashboardService(reporting_repo=reporting_repo)


def get_analytics_service(reporting_repo=Depends(get_reporting_repository)) -> AnalyticsService:
    return AnalyticsService(reporting_repo=reporting_repo)


def get_report_generation_service(
    report_repo=Depends(get_report_repository),
    file_storage: FileStorage = Depends(get_file_storage),
    event_publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
    plant_repo=Depends(get_plant_repository),
    inventory_repo=Depends(get_inventory_repository),
    sale_repo=Depends(get_sale_repository),
    sale_item_repo=Depends(get_sale_item_repository),
    customer_repo=Depends(get_customer_repository),
    employee_repo=Depends(get_employee_repository),
    branch_repo=Depends(get_branch_repository),
    disease_report_repo=Depends(get_disease_report_repository),
    growth_timeline_repo=Depends(get_growth_timeline_repository),
    watering_log_repo=Depends(get_watering_log_repository),
    fertilizer_log_repo=Depends(get_fertilizer_log_repository),
    notification_repo=Depends(get_notification_repository),
    audit_log_repo: AuditLogRepository = Depends(get_audit_log_repository),
    security_event_repo=Depends(get_security_event_repository),
    passport_repo=Depends(get_passport_repository),
    ai_prediction_repo=Depends(get_ai_prediction_repository),
) -> ReportGenerationService:
    """
    The `Depends()`-based dependency `app/api/routes/reports.py`'s
    `POST /reports` route passes to `BackgroundTasks.add_task(...)` --
    every one of the 15 read repositories it takes is the SAME factory a
    native route for that entity already depends on (`get_plant_repository`,
    `get_sale_repository`, ...), so every report type's data comes from
    the exact same query path its own module's routes use, never a
    parallel one (the "No duplicated reporting logic" requirement, applied
    to dependency wiring).
    """
    return ReportGenerationService(
        report_repo=report_repo, file_storage=file_storage, event_publisher=event_publisher, plant_repo=plant_repo,
        inventory_repo=inventory_repo, sale_repo=sale_repo, sale_item_repo=sale_item_repo, customer_repo=customer_repo,
        employee_repo=employee_repo, branch_repo=branch_repo, disease_report_repo=disease_report_repo,
        growth_timeline_repo=growth_timeline_repo, watering_log_repo=watering_log_repo,
        fertilizer_log_repo=fertilizer_log_repo, notification_repo=notification_repo, audit_log_repo=audit_log_repo,
        security_event_repo=security_event_repo, passport_repo=passport_repo, ai_prediction_repo=ai_prediction_repo,
    )


def get_scheduled_report_service(
    scheduled_repo=Depends(get_scheduled_report_repository),
    report_repo=Depends(get_report_repository),
    generation_service: ReportGenerationService = Depends(get_report_generation_service),
) -> ScheduledReportService:
    return ScheduledReportService(scheduled_repo=scheduled_repo, report_repo=report_repo, generation_service=generation_service)


# --------------------------------------------------------------------------
# Module 13 — Administration & System Management
# --------------------------------------------------------------------------


def get_authorization_denial_repository(db: AsyncSession = Depends(get_db)):
    """
    Standalone, `Depends()`-based -- `get_authorization_service` has
    always constructed its own `SqlAlchemyAuthorizationDenialRepository(db)`
    inline (the write side only, Module 3); `AuditAdminService`'s read
    side needs its own injectable factory, mirroring the exact precedent
    `get_security_event_repository`'s own docstring set for the same
    "not needed until a later module wanted the repository on its own"
    situation.
    """
    return SqlAlchemyAuthorizationDenialRepository(db)


def get_feature_flag_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemyFeatureFlagRepository(db)


def get_system_config_repository(db: AsyncSession = Depends(get_db)):
    return SqlAlchemySystemConfigRepository(db)


def get_role_admin_service(
    permission_repo=Depends(get_permission_repository),
    permission_service: PermissionService = Depends(get_permission_service),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
) -> RoleAdminService:
    return RoleAdminService(permission_repo=permission_repo, permission_service=permission_service, audit_repo=audit_repo)


def get_user_admin_service(
    user_repo=Depends(get_user_repository),
    employee_repo=Depends(get_employee_repository),
    permission_repo=Depends(get_permission_repository),
    auth_service: AuthService = Depends(get_auth_service),
    security_event_repo=Depends(get_security_event_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
) -> UserAdminService:
    return UserAdminService(
        user_repo=user_repo, employee_repo=employee_repo, permission_repo=permission_repo,
        auth_service=auth_service, security_event_repo=security_event_repo, audit_repo=audit_repo,
    )


def get_feature_flag_service(
    flag_repo=Depends(get_feature_flag_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
) -> FeatureFlagService:
    return FeatureFlagService(flag_repo=flag_repo, audit_repo=audit_repo)


def get_system_config_service(
    config_repo=Depends(get_system_config_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
) -> SystemConfigService:
    return SystemConfigService(config_repo=config_repo, audit_repo=audit_repo)


def get_audit_admin_service(
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    security_event_repo=Depends(get_security_event_repository),
    denial_repo=Depends(get_authorization_denial_repository),
) -> AuditAdminService:
    return AuditAdminService(audit_repo=audit_repo, security_event_repo=security_event_repo, denial_repo=denial_repo)


def get_health_check_service(
    db: AsyncSession = Depends(get_db),
    cache: Cache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> HealthCheckService:
    return HealthCheckService(db_session=db, cache=cache, settings=settings)


def get_ai_admin_service(
    prediction_repo=Depends(get_ai_prediction_repository),
    failure_repo=Depends(get_ai_inference_failure_repository),
    knowledge_repo=Depends(get_knowledge_base_chunk_repository),
    model_registry: ModelRegistry = Depends(get_model_registry),
) -> AIAdminService:
    return AIAdminService(
        prediction_repo=prediction_repo, failure_repo=failure_repo, knowledge_repo=knowledge_repo,
        model_registry=model_registry,
    )


def get_data_management_service(
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
    security_event_repo=Depends(get_security_event_repository),
    prediction_repo=Depends(get_ai_prediction_repository),
    failure_repo=Depends(get_ai_inference_failure_repository),
) -> DataManagementService:
    return DataManagementService(
        audit_repo=audit_repo, security_event_repo=security_event_repo,
        prediction_repo=prediction_repo, failure_repo=failure_repo,
    )


# --------------------------------------------------------------------------
# Knowledge Articles (RAG Ingestion Pipeline)
# --------------------------------------------------------------------------


def get_knowledge_article_service(
    knowledge_repo=Depends(get_knowledge_base_chunk_repository),
    settings: Settings = Depends(get_settings),
) -> KnowledgeArticleService:
    return KnowledgeArticleService(settings=settings, chunk_repo=knowledge_repo)
