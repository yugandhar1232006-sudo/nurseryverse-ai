"""Pydantic request/response DTOs for Phase 6 Module 11 (Notifications & Communication)."""
from __future__ import annotations

import uuid
from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import (
    NotificationCategory,
    NotificationChannel,
    NotificationFrequency,
)


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID
    recipient_user_id: uuid.UUID
    category: NotificationCategory
    message: str
    deep_link: str | None
    read_at: datetime | None
    created_at: datetime


class UnreadCountResponse(BaseModel):
    unread_count: int


class MarkAllReadResponse(BaseModel):
    marked_read_count: int


class NotificationPreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    category: NotificationCategory
    channel: NotificationChannel
    enabled: bool
    quiet_hours_start: time | None
    quiet_hours_end: time | None
    quiet_hours_timezone: str | None
    frequency: NotificationFrequency


class NotificationPreferenceUpdateRequest(BaseModel):
    """One (category, channel) preference row's desired state -- `PUT /notifications/preferences` accepts a list of these."""

    category: NotificationCategory
    channel: NotificationChannel
    enabled: bool = True
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    quiet_hours_timezone: str | None = Field(default=None, description="IANA tz name, e.g. 'America/New_York'")
    frequency: NotificationFrequency = NotificationFrequency.IMMEDIATE


class NotificationTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID | None
    category: NotificationCategory
    channel: NotificationChannel
    format: str
    locale: str
    version: int
    subject_template: str | None
    body_template: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class NotificationTemplateCreateRequest(BaseModel):
    category: NotificationCategory
    channel: NotificationChannel
    format: str = Field(default="text", pattern="^(text|html)$")
    locale: str = Field(default="en", max_length=10)
    version: int = Field(default=1, ge=1)
    subject_template: str | None = Field(default=None, max_length=500)
    body_template: str
    is_active: bool = True


class SystemAlertRequest(BaseModel):
    """Body for `POST /notifications/system-alerts` -- the on-demand trigger for the `SYSTEM_ALERT` category (no scheduler exists in this codebase; see app/domain_events/events.py's `SystemAlertRaised` docstring)."""

    title: str = Field(..., max_length=255)
    message: str = Field(..., max_length=2000)
    severity: str = Field(default="info", pattern="^(info|warning|critical)$")


class RetryDueResponse(BaseModel):
    retried_count: int
    results: list[dict]
