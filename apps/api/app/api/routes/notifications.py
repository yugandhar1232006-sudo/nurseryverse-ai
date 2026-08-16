"""
Phase 6 Module 11 (Notifications & Communication) -- REST + WebSocket API.

Every read/write route below operates on the *caller's own* notifications
and preferences (`recipient_user_id`/`user_id` is always the authenticated
caller, never a path/query parameter a caller could point at someone
else) -- the same "no resource-id-in-path needed" shape `GET /me` (Module
2) already established for self-scoped resources.

Permission reuse: `notifications:read` and `notifications:manage_preferences`
are the only two permission codes this project's seed matrix
(migration 0002) defines for this module; template management,
system-alert broadcasting, and the on-demand retry sweep all reuse
`notifications:manage_preferences` rather than a new, unseeded permission
code -- the same "reuse an existing permission for a closely related
capability" precedent `app/api/routes/digital_twin.py` already documents
for its own reuse of `plants:read`.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect, status

from app.api.deps import (
    PageParams,
    TenantContext,
    get_current_user,
    get_domain_event_publisher,
    get_notification_preference_repository,
    get_notification_repository,
    get_notification_service,
    get_notification_hub_ws,
    get_notification_template_repository,
    get_settings,
    get_tenant_context,
    get_user_repository,
    require_permission,
)
from app.core.config import Settings
from app.core.exceptions import AuthenticationError, NotFoundError
from app.core.logging import get_logger
from app.core.responses import ErrorResponse, Page, PageMeta
from app.core.security import decode_access_token
from app.db.enums import NotificationCategory
from app.domain_events import DomainEventPublisher, SystemAlertRaised
from app.models.identity import User
from app.notifications.hub import NotificationHub
from app.notifications.notification_handler import NotificationService
from app.schemas.notifications import (
    MarkAllReadResponse,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdateRequest,
    NotificationResponse,
    NotificationTemplateCreateRequest,
    NotificationTemplateResponse,
    RetryDueResponse,
    SystemAlertRequest,
    UnreadCountResponse,
)
from app.services.authorization_service import AuthorizationDecision

router = APIRouter()
logger = get_logger(__name__)

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Missing permission"},
    404: {"model": ErrorResponse, "description": "Notification not found"},
}


@router.get(
    "/notifications", response_model=Page[NotificationResponse], responses=_ERROR_RESPONSES,
    summary="Notification history -- the caller's own notifications, newest first",
)
async def list_notifications(
    request: Request, page_params: PageParams = Depends(),
    unread_only: bool = Query(False),
    category: NotificationCategory | None = Query(None),
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    service: NotificationService = Depends(get_notification_service),
    _decision: AuthorizationDecision = Depends(require_permission("notifications:read")),
) -> Page[NotificationResponse]:
    if tenant.org_id is None:
        return Page(items=[], meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=0, total_pages=0))
    rows, total = await service.list_notifications(
        user_id=user.id, nursery_id=tenant.org_id, unread_only=unread_only, category=category,
        offset=page_params.offset, limit=page_params.page_size,
    )
    total_pages = (total + page_params.page_size - 1) // page_params.page_size if total else 0
    return Page(
        items=[NotificationResponse.model_validate(r) for r in rows],
        meta=PageMeta(page=page_params.page, page_size=page_params.page_size, total_items=total, total_pages=total_pages),
    )


@router.get(
    "/notifications/unread-count", response_model=UnreadCountResponse, responses=_ERROR_RESPONSES,
    summary="Live unread count -- the same number pushed over the WebSocket hub on every new/read event",
)
async def get_unread_count(
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    service: NotificationService = Depends(get_notification_service),
    _decision: AuthorizationDecision = Depends(require_permission("notifications:read")),
) -> UnreadCountResponse:
    if tenant.org_id is None:
        return UnreadCountResponse(unread_count=0)
    return UnreadCountResponse(unread_count=await service.unread_count(user.id, tenant.org_id))


@router.patch(
    "/notifications/{id}/read", response_model=NotificationResponse, responses=_ERROR_RESPONSES,
    summary="Mark one notification read",
)
async def mark_notification_read(
    id: uuid.UUID,
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    service: NotificationService = Depends(get_notification_service),
    notification_repo=Depends(get_notification_repository),
    _decision: AuthorizationDecision = Depends(require_permission("notifications:read")),
) -> NotificationResponse:
    notification = await notification_repo.get_by_id(id)
    if notification is None or notification.recipient_user_id != user.id or notification.nursery_id != tenant.org_id:
        # Deliberately the same 404 whether the row doesn't exist or
        # belongs to someone else -- never leaks another user's
        # notification existence via a 403 vs. 404 distinction.
        raise NotFoundError(f"Notification {id} not found.")
    await service.mark_read(notification)
    return NotificationResponse.model_validate(notification)


@router.post(
    "/notifications/mark-all-read", response_model=MarkAllReadResponse, responses=_ERROR_RESPONSES,
    summary="Mark every unread notification read",
)
async def mark_all_read(
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    service: NotificationService = Depends(get_notification_service),
    _decision: AuthorizationDecision = Depends(require_permission("notifications:read")),
) -> MarkAllReadResponse:
    if tenant.org_id is None:
        return MarkAllReadResponse(marked_read_count=0)
    count = await service.mark_all_read(user.id, tenant.org_id)
    return MarkAllReadResponse(marked_read_count=count)


@router.get(
    "/notifications/preferences", response_model=list[NotificationPreferenceResponse], responses=_ERROR_RESPONSES,
    summary="The caller's own notification preferences (channel selection, quiet hours, frequency)",
)
async def list_preferences(
    user: User = Depends(get_current_user),
    preference_repo=Depends(get_notification_preference_repository),
    _decision: AuthorizationDecision = Depends(require_permission("notifications:manage_preferences")),
) -> list[NotificationPreferenceResponse]:
    rows = await preference_repo.list_for_user(user.id)
    return [NotificationPreferenceResponse.model_validate(r) for r in rows]


@router.put(
    "/notifications/preferences", response_model=list[NotificationPreferenceResponse], responses=_ERROR_RESPONSES,
    summary="Upsert one or more (category, channel) preference rows -- Channel selection / Event subscriptions / Quiet hours / Frequency controls",
)
async def update_preferences(
    updates: list[NotificationPreferenceUpdateRequest],
    user: User = Depends(get_current_user),
    preference_repo=Depends(get_notification_preference_repository),
    _decision: AuthorizationDecision = Depends(require_permission("notifications:manage_preferences")),
) -> list[NotificationPreferenceResponse]:
    results = []
    for update in updates:
        row = await preference_repo.upsert(
            user_id=user.id, category=update.category, channel=update.channel, enabled=update.enabled,
            quiet_hours_start=update.quiet_hours_start, quiet_hours_end=update.quiet_hours_end,
            quiet_hours_timezone=update.quiet_hours_timezone, frequency=update.frequency,
        )
        results.append(row)
    return [NotificationPreferenceResponse.model_validate(r) for r in results]


@router.get(
    "/notifications/templates", response_model=list[NotificationTemplateResponse], responses=_ERROR_RESPONSES,
    summary="This org's template overrides (global platform defaults are not DB rows -- see app/notifications/templates.py's own docstring -- and are not listed here)",
)
async def list_templates(
    tenant: TenantContext = Depends(get_tenant_context),
    template_repo=Depends(get_notification_template_repository),
    _decision: AuthorizationDecision = Depends(require_permission("notifications:manage_preferences")),
) -> list[NotificationTemplateResponse]:
    if tenant.org_id is None:
        return []
    rows = await template_repo.list_for_org(tenant.org_id)
    return [NotificationTemplateResponse.model_validate(r) for r in rows]


@router.post(
    "/notifications/templates", response_model=NotificationTemplateResponse, status_code=status.HTTP_201_CREATED,
    responses=_ERROR_RESPONSES,
    summary="Create/version this org's override of a template (HTML Email, Plain Text Email, SMS, Push, or In-App)",
)
async def create_template(
    body: NotificationTemplateCreateRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    template_repo=Depends(get_notification_template_repository),
    _decision: AuthorizationDecision = Depends(require_permission("notifications:manage_preferences")),
) -> NotificationTemplateResponse:
    from app.models.notifications import NotificationTemplate

    template = NotificationTemplate(
        nursery_id=tenant.org_id, category=body.category, channel=body.channel, format=body.format,
        locale=body.locale, version=body.version, subject_template=body.subject_template,
        body_template=body.body_template, is_active=body.is_active,
    )
    template = await template_repo.add(template)
    return NotificationTemplateResponse.model_validate(template)


@router.post(
    "/notifications/system-alerts", status_code=status.HTTP_202_ACCEPTED, responses=_ERROR_RESPONSES,
    summary="Broadcast a System Alert to every active employee in the caller's org (on-demand -- no scheduler exists in this codebase)",
)
async def raise_system_alert(
    body: SystemAlertRequest,
    request: Request,
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    publisher: DomainEventPublisher = Depends(get_domain_event_publisher),
    _decision: AuthorizationDecision = Depends(require_permission("notifications:manage_preferences")),
) -> dict[str, str]:
    if tenant.org_id is None:
        # `require_permission` above already requires org-scoped
        # `notifications:manage_preferences`, so an org-less caller is
        # rejected there with a 403 before this line is ever reached --
        # this branch exists only so the type checker sees `tenant.org_id`
        # narrowed to non-None below, the same defensive shape
        # `list_digital_twins` (digital_twin.py) uses for its own
        # `tenant.org_id is None` guard.
        raise NotFoundError("No organization context for this request.")
    event = SystemAlertRaised(
        aggregate_id=uuid.uuid4(), nursery_id=tenant.org_id, actor_user_id=user.id,
        title=body.title, message=body.message, severity=body.severity,
    )
    await publisher.publish(event, request_id=getattr(request.state, "request_id", None))
    return {"status": "accepted"}


@router.post(
    "/notifications/retry-due", response_model=RetryDueResponse, responses=_ERROR_RESPONSES,
    summary="On-demand retry sweep for FAILED deliveries whose backoff window has elapsed (no scheduled worker exists in this codebase)",
)
async def retry_due_deliveries(
    service: NotificationService = Depends(get_notification_service),
    _decision: AuthorizationDecision = Depends(require_permission("notifications:manage_preferences")),
) -> RetryDueResponse:
    results = await service.retry_due_deliveries()
    return RetryDueResponse(
        retried_count=len(results),
        results=[{"delivery_id": str(r["delivery_id"]), "notification_id": str(r["notification_id"]), "status": r["status"].value} for r in results],
    )


@router.websocket("/notifications/ws")
async def notifications_websocket(
    websocket: WebSocket,
    token: str = Query(..., description="A valid access token -- browsers cannot set Authorization headers on a WebSocket handshake, so this is passed as a query parameter instead"),
    settings: Settings = Depends(get_settings),
    user_repo=Depends(get_user_repository),
    hub: NotificationHub = Depends(get_notification_hub_ws),
) -> None:
    """
    WebSocket notification hub / live delivery (this module's own REALTIME
    requirement). One connection per browser tab/device; `InMemoryNotificationHub`
    (app/notifications/hub.py) tracks every open connection per user and
    pushes `{"type": "notification", ...}` / `{"type": "unread_count", ...}`
    frames the moment `NotificationService.notify`/`mark_read`/`mark_all_read`
    runs -- there is no polling on either side.

    The user lookup goes through `Depends(get_user_repository)` -- an
    ordinary FastAPI dependency, not a hand-opened DB session -- exactly
    so `tests/conftest.py` can override it to the harness's in-memory
    `FakeUserRepository` the same way every other repository dependency in
    this app is overridden (see `get_user_repository`'s own docstring in
    app/api/deps.py for why this matters: WebSocket routes support
    `Depends(...)` fully, so there was never a technical reason to bypass
    it).
    """
    try:
        payload = decode_access_token(token, settings=settings)
        user_id = uuid.UUID(payload["sub"])
    except (AuthenticationError, KeyError, ValueError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user = await user_repo.get_by_id(user_id)
    if user is None or not user.is_active:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    await hub.connect(user_id, websocket)
    try:
        while True:
            # This hub is push-only (server -> client); any inbound frame
            # is drained and ignored rather than rejected, so a client
            # sending periodic keepalive pings doesn't trip an error.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(user_id, websocket)
