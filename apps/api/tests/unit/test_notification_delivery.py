"""
Retry Tests / Failure Tests / delivery-tracking unit tests for
`NotificationDeliveryService` -- this module's own "Retry policy",
"Dead-letter queue strategy", "Delivery tracking", "Failure logging",
"Delivery status" requirements.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db.enums import NotificationCategory, NotificationChannel, NotificationDeliveryStatus
from app.models.notifications import Notification
from app.notifications.delivery import RETRY_BACKOFF_SECONDS, NotificationDeliveryService
from app.notifications.templates import RenderedTemplate
from tests.fakes.notification_providers import FakeEmailProvider

pytestmark = pytest.mark.unit


async def _make_notification(harness, *, nursery_id=None, recipient_user_id=None) -> Notification:
    notification = Notification(
        nursery_id=nursery_id or uuid.uuid4(), recipient_user_id=recipient_user_id or uuid.uuid4(),
        category=NotificationCategory.PLANT_SOLD, message="Test message",
    )
    return await harness.notifications.add(notification)


async def test_successful_delivery_marks_sent_and_records_provider_message_id(harness):
    notification = await _make_notification(harness)
    delivery = await harness.notification_delivery_service.dispatch(
        notification=notification, channel=NotificationChannel.EMAIL,
        rendered=RenderedTemplate(subject="Sold!", body="Your plant sold."),
        recipient_email="owner@example.com",
    )
    assert delivery.status == NotificationDeliveryStatus.SENT
    assert delivery.attempt_count == 1
    assert delivery.delivered_at is not None
    assert delivery.provider_message_id is not None
    assert harness.email_provider.sent == [
        {"to": "owner@example.com", "subject": "Sold!", "html_body": None, "text_body": "Your plant sold."}
    ]


async def test_in_app_channel_is_always_sent_without_touching_a_provider(harness):
    notification = await _make_notification(harness)
    delivery = await harness.notification_delivery_service.dispatch(
        notification=notification, channel=NotificationChannel.IN_APP,
        rendered=RenderedTemplate(subject=None, body="In-app text"),
    )
    assert delivery.status == NotificationDeliveryStatus.SENT
    assert harness.email_provider.sent == []
    assert harness.sms_provider.sent == []
    assert harness.push_provider.sent == []


async def test_missing_recipient_contact_fails_without_calling_provider(harness):
    notification = await _make_notification(harness)
    delivery = await harness.notification_delivery_service.dispatch(
        notification=notification, channel=NotificationChannel.SMS,
        rendered=RenderedTemplate(subject=None, body="Text"), recipient_phone=None,
    )
    assert delivery.status == NotificationDeliveryStatus.FAILED
    assert delivery.error_message == "No recipient phone on file"
    assert harness.sms_provider.sent == []


async def test_failed_attempt_schedules_retry_with_first_backoff_interval(harness):
    failing_email = FakeEmailProvider(should_fail=True)
    service = NotificationDeliveryService(
        delivery_repo=harness.notification_deliveries, email_provider=failing_email,
        sms_provider=harness.sms_provider, push_provider=harness.push_provider,
    )
    notification = await _make_notification(harness)
    before = datetime.now(timezone.utc)
    delivery = await service.dispatch(
        notification=notification, channel=NotificationChannel.EMAIL,
        rendered=RenderedTemplate(subject="X", body="Y"), recipient_email="a@example.com",
    )
    assert delivery.status == NotificationDeliveryStatus.FAILED
    assert delivery.attempt_count == 1
    assert delivery.next_retry_at is not None
    expected_earliest = before + timedelta(seconds=RETRY_BACKOFF_SECONDS[0])
    assert delivery.next_retry_at >= expected_earliest - timedelta(seconds=1)


async def test_exhausting_max_attempts_transitions_to_dead_letter(harness):
    failing_email = FakeEmailProvider(should_fail=True)
    service = NotificationDeliveryService(
        delivery_repo=harness.notification_deliveries, email_provider=failing_email,
        sms_provider=harness.sms_provider, push_provider=harness.push_provider,
    )
    notification = await _make_notification(harness)
    delivery = await service.dispatch(
        notification=notification, channel=NotificationChannel.EMAIL,
        rendered=RenderedTemplate(subject="X", body="Y"), recipient_email="a@example.com", max_attempts=2,
    )
    assert delivery.status == NotificationDeliveryStatus.FAILED
    assert delivery.attempt_count == 1

    await service.retry_delivery(
        delivery, rendered=RenderedTemplate(subject="X", body="Y"), recipient_email="a@example.com"
    )
    assert delivery.status == NotificationDeliveryStatus.DEAD_LETTER
    assert delivery.attempt_count == 2
    assert delivery.next_retry_at is None


async def test_retry_after_provider_recovers_marks_sent(harness):
    """The classic 'fails once, retried, then succeeds' path -- proves retry logic actually re-attempts, not just re-marks."""
    flaky_email = FakeEmailProvider(should_fail=True)
    service = NotificationDeliveryService(
        delivery_repo=harness.notification_deliveries, email_provider=flaky_email,
        sms_provider=harness.sms_provider, push_provider=harness.push_provider,
    )
    notification = await _make_notification(harness)
    delivery = await service.dispatch(
        notification=notification, channel=NotificationChannel.EMAIL,
        rendered=RenderedTemplate(subject="X", body="Y"), recipient_email="a@example.com",
    )
    assert delivery.status == NotificationDeliveryStatus.FAILED

    flaky_email.should_fail = False  # the provider "recovers"
    await service.retry_delivery(
        delivery, rendered=RenderedTemplate(subject="X", body="Y"), recipient_email="a@example.com"
    )
    assert delivery.status == NotificationDeliveryStatus.SENT
    assert delivery.attempt_count == 2
    assert delivery.delivered_at is not None


async def test_list_due_for_retry_only_returns_failed_rows_past_their_backoff_window(harness):
    notification = await _make_notification(harness)
    now = datetime.now(timezone.utc)

    ready = await harness.notification_delivery_service.dispatch(
        notification=notification, channel=NotificationChannel.SMS,
        rendered=RenderedTemplate(subject=None, body="Y"), recipient_phone=None,  # forces FAILED
    )
    # Backdate its next_retry_at so it's due right now.
    await harness.notification_deliveries.update_status(
        ready, status=NotificationDeliveryStatus.FAILED, attempt_count=1,
        last_attempted_at=now, next_retry_at=now - timedelta(seconds=1),
        delivered_at=None, error_message="forced", provider_message_id=None,
    )

    not_yet_due = await harness.notification_delivery_service.dispatch(
        notification=notification, channel=NotificationChannel.PUSH,
        rendered=RenderedTemplate(subject=None, body="Y"), recipient_device_token=None,
    )
    await harness.notification_deliveries.update_status(
        not_yet_due, status=NotificationDeliveryStatus.FAILED, attempt_count=1,
        last_attempted_at=now, next_retry_at=now + timedelta(hours=1),
        delivered_at=None, error_message="forced", provider_message_id=None,
    )

    due = await harness.notification_delivery_service.list_due_for_retry(now=now)
    due_ids = {d.id for d in due}
    assert ready.id in due_ids
    assert not_yet_due.id not in due_ids


async def test_dead_letter_rows_are_excluded_from_the_retry_queue(harness):
    failing_email = FakeEmailProvider(should_fail=True)
    service = NotificationDeliveryService(
        delivery_repo=harness.notification_deliveries, email_provider=failing_email,
        sms_provider=harness.sms_provider, push_provider=harness.push_provider,
    )
    notification = await _make_notification(harness)
    delivery = await service.dispatch(
        notification=notification, channel=NotificationChannel.EMAIL,
        rendered=RenderedTemplate(subject="X", body="Y"), recipient_email="a@example.com", max_attempts=1,
    )
    assert delivery.status == NotificationDeliveryStatus.DEAD_LETTER

    due = await service.list_due_for_retry(now=datetime.now(timezone.utc) + timedelta(days=365))
    assert delivery.id not in {d.id for d in due}
