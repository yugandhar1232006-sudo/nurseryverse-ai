"""
Response DTOs for Module 3's `GET /api/v1/audit-log` — the worked example
the module's requirements point to: a real, useful endpoint protected by
the full authorization stack (permission check via `audit:read`, tenant
isolation via `get_scoped_db`'s RLS wiring, and response pagination via
`app.core.responses.Page`), rather than only a synthetic test route.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nursery_id: uuid.UUID
    actor_user_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    diff: dict | None
    request_id: str | None
    created_at: datetime
