"""Pydantic request/response DTOs for Phase 6 Module 13 (Administration & System Management)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ======================================================================
# Section 1: Role & Permission Administration
# ======================================================================


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID | None
    code: str
    name: str
    is_system_role: bool


class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    module: str
    action: str
    description: str


class RolePermissionEntry(BaseModel):
    permission_code: str
    scope: str


class EffectivePermissionsResponse(BaseModel):
    org_id: uuid.UUID | None
    role_code: str | None
    branch_ids: list[uuid.UUID]
    is_org_wide: bool
    permissions: list[str]


class ChangeUserRoleRequest(BaseModel):
    new_role_code: str = Field(..., min_length=1, max_length=50)


# ======================================================================
# Section 2: User Administration
# ======================================================================


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    is_email_verified: bool
    locked_until: datetime | None
    failed_login_attempts: int
    last_login_at: datetime | None
    employee_status: str
    department: str | None
    position: str | None


class LockAccountRequest(BaseModel):
    duration_minutes: int = Field(15, ge=1, le=10080, description="1 minute to 7 days")


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_name: str | None
    user_agent: str | None
    ip_address: str | None
    issued_at: datetime
    expires_at: datetime
    last_used_at: datetime | None


# ======================================================================
# Section 6: System Configuration
# ======================================================================


class SystemConfigResponse(BaseModel):
    id: uuid.UUID
    key: str
    value: Any
    value_type: str
    category: str
    description: str | None
    updated_by_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, config) -> "SystemConfigResponse":
        return cls(
            id=config.id,
            key=config.key,
            value=(config.value or {}).get("value"),
            value_type=config.value_type,
            category=config.category,
            description=config.description,
            updated_by_user_id=config.updated_by_user_id,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )


class SetSystemConfigRequest(BaseModel):
    value: Any
    value_type: str = Field(..., pattern="^(bool|int|str|json)$")
    category: str = Field(..., pattern="^(application|feature|notification|ai|report)$")
    description: str | None = Field(None, max_length=500)


# ======================================================================
# Section 7: Feature Flags
# ======================================================================


class FeatureFlagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    nursery_id: uuid.UUID | None
    branch_id: uuid.UUID | None
    is_enabled: bool
    description: str | None
    updated_by_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class SetFeatureFlagRequest(BaseModel):
    is_enabled: bool
    description: str | None = Field(None, max_length=500)
    branch_id: uuid.UUID | None = None


# ======================================================================
# Section 8: Audit & Security Administration
# ======================================================================


class AdminAuditLogEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID
    branch_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    diff: dict | None
    result: str
    request_id: str | None
    created_at: datetime


class SecurityEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    email: str | None
    event_type: str
    ip_address: str | None
    event_metadata: dict | None
    created_at: datetime


class AuthorizationDenialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    permission_code: str
    resource_type: str | None
    resource_id: uuid.UUID | None
    nursery_id: uuid.UUID | None
    branch_id: uuid.UUID | None
    reason: str
    explanation: str
    request_id: str | None
    created_at: datetime


# ======================================================================
# Section 9: System Health
# ======================================================================


class HealthReportResponse(BaseModel):
    api: str
    database_reachable: bool
    cache_reachable: bool
    cache_backend: str
    storage_configured: bool
    ai_anthropic_configured: bool
    ai_model_artifacts_configured: bool
    notifications_email_configured: bool
    notifications_sms_configured: bool
    notifications_push_configured: bool
    background_processing_configured: bool


# ======================================================================
# Section 10: AI Administration
# ======================================================================


class AIModelStatusResponse(BaseModel):
    capability: str
    configured: bool


class AIUsageStatsResponse(BaseModel):
    prediction_type: str
    count: int
    avg_latency_ms: float | None
    avg_confidence: float | None

    @field_validator("prediction_type", mode="before")
    @classmethod
    def _coerce_enum(cls, value: Any) -> str:
        return value.value if hasattr(value, "value") else value


class AIInferenceFailureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID
    branch_id: uuid.UUID | None
    capability: str
    prediction_type: str
    error_type: str
    error_message: str
    latency_ms: int | None
    created_at: datetime


class KnowledgeBaseStatusResponse(BaseModel):
    source_type: str
    count: int


# ======================================================================
# Section 11: Data Management
# ======================================================================


class DataRetentionSummaryResponse(BaseModel):
    cutoff: str
    audit_logs_older_than_cutoff: int
    ai_inference_failures_older_than_cutoff: int
    ai_predictions_older_than_cutoff: int | None
    note: str
