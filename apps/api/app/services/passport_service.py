"""
Phase 6 Module 9 (Sales, CRM, Plant Passport & QR Intelligence) — Plant
Passport generation and QR Intelligence (the public, unauthenticated scan
path).

TOKEN DESIGN (the module's own SECURITY section: "cryptographically
signed", "unguessable", "support expiration if configured", "never expose
internal IDs", "never reveal tenant information"):

`Passport.public_token` is a compact, self-contained, HMAC-SHA256-signed
opaque token — NOT a JWT (a JWT's base64-encoded header/claims are
human-readable once decoded, which would leak the passport_id and any
embedded metadata to casual inspection; this token's payload is raw
bytes, opaque without the server secret) and NOT a bare random string
looked up only by database uniqueness (that satisfies "unguessable" but
not "cryptographically signed" — this module's spec asks for both).
Binary layout, base64url-encoded as one string:

    [ passport_id (16 bytes) | nonce (12 bytes) | expires_at epoch (8 bytes, 0 = never) | HMAC-SHA256 truncated to 16 bytes ]

52 raw bytes -> ~70 base64url characters, comfortably inside the existing
`public_token` column's `String(128)` (Phase 5, migration 0001 — not
altered by this module). Truncating the HMAC to 128 bits is a standard,
NIST SP 800-107-sanctioned practice for a MAC of this kind, and keeps the
token short enough to encode as a small, reliably-scannable QR code — a
practical bonus, not just a size constraint. The signature is verified
with `hmac.compare_digest` (constant-time) before the payload is ever
trusted; `get_passport_by_token` raises the same `NotFoundError` for "no
such token", "signature doesn't verify" (forged/tampered), and "token
expired" — deliberately not distinguishing which, so a public, anonymous
caller can never learn anything about *why* a guess failed (an oracle
that would otherwise slightly narrow a forgery attempt).

"Never expose internal IDs"/"never reveal tenant information": the token
payload carries only the Passport's own id (itself a random UUID, never
returned to a caller in a context that also reveals nursery_id) plus a
random nonce and an expiry timestamp — no `plant_id`, `nursery_id`, or
`branch_id` is ever encoded into the token, and the public schemas built
from a Passport response (app/schemas/passport.py) never include
`nursery_id`/`branch_id`/internal database ids of any kind, only the
frozen `content_snapshot`'s already-scrubbed fields.

QR "code" generation: per Module 6's own `QRCodeService` precedent
(app/services/qr_code_service.py) — "rendering that token into an actual
scannable PNG/SVG image is a presentation concern for Phase 7 (frontend)
... not something a backend token generator should own" — `QRService`
here generates the *payload* a frontend QR-rendering library encodes (the
public passport URL), not a raster/vector image file. No new binary
image-rendering dependency is introduced, and the precedent this module
follows was already established, not invented here.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.domain_events import DomainEventPublisher, PassportGenerated, QRGenerated
from app.models.commerce import Sale, SaleItem
from app.models.platform import AuditLog
from app.models.plants import Plant
from app.models.reports import Passport, QRScanEvent
from app.repositories.interfaces import (
    AuditLogRepository,
    BranchRepository,
    FertilizerLogRepository,
    GrowthTimelineRepository,
    HealthHistoryRepository,
    NurseryRepository,
    PassportRepository,
    PlantRepository,
    PlantVarietyRepository,
    QRScanEventRepository,
    SpeciesRepository,
)

_PAYLOAD_LEN = 36  # 16 (uuid) + 12 (nonce) + 8 (expiry epoch, big-endian uint64)
_SIG_LEN = 16
_TOKEN_RAW_LEN = _PAYLOAD_LEN + _SIG_LEN


def resolve_passport_token_secret(settings: Settings) -> bytes:
    """Same fail-fast-in-production / ephemeral-per-process-in-dev resolution as app/core/keys.py's resolve_jwt_keys."""
    if settings.PASSPORT_TOKEN_SECRET:
        return settings.PASSPORT_TOKEN_SECRET.encode("utf-8")
    if settings.is_production:
        raise RuntimeError(
            "PASSPORT_TOKEN_SECRET must be set in production — refusing to start with an "
            "ephemeral signing secret, which would invalidate every outstanding Plant Passport "
            "QR code on every process restart and cannot be trusted across multiple API instances."
        )
    return _ephemeral_dev_secret()


_dev_secret_cache: bytes | None = None


def _ephemeral_dev_secret() -> bytes:
    global _dev_secret_cache
    if _dev_secret_cache is None:
        _dev_secret_cache = secrets.token_bytes(32)
    return _dev_secret_cache


def _pack_token(passport_id: uuid.UUID, *, expires_at: datetime | None, secret: bytes) -> str:
    nonce = secrets.token_bytes(12)
    exp_epoch = int(expires_at.timestamp()) if expires_at else 0
    payload = passport_id.bytes + nonce + struct.pack(">Q", exp_epoch)
    sig = hmac.new(secret, payload, hashlib.sha256).digest()[:_SIG_LEN]
    return base64.urlsafe_b64encode(payload + sig).rstrip(b"=").decode("ascii")


def _unpack_and_verify_token(token: str, *, secret: bytes) -> uuid.UUID | None:
    try:
        padded = token + "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    except Exception:
        return None
    if len(raw) != _TOKEN_RAW_LEN:
        return None
    payload, sig = raw[:_PAYLOAD_LEN], raw[_PAYLOAD_LEN:]
    expected_sig = hmac.new(secret, payload, hashlib.sha256).digest()[:_SIG_LEN]
    if not hmac.compare_digest(sig, expected_sig):
        return None
    exp_epoch = struct.unpack(">Q", payload[28:36])[0]
    if exp_epoch != 0 and datetime.now(timezone.utc).timestamp() > exp_epoch:
        return None
    return uuid.UUID(bytes=payload[:16])


@dataclass
class PassportContent:
    """The frozen `content_snapshot` shape — see `PassportService._build_snapshot`."""

    data: dict[str, Any]


class PassportService:
    def __init__(
        self,
        *,
        passport_repo: PassportRepository,
        plant_repo: PlantRepository,
        species_repo: SpeciesRepository,
        variety_repo: PlantVarietyRepository,
        nursery_repo: NurseryRepository,
        branch_repo: BranchRepository,
        growth_repo: GrowthTimelineRepository,
        health_repo: HealthHistoryRepository,
        audit_repo: AuditLogRepository,
        event_publisher: DomainEventPublisher,
        token_secret: bytes,
    ) -> None:
        self._passports = passport_repo
        self._plants = plant_repo
        self._species = species_repo
        self._varieties = variety_repo
        self._nurseries = nursery_repo
        self._branches = branch_repo
        self._growth = growth_repo
        self._health = health_repo
        self._audit = audit_repo
        self._events = event_publisher
        self._secret = token_secret

    async def generate_passport(
        self,
        plant: Plant,
        *,
        actor_user_id: uuid.UUID,
        sale: Sale | None = None,
        sale_item: SaleItem | None = None,
        expires_at: datetime | None = None,
        request_id: str | None = None,
    ) -> Passport:
        """
        Every sold plant receives a Plant Passport. Append-only/versioned
        (Passport's own docstring) — calling this again for the same
        plant creates version N+1, never overwrites version N.
        """
        latest = await self._passports.get_latest_for_plant(plant.id)
        version = (latest.version + 1) if latest else 1

        content = await self._build_snapshot(plant, sale=sale, sale_item=sale_item)

        passport_id = uuid.uuid4()
        token = _pack_token(passport_id, expires_at=expires_at, secret=self._secret)
        passport = Passport(
            id=passport_id,
            plant_id=plant.id,
            version=version,
            public_token=token,
            token_expires_at=expires_at,
            content_snapshot=content.data,
            generated_by_user_id=actor_user_id,
        )
        await self._passports.add(passport)

        await self._audit.log(
            AuditLog(
                nursery_id=plant.nursery_id, actor_user_id=actor_user_id, action="passport.generated",
                entity_type="Passport", entity_id=passport.id, diff={"plant_id": str(plant.id), "version": version},
                request_id=request_id, created_at=datetime.now(timezone.utc),
            )
        )
        await self._events.publish(
            PassportGenerated(
                aggregate_id=plant.id, nursery_id=plant.nursery_id, actor_user_id=actor_user_id,
                passport_id=passport.id, version=version,
            ),
            request_id=request_id,
        )
        await self._events.publish(
            QRGenerated(
                aggregate_id=plant.id, nursery_id=plant.nursery_id, actor_user_id=actor_user_id,
                passport_id=passport.id,
            ),
            request_id=request_id,
        )
        return passport

    async def get_passport(self, passport_id: uuid.UUID) -> Passport:
        passport = await self._passports.get_by_id(passport_id)
        if passport is None:
            raise NotFoundError("Passport not found.")
        return passport

    async def get_passport_by_token(self, token: str) -> Passport:
        """The one lookup the public, unauthenticated QR/passport endpoints use — see module docstring for why failures are deliberately undifferentiated."""
        passport_id = _unpack_and_verify_token(token, secret=self._secret)
        if passport_id is None:
            raise NotFoundError("Invalid or expired passport token.")
        passport = await self._passports.get_by_id(passport_id)
        if passport is None:
            raise NotFoundError("Invalid or expired passport token.")
        if passport.token_expires_at is not None:
            expires = passport.token_expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires:
                raise NotFoundError("Invalid or expired passport token.")
        return passport

    async def list_for_plant(self, plant_id: uuid.UUID) -> list[Passport]:
        return await self._passports.list_for_plant(plant_id)

    async def list_for_nursery(self, nursery_id: uuid.UUID, *, offset: int, limit: int) -> tuple[list[Passport], int]:
        return await self._passports.list_for_nursery(nursery_id, offset=offset, limit=limit)

    async def passport_report(self, nursery_id: uuid.UUID) -> dict[str, Any]:
        """Passport Reports — how many plants have a passport, versions issued, expiring-soon count."""
        passports, total = await self._passports.list_for_nursery(nursery_id, offset=0, limit=10_000)
        distinct_plants = {p.plant_id for p in passports}
        now = datetime.now(timezone.utc)
        expiring_soon = 0
        for p in passports:
            if p.token_expires_at is None:
                continue
            expires = p.token_expires_at if p.token_expires_at.tzinfo else p.token_expires_at.replace(tzinfo=timezone.utc)
            if expires > now and (expires - now).days <= 30:
                expiring_soon += 1
        return {
            "total_passports": total,
            "distinct_plants_with_passport": len(distinct_plants),
            "expiring_within_30_days": expiring_soon,
        }

    async def _build_snapshot(self, plant: Plant, *, sale: Sale | None, sale_item: SaleItem | None) -> PassportContent:
        species = await self._species.get_by_id(plant.species_id)
        variety = await self._varieties.get_by_id(plant.variety_id) if plant.variety_id else None
        nursery = await self._nurseries.get_by_id(plant.nursery_id)
        branch = await self._branches.get_by_id(plant.branch_id)
        growth_rows, _ = await self._growth.list_for_plant(plant.id, offset=0, limit=10)
        health_rows, _ = await self._health.list_for_plant(plant.id, offset=0, limit=10)

        data: dict[str, Any] = {
            "plant_origin": {
                "species": species.common_name if species else None,
                "botanical_name": species.botanical_name if species else None,
                "variety": variety.name if variety else None,
                "batch_number": plant.batch_number,
                "planted_at": plant.planted_at.isoformat() if plant.planted_at else None,
                "common_label": plant.common_label,
            },
            "nursery_information": {
                "name": nursery.name if nursery else None,
                "contact_email": nursery.contact_email if nursery else None,
                "branch_name": branch.name if branch else None,
            },
            "care_guide": {
                "light_requirement": species.light_requirement if species else None,
                "water_baseline_ml_per_week": species.water_baseline_ml_per_week if species else None,
                "soil_type": species.soil_type if species else None,
                "temperature_min_celsius": _optfloat(species.temperature_min_celsius) if species else None,
                "temperature_max_celsius": _optfloat(species.temperature_max_celsius) if species else None,
            },
            "growth_timeline": [
                {
                    "height_cm": _optfloat(g.height_cm),
                    "growth_stage": g.growth_stage,
                    "recorded_at": g.recorded_at.isoformat() if g.recorded_at else None,
                }
                for g in growth_rows
            ],
            "health_timeline": [
                {
                    "status_label": h.status_label,
                    "health_score": _optfloat(h.health_score),
                    "recorded_at": h.recorded_at.isoformat() if h.recorded_at else None,
                }
                for h in health_rows
            ],
            # AI Care Recommendations: no module before Module 10 (AI
            # Platform) writes AI recommendations for a plant -- the
            # identical, already-established precedent from Module 7's
            # Digital Twin ("AI Prediction Timeline ... not populated by
            # this module") and Module 9's own domain-events docstring.
            # Left as an empty list rather than faked; correct once
            # Module 10 lands with no further change needed here.
            "ai_care_recommendations": [],
            "purchase_information": (
                {
                    "sale_id": str(sale.id),
                    "sold_at": sale.created_at.isoformat() if sale.created_at else None,
                    "unit_price": str(sale_item.unit_price) if sale_item else None,
                }
                if sale is not None
                else None
            ),
        }
        return PassportContent(data=data)


def _optfloat(value: object) -> float | None:
    return float(value) if value is not None else None  # type: ignore[arg-type]


class QRService:
    """
    QR Intelligence: the public, unauthenticated scan path. Composed with
    `PassportService` for token verification, plus the same live-data
    repositories to refresh care-actionable fields (Health Status, Growth
    Timeline, Water/Fertilizer Schedule) at scan time — the frozen
    `content_snapshot` is what a Passport certificate/origin/purchase
    record always shows (those facts are correctly frozen forever), but a
    scan is explicitly about "what does this plant need right now,"
    which should reflect the plant's *current* state, not a possibly
    months-old snapshot from generation time. This is a deliberate,
    disclosed asymmetry, not an inconsistency.
    """

    def __init__(
        self,
        *,
        passport_service: PassportService,
        scan_repo: QRScanEventRepository,
        plant_repo: PlantRepository,
        growth_repo: GrowthTimelineRepository,
        health_repo: HealthHistoryRepository,
        fertilizer_repo: FertilizerLogRepository,
        frontend_base_url: str,
        db: AsyncSession | None = None,
    ) -> None:
        self._passports = passport_service
        self._scans = scan_repo
        self._plants = plant_repo
        self._growth = growth_repo
        self._health = health_repo
        self._fertilizer = fertilizer_repo
        self._frontend_base_url = frontend_base_url.rstrip("/")
        # `db` is only used for `_scope_to_verified_plant` below -- never
        # for a query of its own (all actual reads still go through the
        # repository Protocols above, same as every other service in this
        # codebase). Optional and unused by the in-memory Fake* test
        # harness (tests/conftest.py constructs this service with no
        # `db`), which has no RLS to scope in the first place; production
        # wiring (app/api/deps.py's `get_qr_service`) always passes the
        # real request-scoped `AsyncSession`.
        self._db = db

    async def _scope_to_verified_plant(self, plant_id: uuid.UUID) -> None:
        """
        Sets `app.qr_scan_plant_id` for the remainder of this request's
        transaction -- see migrations/versions/0014_public_qr_scan_rls_
        carveout.py's docstring for the full reasoning. Must only ever be
        called with a `plant_id` that came from an already-verified
        `Passport` row (i.e. after `PassportService.get_passport_by_token`
        has succeeded), never with unvalidated caller input -- this is
        what keeps the carve-out narrow (one specific, token-unlocked
        plant) rather than a blanket bypass.
        """
        if self._db is None:
            return
        await self._db.execute(
            text("SELECT set_config('app.qr_scan_plant_id', :val, true)"), {"val": str(plant_id)}
        )

    def qr_payload_url(self, passport: Passport) -> str:
        """The URL a frontend QR-rendering library encodes — see module docstring on why no image is rendered server-side."""
        return f"{self._frontend_base_url}/passport/{passport.public_token}"

    async def scan(
        self, token: str, *, ip_hash: str | None = None, user_agent: str | None = None, referrer: str | None = None
    ) -> dict[str, Any]:
        passport = await self._passports.get_passport_by_token(token)
        await self._scans.add(
            QRScanEvent(passport_id=passport.id, ip_hash=ip_hash, user_agent=user_agent, referrer=referrer)
        )
        # Token is verified (the line above didn't raise) -- narrowly
        # unlock RLS-protected reads for exactly this one plant. Must
        # happen after verification and before the reads below; see
        # `_scope_to_verified_plant`'s docstring.
        await self._scope_to_verified_plant(passport.plant_id)

        plant = await self._plants.get_by_id(passport.plant_id)
        latest_health = None
        latest_growth = None
        latest_fertilizer = None
        if plant is not None:
            health_rows, _ = await self._health.list_for_plant(plant.id, offset=0, limit=1)
            latest_health = health_rows[0] if health_rows else None
            growth_rows, _ = await self._growth.list_for_plant(plant.id, offset=0, limit=5)
            latest_growth = growth_rows
            fert_rows, _ = await self._fertilizer.list_for_plant(plant.id, offset=0, limit=1)
            latest_fertilizer = fert_rows[0] if fert_rows else None

        return {
            "passport": passport.content_snapshot,
            "care_instructions": passport.content_snapshot.get("care_guide"),
            "water_schedule": {
                "baseline_ml_per_week": passport.content_snapshot.get("care_guide", {}).get(
                    "water_baseline_ml_per_week"
                )
            },
            "fertilizer_schedule": (
                {
                    "product_name": latest_fertilizer.product_name,
                    "schedule": latest_fertilizer.schedule,
                    "next_application_date": (
                        latest_fertilizer.next_application_date.isoformat()
                        if latest_fertilizer.next_application_date
                        else None
                    ),
                }
                if latest_fertilizer is not None
                else None
            ),
            "health_status": (
                {"status_label": latest_health.status_label, "health_score": _optfloat(latest_health.health_score)}
                if latest_health is not None
                else None
            ),
            "growth_timeline": [
                {
                    "height_cm": _optfloat(g.height_cm),
                    "growth_stage": g.growth_stage,
                    "recorded_at": g.recorded_at.isoformat() if g.recorded_at else None,
                }
                for g in (latest_growth or [])
            ],
            "ai_recommendations": passport.content_snapshot.get("ai_care_recommendations", []),
        }
