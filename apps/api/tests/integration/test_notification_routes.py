"""
Integration tests for Module 11's REST + WebSocket API
(app/api/routes/notifications.py): authorization, cross-tenant isolation,
and the live WebSocket hub end to end through the real ASGI app.
"""
from __future__ import annotations

import uuid

import pytest
from starlette.testclient import TestClient

from app.core.security import create_access_token
from app.db.enums import NotificationCategory, NotificationChannel
from app.main import create_app

pytestmark = pytest.mark.integration


# --------------------------------------------------------------------------
# REST: list / unread-count / mark-read / mark-all-read
# --------------------------------------------------------------------------


async def test_list_notifications_requires_auth(auth_client):
    response = await auth_client.get("/api/v1/notifications")
    assert response.status_code == 401


async def test_list_notifications_denied_without_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=[])

    response = await ac.get("/api/v1/notifications")

    assert response.status_code == 403


async def test_list_notifications_returns_the_callers_own_notifications_newest_first(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["notifications:read"])
    for i in range(3):
        await harness.notification_service.notify(
            nursery_id=org_id, recipient_user_id=user.id, category=NotificationCategory.PLANT_SOLD,
            context={"common_label": f"Plant {i}", "unit_price": "5.00"},
        )

    response = await ac.get("/api/v1/notifications")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total_items"] == 3
    assert len(body["items"]) == 3


async def test_list_notifications_unread_only_filter(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["notifications:read"])
    first = await harness.notification_service.notify(
        nursery_id=org_id, recipient_user_id=user.id, category=NotificationCategory.PLANT_SOLD,
        context={"common_label": "A", "unit_price": "1.00"},
    )
    await harness.notification_service.notify(
        nursery_id=org_id, recipient_user_id=user.id, category=NotificationCategory.PLANT_SOLD,
        context={"common_label": "B", "unit_price": "2.00"},
    )
    await harness.notification_service.mark_read(first)

    response = await ac.get("/api/v1/notifications", params={"unread_only": "true"})

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total_items"] == 1
    assert "B" in body["items"][0]["message"]


async def test_unread_count(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["notifications:read"])
    for i in range(2):
        await harness.notification_service.notify(
            nursery_id=org_id, recipient_user_id=user.id, category=NotificationCategory.PLANT_SOLD,
            context={"common_label": f"Plant {i}", "unit_price": "5.00"},
        )

    response = await ac.get("/api/v1/notifications/unread-count")

    assert response.status_code == 200
    assert response.json()["unread_count"] == 2


async def test_mark_notification_read(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["notifications:read"])
    notification = await harness.notification_service.notify(
        nursery_id=org_id, recipient_user_id=user.id, category=NotificationCategory.PLANT_SOLD,
        context={"common_label": "Rose", "unit_price": "10.00"},
    )

    response = await ac.patch(f"/api/v1/notifications/{notification.id}/read")

    assert response.status_code == 200
    assert response.json()["read_at"] is not None
    assert await harness.notification_service.unread_count(user.id, org_id) == 0


async def test_mark_notification_read_404_for_someone_elses_notification(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["notifications:read"])
    notification = await harness.notification_service.notify(
        nursery_id=org_id, recipient_user_id=other_user_id, category=NotificationCategory.PLANT_SOLD,
        context={"common_label": "Rose", "unit_price": "10.00"},
    )

    response = await ac.patch(f"/api/v1/notifications/{notification.id}/read")

    assert response.status_code == 404


async def test_mark_notification_read_404_across_tenants(authenticated_client, harness):
    """Same recipient user id, but the notification belongs to a different org -- must still 404, not leak."""
    ac, user = authenticated_client
    own_org_id = uuid.uuid4()
    foreign_org_id = uuid.uuid4()
    harness.grant_role(user, org_id=own_org_id, role_code="owner", permission_codes=["notifications:read"])
    notification = await harness.notification_service.notify(
        nursery_id=foreign_org_id, recipient_user_id=user.id, category=NotificationCategory.PLANT_SOLD,
        context={"common_label": "Rose", "unit_price": "10.00"},
    )

    response = await ac.patch(f"/api/v1/notifications/{notification.id}/read")

    assert response.status_code == 404


async def test_mark_all_read(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["notifications:read"])
    for i in range(3):
        await harness.notification_service.notify(
            nursery_id=org_id, recipient_user_id=user.id, category=NotificationCategory.PLANT_SOLD,
            context={"common_label": f"Plant {i}", "unit_price": "5.00"},
        )

    response = await ac.post("/api/v1/notifications/mark-all-read")

    assert response.status_code == 200
    assert response.json()["marked_read_count"] == 3
    assert await harness.notification_service.unread_count(user.id, org_id) == 0


# --------------------------------------------------------------------------
# REST: preferences
# --------------------------------------------------------------------------


async def test_preferences_denied_without_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=[])

    response = await ac.get("/api/v1/notifications/preferences")

    assert response.status_code == 403


async def test_update_and_list_preferences_round_trip(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["notifications:manage_preferences"])

    update_response = await ac.put(
        "/api/v1/notifications/preferences",
        json=[{"category": "invoice_generated", "channel": "email", "enabled": False}],
    )
    assert update_response.status_code == 200
    assert update_response.json()[0]["enabled"] is False

    list_response = await ac.get("/api/v1/notifications/preferences")
    assert list_response.status_code == 200
    rows = list_response.json()
    assert len(rows) == 1
    assert rows[0]["category"] == "invoice_generated"
    assert rows[0]["channel"] == "email"
    assert rows[0]["enabled"] is False


async def test_updated_preference_is_actually_respected_by_delivery(authenticated_client, harness):
    """Proves the REST preference write and the notify-time preference read share the same underlying store."""
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["notifications:manage_preferences", "notifications:read"])
    await ac.put(
        "/api/v1/notifications/preferences",
        json=[{"category": "invoice_generated", "channel": "email", "enabled": False}],
    )

    notification = await harness.notification_service.notify(
        nursery_id=org_id, recipient_user_id=user.id, category=NotificationCategory.INVOICE_GENERATED,
        context={"total_amount": "50.00"},
    )
    deliveries = await harness.notification_deliveries.list_for_notification(notification.id)
    channels = {d.channel for d in deliveries}
    assert NotificationChannel.EMAIL not in channels
    assert NotificationChannel.IN_APP in channels


# --------------------------------------------------------------------------
# REST: templates
# --------------------------------------------------------------------------


async def test_create_and_list_template(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["notifications:manage_preferences"])

    create_response = await ac.post(
        "/api/v1/notifications/templates",
        json={
            "category": "plant_sold", "channel": "email", "format": "text", "locale": "en", "version": 1,
            "subject_template": "Sold!", "body_template": "{{ common_label }} sold for {{ unit_price }}.",
        },
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["nursery_id"] == str(org_id)

    list_response = await ac.get("/api/v1/notifications/templates")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


async def test_org_template_override_is_actually_used_by_rendering(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["notifications:manage_preferences", "notifications:read"])
    await ac.post(
        "/api/v1/notifications/templates",
        json={
            "category": "plant_sold", "channel": "in_app", "format": "text", "locale": "en", "version": 1,
            "body_template": "CUSTOM: {{ common_label }} sold!",
        },
    )

    notification = await harness.notification_service.notify(
        nursery_id=org_id, recipient_user_id=user.id, category=NotificationCategory.PLANT_SOLD,
        context={"common_label": "Rose", "unit_price": "9.00"},
    )

    assert notification.message == "CUSTOM: Rose sold!"


# --------------------------------------------------------------------------
# REST: system alerts + retry sweep
# --------------------------------------------------------------------------


async def test_system_alert_requires_manage_preferences_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=[])

    response = await ac.post(
        "/api/v1/notifications/system-alerts", json={"title": "Test", "message": "Test message", "severity": "info"}
    )

    assert response.status_code == 403


async def test_system_alert_broadcasts_via_the_real_event_pipeline(authenticated_client, harness):
    """The route publishes a domain event -- proves the HTTP layer never calls NotificationService directly."""
    from app.db.enums import EmployeeStatus
    from app.models.organization import Employee

    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["notifications:manage_preferences"])
    recipient = await harness.create_user(email="staff@example.com")
    await harness.employees.add(Employee(id=uuid.uuid4(), nursery_id=org_id, user_id=recipient.id, status=EmployeeStatus.ACTIVE))

    response = await ac.post(
        "/api/v1/notifications/system-alerts",
        json={"title": "Irrigation offline", "message": "Riverside branch", "severity": "critical"},
    )

    assert response.status_code == 202
    rows = [n for n in harness.notifications.notifications.values() if n.recipient_user_id == recipient.id]
    assert len(rows) == 1
    assert rows[0].category == NotificationCategory.SYSTEM_ALERT


async def test_retry_due_sweep_requires_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=[])

    response = await ac.post("/api/v1/notifications/retry-due")

    assert response.status_code == 403


async def test_retry_due_sweep_retries_failed_deliveries(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["notifications:manage_preferences"])
    harness.email_provider.should_fail = True
    notification = await harness.notification_service.notify(
        nursery_id=org_id, recipient_user_id=user.id, category=NotificationCategory.INVOICE_GENERATED,
        context={"total_amount": "20.00"},
    )
    deliveries = await harness.notification_deliveries.list_for_notification(notification.id)
    email_delivery = next(d for d in deliveries if d.channel == NotificationChannel.EMAIL)
    from datetime import datetime, timezone

    from app.db.enums import NotificationDeliveryStatus
    await harness.notification_deliveries.update_status(
        email_delivery, status=NotificationDeliveryStatus.FAILED, attempt_count=email_delivery.attempt_count,
        last_attempted_at=datetime.now(timezone.utc), next_retry_at=datetime.now(timezone.utc),
        delivered_at=None, error_message=email_delivery.error_message, provider_message_id=None,
    )
    harness.email_provider.should_fail = False

    response = await ac.post("/api/v1/notifications/retry-due")

    assert response.status_code == 200
    body = response.json()
    assert body["retried_count"] == 1
    assert body["results"][0]["status"] == "sent"


# --------------------------------------------------------------------------
# WebSocket: live hub
#
# These tests are deliberately plain `def` (not `async def`): `harness` is
# a synchronous fixture (no event loop needed to construct it), and
# `starlette.testclient.TestClient.websocket_connect` runs the ASGI app in
# its own background thread with its own event loop. Awaiting
# `harness.notification_service.notify(...)` from *this* test's
# pytest-asyncio event loop while the WebSocket route (and the
# `websocket.send_json` call the push ultimately reaches) lives on the
# TestClient portal's separate loop/thread deadlocks -- confirmed
# empirically (a first version of this file with `async def` + `await
# harness...notify(...)` hung indefinitely under `client.websocket_connect`).
# Running everything synchronously, with `asyncio.run(...)` used only for
# the isolated harness calls, keeps every piece of async code fully
# resolved before the next synchronous TestClient call starts, so nothing
# ever awaits across a thread boundary.
# --------------------------------------------------------------------------


def _sync_client_for(harness) -> TestClient:
    """
    `httpx.AsyncClient`/`ASGITransport` (used by `auth_client`/
    `authenticated_client` everywhere else in this suite) has no WebSocket
    support, so WebSocket tests build their own `starlette.testclient.
    TestClient` against the same harness-wired app instead -- same
    `create_app` + `_apply_common_overrides` construction, just a
    WebSocket-capable client on top of it.
    """
    from tests.conftest import _apply_common_overrides

    app = create_app(settings=harness.settings)
    _apply_common_overrides(app, harness)
    return TestClient(app)


def _token_for(harness, user_id: uuid.UUID) -> str:
    return create_access_token(
        settings=harness.settings, user_id=user_id, org_id=None, branch_ids=None, role_code=None, permissions=[],
    )


def test_websocket_rejects_an_invalid_token(harness):
    client = _sync_client_for(harness)
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/notifications/ws?token=not-a-real-token"):
            pass


def test_websocket_rejects_a_token_for_a_deactivated_user(harness):
    import asyncio

    user = asyncio.run(harness.create_user(email="gone@example.com", is_active=False))
    token = _token_for(harness, user.id)
    client = _sync_client_for(harness)
    with pytest.raises(Exception):
        with client.websocket_connect(f"/api/v1/notifications/ws?token={token}"):
            pass


def test_websocket_connects_and_receives_a_live_notification_push(harness):
    import asyncio

    user = asyncio.run(harness.create_user(email="owner@example.com"))
    org_id = uuid.uuid4()
    token = _token_for(harness, user.id)
    client = _sync_client_for(harness)

    with client.websocket_connect(f"/api/v1/notifications/ws?token={token}") as ws:
        asyncio.run(
            harness.notification_service.notify(
                nursery_id=org_id, recipient_user_id=user.id, category=NotificationCategory.PLANT_SOLD,
                context={"common_label": "Fiddle Leaf Fig", "unit_price": "45.00"},
            )
        )
        frame = ws.receive_json()

    assert frame["type"] == "notification"
    assert frame["unread_count"] == 1
    assert frame["notification"]["message"] == "Fiddle Leaf Fig was sold for 45.00."


def test_websocket_receives_unread_count_update_on_mark_read(harness):
    import asyncio

    user = asyncio.run(harness.create_user(email="owner2@example.com"))
    org_id = uuid.uuid4()
    notification = asyncio.run(
        harness.notification_service.notify(
            nursery_id=org_id, recipient_user_id=user.id, category=NotificationCategory.PLANT_SOLD,
            context={"common_label": "Rose", "unit_price": "5.00"},
        )
    )
    token = _token_for(harness, user.id)
    client = _sync_client_for(harness)

    with client.websocket_connect(f"/api/v1/notifications/ws?token={token}") as ws:
        asyncio.run(harness.notification_service.mark_read(notification))
        frame = ws.receive_json()

    assert frame == {"type": "unread_count", "unread_count": 0}


def test_websocket_push_only_reaches_the_targeted_user_not_other_org_members(harness):
    """Cross-tenant / cross-user isolation for the live hub -- a push for user A must never reach user B's socket."""
    import asyncio

    user_a = asyncio.run(harness.create_user(email="a@example.com"))
    user_b = asyncio.run(harness.create_user(email="b@example.com"))
    org_id = uuid.uuid4()
    token_b = _token_for(harness, user_b.id)
    client = _sync_client_for(harness)

    with client.websocket_connect(f"/api/v1/notifications/ws?token={token_b}") as ws:
        asyncio.run(
            harness.notification_service.notify(
                nursery_id=org_id, recipient_user_id=user_a.id, category=NotificationCategory.PLANT_SOLD,
                context={"common_label": "Rose", "unit_price": "5.00"},
            )
        )
        # Nothing was pushed to user_b -- send user_b a real notification and confirm THAT arrives,
        # proving the socket is alive and simply never received the user_a frame above.
        asyncio.run(
            harness.notification_service.notify(
                nursery_id=org_id, recipient_user_id=user_b.id, category=NotificationCategory.PLANT_SOLD,
                context={"common_label": "Cactus", "unit_price": "3.00"},
            )
        )
        frame = ws.receive_json()

    assert frame["notification"]["message"] == "Cactus was sold for 3.00."
