"""Pydantic request/response DTOs for Module 2 (Authentication)."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

_PASSWORD_MIN_LENGTH = 12


def _validate_password_strength(value: str) -> str:
    if len(value) < _PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {_PASSWORD_MIN_LENGTH} characters long.")
    if not any(c.isupper() for c in value):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not any(c.islower() for c in value):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not any(c.isdigit() for c in value):
        raise ValueError("Password must contain at least one digit.")
    return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=255)
    device_name: str | None = Field(None, max_length=255)


class SignupRequest(BaseModel):
    """
    Creates a `User` identity only -- see `AuthService.signup`'s
    docstring for why organization creation is a separate, subsequent
    call (`POST /orgs`, Module 4) rather than bundled into this one.
    """

    email: EmailStr
    password: str = Field(..., min_length=1, max_length=255)
    full_name: str = Field(..., min_length=1, max_length=255)
    device_name: str | None = Field(None, max_length=255)

    _validate_password = field_validator("password")(_validate_password_strength)


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    # Optional: in cookie mode (Settings.AUTH_USE_REFRESH_COOKIE) the
    # refresh token comes from the httpOnly cookie instead, and the
    # request body may be omitted entirely -- see app/api/routes/auth.py.
    refresh_token: str | None = None


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    _validate_new_password = field_validator("new_password")(_validate_password_strength)


class PasswordResetRequestRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str

    _validate_new_password = field_validator("new_password")(_validate_password_strength)


class EmailVerificationConfirmRequest(BaseModel):
    token: str


class AcceptInviteRequest(BaseModel):
    """
    Consumes an Invite (already-existing `invites` table, Phase 5) to set
    the invited user's initial password. Full account provisioning
    (creating the Employee + RoleAssignment rows) is Module 5's (User
    Management) responsibility — this endpoint only covers the
    authentication half: proving the invite token is valid and setting a
    password satisfying this module's strength policy.
    """

    token: str
    password: str

    _validate_password = field_validator("password")(_validate_password_strength)


class SessionResponse(BaseModel):
    id: uuid.UUID
    device_name: str | None
    ip_address: str | None
    issued_at: datetime
    last_used_at: datetime | None
    expires_at: datetime
    is_current: bool = False


class MeResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_email_verified: bool
    org_id: uuid.UUID | None
    role: str | None
    permissions: list[str]


class MessageResponse(BaseModel):
    message: str
