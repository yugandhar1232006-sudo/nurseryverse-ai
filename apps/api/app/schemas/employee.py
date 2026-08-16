"""Pydantic request/response DTOs for Module 4's Employee Management + Organization Membership."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class InviteEmployeeRequest(BaseModel):
    email: EmailStr
    role_code: str = Field(..., min_length=1, max_length=50)
    branch_ids: list[uuid.UUID] = Field(default_factory=list)


class InviteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID
    email: str
    role_id: uuid.UUID
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID
    user_id: uuid.UUID
    status: str
    department: str | None
    position: str | None
    hired_at: date | None
    deactivated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UpdateEmployeeProfileRequest(BaseModel):
    department: str | None = Field(None, max_length=100)
    position: str | None = Field(None, max_length=100)


class TransferBranchesRequest(BaseModel):
    branch_ids: list[uuid.UUID] = Field(default_factory=list)


class RemoveEmployeeRequest(BaseModel):
    reason: str | None = Field(None, max_length=500)


class TransferOwnershipRequest(BaseModel):
    new_owner_user_id: uuid.UUID


class ReactivateEmployeeRequest(BaseModel):
    """Added by Phase 6 Module 13 (Administration & System Management) -- see `EmployeeService.reactivate_employee`'s own docstring for why a role must be supplied explicitly."""

    role_code: str = Field(..., min_length=1, max_length=50)
    branch_ids: list[uuid.UUID] = Field(default_factory=list)
