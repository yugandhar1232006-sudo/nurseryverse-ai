"""Pydantic request/response DTOs for Module 4's Organization Management."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CreateNurseryRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    contact_email: EmailStr
    contact_phone: str | None = Field(None, max_length=50)
    logo_url: str | None = Field(None, max_length=500)


class UpdateNurseryRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(None, max_length=50)
    logo_url: str | None = Field(None, max_length=500)


class NurseryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    contact_email: str
    contact_phone: str | None
    logo_url: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class UpdateOrgSettingsRequest(BaseModel):
    currency: str | None = Field(None, min_length=3, max_length=3, description="ISO 4217, e.g. 'INR'")
    timezone: str | None = Field(None, description="IANA timezone name, e.g. 'America/New_York'")
    branding_primary_color: str | None = Field(None, description="Hex color, e.g. '#2E7D32'")
    email_sender_identity: str | None = Field(None, max_length=255)
    sms_enabled: bool | None = None


class OrgSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID
    default_currency: str
    default_timezone: str
    branding_primary_color: str | None
    email_sender_identity: str | None
    sms_enabled: bool
