"""Pydantic request/response DTOs for Module 9's Customer CRM."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import CommunicationChannel, CommunicationDirection, CustomerAddressType, CustomerType


class CreateCustomerRequest(BaseModel):
    branch_id: uuid.UUID
    name: str = Field(..., max_length=255)
    email: str | None = Field(None, max_length=320)
    phone: str | None = Field(None, max_length=50)
    customer_type: CustomerType = CustomerType.RETAIL


class UpdateCustomerRequest(BaseModel):
    name: str | None = Field(None, max_length=255)
    email: str | None = Field(None, max_length=320)
    phone: str | None = Field(None, max_length=50)
    customer_type: CustomerType | None = None


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID
    branch_id: uuid.UUID
    name: str
    email: str | None
    phone: str | None
    customer_type: CustomerType
    created_at: datetime
    updated_at: datetime


class CreateCustomerContactRequest(BaseModel):
    name: str = Field(..., max_length=255)
    role: str | None = Field(None, max_length=100)
    email: str | None = Field(None, max_length=320)
    phone: str | None = Field(None, max_length=50)
    is_primary: bool = False


class CustomerContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    name: str
    role: str | None
    email: str | None
    phone: str | None
    is_primary: bool
    created_at: datetime


class CreateCustomerAddressRequest(BaseModel):
    address_type: CustomerAddressType = CustomerAddressType.OTHER
    line1: str = Field(..., max_length=255)
    line2: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    postal_code: str | None = Field(None, max_length=20)
    country: str | None = Field(None, max_length=100)
    is_default: bool = False


class CustomerAddressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    address_type: CustomerAddressType
    line1: str
    line2: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    country: str | None
    is_default: bool
    created_at: datetime


class AddCustomerTagRequest(BaseModel):
    tag: str = Field(..., max_length=50)


class CustomerTagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    tag: str


class CreateCustomerNoteRequest(BaseModel):
    note: str = Field(..., max_length=5000)
    pinned: bool = False


class CustomerNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    author_user_id: uuid.UUID
    note: str
    pinned: bool
    created_at: datetime


class LogCommunicationRequest(BaseModel):
    channel: CommunicationChannel
    direction: CommunicationDirection = CommunicationDirection.OUTBOUND
    subject: str | None = Field(None, max_length=255)
    notes: str | None = Field(None, max_length=5000)


class CustomerCommunicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    channel: CommunicationChannel
    direction: CommunicationDirection
    subject: str | None
    notes: str | None
    logged_by_user_id: uuid.UUID
    occurred_at: datetime


class CustomerAnalyticsResponse(BaseModel):
    customer_id: uuid.UUID
    total_orders: int
    total_spent: float
    average_order_value: float
    last_purchase_at: datetime | None


class CustomerReportRow(BaseModel):
    customer_id: uuid.UUID
    name: str
    total_orders: int
    total_spent: float
    average_order_value: float
    last_purchase_at: datetime | None
