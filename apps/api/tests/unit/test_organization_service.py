"""
Module 4 unit tests: OrganizationService (create/update/archive Nursery,
Settings) against in-memory fakes -- no HTTP, no database, no
authorization layer (that's Module 3's concern and is exercised
separately at the route level in tests/integration/test_organization_routes.py).
"""
from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.enums import NurseryStatus
from app.domain_events import DomainEventPublisher
from app.services.organization_service import OrganizationService
from tests.fakes.repositories import FakeAuditLogRepository, FakeDomainEventRepository, FakeNurseryRepository


@pytest.fixture
def org_service() -> OrganizationService:
    nurseries = FakeNurseryRepository()
    audit = FakeAuditLogRepository()
    events = DomainEventPublisher(FakeDomainEventRepository())
    return OrganizationService(nursery_repo=nurseries, audit_repo=audit, event_publisher=events)


class TestCreateNursery:
    async def test_creates_nursery_and_default_settings(self, org_service: OrganizationService) -> None:
        actor_id = uuid.uuid4()
        nursery = await org_service.create_nursery(
            name="  Green Thumb Nursery  ",
            contact_email="Owner@Example.com",
            actor_user_id=actor_id,
        )

        assert nursery.id is not None
        assert nursery.name == "Green Thumb Nursery"  # stripped
        assert nursery.contact_email == "owner@example.com"  # normalized
        assert nursery.status == NurseryStatus.ACTIVE

        settings = await org_service.get_settings(nursery.id)
        assert settings.default_currency == "USD"
        assert settings.default_timezone == "UTC"

    async def test_creation_writes_audit_log_and_domain_event(self, org_service: OrganizationService) -> None:
        actor_id = uuid.uuid4()
        nursery = await org_service.create_nursery(
            name="Fern Co", contact_email="a@b.com", actor_user_id=actor_id, request_id="req-1"
        )

        assert len(org_service._audit.rows) == 1  # type: ignore[attr-defined]
        entry = org_service._audit.rows[0]  # type: ignore[attr-defined]
        assert entry.action == "nursery.created"
        assert entry.nursery_id == nursery.id
        assert entry.actor_user_id == actor_id
        assert entry.request_id == "req-1"

        published = org_service._events._repo.events  # type: ignore[attr-defined]
        assert len(published) == 1
        assert published[0].event_type == "nursery.created"
        assert published[0].nursery_id == nursery.id


class TestGetNursery:
    async def test_not_found_raises(self, org_service: OrganizationService) -> None:
        with pytest.raises(NotFoundError):
            await org_service.get_nursery(uuid.uuid4())


class TestUpdateNursery:
    async def test_updates_changed_fields_only(self, org_service: OrganizationService) -> None:
        nursery = await org_service.create_nursery(
            name="Old Name", contact_email="old@example.com", actor_user_id=uuid.uuid4()
        )
        updated = await org_service.update_nursery(
            nursery_id=nursery.id,
            actor_user_id=uuid.uuid4(),
            name="New Name",
        )
        assert updated.name == "New Name"
        assert updated.contact_email == "old@example.com"  # untouched

    async def test_updates_all_other_fields(self, org_service: OrganizationService) -> None:
        nursery = await org_service.create_nursery(
            name="Multi Co", contact_email="old@example.com", actor_user_id=uuid.uuid4()
        )
        updated = await org_service.update_nursery(
            nursery_id=nursery.id,
            actor_user_id=uuid.uuid4(),
            contact_email="New.Contact@Example.com",
            contact_phone="+1-555-0100",
            logo_url="https://cdn.example.com/logo.png",
        )
        assert updated.contact_email == "new.contact@example.com"
        assert updated.contact_phone == "+1-555-0100"
        assert updated.logo_url == "https://cdn.example.com/logo.png"

    async def test_noop_update_skips_audit_and_event(self, org_service: OrganizationService) -> None:
        nursery = await org_service.create_nursery(
            name="Same Name", contact_email="same@example.com", actor_user_id=uuid.uuid4()
        )
        audit_count_before = len(org_service._audit.rows)  # type: ignore[attr-defined]
        events_before = len(org_service._events._repo.events)  # type: ignore[attr-defined]

        await org_service.update_nursery(
            nursery_id=nursery.id, actor_user_id=uuid.uuid4(), name="Same Name"
        )

        assert len(org_service._audit.rows) == audit_count_before  # type: ignore[attr-defined]
        assert len(org_service._events._repo.events) == events_before  # type: ignore[attr-defined]


class TestArchiveNursery:
    async def test_archives_active_nursery(self, org_service: OrganizationService) -> None:
        nursery = await org_service.create_nursery(
            name="To Archive", contact_email="x@example.com", actor_user_id=uuid.uuid4()
        )
        archived = await org_service.archive_nursery(nursery_id=nursery.id, actor_user_id=uuid.uuid4())
        assert archived.status == NurseryStatus.ARCHIVED

    async def test_archiving_twice_conflicts(self, org_service: OrganizationService) -> None:
        nursery = await org_service.create_nursery(
            name="To Archive", contact_email="x@example.com", actor_user_id=uuid.uuid4()
        )
        await org_service.archive_nursery(nursery_id=nursery.id, actor_user_id=uuid.uuid4())
        with pytest.raises(ConflictError):
            await org_service.archive_nursery(nursery_id=nursery.id, actor_user_id=uuid.uuid4())


class TestOrgSettings:
    async def test_get_settings_not_found_when_nursery_never_created(
        self, org_service: OrganizationService
    ) -> None:
        with pytest.raises(NotFoundError):
            await org_service.get_settings(uuid.uuid4())

    async def test_update_settings_validates_currency_timezone_color(
        self, org_service: OrganizationService
    ) -> None:
        nursery = await org_service.create_nursery(
            name="Settings Co", contact_email="s@example.com", actor_user_id=uuid.uuid4()
        )
        updated = await org_service.update_settings(
            nursery_id=nursery.id,
            actor_user_id=uuid.uuid4(),
            currency="eur",
            timezone_name="America/New_York",
            branding_primary_color="#2e7d32",
        )
        assert updated.default_currency == "EUR"
        assert updated.default_timezone == "America/New_York"
        assert updated.branding_primary_color == "#2e7d32"

    async def test_update_settings_updates_email_identity_and_sms(self, org_service: OrganizationService) -> None:
        nursery = await org_service.create_nursery(
            name="Settings Co", contact_email="s@example.com", actor_user_id=uuid.uuid4()
        )
        updated = await org_service.update_settings(
            nursery_id=nursery.id,
            actor_user_id=uuid.uuid4(),
            email_sender_identity="hello@greenthumb.com",
            sms_enabled=True,
        )
        assert updated.email_sender_identity == "hello@greenthumb.com"
        assert updated.sms_enabled is True

    async def test_update_settings_rejects_invalid_currency(self, org_service: OrganizationService) -> None:
        nursery = await org_service.create_nursery(
            name="Settings Co", contact_email="s@example.com", actor_user_id=uuid.uuid4()
        )
        with pytest.raises(ValidationError):
            await org_service.update_settings(nursery_id=nursery.id, actor_user_id=uuid.uuid4(), currency="US")

    async def test_update_settings_rejects_invalid_timezone(self, org_service: OrganizationService) -> None:
        nursery = await org_service.create_nursery(
            name="Settings Co", contact_email="s@example.com", actor_user_id=uuid.uuid4()
        )
        with pytest.raises(ValidationError):
            await org_service.update_settings(
                nursery_id=nursery.id, actor_user_id=uuid.uuid4(), timezone_name="Not/AZone"
            )

    async def test_update_settings_noop_skips_audit(self, org_service: OrganizationService) -> None:
        nursery = await org_service.create_nursery(
            name="Settings Co", contact_email="s@example.com", actor_user_id=uuid.uuid4()
        )
        before = len(org_service._audit.rows)  # type: ignore[attr-defined]
        await org_service.update_settings(nursery_id=nursery.id, actor_user_id=uuid.uuid4(), currency="USD")
        assert len(org_service._audit.rows) == before  # type: ignore[attr-defined]
