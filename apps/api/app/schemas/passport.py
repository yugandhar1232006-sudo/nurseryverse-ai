"""
Pydantic request/response DTOs for Module 9's Plant Passport & QR
Intelligence.

Two distinct response shapes, deliberately: `PassportResponse` (internal,
authenticated management view) includes `plant_id`/`generated_by_user_id`
and other internal ids an authenticated nursery staff member is entitled
to see. `PublicPassportResponse`/`QRScanResponse` (the public,
unauthenticated views) never include a database id, `nursery_id`,
`branch_id`, or `plant_id` anywhere -- only the passport's own frozen
`content_snapshot` fields and a `passport_number` (a human-friendly,
non-sequential display label, not the raw UUID), per the module's own
"never expose internal IDs" / "never reveal tenant information" security
requirement.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class GeneratePassportRequest(BaseModel):
    expires_at: datetime | None = None
    sale_id: uuid.UUID | None = None
    sale_item_id: uuid.UUID | None = None


class PassportResponse(BaseModel):
    """Internal, authenticated view -- includes ids an authorized nursery staff member is entitled to see."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plant_id: uuid.UUID
    version: int
    public_token: str
    public_url: str
    token_expires_at: datetime | None
    content_snapshot: dict[str, Any]
    generated_by_user_id: uuid.UUID
    generated_at: datetime


def passport_response(passport, *, public_url: str) -> PassportResponse:
    """
    `public_url` is not a column on `Passport` (only the raw
    `public_token` is persisted -- see app/models/reports.py) -- it is
    computed per-request from `QRService.qr_payload_url()`, so this is a
    plain constructor call rather than `PassportResponse.model_validate`
    (which would fail: `from_attributes=True` has no `public_url`
    attribute to read off the ORM row).
    """
    return PassportResponse(
        id=passport.id, plant_id=passport.plant_id, version=passport.version, public_token=passport.public_token,
        public_url=public_url, token_expires_at=passport.token_expires_at, content_snapshot=passport.content_snapshot,
        generated_by_user_id=passport.generated_by_user_id, generated_at=passport.generated_at,
    )


class PublicPassportResponse(BaseModel):
    """The public, unauthenticated view -- no database ids, no nursery/branch/plant id anywhere."""

    passport_number: str
    version: int
    content: dict[str, Any]
    generated_at: datetime


class QRScanResponse(BaseModel):
    """What scanning a QR must return, per the module's own QR Intelligence spec -- also fully scrubbed of internal ids."""

    passport: dict[str, Any]
    care_instructions: dict[str, Any] | None
    water_schedule: dict[str, Any] | None
    fertilizer_schedule: dict[str, Any] | None
    health_status: dict[str, Any] | None
    growth_timeline: list[dict[str, Any]]
    ai_recommendations: list[dict[str, Any]]


class PassportReportResponse(BaseModel):
    total_passports: int
    distinct_plants_with_passport: int
    expiring_within_30_days: int


class QRScanAnalyticsResponse(BaseModel):
    scan_count: int
    scans: list[dict[str, Any]]


def public_passport_response(passport) -> PublicPassportResponse:
    """
    `passport_number` is a one-way SHA-256 digest of the passport's own
    id, truncated to 8 hex characters -- a stable, deterministic display
    label with no reverse path back to the real UUID (unlike simply
    truncating the UUID's own characters, which would still leak a real
    fragment of an internal id). Satisfies "never expose internal IDs"
    while still giving the public certificate a human-shareable reference
    number.
    """
    digest = hashlib.sha256(str(passport.id).encode("utf-8")).hexdigest()[:8].upper()
    return PublicPassportResponse(
        passport_number=f"NVA-PP-{digest}",
        version=passport.version,
        content=passport.content_snapshot,
        generated_at=passport.generated_at,
    )
