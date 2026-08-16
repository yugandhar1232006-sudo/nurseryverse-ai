"""Pydantic request/response DTOs for Module 4's Branch Management."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class OperatingHoursWindow(BaseModel):
    open: str = Field(..., pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    close: str = Field(..., pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class CreateBranchRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    address_line1: str = Field(..., min_length=1, max_length=255)
    address_line2: str | None = Field(None, max_length=255)
    city: str = Field(..., min_length=1, max_length=120)
    region: str | None = Field(None, max_length=120)
    postal_code: str | None = Field(None, max_length=20)
    country: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2")
    timezone: str = Field(..., description="IANA timezone name")
    phone: str | None = Field(None, max_length=50)
    email: EmailStr | None = None
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    operating_hours: dict[str, OperatingHoursWindow | None] | None = None


class UpdateBranchRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    address_line1: str | None = Field(None, min_length=1, max_length=255)
    address_line2: str | None = Field(None, max_length=255)
    city: str | None = Field(None, min_length=1, max_length=120)
    region: str | None = Field(None, max_length=120)
    postal_code: str | None = Field(None, max_length=20)
    country: str | None = Field(None, min_length=2, max_length=2)
    timezone: str | None = None
    phone: str | None = Field(None, max_length=50)
    email: EmailStr | None = None
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    operating_hours: dict[str, OperatingHoursWindow | None] | None = None


class BranchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID
    name: str
    address_line1: str
    address_line2: str | None
    city: str
    region: str | None
    postal_code: str | None
    country: str
    timezone: str
    status: str
    phone: str | None
    email: str | None
    latitude: float | None
    longitude: float | None
    operating_hours: dict | None
    created_at: datetime
    updated_at: datetime
