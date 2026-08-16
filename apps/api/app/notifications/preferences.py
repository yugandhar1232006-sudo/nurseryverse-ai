"""
This module's own "Implement user notification preferences: Channel
selection, Event subscriptions, Quiet hours, Frequency controls"
requirement. `PreferenceService` is the single place that answers "should
this (user, category, channel) actually be delivered right now" --
`NotificationEventHandler`/`NotificationService` call it for every
channel candidate rather than checking `NotificationPreference` rows
themselves, so the suppression rules (defaults, quiet hours, frequency)
live in exactly one place.

Default-on/off per channel when a user has no explicit
`NotificationPreference` row yet (the common case -- a fresh user has
created none): `IN_APP` and `EMAIL` default enabled (docs/ux/14-notification-workflow.md's
"In-app always-on for High severity" plus this module's own "every
Notification row is created first, regardless of preferences" rule for
the in-app channel specifically); `SMS`/`PUSH` default *disabled* -- the
same doc's "SMS gated by org+user opt-in" rule, extended to Push since no
device token exists to send to until a user has opted in via one anyway.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from app.db.enums import NotificationCategory, NotificationChannel, NotificationFrequency
from app.models.notifications import NotificationPreference
from app.repositories.interfaces import NotificationPreferenceRepository

_DEFAULT_ENABLED: dict[NotificationChannel, bool] = {
    NotificationChannel.IN_APP: True,
    NotificationChannel.EMAIL: True,
    NotificationChannel.SMS: False,
    NotificationChannel.PUSH: False,
}


@dataclass(frozen=True)
class ChannelDecision:
    channel: NotificationChannel
    should_send: bool
    reason: str | None = None  # populated only when should_send is False -- "disabled" / "quiet_hours" / "digest_frequency"


class PreferenceService:
    def __init__(self, preference_repo: NotificationPreferenceRepository) -> None:
        self._preferences = preference_repo

    async def resolve_channels(
        self,
        *,
        user_id: uuid.UUID,
        category: NotificationCategory,
        candidate_channels: list[NotificationChannel],
        now: datetime | None = None,
    ) -> list[ChannelDecision]:
        """
        One decision per candidate channel `NotificationEventHandler`
        proposed for this category. `IN_APP` is never suppressed by quiet
        hours or frequency -- it's a passive record a user reads on their
        own schedule, not an interruption -- only by an explicit
        `enabled=False` preference row.
        """
        now = now or datetime.now(timezone.utc)
        decisions: list[ChannelDecision] = []
        for channel in candidate_channels:
            pref = await self._preferences.get(user_id, category, channel)
            enabled = pref.enabled if pref is not None else _DEFAULT_ENABLED.get(channel, False)
            if not enabled:
                decisions.append(ChannelDecision(channel=channel, should_send=False, reason="disabled"))
                continue

            if channel != NotificationChannel.IN_APP and pref is not None:
                if self._in_quiet_hours(pref, now):
                    decisions.append(ChannelDecision(channel=channel, should_send=False, reason="quiet_hours"))
                    continue
                if pref.frequency != NotificationFrequency.IMMEDIATE:
                    # Digest frequencies suppress the *immediate* send;
                    # the actual digest compilation/send job has no
                    # scheduler in this codebase (no Celery worker
                    # infrastructure exists anywhere through Module 10) --
                    # see NotificationService's own module docstring.
                    decisions.append(ChannelDecision(channel=channel, should_send=False, reason="digest_frequency"))
                    continue

            decisions.append(ChannelDecision(channel=channel, should_send=True))
        return decisions

    @staticmethod
    def _in_quiet_hours(pref: NotificationPreference, now: datetime) -> bool:
        if pref.quiet_hours_start is None or pref.quiet_hours_end is None:
            return False
        tz = ZoneInfo(pref.quiet_hours_timezone) if pref.quiet_hours_timezone else timezone.utc
        local_time = now.astimezone(tz).timetz().replace(tzinfo=None)
        start: time = pref.quiet_hours_start
        end: time = pref.quiet_hours_end
        if start <= end:
            return start <= local_time < end
        # Wraps midnight, e.g. 22:00 -> 07:00.
        return local_time >= start or local_time < end
