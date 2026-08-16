"""
Shared test fixtures. `client` gives every test an ASGI-transport httpx
client against a freshly-constructed app (no real network socket, no live
server process) -- fast, and isolated from whatever is/isn't running on
the host. DB-touching tests (readyz when a DB happens to be reachable,
and any future module's true DB integration tests) are expected to skip
gracefully rather than fail when no database is reachable, which is the
normal state of this sandbox (see
docs/architecture/14-phase5-database-implementation.md's "Migration
Validation" section for why) and will be the normal state of a CI runner
without a service container attached too.

`harness`/`device` (Module 2 onward): an AuthService wired to in-memory
fake repositories (tests/fakes/repositories.py), shared by both the unit
tests (call the service directly) and the integration tests (override
FastAPI's `get_auth_service`/`get_current_user` dependencies to return
this same harness's service/users) -- so both layers exercise the exact
same lockout/rotation/replay-detection logic, just through different
entry points.
"""
from __future__ import annotations

import tempfile
import uuid
from dataclasses import dataclass

import pytest
from httpx import ASGITransport, AsyncClient

from app.ai.assistant.knowledge_retrieval import KnowledgeRetrievalService
from app.ai.assistant.orchestrator import AssistantOrchestrator
from app.ai.assistant.tool_registry import AssistantToolRegistry
from app.ai.common import FeatureStore, ModelRegistry, PredictionLogger
from app.ai.disease_detection.inference import DiseaseDetectionInference
from app.ai.growth_prediction.inference import GrowthPredictionInference
from app.ai.recommendation_engine.engine import RecommendationEngine
from app.ai.revenue_forecast.inference import RevenueForecastInference
from app.ai.survival_prediction.inference import SurvivalPredictionInference
from app.ai.water_recommendation.inference import WaterRecommendationInference
from app.core.cache import InMemoryCache
from app.core.config import Settings
from app.core.security import hash_password
from app.domain_events import DomainEventPublisher, EventDispatcher
from app.main import create_app
from app.models.identity import Permission, Role, RoleAssignment, User
from app.notifications.delivery import NotificationDeliveryService
from app.notifications.hub import InMemoryNotificationHub
from app.notifications.notification_handler import NotificationEventHandler, NotificationService
from app.notifications.preferences import PreferenceService
from app.notifications.templates import TemplateService
from app.reporting.file_storage import LocalFileStorage
from app.services.analytics_service import AnalyticsService
from app.services.assistant_conversation_service import AssistantConversationService
from app.services.auth_service import AuthService, DeviceContext
from app.services.authorization_service import AuthorizationService, RequestContext
from app.services.branch_service import BranchService
from app.services.digital_twin_service import DigitalTwinEventHandler, DigitalTwinService
from app.services.disease_service import DiseaseReportService, TreatmentService
from app.services.employee_service import EmployeeService
from app.services.inventory_service import InventoryLocationService, InventoryService
from app.services.organization_service import OrganizationService
from app.services.passport_service import PassportService, QRService
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
from app.services.admin_service import (
    AIAdminService,
    AuditAdminService,
    DataManagementService,
    FeatureFlagService,
    RoleAdminService,
    SystemConfigService,
    UserAdminService,
)
from app.services.sales_service import (
    PaymentService,
    QuotationService,
    RefundService,
    ReturnService,
    SalesOrderService,
    SalesReportingService,
)
from app.services.customer_service import CustomerService
from app.services.scheduled_report_service import ScheduledReportService
from app.services.species_service import SpeciesService
from tests.fakes.repositories import (
    FakeAuditLogRepository,
    FakeAuthorizationDenialRepository,
    FakeBranchRepository,
    FakeCustomerAddressRepository,
    FakeCustomerCommunicationRepository,
    FakeCustomerContactRepository,
    FakeCustomerNoteRepository,
    FakeCustomerRepository,
    FakeCustomerTagRepository,
    FakeDigitalTwinRepository,
    FakeDigitalTwinVersionRepository,
    FakeDiseaseReportRepository,
    FakeDomainEventRepository,
    FakeEmailSender,
    FakeEmailVerificationTokenRepository,
    FakeEmployeeRepository,
    FakeAIInferenceFailureRepository,
    FakeEnvironmentalReadingRepository,
    FakeEventDispatchLogRepository,
    FakeFeatureFlagRepository,
    FakeFertilizerLogRepository,
    FakeGrowthTimelineRepository,
    FakeHealthHistoryRepository,
    FakeInventoryLocationRepository,
    FakeInventoryRepository,
    FakeInviteRepository,
    FakeAIAssistantConversationRepository,
    FakeAIAssistantMessageRepository,
    FakeAIPredictionRepository,
    FakeAIRecommendationRepository,
    FakeInvoiceItemRepository,
    FakeInvoiceRepository,
    FakeInvoiceSaleRepository,
    FakeKnowledgeBaseChunkRepository,
    FakeNotificationDeliveryRepository,
    FakeNotificationPreferenceRepository,
    FakeNotificationRepository,
    FakeNotificationTemplateRepository,
    FakeNurseryRepository,
    FakeOrderItemRepository,
    FakePassportRepository,
    FakePasswordResetTokenRepository,
    FakePaymentRepository,
    FakePermissionRepository,
    FakePlantCategoryRepository,
    FakePlantImageRepository,
    FakePlantRepository,
    FakePlantTransferRepository,
    FakePlantVarietyRepository,
    FakeUnitRepository,
    FakeQRScanEventRepository,
    FakeQuotationItemRepository,
    FakeQuotationRepository,
    FakeRefreshTokenRepository,
    FakeRefundRepository,
    FakeReportingRepository,
    FakeReportRepository,
    FakeReturnItemRepository,
    FakeReturnRepository,
    FakeScheduledReportRepository,
    FakeSalesOrderRepository,
    FakeSaleItemRepository,
    FakeSaleRepository,
    FakeSecurityEventRepository,
    FakeSpeciesRepository,
    FakeStockMovementRepository,
    FakeStockReservationRepository,
    FakeSupplierRepository,
    FakeSystemConfigRepository,
    FakeTreatmentRepository,
    FakeUserRepository,
    FakeWateringLogRepository,
)
from tests.fakes.notification_providers import FakeEmailProvider, FakePushProvider, FakeSmsProvider


@pytest.fixture
def test_settings() -> Settings:
    return Settings(APP_ENV="test", APP_DEBUG=True)


@pytest.fixture
async def client(test_settings: Settings):
    app = create_app(settings=test_settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@dataclass
class AuthTestHarness:
    settings: Settings
    service: AuthService
    users: FakeUserRepository
    refresh_tokens: FakeRefreshTokenRepository
    email_verification_tokens: FakeEmailVerificationTokenRepository
    password_reset_tokens: FakePasswordResetTokenRepository
    security_events: FakeSecurityEventRepository
    permissions: FakePermissionRepository
    invites: FakeInviteRepository
    email_sender: FakeEmailSender
    denials: FakeAuthorizationDenialRepository
    audit_logs: FakeAuditLogRepository
    cache: InMemoryCache
    permission_service: PermissionService
    authorization_service: AuthorizationService
    # --- Added by Phase 6 Module 4 ---
    nurseries: FakeNurseryRepository
    branches: FakeBranchRepository
    employees: FakeEmployeeRepository
    domain_events: FakeDomainEventRepository
    organization_service: OrganizationService
    branch_service: BranchService
    employee_service: EmployeeService
    # --- Added by Phase 6 Module 5 ---
    plant_categories: FakePlantCategoryRepository
    species: FakeSpeciesRepository
    plant_varieties: FakePlantVarietyRepository
    species_service: SpeciesService
    plant_variety_service: PlantVarietyService
    # --- Added by Phase 6 Module 6 ---
    plants: FakePlantRepository
    plant_images: FakePlantImageRepository
    plant_transfers: FakePlantTransferRepository
    growth_timeline: FakeGrowthTimelineRepository
    health_history: FakeHealthHistoryRepository
    watering_logs: FakeWateringLogRepository
    fertilizer_logs: FakeFertilizerLogRepository
    environmental_readings: FakeEnvironmentalReadingRepository
    disease_reports: FakeDiseaseReportRepository
    treatments: FakeTreatmentRepository
    suppliers: FakeSupplierRepository
    qr_code_service: QRCodeService
    plant_service: PlantService
    growth_service: GrowthService
    health_service: HealthService
    watering_service: WateringService
    fertilizer_service: FertilizerService
    environmental_service: EnvironmentalService
    disease_report_service: DiseaseReportService
    treatment_service: TreatmentService
    plant_timeline_service: PlantTimelineService
    # --- Added by Phase 6 Module 7 ---
    digital_twins: FakeDigitalTwinRepository
    digital_twin_versions: FakeDigitalTwinVersionRepository
    event_dispatch_log: FakeEventDispatchLogRepository
    event_dispatcher: EventDispatcher
    digital_twin_service: DigitalTwinService
    # --- Added by Phase 6 Module 8 ---
    inventory_locations: FakeInventoryLocationRepository
    inventory: FakeInventoryRepository
    stock_movements: FakeStockMovementRepository
    stock_reservations: FakeStockReservationRepository
    units: FakeUnitRepository
    inventory_location_service: InventoryLocationService
    inventory_service: InventoryService
    # --- Added by Phase 6 Module 9 ---
    customers: FakeCustomerRepository
    customer_contacts: FakeCustomerContactRepository
    customer_addresses: FakeCustomerAddressRepository
    customer_tags: FakeCustomerTagRepository
    customer_notes: FakeCustomerNoteRepository
    customer_communications: FakeCustomerCommunicationRepository
    quotations: FakeQuotationRepository
    quotation_items: FakeQuotationItemRepository
    sales_orders: FakeSalesOrderRepository
    order_items: FakeOrderItemRepository
    sales: FakeSaleRepository
    sale_items: FakeSaleItemRepository
    invoices: FakeInvoiceRepository
    invoice_items: FakeInvoiceItemRepository
    invoice_sales: FakeInvoiceSaleRepository
    payments: FakePaymentRepository
    returns: FakeReturnRepository
    return_items: FakeReturnItemRepository
    refunds: FakeRefundRepository
    passports: FakePassportRepository
    qr_scan_events: FakeQRScanEventRepository
    customer_service: CustomerService
    quotation_service: QuotationService
    sales_order_service: SalesOrderService
    payment_service: PaymentService
    return_service: ReturnService
    refund_service: RefundService
    sales_reporting_service: SalesReportingService
    passport_service: PassportService
    qr_service: QRService
    # --- Added by Phase 6 Module 10 ---
    ai_predictions: FakeAIPredictionRepository
    ai_recommendations: FakeAIRecommendationRepository
    ai_assistant_conversations: FakeAIAssistantConversationRepository
    ai_assistant_messages: FakeAIAssistantMessageRepository
    knowledge_base_chunks: FakeKnowledgeBaseChunkRepository
    model_registry: ModelRegistry
    prediction_logger: PredictionLogger
    feature_store: FeatureStore
    disease_detection_inference: DiseaseDetectionInference
    growth_prediction_inference: GrowthPredictionInference
    survival_prediction_inference: SurvivalPredictionInference
    water_recommendation_inference: WaterRecommendationInference
    revenue_forecast_inference: RevenueForecastInference
    recommendation_engine: RecommendationEngine
    knowledge_retrieval_service: KnowledgeRetrievalService
    assistant_orchestrator: AssistantOrchestrator
    assistant_conversation_service: AssistantConversationService
    # --- Added by Phase 6 Module 11 (Notifications & Communication) ---
    event_publisher: DomainEventPublisher
    notifications: FakeNotificationRepository
    notification_preferences: FakeNotificationPreferenceRepository
    notification_templates: FakeNotificationTemplateRepository
    notification_deliveries: FakeNotificationDeliveryRepository
    notification_hub: InMemoryNotificationHub
    email_provider: FakeEmailProvider
    sms_provider: FakeSmsProvider
    push_provider: FakePushProvider
    notification_delivery_service: NotificationDeliveryService
    preference_service: PreferenceService
    template_service: TemplateService
    notification_service: NotificationService
    notification_event_handler: NotificationEventHandler
    # --- Added by Phase 6 Module 12 (Reports & Analytics) ---
    reports: FakeReportRepository
    scheduled_reports: FakeScheduledReportRepository
    reporting: FakeReportingRepository
    report_file_storage: LocalFileStorage
    dashboard_service: DashboardService
    analytics_service: AnalyticsService
    report_generation_service: ReportGenerationService
    scheduled_report_service: ScheduledReportService
    # --- Added by Phase 6 Module 13 (Administration & System Management) ---
    feature_flags: FakeFeatureFlagRepository
    system_configs: FakeSystemConfigRepository
    ai_inference_failures: FakeAIInferenceFailureRepository
    role_admin_service: RoleAdminService
    user_admin_service: UserAdminService
    feature_flag_service: FeatureFlagService
    system_config_service: SystemConfigService
    audit_admin_service: AuditAdminService
    ai_admin_service: AIAdminService
    data_management_service: DataManagementService

    def build_assistant_tool_registry(
        self, *, user: User, org_id: uuid.UUID | None, authz: AuthorizationService, request_context: RequestContext
    ) -> AssistantToolRegistry:
        """
        Unlike every other Module 10 service above, `AssistantToolRegistry`
        is NOT a single shared harness instance -- production constructs a
        fresh one per request (see that class's own docstring on why: it
        closes over the specific caller's `user`/`org_id`/`RequestContext`).
        Tests call this helper to build one the same way app/api/deps.py's
        `get_assistant_tool_registry` factory does, from the same harness
        repositories/services every other Module 10 fixture already shares.
        """
        return AssistantToolRegistry(
            user=user, org_id=org_id, authz=authz, request_context=request_context,
            plant_repo=self.plants, plant_service=self.plant_service, inventory_service=self.inventory_service,
            sales_reporting_service=self.sales_reporting_service, ai_prediction_repo=self.ai_predictions,
            watering_service=self.watering_service, health_service=self.health_service,
        )

    async def create_user(
        self, *, email: str = "grower@example.com", password: str = "Correct-Horse12", **overrides
    ) -> User:
        user = User(
            id=uuid.uuid4(),
            email=email.lower(),
            password_hash=hash_password(password),
            full_name="Test Grower",
            is_active=True,
            is_email_verified=False,
            failed_login_attempts=0,
            locked_until=None,
        )
        for key, value in overrides.items():
            setattr(user, key, value)
        return await self.users.add(user)

    def grant_role(
        self,
        user: User,
        *,
        org_id: uuid.UUID,
        role_code: str,
        permission_codes: list[str],
        branch_ids: list[uuid.UUID] | None = None,
    ) -> RoleAssignment:
        """
        `branch_ids=None` (the default) grants an org-wide role — no
        branch_scopes rows, matching `RoleAssignmentBranchScope`'s own
        "absent rows == all branches" semantics (see
        `ResolvedAccess.is_org_wide()`'s docstring). Pass a non-empty list
        to build a branch-scoped role assignment for cross-tenant-branch
        and matrix tests (Module 3).
        """
        role_id = uuid.uuid4()
        permissions = [
            Permission(id=uuid.uuid4(), code=code, module=code.split(":")[0], action=code.split(":")[1], description=code)
            for code in permission_codes
        ]
        role = Role(id=role_id, nursery_id=org_id, code=role_code, name=role_code, is_system_role=True)
        role.permissions = permissions
        self.permissions.roles[role_id] = role

        assignment = RoleAssignment(id=uuid.uuid4(), user_id=user.id, nursery_id=org_id, role_id=role_id)
        self.permissions.role_assignments[user.id] = assignment
        if branch_ids:
            self.permissions.branch_scopes[assignment.id] = list(branch_ids)
        return assignment

    def seed_system_role(self, code: str, permission_codes: list[str]) -> Role:
        """
        Module 4: seeds a *system* role (`nursery_id=None`, the same shape
        migration 0002's RBAC seed data gives `owner`/`org_admin`/etc.) so
        `EmployeeService.invite_employee`/`provision_owner`/
        `transfer_ownership` (all of which resolve roles by code via
        `PermissionRepository.get_system_role_by_code`) have something real
        to find — distinct from `grant_role`, which builds an org-scoped
        `RoleAssignment` for a specific already-authenticated user.
        """
        role = Role(id=uuid.uuid4(), nursery_id=None, code=code, name=code, is_system_role=True)
        role.permissions = [
            Permission(id=uuid.uuid4(), code=c, module=c.split(":")[0], action=c.split(":")[1], description=c)
            for c in permission_codes
        ]
        self.permissions.roles[role.id] = role
        return role


@pytest.fixture
def device() -> DeviceContext:
    return DeviceContext(device_name="pytest-device", user_agent="pytest", ip_address="127.0.0.1")


@pytest.fixture
def harness() -> AuthTestHarness:
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        AUTH_MAX_FAILED_LOGIN_ATTEMPTS=3,
        AUTH_LOCKOUT_DURATION_MINUTES=15,
    )
    users = FakeUserRepository()
    refresh_tokens = FakeRefreshTokenRepository()
    email_verification_tokens = FakeEmailVerificationTokenRepository()
    password_reset_tokens = FakePasswordResetTokenRepository()
    security_events = FakeSecurityEventRepository()
    permissions = FakePermissionRepository()
    invites = FakeInviteRepository()
    email_sender = FakeEmailSender()
    denials = FakeAuthorizationDenialRepository()
    audit_logs = FakeAuditLogRepository()
    cache = InMemoryCache()

    service = AuthService(
        settings=settings,
        user_repo=users,
        refresh_token_repo=refresh_tokens,
        email_verification_repo=email_verification_tokens,
        password_reset_repo=password_reset_tokens,
        security_event_repo=security_events,
        permission_repo=permissions,
        invite_repo=invites,
        email_sender=email_sender,
    )
    permission_service = PermissionService(permissions, cache=cache)
    authorization_service = AuthorizationService(
        permission_service=permission_service, denial_repo=denials
    )

    # --- Added by Phase 6 Module 4 ---
    nurseries = FakeNurseryRepository()
    branches = FakeBranchRepository()
    employees = FakeEmployeeRepository()
    # `security_events` was already constructed above (Module 2 needs it
    # for `AuthService` before `employees` exists) -- its optional
    # Phase 6 Module 12 `_employee_repo` reference (Security Reports'
    # `list_for_nursery`) is patched in here instead of at construction
    # time, the one exception to this file's usual "pass every fake
    # dependency through the constructor" convention, forced by that
    # construction-order constraint rather than a design choice.
    security_events._employee_repo = employees
    domain_events = FakeDomainEventRepository()
    event_publisher = DomainEventPublisher(domain_events)

    organization_service = OrganizationService(
        nursery_repo=nurseries, audit_repo=audit_logs, event_publisher=event_publisher
    )
    branch_service = BranchService(
        branch_repo=branches, nursery_repo=nurseries, audit_repo=audit_logs, event_publisher=event_publisher
    )
    employee_service = EmployeeService(
        settings=settings,
        employee_repo=employees,
        invite_repo=invites,
        branch_repo=branches,
        user_repo=users,
        permission_repo=permissions,
        permission_service=permission_service,
        audit_repo=audit_logs,
        event_publisher=event_publisher,
        email_sender=email_sender,
    )

    # --- Added by Phase 6 Module 5 ---
    plant_categories = FakePlantCategoryRepository()
    species = FakeSpeciesRepository()
    plant_varieties = FakePlantVarietyRepository()
    species_service = SpeciesService(
        species_repo=species, category_repo=plant_categories, audit_repo=audit_logs, event_publisher=event_publisher
    )
    plant_variety_service = PlantVarietyService(
        variety_repo=plant_varieties, species_repo=species, audit_repo=audit_logs, event_publisher=event_publisher
    )

    # --- Added by Phase 6 Module 6 ---
    plants = FakePlantRepository()
    plant_images = FakePlantImageRepository()
    plant_transfers = FakePlantTransferRepository()
    growth_timeline = FakeGrowthTimelineRepository(plants)
    health_history = FakeHealthHistoryRepository()
    watering_logs = FakeWateringLogRepository(branches)
    fertilizer_logs = FakeFertilizerLogRepository(branches)
    environmental_readings = FakeEnvironmentalReadingRepository()
    disease_reports = FakeDiseaseReportRepository(plants)
    treatments = FakeTreatmentRepository()
    suppliers = FakeSupplierRepository()

    # --- Added by Phase 6 Module 7 ---
    # Built here (not up where `event_publisher` itself was constructed)
    # because DigitalTwinService needs the Module 6 repositories above to
    # already exist. `event_publisher.set_dispatcher(...)` below attaches
    # the dispatcher to the *same* publisher instance every earlier
    # Module 4/5 service already received, so they all see it -- see
    # `DomainEventPublisher.set_dispatcher`'s own docstring.
    digital_twins = FakeDigitalTwinRepository()
    digital_twin_versions = FakeDigitalTwinVersionRepository()
    event_dispatch_log = FakeEventDispatchLogRepository()
    # `return_items` (Module 9) is constructed here, ahead of the rest of
    # Module 9's fakes further below, purely because `DigitalTwinService`
    # now depends on it (`_on_plant_returned`'s `line_refund_amount`
    # enrichment read) -- the same "must exist before this constructor
    # call" ordering constraint app/api/deps.py's own
    # `get_return_item_repository` docstring explains. It's a
    # freestanding dict-backed fake with no dependencies of its own, so
    # constructing it early and reusing the same instance in Module 9's
    # `return_service` below is safe and matches every other fake's
    # single-shared-instance-per-harness pattern.
    return_items = FakeReturnItemRepository()
    digital_twin_service = DigitalTwinService(
        twin_repo=digital_twins, version_repo=digital_twin_versions, domain_event_repo=domain_events,
        plant_repo=plants, growth_repo=growth_timeline, health_repo=health_history, watering_repo=watering_logs,
        fertilizer_repo=fertilizer_logs, environmental_repo=environmental_readings, disease_repo=disease_reports,
        treatment_repo=treatments, return_item_repo=return_items,
    )
    event_dispatcher = EventDispatcher(event_dispatch_log)
    event_dispatcher.register(DigitalTwinEventHandler(digital_twin_service))
    event_publisher.set_dispatcher(event_dispatcher)

    # --- Added by Phase 6 Module 8 ---
    # No new dispatcher registration needed: InventoryService publishes
    # through this same `event_publisher`, and `plant.inventory_movement_recorded`
    # is already in `DigitalTwinService.PROJECTED_EVENT_TYPES`, so the
    # `DigitalTwinEventHandler` registered above picks it up automatically
    # -- see app/api/deps.py's `get_inventory_service` docstring.
    inventory_locations = FakeInventoryLocationRepository()
    inventory = FakeInventoryRepository()
    stock_movements = FakeStockMovementRepository(inventory)
    stock_reservations = FakeStockReservationRepository()
    units = FakeUnitRepository()
    inventory_location_service = InventoryLocationService(
        location_repo=inventory_locations, unit_repo=units, audit_repo=audit_logs, event_publisher=event_publisher
    )
    inventory_service = InventoryService(
        inventory_repo=inventory, location_repo=inventory_locations, movement_repo=stock_movements,
        reservation_repo=stock_reservations, audit_repo=audit_logs, event_publisher=event_publisher,
    )

    qr_code_service = QRCodeService(plants)
    plant_service = PlantService(
        plant_repo=plants, image_repo=plant_images, transfer_repo=plant_transfers, species_repo=species,
        variety_repo=plant_varieties, branch_repo=branches, supplier_repo=suppliers, disease_repo=disease_reports,
        treatment_repo=treatments, qr_service=qr_code_service, audit_repo=audit_logs, event_publisher=event_publisher,
    )
    growth_service = GrowthService(
        growth_repo=growth_timeline, plant_repo=plants, audit_repo=audit_logs, event_publisher=event_publisher
    )
    health_service = HealthService(
        health_repo=health_history, plant_repo=plants, audit_repo=audit_logs, event_publisher=event_publisher
    )
    watering_service = WateringService(
        watering_repo=watering_logs, plant_repo=plants, audit_repo=audit_logs, event_publisher=event_publisher
    )
    fertilizer_service = FertilizerService(
        fertilizer_repo=fertilizer_logs, plant_repo=plants, audit_repo=audit_logs, event_publisher=event_publisher
    )
    environmental_service = EnvironmentalService(
        environmental_repo=environmental_readings, plant_repo=plants, audit_repo=audit_logs,
        event_publisher=event_publisher,
    )
    disease_report_service = DiseaseReportService(
        disease_repo=disease_reports, plant_service=plant_service, audit_repo=audit_logs,
        event_publisher=event_publisher,
    )
    treatment_service = TreatmentService(
        treatment_repo=treatments, disease_repo=disease_reports, plant_service=plant_service,
        audit_repo=audit_logs, event_publisher=event_publisher,
    )
    plant_timeline_service = PlantTimelineService(
        plant_repo=plants, transfer_repo=plant_transfers, image_repo=plant_images, growth_repo=growth_timeline,
        health_repo=health_history, watering_repo=watering_logs, fertilizer_repo=fertilizer_logs,
        disease_repo=disease_reports, treatment_repo=treatments,
    )

    # --- Added by Phase 6 Module 9 ---
    # No new dispatcher registration needed here either: `PlantSold`/
    # `PlantReturned`/`PassportGenerated`/`QRGenerated` are all published
    # through this same `event_publisher` (Sales' own services below, and
    # `PassportService.generate_passport`), and all four are already in
    # `DigitalTwinService.PROJECTED_EVENT_TYPES` -- the
    # `DigitalTwinEventHandler` registered above (Module 7) picks them up
    # automatically, exactly the same "zero new plumbing" precedent
    # Module 8's own comment right above describes.
    sales_orders = FakeSalesOrderRepository()
    order_items = FakeOrderItemRepository()
    sales = FakeSaleRepository()
    sale_items = FakeSaleItemRepository()
    invoices = FakeInvoiceRepository()
    invoice_items = FakeInvoiceItemRepository()
    invoice_sales = FakeInvoiceSaleRepository()

    customer_tags = FakeCustomerTagRepository()
    customers = FakeCustomerRepository(tag_repo=customer_tags)
    customer_contacts = FakeCustomerContactRepository()
    customer_addresses = FakeCustomerAddressRepository()
    customer_notes = FakeCustomerNoteRepository()
    customer_communications = FakeCustomerCommunicationRepository()
    customer_service = CustomerService(
        customer_repo=customers, contact_repo=customer_contacts, address_repo=customer_addresses,
        tag_repo=customer_tags, note_repo=customer_notes, communication_repo=customer_communications,
        sale_repo=sales, audit_repo=audit_logs, event_publisher=event_publisher,
    )

    quotations = FakeQuotationRepository()
    quotation_items = FakeQuotationItemRepository()
    quotation_service = QuotationService(
        quotation_repo=quotations, quotation_item_repo=quotation_items, audit_repo=audit_logs,
        event_publisher=event_publisher,
    )

    passports = FakePassportRepository(plant_repo=plants)
    qr_scan_events = FakeQRScanEventRepository(passports, plant_repo=plants)
    passport_service = PassportService(
        passport_repo=passports, plant_repo=plants, species_repo=species, variety_repo=plant_varieties,
        nursery_repo=nurseries, branch_repo=branches, growth_repo=growth_timeline, health_repo=health_history,
        audit_repo=audit_logs, event_publisher=event_publisher, token_secret=b"test-passport-token-secret-32b!",
    )
    qr_service = QRService(
        passport_service=passport_service, scan_repo=qr_scan_events, plant_repo=plants,
        growth_repo=growth_timeline, health_repo=health_history, fertilizer_repo=fertilizer_logs,
        frontend_base_url="http://localhost:3000",
    )
    sales_order_service = SalesOrderService(
        order_repo=sales_orders, order_item_repo=order_items, sale_repo=sales, sale_item_repo=sale_items,
        invoice_repo=invoices, invoice_item_repo=invoice_items, invoice_sale_repo=invoice_sales,
        inventory_service=inventory_service, passport_service=passport_service, plant_repo=plants,
        audit_repo=audit_logs, event_publisher=event_publisher,
    )

    payments = FakePaymentRepository()
    payment_service = PaymentService(
        payment_repo=payments, invoice_repo=invoices, order_repo=sales_orders, audit_repo=audit_logs,
        event_publisher=event_publisher,
    )

    return_items_repo = return_items  # constructed early, above, for DigitalTwinService
    returns = FakeReturnRepository()
    return_service = ReturnService(
        return_repo=returns, return_item_repo=return_items_repo, sale_item_repo=sale_items,
        inventory_service=inventory_service, audit_repo=audit_logs, event_publisher=event_publisher,
    )

    refunds = FakeRefundRepository()
    refund_service = RefundService(refund_repo=refunds, audit_repo=audit_logs, event_publisher=event_publisher)

    sales_reporting_service = SalesReportingService(sale_repo=sales)

    # --- Added by Phase 6 Module 10 (AI Platform) ---
    # No new dispatcher registration needed here either: `AIPredictionGenerated`
    # (published by `PredictionLogger.persist`, below) is already in
    # `DigitalTwinService.PROJECTED_EVENT_TYPES` -- the `DigitalTwinEventHandler`
    # registered in the Module 7 block above picks it up automatically, the
    # same "zero new plumbing" precedent Module 8's/Module 9's own comments
    # above describe. `AIPredictionGeneratedForBranch` is NOT projected (see
    # that event's own docstring), so no handler entry exists for it either.
    ai_predictions = FakeAIPredictionRepository()
    ai_recommendations = FakeAIRecommendationRepository()
    ai_assistant_conversations = FakeAIAssistantConversationRepository()
    ai_assistant_messages = FakeAIAssistantMessageRepository()
    knowledge_base_chunks = FakeKnowledgeBaseChunkRepository()

    model_registry = ModelRegistry(settings=settings)
    prediction_logger = PredictionLogger(prediction_repo=ai_predictions, event_publisher=event_publisher)
    feature_store = FeatureStore(
        species_repo=species, growth_repo=growth_timeline, health_repo=health_history, watering_repo=watering_logs,
        fertilizer_repo=fertilizer_logs, environmental_repo=environmental_readings, disease_repo=disease_reports,
        sale_repo=sales,
    )
    disease_detection_inference = DiseaseDetectionInference(prediction_logger=prediction_logger, model_registry=model_registry)
    growth_prediction_inference = GrowthPredictionInference(prediction_logger=prediction_logger)
    survival_prediction_inference = SurvivalPredictionInference(prediction_logger=prediction_logger)
    water_recommendation_inference = WaterRecommendationInference(prediction_logger=prediction_logger)
    revenue_forecast_inference = RevenueForecastInference(prediction_logger=prediction_logger)
    recommendation_engine = RecommendationEngine()

    knowledge_retrieval_service = KnowledgeRetrievalService(settings=settings, chunk_repo=knowledge_base_chunks)
    assistant_orchestrator = AssistantOrchestrator(settings=settings)
    assistant_conversation_service = AssistantConversationService(
        conversation_repo=ai_assistant_conversations, message_repo=ai_assistant_messages,
        orchestrator=assistant_orchestrator, event_publisher=event_publisher,
        knowledge_retrieval=knowledge_retrieval_service,
    )

    # --- Added by Phase 6 Module 11 (Notifications & Communication) ---
    # `NotificationEventHandler` is registered on the SAME `event_dispatcher`
    # the Module 7 block above already built and attached to `event_publisher`
    # -- so any harness-driven `publisher.publish(...)` call (from any
    # Module 4-11 service under test) reaches both `DigitalTwinEventHandler`
    # and this handler, exactly like production's `get_domain_event_publisher`.
    notifications = FakeNotificationRepository()
    notification_preferences = FakeNotificationPreferenceRepository()
    notification_templates = FakeNotificationTemplateRepository()
    notification_deliveries = FakeNotificationDeliveryRepository()
    notification_hub = InMemoryNotificationHub()
    email_provider = FakeEmailProvider()
    sms_provider = FakeSmsProvider()
    push_provider = FakePushProvider()
    notification_delivery_service = NotificationDeliveryService(
        delivery_repo=notification_deliveries, email_provider=email_provider,
        sms_provider=sms_provider, push_provider=push_provider,
    )
    preference_service = PreferenceService(notification_preferences)
    template_service = TemplateService(notification_templates)
    notification_service = NotificationService(
        notification_repo=notifications, delivery_service=notification_delivery_service,
        preference_service=preference_service, template_service=template_service,
        hub=notification_hub, user_repo=users,
    )
    notification_event_handler = NotificationEventHandler(
        notification_service=notification_service, permission_repo=permissions, plant_repo=plants,
        inventory_repo=inventory, invoice_repo=invoices, sales_order_repo=sales_orders, employee_repo=employees,
    )
    event_dispatcher.register(notification_event_handler)

    # --- Added by Phase 6 Module 12 (Reports & Analytics) ---
    # `FakeReportingRepository` takes constructor references to every other
    # fake repository it aggregates over (see that class's own docstring),
    # the same precedent `FakeDiseaseReportRepository(plants)`/
    # `FakeStockMovementRepository(inventory)` above already established --
    # sharing the live dicts this harness already populated for Modules
    # 4-11 is simpler and less error-prone than this fake maintaining its
    # own duplicate index.
    reports = FakeReportRepository()
    scheduled_reports = FakeScheduledReportRepository()
    reporting = FakeReportingRepository(
        plant_repo=plants, species_repo=species, inventory_repo=inventory,
        stock_movement_repo=stock_movements, sale_repo=sales, sale_item_repo=sale_items,
        invoice_repo=invoices, customer_repo=customers, branch_repo=branches,
        nursery_repo=nurseries, employee_repo=employees, growth_timeline_repo=growth_timeline,
        health_history_repo=health_history, disease_report_repo=disease_reports,
        ai_prediction_repo=ai_predictions,
    )
    # `LocalFileStorage` (not a hand-rolled fake) -- a real, working, dependency-free
    # implementation already exists for exactly the "no Cloudinary credentials in this
    # sandbox" case (see app/reporting/file_storage.py's own docstring), so report-
    # generation/download tests exercise real disk write/read logic through a per-test
    # temp directory rather than a parallel in-memory stand-in that could drift from
    # production behavior.
    report_file_storage = LocalFileStorage(base_path=tempfile.mkdtemp(prefix="reports-test-"))
    dashboard_service = DashboardService(reporting_repo=reporting)
    analytics_service = AnalyticsService(reporting_repo=reporting)
    report_generation_service = ReportGenerationService(
        report_repo=reports, file_storage=report_file_storage, event_publisher=event_publisher,
        plant_repo=plants, inventory_repo=inventory, sale_repo=sales, sale_item_repo=sale_items,
        customer_repo=customers, employee_repo=employees, branch_repo=branches,
        disease_report_repo=disease_reports, growth_timeline_repo=growth_timeline,
        watering_log_repo=watering_logs, fertilizer_log_repo=fertilizer_logs,
        notification_repo=notifications, audit_log_repo=audit_logs, security_event_repo=security_events,
        passport_repo=passports, ai_prediction_repo=ai_predictions,
    )
    scheduled_report_service = ScheduledReportService(
        scheduled_repo=scheduled_reports, report_repo=reports, generation_service=report_generation_service
    )

    # --- Added by Phase 6 Module 13 (Administration & System Management) ---
    feature_flags = FakeFeatureFlagRepository()
    system_configs = FakeSystemConfigRepository()
    ai_inference_failures = FakeAIInferenceFailureRepository()
    role_admin_service = RoleAdminService(
        permission_repo=permissions, permission_service=permission_service, audit_repo=audit_logs
    )
    user_admin_service = UserAdminService(
        user_repo=users, employee_repo=employees, permission_repo=permissions, auth_service=service,
        security_event_repo=security_events, audit_repo=audit_logs,
    )
    feature_flag_service = FeatureFlagService(flag_repo=feature_flags, audit_repo=audit_logs)
    system_config_service = SystemConfigService(config_repo=system_configs, audit_repo=audit_logs)
    audit_admin_service = AuditAdminService(
        audit_repo=audit_logs, security_event_repo=security_events, denial_repo=denials
    )
    ai_admin_service = AIAdminService(
        prediction_repo=ai_predictions, failure_repo=ai_inference_failures,
        knowledge_repo=knowledge_base_chunks, model_registry=model_registry,
    )
    data_management_service = DataManagementService(
        audit_repo=audit_logs, security_event_repo=security_events,
        prediction_repo=ai_predictions, failure_repo=ai_inference_failures,
    )

    return AuthTestHarness(
        settings=settings,
        service=service,
        users=users,
        refresh_tokens=refresh_tokens,
        email_verification_tokens=email_verification_tokens,
        password_reset_tokens=password_reset_tokens,
        security_events=security_events,
        permissions=permissions,
        invites=invites,
        email_sender=email_sender,
        denials=denials,
        audit_logs=audit_logs,
        cache=cache,
        permission_service=permission_service,
        authorization_service=authorization_service,
        nurseries=nurseries,
        branches=branches,
        employees=employees,
        domain_events=domain_events,
        organization_service=organization_service,
        branch_service=branch_service,
        employee_service=employee_service,
        plant_categories=plant_categories,
        species=species,
        plant_varieties=plant_varieties,
        species_service=species_service,
        plant_variety_service=plant_variety_service,
        plants=plants,
        plant_images=plant_images,
        plant_transfers=plant_transfers,
        growth_timeline=growth_timeline,
        health_history=health_history,
        watering_logs=watering_logs,
        fertilizer_logs=fertilizer_logs,
        environmental_readings=environmental_readings,
        disease_reports=disease_reports,
        treatments=treatments,
        suppliers=suppliers,
        qr_code_service=qr_code_service,
        plant_service=plant_service,
        growth_service=growth_service,
        health_service=health_service,
        watering_service=watering_service,
        fertilizer_service=fertilizer_service,
        environmental_service=environmental_service,
        disease_report_service=disease_report_service,
        treatment_service=treatment_service,
        plant_timeline_service=plant_timeline_service,
        digital_twins=digital_twins,
        digital_twin_versions=digital_twin_versions,
        event_dispatch_log=event_dispatch_log,
        event_dispatcher=event_dispatcher,
        digital_twin_service=digital_twin_service,
        inventory_locations=inventory_locations,
        inventory=inventory,
        stock_movements=stock_movements,
        stock_reservations=stock_reservations,
        units=units,
        inventory_location_service=inventory_location_service,
        inventory_service=inventory_service,
        customers=customers,
        customer_contacts=customer_contacts,
        customer_addresses=customer_addresses,
        customer_tags=customer_tags,
        customer_notes=customer_notes,
        customer_communications=customer_communications,
        quotations=quotations,
        quotation_items=quotation_items,
        sales_orders=sales_orders,
        order_items=order_items,
        sales=sales,
        sale_items=sale_items,
        invoices=invoices,
        invoice_items=invoice_items,
        invoice_sales=invoice_sales,
        payments=payments,
        returns=returns,
        return_items=return_items,
        refunds=refunds,
        passports=passports,
        qr_scan_events=qr_scan_events,
        customer_service=customer_service,
        quotation_service=quotation_service,
        sales_order_service=sales_order_service,
        payment_service=payment_service,
        return_service=return_service,
        refund_service=refund_service,
        sales_reporting_service=sales_reporting_service,
        passport_service=passport_service,
        qr_service=qr_service,
        ai_predictions=ai_predictions,
        ai_recommendations=ai_recommendations,
        ai_assistant_conversations=ai_assistant_conversations,
        ai_assistant_messages=ai_assistant_messages,
        knowledge_base_chunks=knowledge_base_chunks,
        model_registry=model_registry,
        prediction_logger=prediction_logger,
        feature_store=feature_store,
        disease_detection_inference=disease_detection_inference,
        growth_prediction_inference=growth_prediction_inference,
        survival_prediction_inference=survival_prediction_inference,
        water_recommendation_inference=water_recommendation_inference,
        revenue_forecast_inference=revenue_forecast_inference,
        recommendation_engine=recommendation_engine,
        knowledge_retrieval_service=knowledge_retrieval_service,
        assistant_orchestrator=assistant_orchestrator,
        assistant_conversation_service=assistant_conversation_service,
        event_publisher=event_publisher,
        notifications=notifications,
        notification_preferences=notification_preferences,
        notification_templates=notification_templates,
        notification_deliveries=notification_deliveries,
        notification_hub=notification_hub,
        email_provider=email_provider,
        sms_provider=sms_provider,
        push_provider=push_provider,
        notification_delivery_service=notification_delivery_service,
        preference_service=preference_service,
        template_service=template_service,
        notification_service=notification_service,
        notification_event_handler=notification_event_handler,
        reports=reports,
        scheduled_reports=scheduled_reports,
        reporting=reporting,
        report_file_storage=report_file_storage,
        dashboard_service=dashboard_service,
        analytics_service=analytics_service,
        report_generation_service=report_generation_service,
        scheduled_report_service=scheduled_report_service,
        feature_flags=feature_flags,
        system_configs=system_configs,
        ai_inference_failures=ai_inference_failures,
        role_admin_service=role_admin_service,
        user_admin_service=user_admin_service,
        feature_flag_service=feature_flag_service,
        system_config_service=system_config_service,
        audit_admin_service=audit_admin_service,
        ai_admin_service=ai_admin_service,
        data_management_service=data_management_service,
    )


def _apply_common_overrides(app, harness: "AuthTestHarness") -> None:
    """
    Shared by `auth_client`/`authenticated_client`: overrides every
    Module 2/3 dependency that would otherwise try to reach a real
    database or Redis (`get_auth_service`, `get_permission_service`,
    `get_authorization_service`, `get_audit_log_repository`, `get_cache`)
    with objects wired to the same `harness` instance, so unit-tested
    business logic (`harness.service`, `harness.permission_service`,
    `harness.authorization_service`) and HTTP-level integration tests
    exercise the exact same state -- e.g. a permission-cache entry warmed
    by a direct `harness.permission_service.resolve_for_user(...)` call
    is visible to a subsequent request through `auth_client` too.
    """
    from app.api.deps import (
        get_ai_assistant_conversation_repository,
        get_ai_assistant_message_repository,
        get_ai_prediction_repository,
        get_ai_recommendation_repository,
        get_assistant_conversation_service,
        get_audit_log_repository,
        get_auth_service,
        get_authorization_service,
        get_branch_service,
        get_cache,
        get_customer_service,
        get_digital_twin_service,
        get_disease_detection_inference,
        get_disease_report_service,
        get_employee_service,
        get_environmental_service,
        get_feature_store,
        get_fertilizer_service,
        get_growth_prediction_inference,
        get_growth_service,
        get_health_service,
        get_domain_event_publisher,
        get_invoice_item_repository,
        get_invoice_repository,
        get_inventory_location_service,
        get_inventory_service,
        get_knowledge_base_chunk_repository,
        get_notification_delivery_repository,
        get_notification_hub,
        get_notification_hub_ws,
        get_notification_preference_repository,
        get_notification_repository,
        get_notification_service,
        get_notification_template_repository,
        get_organization_service,
        get_user_repository,
        get_passport_service,
        get_payment_service,
        get_permission_service,
        get_plant_repository,
        get_plant_service,
        get_plant_timeline_service,
        get_plant_variety_service,
        get_public_passport_service,
        get_qr_service,
        get_quotation_service,
        get_recommendation_engine,
        get_refund_service,
        get_return_service,
        get_revenue_forecast_inference,
        get_sale_item_repository,
        get_sale_repository,
        get_sales_order_service,
        get_sales_reporting_service,
        get_species_service,
        get_survival_prediction_inference,
        get_treatment_service,
        get_water_recommendation_inference,
        get_watering_service,
        get_analytics_service,
        get_dashboard_service,
        get_file_storage,
        get_report_generation_service,
        get_report_repository,
        get_reporting_repository,
        get_scheduled_report_repository,
        get_scheduled_report_service,
        get_security_event_repository,
        get_ai_admin_service,
        get_audit_admin_service,
        get_authorization_denial_repository,
        get_data_management_service,
        get_feature_flag_repository,
        get_feature_flag_service,
        get_role_admin_service,
        get_system_config_repository,
        get_system_config_service,
        get_user_admin_service,
    )

    app.dependency_overrides[get_auth_service] = lambda: harness.service
    app.dependency_overrides[get_permission_service] = lambda: harness.permission_service
    app.dependency_overrides[get_authorization_service] = lambda: harness.authorization_service
    app.dependency_overrides[get_audit_log_repository] = lambda: harness.audit_logs
    app.dependency_overrides[get_cache] = lambda: harness.cache
    # --- Added by Phase 6 Module 4 ---
    app.dependency_overrides[get_organization_service] = lambda: harness.organization_service
    app.dependency_overrides[get_branch_service] = lambda: harness.branch_service
    app.dependency_overrides[get_employee_service] = lambda: harness.employee_service
    # --- Added by Phase 6 Module 5 ---
    app.dependency_overrides[get_species_service] = lambda: harness.species_service
    app.dependency_overrides[get_plant_variety_service] = lambda: harness.plant_variety_service
    # --- Added by Phase 6 Module 6 ---
    app.dependency_overrides[get_plant_service] = lambda: harness.plant_service
    app.dependency_overrides[get_growth_service] = lambda: harness.growth_service
    app.dependency_overrides[get_health_service] = lambda: harness.health_service
    app.dependency_overrides[get_watering_service] = lambda: harness.watering_service
    app.dependency_overrides[get_fertilizer_service] = lambda: harness.fertilizer_service
    app.dependency_overrides[get_environmental_service] = lambda: harness.environmental_service
    app.dependency_overrides[get_disease_report_service] = lambda: harness.disease_report_service
    app.dependency_overrides[get_treatment_service] = lambda: harness.treatment_service
    app.dependency_overrides[get_plant_timeline_service] = lambda: harness.plant_timeline_service
    # --- Added by Phase 6 Module 7 ---
    app.dependency_overrides[get_digital_twin_service] = lambda: harness.digital_twin_service
    # --- Added by Phase 6 Module 8 ---
    app.dependency_overrides[get_inventory_location_service] = lambda: harness.inventory_location_service
    app.dependency_overrides[get_inventory_service] = lambda: harness.inventory_service
    # --- Added by Phase 6 Module 9 ---
    # `get_passport_service`/`get_qr_service` are overridden here too even
    # though the public routes that use them (app/api/routes/passport.py's
    # `public_router`) take no `get_current_user`/`get_authorization_
    # service` dependency at all -- these two overrides are what let
    # `auth_client`/`authenticated_client` exercise the public QR/passport
    # endpoints against the harness's in-memory fakes instead of trying to
    # open a real database connection, same as every other service override
    # in this function; it has nothing to do with authorization.
    app.dependency_overrides[get_customer_service] = lambda: harness.customer_service
    app.dependency_overrides[get_quotation_service] = lambda: harness.quotation_service
    app.dependency_overrides[get_sales_order_service] = lambda: harness.sales_order_service
    app.dependency_overrides[get_payment_service] = lambda: harness.payment_service
    app.dependency_overrides[get_return_service] = lambda: harness.return_service
    app.dependency_overrides[get_refund_service] = lambda: harness.refund_service
    app.dependency_overrides[get_sales_reporting_service] = lambda: harness.sales_reporting_service
    app.dependency_overrides[get_passport_service] = lambda: harness.passport_service
    # `get_public_passport_service` is a distinct factory function from
    # `get_passport_service` (see app/api/deps.py's docstring on why --
    # the public route must not transitively require `get_current_user`),
    # but both must resolve to the SAME `PassportService` instance in
    # tests, or a passport generated through the internal authenticated
    # route wouldn't be found by the public token lookup (they'd be two
    # separate `PassportService`s wrapping two separate, unrelated
    # `FakePassportRepository` state) -- caught by
    # tests/integration/test_passport_routes.py's
    # `test_public_passport_lookup_requires_no_authentication` immediately
    # after this factory split was introduced.
    app.dependency_overrides[get_public_passport_service] = lambda: harness.passport_service
    app.dependency_overrides[get_qr_service] = lambda: harness.qr_service
    # Raw repository dependencies app/api/routes/sales.py and
    # app/api/routes/passport.py fetch-then-authorize against directly
    # (Sale/Invoice/InvoiceItem for `GET /sales/{id}`,`GET /invoices/{id}`,
    # etc.; Plant/Sale/SaleItem for `POST /plants/{plant_id}/passports`'s
    # optional sale_id/sale_item_id lookup) rather than through one of the
    # services above -- these need the exact same harness-backed override
    # treatment or they'd try to open a real database connection too.
    app.dependency_overrides[get_sale_repository] = lambda: harness.sales
    app.dependency_overrides[get_sale_item_repository] = lambda: harness.sale_items
    app.dependency_overrides[get_invoice_repository] = lambda: harness.invoices
    app.dependency_overrides[get_invoice_item_repository] = lambda: harness.invoice_items
    app.dependency_overrides[get_plant_repository] = lambda: harness.plants
    # --- Added by Phase 6 Module 10 (AI Platform) ---
    app.dependency_overrides[get_ai_prediction_repository] = lambda: harness.ai_predictions
    app.dependency_overrides[get_ai_recommendation_repository] = lambda: harness.ai_recommendations
    app.dependency_overrides[get_ai_assistant_conversation_repository] = lambda: harness.ai_assistant_conversations
    app.dependency_overrides[get_ai_assistant_message_repository] = lambda: harness.ai_assistant_messages
    app.dependency_overrides[get_knowledge_base_chunk_repository] = lambda: harness.knowledge_base_chunks
    app.dependency_overrides[get_feature_store] = lambda: harness.feature_store
    app.dependency_overrides[get_disease_detection_inference] = lambda: harness.disease_detection_inference
    app.dependency_overrides[get_growth_prediction_inference] = lambda: harness.growth_prediction_inference
    app.dependency_overrides[get_survival_prediction_inference] = lambda: harness.survival_prediction_inference
    app.dependency_overrides[get_water_recommendation_inference] = lambda: harness.water_recommendation_inference
    app.dependency_overrides[get_revenue_forecast_inference] = lambda: harness.revenue_forecast_inference
    app.dependency_overrides[get_recommendation_engine] = lambda: harness.recommendation_engine
    app.dependency_overrides[get_assistant_conversation_service] = lambda: harness.assistant_conversation_service
    # --- Added by Phase 6 Module 11 (Notifications & Communication) ---
    app.dependency_overrides[get_domain_event_publisher] = lambda: harness.event_publisher
    app.dependency_overrides[get_notification_service] = lambda: harness.notification_service
    app.dependency_overrides[get_notification_repository] = lambda: harness.notifications
    app.dependency_overrides[get_notification_preference_repository] = lambda: harness.notification_preferences
    app.dependency_overrides[get_notification_template_repository] = lambda: harness.notification_templates
    app.dependency_overrides[get_notification_delivery_repository] = lambda: harness.notification_deliveries
    app.dependency_overrides[get_notification_hub] = lambda: harness.notification_hub
    app.dependency_overrides[get_notification_hub_ws] = lambda: harness.notification_hub
    app.dependency_overrides[get_user_repository] = lambda: harness.users
    # `get_assistant_tool_registry` is deliberately NOT overridden here -- it's
    # constructed fresh per-request from `get_current_user`/`get_tenant_context`/
    # `get_authorization_service`/`get_plant_service`/`get_inventory_service`/
    # `get_sales_reporting_service`/`get_ai_prediction_repository`/
    # `get_watering_service`/`get_health_service`, every one of which is
    # already overridden above -- so FastAPI's normal dependency resolution
    # already builds a real `AssistantToolRegistry` wired to `harness`'s fakes,
    # exactly matching production's per-request construction (see that
    # factory's own docstring in app/api/deps.py). Overriding it directly
    # would mean tests exercising a DIFFERENT object than what a real request
    # actually builds.
    # --- Added by Phase 6 Module 12 (Reports & Analytics) ---
    app.dependency_overrides[get_security_event_repository] = lambda: harness.security_events
    app.dependency_overrides[get_report_repository] = lambda: harness.reports
    app.dependency_overrides[get_scheduled_report_repository] = lambda: harness.scheduled_reports
    app.dependency_overrides[get_reporting_repository] = lambda: harness.reporting
    app.dependency_overrides[get_file_storage] = lambda: harness.report_file_storage
    app.dependency_overrides[get_dashboard_service] = lambda: harness.dashboard_service
    app.dependency_overrides[get_analytics_service] = lambda: harness.analytics_service
    app.dependency_overrides[get_report_generation_service] = lambda: harness.report_generation_service
    app.dependency_overrides[get_scheduled_report_service] = lambda: harness.scheduled_report_service
    # --- Added by Phase 6 Module 13 (Administration & System Management) ---
    app.dependency_overrides[get_authorization_denial_repository] = lambda: harness.denials
    app.dependency_overrides[get_feature_flag_repository] = lambda: harness.feature_flags
    app.dependency_overrides[get_system_config_repository] = lambda: harness.system_configs
    app.dependency_overrides[get_role_admin_service] = lambda: harness.role_admin_service
    app.dependency_overrides[get_user_admin_service] = lambda: harness.user_admin_service
    app.dependency_overrides[get_feature_flag_service] = lambda: harness.feature_flag_service
    app.dependency_overrides[get_system_config_service] = lambda: harness.system_config_service
    app.dependency_overrides[get_audit_admin_service] = lambda: harness.audit_admin_service
    app.dependency_overrides[get_ai_admin_service] = lambda: harness.ai_admin_service
    app.dependency_overrides[get_data_management_service] = lambda: harness.data_management_service
    # `get_health_check_service` is deliberately NOT overridden here -- it
    # takes a real `AsyncSession` (`db_session`) this harness has no fake
    # for (every other Module 13 service takes only Protocol-shaped
    # repositories, which is exactly why this is the one exception);
    # `tests/integration/test_admin_routes.py` overrides it per-test with a
    # small stub session instead, the same way `test_health_routes.py`
    # (Module 1) already handles `/readyz`'s own direct `get_db` dependency.


@pytest.fixture
async def auth_client(harness: AuthTestHarness):
    """
    An HTTP client against the real app with every Module 2/3 dependency
    overridden to return objects wired to `harness`'s in-memory fakes --
    exercises real routing, validation, error-envelope handling, and
    cookie/CSRF logic, without needing a database or Redis.
    """
    app = create_app(settings=harness.settings)
    _apply_common_overrides(app, harness)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def authenticated_client(harness: AuthTestHarness):
    """
    Like `auth_client`, but also overrides `get_current_user` to return a
    freshly-created harness user directly -- for endpoints that require a
    bearer token (sessions, logout-all, change-password, me, audit-log)
    without the test needing to thread a real JWT through headers.
    """
    from app.api.deps import get_current_user

    user = await harness.create_user()
    app = create_app(settings=harness.settings)
    _apply_common_overrides(app, harness)
    app.dependency_overrides[get_current_user] = lambda: user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac, user
    app.dependency_overrides.clear()
