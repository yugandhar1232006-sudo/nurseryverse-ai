"""
Module 4 (Nursery & Organization Management) — Branch Management:
create/update/archive a Branch, operating hours, location, status.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.enums import BranchStatus
from app.domain_events import BranchArchived, BranchCreated, BranchUpdated, DomainEventPublisher
from app.models.organization import Branch
from app.models.platform import AuditLog
from app.repositories.interfaces import AuditLogRepository, BranchRepository, NurseryRepository
from app.services.validation import validate_country_code, validate_operating_hours, validate_timezone


class BranchService:
    def __init__(
        self,
        *,
        branch_repo: BranchRepository,
        nursery_repo: NurseryRepository,
        audit_repo: AuditLogRepository,
        event_publisher: DomainEventPublisher,
    ) -> None:
        self._branches = branch_repo
        self._nurseries = nursery_repo
        self._audit = audit_repo
        self._events = event_publisher

    async def list_branches(self, *, nursery_id: uuid.UUID, include_inactive: bool = False) -> list[Branch]:
        return await self._branches.list_for_nursery(nursery_id, include_inactive=include_inactive)

    async def get_branch(self, branch_id: uuid.UUID) -> Branch:
        branch = await self._branches.get_by_id(branch_id)
        if branch is None:
            raise NotFoundError("Branch not found.")
        return branch

    async def create_branch(
        self,
        *,
        nursery_id: uuid.UUID,
        name: str,
        address_line1: str,
        city: str,
        country: str,
        timezone_name: str,
        actor_user_id: uuid.UUID,
        address_line2: str | None = None,
        region: str | None = None,
        postal_code: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        operating_hours: dict | None = None,
        request_id: str | None = None,
    ) -> Branch:
        nursery = await self._nurseries.get_by_id(nursery_id)
        if nursery is None:
            raise NotFoundError("Nursery not found.")

        normalized_name = name.strip()
        if not normalized_name:
            raise ValidationError("Branch name cannot be blank.")
        if await self._branches.get_by_name(nursery_id, normalized_name) is not None:
            raise ConflictError(f"A branch named '{normalized_name}' already exists in this organization.")

        validated_country = validate_country_code(country)
        validated_tz = validate_timezone(timezone_name)
        validated_hours = validate_operating_hours(operating_hours)
        _validate_coordinates(latitude, longitude)

        branch = Branch(
            nursery_id=nursery_id,
            name=normalized_name,
            address_line1=address_line1.strip(),
            address_line2=address_line2,
            city=city.strip(),
            region=region,
            postal_code=postal_code,
            country=validated_country,
            timezone=validated_tz,
            status=BranchStatus.ACTIVE,
            phone=phone,
            email=email.strip().lower() if email else None,
            latitude=latitude,
            longitude=longitude,
            operating_hours=validated_hours,
        )
        await self._branches.add(branch)

        await self._log_audit(
            nursery_id=nursery_id,
            actor_user_id=actor_user_id,
            action="branch.created",
            entity_id=branch.id,
            diff={"after": {"name": branch.name, "city": branch.city, "country": branch.country}},
            request_id=request_id,
        )
        await self._events.publish(
            BranchCreated(
                aggregate_id=branch.id,
                nursery_id=nursery_id,
                actor_user_id=actor_user_id,
                name=branch.name,
                branch_id=branch.id,
            ),
            request_id=request_id,
        )
        return branch

    async def update_branch(
        self,
        *,
        branch_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        name: str | None = None,
        address_line1: str | None = None,
        address_line2: str | None = None,
        city: str | None = None,
        region: str | None = None,
        postal_code: str | None = None,
        country: str | None = None,
        timezone_name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        operating_hours: dict | None = None,
        request_id: str | None = None,
    ) -> Branch:
        branch = await self.get_branch(branch_id)
        before = _snapshot(branch)
        changed: list[str] = []

        if name is not None:
            normalized = name.strip()
            if normalized != branch.name:
                existing = await self._branches.get_by_name(branch.nursery_id, normalized)
                if existing is not None and existing.id != branch.id:
                    raise ConflictError(f"A branch named '{normalized}' already exists in this organization.")
                branch.name = normalized
                changed.append("name")
        if address_line1 is not None and address_line1.strip() != branch.address_line1:
            branch.address_line1 = address_line1.strip()
            changed.append("address_line1")
        if address_line2 is not None and address_line2 != branch.address_line2:
            branch.address_line2 = address_line2
            changed.append("address_line2")
        if city is not None and city.strip() != branch.city:
            branch.city = city.strip()
            changed.append("city")
        if region is not None and region != branch.region:
            branch.region = region
            changed.append("region")
        if postal_code is not None and postal_code != branch.postal_code:
            branch.postal_code = postal_code
            changed.append("postal_code")
        if country is not None:
            validated_country = validate_country_code(country)
            if validated_country != branch.country:
                branch.country = validated_country
                changed.append("country")
        if timezone_name is not None:
            validated_tz = validate_timezone(timezone_name)
            if validated_tz != branch.timezone:
                branch.timezone = validated_tz
                changed.append("timezone")
        if phone is not None and phone != branch.phone:
            branch.phone = phone
            changed.append("phone")
        if email is not None:
            normalized_email = email.strip().lower()
            if normalized_email != branch.email:
                branch.email = normalized_email
                changed.append("email")
        if latitude is not None or longitude is not None:
            new_lat = latitude if latitude is not None else branch.latitude
            new_lng = longitude if longitude is not None else branch.longitude
            _validate_coordinates(new_lat, new_lng)
            if new_lat != branch.latitude:
                branch.latitude = new_lat
                changed.append("latitude")
            if new_lng != branch.longitude:
                branch.longitude = new_lng
                changed.append("longitude")
        if operating_hours is not None:
            validated_hours = validate_operating_hours(operating_hours)
            if validated_hours != branch.operating_hours:
                branch.operating_hours = validated_hours
                changed.append("operating_hours")

        if not changed:
            return branch

        await self._log_audit(
            nursery_id=branch.nursery_id,
            actor_user_id=actor_user_id,
            action="branch.updated",
            entity_id=branch.id,
            diff={"before": before, "after": _snapshot(branch)},
            request_id=request_id,
        )
        await self._events.publish(
            BranchUpdated(
                aggregate_id=branch.id,
                nursery_id=branch.nursery_id,
                actor_user_id=actor_user_id,
                branch_id=branch.id,
                changed_fields=tuple(changed),
            ),
            request_id=request_id,
        )
        return branch

    async def archive_branch(
        self, *, branch_id: uuid.UUID, actor_user_id: uuid.UUID, request_id: str | None = None
    ) -> Branch:
        branch = await self.get_branch(branch_id)
        if branch.status == BranchStatus.INACTIVE:
            raise ConflictError("This branch is already archived.")

        branch.status = BranchStatus.INACTIVE
        await self._log_audit(
            nursery_id=branch.nursery_id,
            actor_user_id=actor_user_id,
            action="branch.archived",
            entity_id=branch.id,
            diff={"before": {"status": "active"}, "after": {"status": "inactive"}},
            request_id=request_id,
        )
        await self._events.publish(
            BranchArchived(
                aggregate_id=branch.id,
                nursery_id=branch.nursery_id,
                actor_user_id=actor_user_id,
                branch_id=branch.id,
            ),
            request_id=request_id,
        )
        return branch

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    async def _log_audit(
        self,
        *,
        nursery_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        action: str,
        entity_id: uuid.UUID,
        diff: dict,
        request_id: str | None,
    ) -> None:
        await self._audit.log(
            AuditLog(
                nursery_id=nursery_id,
                actor_user_id=actor_user_id,
                action=action,
                entity_type="Branch",
                entity_id=entity_id,
                diff=diff,
                request_id=request_id,
                created_at=datetime.now(timezone.utc),
            )
        )


def _validate_coordinates(latitude: float | None, longitude: float | None) -> None:
    if latitude is not None and not (-90 <= latitude <= 90):
        raise ValidationError("latitude must be between -90 and 90.")
    if longitude is not None and not (-180 <= longitude <= 180):
        raise ValidationError("longitude must be between -180 and 180.")


def _snapshot(branch: Branch) -> dict:
    return {
        "name": branch.name,
        "address_line1": branch.address_line1,
        "address_line2": branch.address_line2,
        "city": branch.city,
        "region": branch.region,
        "postal_code": branch.postal_code,
        "country": branch.country,
        "timezone": branch.timezone,
        "phone": branch.phone,
        "email": branch.email,
        "latitude": float(branch.latitude) if branch.latitude is not None else None,
        "longitude": float(branch.longitude) if branch.longitude is not None else None,
        "operating_hours": branch.operating_hours,
    }
