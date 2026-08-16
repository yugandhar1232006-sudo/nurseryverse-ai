"""
Unit tests for `NotificationService` -- the only code path that creates a
`Notification` row: in-app-first creation, unread count, read/unread
state, notification history, live WebSocket push, and preference-gated
fan-out to other channels.
"""
from __future__ import annotations

import uuid

import pytest

from app.db.enums import NotificationCategory, NotificationChannel, NotificationDeliveryStatus
from app.models.identity import User
from app.core.security import hash_password

pytestmark = pytest.mark.unit


class _FakeWebSocket:
    def __init__(self) -> None:
        self.frames: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.frames.append(payload)


async def _seed_user(harness, *, email: str = "grower@example.com") -> User:
    user = User(
        id=uuid.uuid4(), email=email, password_hash=hash_password("Correct-Horse12"), full_name="Test User",
        is_active=True,
    )
    return await harness.users.add(user)


async def test_notify_creates_in_app_notification_and_delivery(harness):
    user = await _seed_user(harness)
    org_id = uuid.uuid4()

    notification = await harness.notification_service.notify(
        nursery_id=org_id, recipient_user_id=user.id, category=NotificationCategory.PLANT_SOLD,
        context={"common_label": "Fiddle Leaf Fig", "unit_price": "45.00"},
    )

    assert notification.message == "Fiddle Leaf Fig was sold for 45.00."
    assert notification.read_at is None
    stored = await harness.notifications.get_by_id(notification.id)
    assert stored is not None

    deliveries = await harness.notification_deliveries.list_for_notification(notification.id)
    in_app = [d for d in deliveries if d.channel == NotificationChannel.IN_APP]
    assert len(in_app) == 1
    assert in_app[0].status == NotificationDeliveryStatus.SENT


async def test_notify_pushes_live_frame_to_connected_websocket(harness):
    user = await _seed_user(harness)
    org_id = uuid.uuid4()
    socket = _FakeWebSocket()
    await harness.notification_hub.connect(user.id, socket)

    await harness.notification_service.notify(
        nursery_id=org_id, recipient_user_id=user.id, category=NotificationCategory.PLANT_SOLD,
        context={"common_label": "Rose", "unit_price": "10.00"},
    )

    assert len(socket.frames) == 1
    assert socket.frames[0]["type"] == "notification"
    assert socket.frames[0]["unread_count"] == 1
    assert socket.frames[0]["notification"]["message"] == "Rose was sold for 10.00."


async def test_unread_count_and_list_notifications(harness):
    user = await _seed_user(harness)
    org_id = uuid.uuid4()
    for i in range(3):
        await harness.notification_service.notify(
            nursery_id=org_id, recipient_user_id=user.id, category=NotificationCategory.PLANT_SOLD,
            context={"common_label": f"Plant {i}", "unit_price": "5.00"},
        )
    assert await harness.notification_service.unread_count(user.id, org_id) == 3

    rows, total = await harness.notification_service.list_notifications(user_id=user.id, nursery_id=org_id)
    assert total == 3
    assert len(rows) == 3
    # newest first
    assert rows[0].created_at >= rows[-1].created_at


async def test_mark_read_decrements_unread_count_and_pushes_update(harness):
    user = await _seed_user(harness)
    org_id = uuid.uuid4()
    socket = _FakeWebSocket()
    notification = await harness.notification_service.notify(
        nursery_id=org_id, recipient_user_id=user.id, category=NotificationCategory.PLANT_SOLD,
        context={"common_label": "Rose", "unit_price": "10.00"},
    )
    await harness.notification_hub.connect(user.id, socket)

    await harness.notification_service.mark_read(notification)

    assert notification.read_at is not None
    assert await harness.notification_service.unread_count(user.id, org_id) == 0
    assert socket.frames[-1] == {"type": "unread_count", "unread_count": 0}


async def test_mark_all_read(harness):
    user = await _seed_user(harness)
    org_id = uuid.uuid4()
    for i in range(4):
        await harness.notification_service.notify(
            nursery_id=org_id, recipient_user_id=user.id, category=NotificationCategory.PLANT_SOLD,
            context={"common_label": f"Plant {i}", "unit_price": "5.00"},
        )
    count = await harness.notification_service.mark_all_read(user.id, org_id)
    assert count == 4
    assert await harness.notification_service.unread_count(user.id, org_id) == 0


async def test_unread_only_filter(harness):
    user = await _seed_user(harness)
    org_id = uuid.uuid4()
    first = await harness.notification_service.notify(
        nursery_id=org_id, recipient_user_id=user.id, category=NotificationCategory.PLANT_SOLD,
        context={"common_label": "A", "unit_price": "1.00"},
    )
    await harness.notification_service.notify(
        nursery_id=org_id, recipient_user_id=user.id, category=NotificationCategory.PLANT_SOLD,
        context={"common_label": "B", "unit_price": "2.00"},
    )
    await harness.notification_service.mark_read(first)

    rows, total = await harness.notification_service.list_notifications(
        user_id=user.id, nursery_id=org_id, unread_only=True
    )
    assert total == 1
    assert rows[0].message == "B was sold for 2.00."


async def test_disabled_email_preference_prevents_email_delivery_but_not_in_app(harness):
    user = await _seed_user(harness)
    org_id = uuid.uuid4()
    await harness.notification_preferences.upsert(
        user_id=user.id, category=NotificationCategory.INVOICE_GENERATED, channel=NotificationChannel.EMAIL,
        enabled=False,
    )
    notification = await harness.notification_service.notify(
        nursery_id=org_id, recipient_user_id=user.id, category=NotificationCategory.INVOICE_GENERATED,
        context={"total_amount": "199.99"},
    )
    deliveries = await harness.notification_deliveries.list_for_notification(notification.id)
    channels = {d.channel for d in deliveries}
    assert NotificationChannel.IN_APP in channels
    assert NotificationChannel.EMAIL not in channels
    assert harness.email_provider.sent == []


async def test_enabled_email_preference_sends_through_the_email_provider(harness):
    user = await _seed_user(harness, email="owner@example.com")
    org_id = uuid.uuid4()
    notification = await harness.notification_service.notify(
        nursery_id=org_id, recipient_user_id=user.id, category=NotificationCategory.INVOICE_GENERATED,
        context={"total_amount": "199.99"},
    )
    deliveries = await harness.notification_deliveries.list_for_notification(notification.id)
    email_deliveries = [d for d in deliveries if d.channel == NotificationChannel.EMAIL]
    assert len(email_deliveries) == 1
    assert email_deliveries[0].status == NotificationDeliveryStatus.SENT
    assert harness.email_provider.sent[0]["to"] == "owner@example.com"


async def test_retry_due_deliveries_resends_failed_email_using_stored_message(harness):
    user = await _seed_user(harness, email="owner@example.com")
    org_id = uuid.uuid4()
    harness.email_provider.should_fail = True
    notification = await harness.notification_service.notify(
        nursery_id=org_id, recipient_user_id=user.id, category=NotificationCategory.INVOICE_GENERATED,
        context={"total_amount": "50.00"},
    )
    deliveries = await harness.notification_deliveries.list_for_notification(notification.id)
    email_delivery = next(d for d in deliveries if d.channel == NotificationChannel.EMAIL)
    assert email_delivery.status == NotificationDeliveryStatus.FAILED

    # Force it due now (bypassing the real backoff window for test speed).
    from datetime import datetime, timezone
    await harness.notification_deliveries.update_status(
        email_delivery, status=NotificationDeliveryStatus.FAILED, attempt_count=email_delivery.attempt_count,
        last_attempted_at=datetime.now(timezone.utc), next_retry_at=datetime.now(timezone.utc),
        delivered_at=None, error_message=email_delivery.error_message, provider_message_id=None,
    )

    harness.email_provider.should_fail = False
    results = await harness.notification_service.retry_due_deliveries()

    assert len(results) == 1
    assert results[0]["status"] == NotificationDeliveryStatus.SENT
    assert email_delivery.status == NotificationDeliveryStatus.SENT
