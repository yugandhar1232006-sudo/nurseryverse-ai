"""
Phase 6 Module 14 (Production Readiness) — Celery application + periodic
("beat") tasks.

Two on-demand sweeps already existed before this module, and both of
their own docstrings explicitly disclosed the exact same gap:
`NotificationService.retry_due_deliveries` (Module 11, reachable via
`POST /notifications/retry-due`) and `ScheduledReportService.run_due`
(Module 12) each say, in one form or another, "no scheduler exists in
this codebase — needs an external cron trigger." This module IS that
trigger: a real, working Celery Beat schedule that calls those exact
same, already-tested service methods on an interval, instead of leaving
them reachable only by an inbound HTTP request. `docs/architecture/
09-infrastructure.md` §1/§2 documents the `worker`/`beat` processes this
module is the entrypoint for (`celery -A app.workers worker` /
`celery -A app.workers beat`).

Deliberately does NOT go through HTTP (no service-account JWT, no
self-referential API call from inside the API process). Each task opens
its own `AsyncSession` and builds the same repository/service dependency
graph `app/api/deps.py`'s `get_domain_event_publisher` builds for a real
request — `_build_event_publisher` below mirrors that function almost
verbatim (see its own docstring for why every repository is constructed
directly from `db` rather than through another `Depends()`-shaped
factory: forward-reference ordering, the identical constraint that
function already documents). The one difference: a fresh, empty
`InMemoryNotificationHub()` per task run, not `request.app.state`'s —
a worker process is never holding a live WebSocket connection to push
an in-app notification over in the first place, so there is nothing this
substitution could regress; a real multi-replica deployment already needs
a Redis pub/sub-backed hub to fan a push out across API replicas too
(disclosed in `app/notifications/hub.py`'s own module docstring since
Module 11) — this worker's use of an in-process hub is the same disclosed
gap, not a new one.
"""
from __future__ import annotations

import asyncio

from celery import Celery
from celery.schedules import crontab

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import AsyncSessionLocal
from app.domain_events import DomainEventPublisher, EventDispatcher
from app.notifications.delivery import NotificationDeliveryService
from app.notifications.hub import InMemoryNotificationHub
from app.notifications.notification_handler import NotificationEventHandler, NotificationService
from app.notifications.preferences import PreferenceService
from app.notifications.providers import LoggingPushProvider, LoggingSmsProvider, SmtpEmailProvider
from app.notifications.templates import TemplateService
from app.reporting.file_storage import get_file_storage
from app.repositories.sqlalchemy_repositories import (
    SqlAlchemyAuditLogRepository,
    SqlAlchemyAIPredictionRepository,
    SqlAlchemyBranchRepository,
    SqlAlchemyCustomerRepository,
    SqlAlchemyDigitalTwinRepository,
    SqlAlchemyDigitalTwinVersionRepository,
    SqlAlchemyDiseaseReportRepository,
    SqlAlchemyDomainEventRepository,
    SqlAlchemyEmployeeRepository,
    SqlAlchemyEnvironmentalReadingRepository,
    SqlAlchemyEventDispatchLogRepository,
    SqlAlchemyFertilizerLogRepository,
    SqlAlchemyGrowthTimelineRepository,
    SqlAlchemyHealthHistoryRepository,
    SqlAlchemyInventoryRepository,
    SqlAlchemyInvoiceRepository,
    SqlAlchemyNotificationDeliveryRepository,
    SqlAlchemyNotificationPreferenceRepository,
    SqlAlchemyNotificationRepository,
    SqlAlchemyNotificationTemplateRepository,
    SqlAlchemyPassportRepository,
    SqlAlchemyPermissionRepository,
    SqlAlchemyPlantRepository,
    SqlAlchemyReportRepository,
    SqlAlchemyReturnItemRepository,
    SqlAlchemySaleItemRepository,
    SqlAlchemySaleRepository,
    SqlAlchemySalesOrderRepository,
    SqlAlchemyScheduledReportRepository,
    SqlAlchemySecurityEventRepository,
    SqlAlchemyTreatmentRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyWateringLogRepository,
)
from app.services.digital_twin_service import DigitalTwinEventHandler, DigitalTwinService
from app.services.report_generation_service import ReportGenerationService
from app.services.scheduled_report_service import ScheduledReportService

logger = get_logger(__name__)
_settings = get_settings()
configure_logging(json_logs=_settings.is_production, log_level="DEBUG" if _settings.APP_DEBUG else "INFO")

celery_app = Celery(
    "nurseryverse", broker=_settings.CELERY_BROKER_URL, backend=_settings.CELERY_RESULT_BACKEND
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # A stuck/hung task (e.g. a wedged DB connection) should not hold a
    # worker slot forever -- 10 minutes is generously above either sweep's
    # expected real runtime (both operate on a bounded `limit`), so this
    # only ever fires on a genuine hang, not a slow-but-healthy run.
    task_time_limit=600,
)
celery_app.conf.beat_schedule = {
    # Matches Module 11's own disclosed retry cadence expectation (delivery
    # attempts back off on a schedule measured in minutes, not seconds) --
    # every 5 minutes is frequent enough that a transient provider outage
    # recovers within one delivery's user-visible SLA, without hammering
    # SMTP/SMS/push providers on every tick.
    "notifications-retry-due": {
        "task": "app.workers.retry_due_notifications",
        "schedule": crontab(minute="*/5"),
    },
    # Scheduled reports are typically daily/weekly/monthly (ReportScheduleFrequency,
    # Module 12) -- checking every minute for "is anything due right now"
    # is cheap (a single indexed query returning zero rows the overwhelming
    # majority of ticks) and keeps the worst-case delay between a report's
    # `next_run_at` and it actually running under a minute.
    "scheduled-reports-run-due": {
        "task": "app.workers.run_due_scheduled_reports",
        "schedule": crontab(minute="*"),
    },
}


def _build_event_publisher(db, settings: Settings) -> DomainEventPublisher:
    """
    Mirrors `app/api/deps.py`'s `get_domain_event_publisher` -- see that
    function's own docstring for why every repository below is
    constructed directly from `db` rather than through another
    `Depends()`-shaped factory (a forward-reference ordering constraint
    that applies equally here, even though this module has no `Depends()`
    machinery at all). Returns the publisher; callers that only need the
    `NotificationService` half use `_build_notification_service` below
    instead of duplicating this.
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
    notification_service = _build_notification_service(db, settings)
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


def _build_notification_service(db, settings: Settings) -> NotificationService:
    return NotificationService(
        notification_repo=SqlAlchemyNotificationRepository(db),
        delivery_service=NotificationDeliveryService(
            delivery_repo=SqlAlchemyNotificationDeliveryRepository(db),
            email_provider=SmtpEmailProvider(settings),
            sms_provider=LoggingSmsProvider(settings),
            push_provider=LoggingPushProvider(settings),
        ),
        preference_service=PreferenceService(SqlAlchemyNotificationPreferenceRepository(db)),
        template_service=TemplateService(SqlAlchemyNotificationTemplateRepository(db)),
        hub=InMemoryNotificationHub(),  # see this module's own docstring
        user_repo=SqlAlchemyUserRepository(db),
    )


async def _retry_due_notifications_async() -> list[dict]:
    async with AsyncSessionLocal() as db:
        try:
            notification_service = _build_notification_service(db, _settings)
            results = await notification_service.retry_due_deliveries()
            await db.commit()
            logger.info("worker_retry_due_notifications_completed", attempted=len(results))
            return results
        except Exception:
            await db.rollback()
            raise


@celery_app.task(name="app.workers.retry_due_notifications")
def retry_due_notifications() -> list[dict]:
    return asyncio.run(_retry_due_notifications_async())


async def _run_due_scheduled_reports_async() -> list[dict]:
    async with AsyncSessionLocal() as db:
        try:
            event_publisher = _build_event_publisher(db, _settings)
            report_repo = SqlAlchemyReportRepository(db)
            generation_service = ReportGenerationService(
                report_repo=report_repo,
                file_storage=get_file_storage(_settings),
                event_publisher=event_publisher,
                plant_repo=SqlAlchemyPlantRepository(db),
                inventory_repo=SqlAlchemyInventoryRepository(db),
                sale_repo=SqlAlchemySaleRepository(db),
                sale_item_repo=SqlAlchemySaleItemRepository(db),
                customer_repo=SqlAlchemyCustomerRepository(db),
                employee_repo=SqlAlchemyEmployeeRepository(db),
                branch_repo=SqlAlchemyBranchRepository(db),
                disease_report_repo=SqlAlchemyDiseaseReportRepository(db),
                growth_timeline_repo=SqlAlchemyGrowthTimelineRepository(db),
                watering_log_repo=SqlAlchemyWateringLogRepository(db),
                fertilizer_log_repo=SqlAlchemyFertilizerLogRepository(db),
                notification_repo=SqlAlchemyNotificationRepository(db),
                audit_log_repo=SqlAlchemyAuditLogRepository(db),
                security_event_repo=SqlAlchemySecurityEventRepository(db),
                passport_repo=SqlAlchemyPassportRepository(db),
                ai_prediction_repo=SqlAlchemyAIPredictionRepository(db),
            )
            scheduled_report_service = ScheduledReportService(
                scheduled_repo=SqlAlchemyScheduledReportRepository(db),
                report_repo=report_repo,
                generation_service=generation_service,
            )
            results = await scheduled_report_service.run_due()
            await db.commit()
            logger.info("worker_run_due_scheduled_reports_completed", executed=len(results))
            return results
        except Exception:
            await db.rollback()
            raise


@celery_app.task(name="app.workers.run_due_scheduled_reports")
def run_due_scheduled_reports() -> list[dict]:
    return asyncio.run(_run_due_scheduled_reports_async())
