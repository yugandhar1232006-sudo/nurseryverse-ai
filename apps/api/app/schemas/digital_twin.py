"""Pydantic response DTOs for Module 7 (Plant Digital Twin Engine). Read-only -- there is no request body schema in this file because there is no write route in this module."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DigitalTwinResponse(BaseModel):
    """"Current Digital Twin" -- the read-optimized projection, one row per plant."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plant_id: uuid.UUID
    nursery_id: uuid.UUID
    branch_id: uuid.UUID | None
    current_version: int
    lifecycle_state: str
    operational_status: str
    growth_stage: str | None
    snapshot: dict
    last_event_id: uuid.UUID | None
    last_event_type: str | None
    last_event_sequence: int | None
    last_projected_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DigitalTwinVersionResponse(BaseModel):
    """One immutable version -- backs both "Timeline" and "Version history" (see digital_twin_service.py's own note on why they share a shape)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plant_id: uuid.UUID
    version: int
    snapshot: dict
    event_id: uuid.UUID | None
    event_type: str
    event_sequence: int
    occurred_at: datetime
    created_at: datetime


class VersionComparisonResponse(BaseModel):
    """"Version comparison" -- both full snapshots plus the flat set of top-level keys that differ."""

    model_config = ConfigDict(from_attributes=True)

    plant_id: uuid.UUID
    version_a: int
    version_b: int
    snapshot_a: dict
    snapshot_b: dict
    changed_keys: list[str]


class DomainEventResponse(BaseModel):
    """"Event history" -- the raw `domain_events` rows for this plant, including full payloads (distinct from the twin-shaped `DigitalTwinVersionResponse`)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    aggregate_type: str
    aggregate_id: uuid.UUID
    nursery_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    payload: dict
    request_id: str | None
    occurred_at: datetime
    sequence: int


class ReplayConsistencyResponse(BaseModel):
    """
    Live diagnostic for the module's own "Event replay produces identical
    projections" validation requirement: independently recomputes the
    projection from the full `domain_events` history and reports whether
    it matches the currently-stored twin.
    """

    plant_id: uuid.UUID
    consistent: bool
    current_version: int
    differing_keys: list[str]
