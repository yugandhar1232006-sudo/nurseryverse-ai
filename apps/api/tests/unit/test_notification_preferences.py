"""
Unit tests for `PreferenceService` -- channel selection defaults, event
subscriptions (`enabled=False`), quiet hours (including midnight-wrapping
windows), and frequency controls (digest suppression).
"""
from __future__ import annotations

import uuid
from datetime import datetime, time, timezone

import pytest

from app.db.enums import NotificationCategory, NotificationChannel, NotificationFrequency

pytestmark = pytest.mark.unit


async def test_defaults_when_no_preference_row_exists(harness):
    user_id = uuid.uuid4()
    decisions = await harness.preference_service.resolve_channels(
        user_id=user_id, category=NotificationCategory.PLANT_SOLD,
        candidate_channels=[NotificationChannel.EMAIL, NotificationChannel.SMS, NotificationChannel.PUSH],
    )
    by_channel = {d.channel: d for d in decisions}
    assert by_channel[NotificationChannel.EMAIL].should_send is True
    assert by_channel[NotificationChannel.SMS].should_send is False
    assert by_channel[NotificationChannel.SMS].reason == "disabled"
    assert by_channel[NotificationChannel.PUSH].should_send is False


async def test_explicit_enabled_true_overrides_sms_default(harness):
    user_id = uuid.uuid4()
    await harness.notification_preferences.upsert(
        user_id=user_id, category=NotificationCategory.DISEASE_CONFIRMED, channel=NotificationChannel.SMS,
        enabled=True,
    )
    decisions = await harness.preference_service.resolve_channels(
        user_id=user_id, category=NotificationCategory.DISEASE_CONFIRMED, candidate_channels=[NotificationChannel.SMS],
    )
    assert decisions[0].should_send is True


async def test_disabled_preference_suppresses_channel(harness):
    user_id = uuid.uuid4()
    await harness.notification_preferences.upsert(
        user_id=user_id, category=NotificationCategory.INVOICE_GENERATED, channel=NotificationChannel.EMAIL,
        enabled=False,
    )
    decisions = await harness.preference_service.resolve_channels(
        user_id=user_id, category=NotificationCategory.INVOICE_GENERATED, candidate_channels=[NotificationChannel.EMAIL],
    )
    assert decisions[0].should_send is False
    assert decisions[0].reason == "disabled"


async def test_quiet_hours_suppresses_within_window(harness):
    user_id = uuid.uuid4()
    await harness.notification_preferences.upsert(
        user_id=user_id, category=NotificationCategory.LOW_STOCK, channel=NotificationChannel.EMAIL,
        enabled=True, quiet_hours_start=time(22, 0), quiet_hours_end=time(7, 0), quiet_hours_timezone="UTC",
    )
    inside_window = datetime(2026, 1, 1, 23, 0, tzinfo=timezone.utc)  # 23:00 UTC, within 22:00->07:00
    decisions = await harness.preference_service.resolve_channels(
        user_id=user_id, category=NotificationCategory.LOW_STOCK, candidate_channels=[NotificationChannel.EMAIL],
        now=inside_window,
    )
    assert decisions[0].should_send is False
    assert decisions[0].reason == "quiet_hours"


async def test_quiet_hours_does_not_suppress_outside_window(harness):
    user_id = uuid.uuid4()
    await harness.notification_preferences.upsert(
        user_id=user_id, category=NotificationCategory.LOW_STOCK, channel=NotificationChannel.EMAIL,
        enabled=True, quiet_hours_start=time(22, 0), quiet_hours_end=time(7, 0), quiet_hours_timezone="UTC",
    )
    outside_window = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)  # noon, outside 22:00->07:00
    decisions = await harness.preference_service.resolve_channels(
        user_id=user_id, category=NotificationCategory.LOW_STOCK, candidate_channels=[NotificationChannel.EMAIL],
        now=outside_window,
    )
    assert decisions[0].should_send is True


async def test_quiet_hours_never_suppresses_in_app(harness):
    """IN_APP is a passive record, not an interruption -- never gated by quiet hours (this file's own module docstring)."""
    user_id = uuid.uuid4()
    await harness.notification_preferences.upsert(
        user_id=user_id, category=NotificationCategory.LOW_STOCK, channel=NotificationChannel.IN_APP,
        enabled=True, quiet_hours_start=time(0, 0), quiet_hours_end=time(23, 59), quiet_hours_timezone="UTC",
    )
    inside_window = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    decisions = await harness.preference_service.resolve_channels(
        user_id=user_id, category=NotificationCategory.LOW_STOCK, candidate_channels=[NotificationChannel.IN_APP],
        now=inside_window,
    )
    assert decisions[0].should_send is True


async def test_digest_frequency_suppresses_immediate_send(harness):
    user_id = uuid.uuid4()
    await harness.notification_preferences.upsert(
        user_id=user_id, category=NotificationCategory.AI_RECOMMENDATION_READY, channel=NotificationChannel.EMAIL,
        enabled=True, frequency=NotificationFrequency.DAILY_DIGEST,
    )
    decisions = await harness.preference_service.resolve_channels(
        user_id=user_id, category=NotificationCategory.AI_RECOMMENDATION_READY, candidate_channels=[NotificationChannel.EMAIL],
    )
    assert decisions[0].should_send is False
    assert decisions[0].reason == "digest_frequency"


async def test_immediate_frequency_is_not_suppressed(harness):
    user_id = uuid.uuid4()
    await harness.notification_preferences.upsert(
        user_id=user_id, category=NotificationCategory.AI_RECOMMENDATION_READY, channel=NotificationChannel.EMAIL,
        enabled=True, frequency=NotificationFrequency.IMMEDIATE,
    )
    decisions = await harness.preference_service.resolve_channels(
        user_id=user_id, category=NotificationCategory.AI_RECOMMENDATION_READY, candidate_channels=[NotificationChannel.EMAIL],
    )
    assert decisions[0].should_send is True
