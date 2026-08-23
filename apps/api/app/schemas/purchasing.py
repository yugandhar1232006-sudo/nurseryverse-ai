"""Suppliers & Purchasing schemas. Phase 1 provides a minimal SupplierResponse
for the Plant Registration dropdown; full CRUD schemas belong to the real
Suppliers & Purchasing module."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SupplierResponse(BaseModel):
    """Minimal read-only supplier representation for dropdowns."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    nursery_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
