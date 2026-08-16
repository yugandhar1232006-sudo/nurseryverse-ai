"""
Unit tests for Module 9's `PassportService`/`QRService` -- Plant
Passport generation, versioning, the signed public token (round-trip,
tamper detection, wrong-secret rejection, expiry enforcement -- the
module's own "Public Token Security" requirement), and QR Intelligence's
combined frozen-snapshot + live-data scan response. Also verifies the
public response schemas never leak internal ids -- see
app/schemas/passport.py's own docstring.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.exceptions import NotFoundError
from app.models.catalog import Species
from app.models.organization import Branch
from app.schemas.passport import public_passport_response
from app.services.passport_service import PassportService

pytestmark = pytest.mark.unit


def _branch(*, nursery_id: uuid.UUID) -> Branch:
    now = datetime.now(timezone.utc)
    return Branch(
        id=uuid.uuid4(), nursery_id=nursery_id, name="Main", address_line1="123 St", city="Springfield",
        country="US", timezone="UTC", created_at=now, updated_at=now,
    )


def _species(*, nursery_id: uuid.UUID) -> Species:
    now = datetime.now(timezone.utc)
    return Species(
        id=uuid.uuid4(), nursery_id=nursery_id, category_id=uuid.uuid4(), common_name="Fig", botanical_name="Ficus lyrata",
        created_at=now, updated_at=now,
    )


async def _register_plant(harness):
    org_id = uuid.uuid4()
    branch = _branch(nursery_id=org_id)
    species = _species(nursery_id=org_id)
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    return org_id, plant


# ------------------------------------------------------------------
# Passport generation / versioning
# ------------------------------------------------------------------


async def test_generate_passport_creates_version_one(harness):
    _, plant = await _register_plant(harness)
    passport = await harness.passport_service.generate_passport(plant, actor_user_id=uuid.uuid4())
    assert passport.version == 1
    assert passport.plant_id == plant.id
    assert passport.public_token
    assert passport.content_snapshot["plant_origin"]["species"] == "Fig"
    assert passport.content_snapshot["ai_care_recommendations"] == []  # Module 10 not landed yet -- disclosed


async def test_generate_passport_is_append_only_versioned(harness):
    _, plant = await _register_plant(harness)
    v1 = await harness.passport_service.generate_passport(plant, actor_user_id=uuid.uuid4())
    v2 = await harness.passport_service.generate_passport(plant, actor_user_id=uuid.uuid4())

    assert v1.id != v2.id
    assert v2.version == 2
    versions = await harness.passport_service.list_for_plant(plant.id)
    assert [v.version for v in versions] == [2, 1]  # newest first
    latest = await harness.passports.get_latest_for_plant(plant.id)
    assert latest.id == v2.id


# ------------------------------------------------------------------
# Public token security: round-trip, tamper, wrong-secret, expiry
# ------------------------------------------------------------------


async def test_token_round_trip_resolves_the_same_passport(harness):
    _, plant = await _register_plant(harness)
    passport = await harness.passport_service.generate_passport(plant, actor_user_id=uuid.uuid4())

    resolved = await harness.passport_service.get_passport_by_token(passport.public_token)
    assert resolved.id == passport.id


async def test_forged_token_is_rejected(harness):
    _, plant = await _register_plant(harness)
    passport = await harness.passport_service.generate_passport(plant, actor_user_id=uuid.uuid4())

    forged = passport.public_token[:-4] + ("aaaa" if not passport.public_token.endswith("aaaa") else "bbbb")
    with pytest.raises(NotFoundError):
        await harness.passport_service.get_passport_by_token(forged)


async def test_tampered_middle_byte_is_rejected(harness):
    _, plant = await _register_plant(harness)
    passport = await harness.passport_service.generate_passport(plant, actor_user_id=uuid.uuid4())
    token = passport.public_token
    mid = len(token) // 2
    swapped_char = "x" if token[mid] != "x" else "y"
    tampered = token[:mid] + swapped_char + token[mid + 1 :]

    with pytest.raises(NotFoundError):
        await harness.passport_service.get_passport_by_token(tampered)


async def test_nonexistent_token_is_rejected(harness):
    with pytest.raises(NotFoundError):
        await harness.passport_service.get_passport_by_token("not-a-real-token-at-all")


async def test_token_signed_with_a_different_secret_is_rejected(harness):
    """A token minted by a *different* PassportService instance (different signing secret) must never verify -- proves the signature, not just DB presence, is what's checked."""
    _, plant = await _register_plant(harness)
    passport = await harness.passport_service.generate_passport(plant, actor_user_id=uuid.uuid4())

    other_service = PassportService(
        passport_repo=harness.passports, plant_repo=harness.plants, species_repo=harness.species,
        variety_repo=harness.plant_varieties, nursery_repo=harness.nurseries, branch_repo=harness.branches,
        growth_repo=harness.growth_timeline, health_repo=harness.health_history, audit_repo=harness.audit_logs,
        event_publisher=harness.passport_service._events, token_secret=b"a-completely-different-secret-32b",
    )
    with pytest.raises(NotFoundError):
        await other_service.get_passport_by_token(passport.public_token)


async def test_expired_token_is_rejected(harness):
    _, plant = await _register_plant(harness)
    expired_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    passport = await harness.passport_service.generate_passport(
        plant, actor_user_id=uuid.uuid4(), expires_at=expired_at
    )
    with pytest.raises(NotFoundError):
        await harness.passport_service.get_passport_by_token(passport.public_token)


async def test_unexpired_token_with_expiry_configured_still_works(harness):
    _, plant = await _register_plant(harness)
    future = datetime.now(timezone.utc) + timedelta(days=30)
    passport = await harness.passport_service.generate_passport(
        plant, actor_user_id=uuid.uuid4(), expires_at=future
    )
    resolved = await harness.passport_service.get_passport_by_token(passport.public_token)
    assert resolved.id == passport.id


# ------------------------------------------------------------------
# Public response scrubbing -- "never expose internal IDs"/"never reveal tenant information"
# ------------------------------------------------------------------


async def test_public_passport_response_never_leaks_internal_ids(harness):
    _, plant = await _register_plant(harness)
    passport = await harness.passport_service.generate_passport(plant, actor_user_id=uuid.uuid4())

    response = public_passport_response(passport)
    dumped = response.model_dump()

    assert "id" not in dumped
    assert "plant_id" not in dumped
    assert "nursery_id" not in dumped
    assert "branch_id" not in dumped
    # passport_number is a one-way digest, not a truncation of the raw UUID's own characters.
    raw_uuid_fragment = str(passport.id).split("-")[0]
    assert raw_uuid_fragment not in dumped["passport_number"]


# ------------------------------------------------------------------
# QR Intelligence -- combined frozen snapshot + live care data
# ------------------------------------------------------------------


async def test_qr_scan_returns_required_sections_and_records_a_scan_event(harness):
    _, plant = await _register_plant(harness)
    passport = await harness.passport_service.generate_passport(plant, actor_user_id=uuid.uuid4())

    result = await harness.qr_service.scan(passport.public_token, user_agent="pytest", referrer=None)

    for key in (
        "passport", "care_instructions", "water_schedule", "fertilizer_schedule",
        "health_status", "growth_timeline", "ai_recommendations",
    ):
        assert key in result

    count = await harness.qr_scan_events.count_for_passport(passport.id)
    assert count == 1


async def test_qr_scan_reflects_live_health_data_not_just_the_frozen_snapshot(harness):
    """The care-actionable fields (health/growth) are LIVE-queried at scan time, not from `content_snapshot` -- a deliberate asymmetry (see QRService's own docstring)."""
    org_id, plant = await _register_plant(harness)
    passport = await harness.passport_service.generate_passport(plant, actor_user_id=uuid.uuid4())

    await harness.health_service.record_health(
        plant_id=plant.id, actor_user_id=uuid.uuid4(), status_label="thriving", health_score=95,
    )

    result = await harness.qr_service.scan(passport.public_token)
    assert result["health_status"]["status_label"] == "thriving"


async def test_qr_scan_with_invalid_token_raises_not_found(harness):
    with pytest.raises(NotFoundError):
        await harness.qr_service.scan("bogus-token")
