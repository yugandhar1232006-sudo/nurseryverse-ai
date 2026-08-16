"""Module 4 unit tests: BranchService (create/update/archive Branch) against in-memory fakes."""
from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.enums import BranchStatus, NurseryStatus
from app.domain_events import DomainEventPublisher
from app.models.organization import Nursery
from app.services.branch_service import BranchService
from tests.fakes.repositories import FakeAuditLogRepository, FakeBranchRepository, FakeDomainEventRepository, FakeNurseryRepository


@pytest.fixture
async def nursery_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
async def branch_service(nursery_id: uuid.UUID) -> BranchService:
    nurseries = FakeNurseryRepository()
    nurseries.nurseries[nursery_id] = Nursery(
        id=nursery_id, name="Test Nursery", contact_email="n@example.com", status=NurseryStatus.ACTIVE
    )
    branches = FakeBranchRepository()
    audit = FakeAuditLogRepository()
    events = DomainEventPublisher(FakeDomainEventRepository())
    return BranchService(branch_repo=branches, nursery_repo=nurseries, audit_repo=audit, event_publisher=events)


VALID_KWARGS = dict(
    name="Downtown Branch",
    address_line1="123 Main St",
    city="Austin",
    country="us",
    timezone_name="America/Chicago",
)


class TestCreateBranch:
    async def test_creates_branch(self, branch_service: BranchService, nursery_id: uuid.UUID) -> None:
        branch = await branch_service.create_branch(
            nursery_id=nursery_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS
        )
        assert branch.id is not None
        assert branch.country == "US"  # normalized uppercase
        assert branch.status == BranchStatus.ACTIVE

    async def test_nursery_not_found(self, branch_service: BranchService) -> None:
        with pytest.raises(NotFoundError):
            await branch_service.create_branch(
                nursery_id=uuid.uuid4(), actor_user_id=uuid.uuid4(), **VALID_KWARGS
            )

    async def test_duplicate_name_conflicts(self, branch_service: BranchService, nursery_id: uuid.UUID) -> None:
        await branch_service.create_branch(nursery_id=nursery_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS)
        with pytest.raises(ConflictError):
            await branch_service.create_branch(nursery_id=nursery_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS)

    async def test_blank_name_rejected(self, branch_service: BranchService, nursery_id: uuid.UUID) -> None:
        kwargs = dict(VALID_KWARGS, name="   ")
        with pytest.raises(ValidationError):
            await branch_service.create_branch(nursery_id=nursery_id, actor_user_id=uuid.uuid4(), **kwargs)

    async def test_invalid_country_rejected(self, branch_service: BranchService, nursery_id: uuid.UUID) -> None:
        kwargs = dict(VALID_KWARGS, country="USA")  # not alpha-2
        with pytest.raises(ValidationError):
            await branch_service.create_branch(nursery_id=nursery_id, actor_user_id=uuid.uuid4(), **kwargs)

    async def test_invalid_timezone_rejected(self, branch_service: BranchService, nursery_id: uuid.UUID) -> None:
        kwargs = dict(VALID_KWARGS, timezone_name="Mars/Colony_One")
        with pytest.raises(ValidationError):
            await branch_service.create_branch(nursery_id=nursery_id, actor_user_id=uuid.uuid4(), **kwargs)

    async def test_invalid_coordinates_rejected(self, branch_service: BranchService, nursery_id: uuid.UUID) -> None:
        with pytest.raises(ValidationError):
            await branch_service.create_branch(
                nursery_id=nursery_id, actor_user_id=uuid.uuid4(), latitude=200.0, **VALID_KWARGS
            )

    async def test_invalid_operating_hours_rejected(self, branch_service: BranchService, nursery_id: uuid.UUID) -> None:
        with pytest.raises(ValidationError):
            await branch_service.create_branch(
                nursery_id=nursery_id,
                actor_user_id=uuid.uuid4(),
                operating_hours={"mon": {"open": "18:00", "close": "09:00"}},  # open after close
                **VALID_KWARGS,
            )

    async def test_valid_operating_hours_persisted(self, branch_service: BranchService, nursery_id: uuid.UUID) -> None:
        branch = await branch_service.create_branch(
            nursery_id=nursery_id,
            actor_user_id=uuid.uuid4(),
            operating_hours={"mon": {"open": "09:00", "close": "17:00"}, "sun": None},
            **VALID_KWARGS,
        )
        assert branch.operating_hours["mon"]["open"] == "09:00"
        assert branch.operating_hours["sun"] is None


class TestGetBranch:
    async def test_not_found_raises(self, branch_service: BranchService) -> None:
        with pytest.raises(NotFoundError):
            await branch_service.get_branch(uuid.uuid4())


class TestUpdateBranch:
    async def test_updates_changed_fields(self, branch_service: BranchService, nursery_id: uuid.UUID) -> None:
        branch = await branch_service.create_branch(
            nursery_id=nursery_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS
        )
        updated = await branch_service.update_branch(
            branch_id=branch.id, actor_user_id=uuid.uuid4(), city="Round Rock"
        )
        assert updated.city == "Round Rock"
        assert updated.name == VALID_KWARGS["name"]  # untouched

    async def test_updates_every_field(self, branch_service: BranchService, nursery_id: uuid.UUID) -> None:
        branch = await branch_service.create_branch(
            nursery_id=nursery_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS
        )
        updated = await branch_service.update_branch(
            branch_id=branch.id,
            actor_user_id=uuid.uuid4(),
            name="Renamed Branch",
            address_line1="456 Oak Ave",
            address_line2="Suite 2",
            city="Dallas",
            region="TX",
            postal_code="75201",
            country="ca",
            timezone_name="America/Denver",
            phone="555-1234",
            email="Branch@Example.com",
            latitude=32.78,
            longitude=-96.8,
            operating_hours={"tue": {"open": "08:00", "close": "16:00"}},
        )
        assert updated.name == "Renamed Branch"
        assert updated.address_line1 == "456 Oak Ave"
        assert updated.address_line2 == "Suite 2"
        assert updated.city == "Dallas"
        assert updated.region == "TX"
        assert updated.postal_code == "75201"
        assert updated.country == "CA"
        assert updated.timezone == "America/Denver"
        assert updated.phone == "555-1234"
        assert updated.email == "branch@example.com"
        assert float(updated.latitude) == 32.78
        assert float(updated.longitude) == -96.8
        assert updated.operating_hours == {"tue": {"open": "08:00", "close": "16:00"}}

    async def test_update_only_longitude_still_validates_coordinates(
        self, branch_service: BranchService, nursery_id: uuid.UUID
    ) -> None:
        branch = await branch_service.create_branch(
            nursery_id=nursery_id, actor_user_id=uuid.uuid4(), latitude=10.0, longitude=20.0, **VALID_KWARGS
        )
        with pytest.raises(ValidationError):
            await branch_service.update_branch(branch_id=branch.id, actor_user_id=uuid.uuid4(), longitude=200.0)

    async def test_rename_to_existing_name_conflicts(self, branch_service: BranchService, nursery_id: uuid.UUID) -> None:
        await branch_service.create_branch(nursery_id=nursery_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS)
        other = await branch_service.create_branch(
            nursery_id=nursery_id, actor_user_id=uuid.uuid4(), **dict(VALID_KWARGS, name="Second Branch")
        )
        with pytest.raises(ConflictError):
            await branch_service.update_branch(
                branch_id=other.id, actor_user_id=uuid.uuid4(), name=VALID_KWARGS["name"]
            )

    async def test_rename_to_own_current_name_is_noop_safe(
        self, branch_service: BranchService, nursery_id: uuid.UUID
    ) -> None:
        branch = await branch_service.create_branch(
            nursery_id=nursery_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS
        )
        # Renaming to the exact same name should not raise, and should be a no-op.
        result = await branch_service.update_branch(
            branch_id=branch.id, actor_user_id=uuid.uuid4(), name=VALID_KWARGS["name"]
        )
        assert result.name == VALID_KWARGS["name"]

    async def test_noop_update_skips_audit(self, branch_service: BranchService, nursery_id: uuid.UUID) -> None:
        branch = await branch_service.create_branch(
            nursery_id=nursery_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS
        )
        before = len(branch_service._audit.rows)  # type: ignore[attr-defined]
        await branch_service.update_branch(branch_id=branch.id, actor_user_id=uuid.uuid4())
        assert len(branch_service._audit.rows) == before  # type: ignore[attr-defined]

    async def test_invalid_country_on_update_rejected(self, branch_service: BranchService, nursery_id: uuid.UUID) -> None:
        branch = await branch_service.create_branch(
            nursery_id=nursery_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS
        )
        with pytest.raises(ValidationError):
            await branch_service.update_branch(branch_id=branch.id, actor_user_id=uuid.uuid4(), country="ZZZZ")


class TestArchiveBranch:
    async def test_archives_active_branch(self, branch_service: BranchService, nursery_id: uuid.UUID) -> None:
        branch = await branch_service.create_branch(
            nursery_id=nursery_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS
        )
        archived = await branch_service.archive_branch(branch_id=branch.id, actor_user_id=uuid.uuid4())
        assert archived.status == BranchStatus.INACTIVE

    async def test_archiving_twice_conflicts(self, branch_service: BranchService, nursery_id: uuid.UUID) -> None:
        branch = await branch_service.create_branch(
            nursery_id=nursery_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS
        )
        await branch_service.archive_branch(branch_id=branch.id, actor_user_id=uuid.uuid4())
        with pytest.raises(ConflictError):
            await branch_service.archive_branch(branch_id=branch.id, actor_user_id=uuid.uuid4())


class TestListBranches:
    async def test_excludes_inactive_by_default(self, branch_service: BranchService, nursery_id: uuid.UUID) -> None:
        active = await branch_service.create_branch(
            nursery_id=nursery_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS
        )
        inactive = await branch_service.create_branch(
            nursery_id=nursery_id, actor_user_id=uuid.uuid4(), **dict(VALID_KWARGS, name="Closing Soon")
        )
        await branch_service.archive_branch(branch_id=inactive.id, actor_user_id=uuid.uuid4())

        visible = await branch_service.list_branches(nursery_id=nursery_id)
        assert [b.id for b in visible] == [active.id]

        all_branches = await branch_service.list_branches(nursery_id=nursery_id, include_inactive=True)
        assert {b.id for b in all_branches} == {active.id, inactive.id}

    async def test_scoped_to_nursery(self, branch_service: BranchService, nursery_id: uuid.UUID) -> None:
        other_nursery_id = uuid.uuid4()
        branch_service._nurseries.nurseries[other_nursery_id] = Nursery(  # type: ignore[attr-defined]
            id=other_nursery_id, name="Other", contact_email="o@example.com", status=NurseryStatus.ACTIVE
        )
        await branch_service.create_branch(nursery_id=nursery_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS)
        await branch_service.create_branch(
            nursery_id=other_nursery_id, actor_user_id=uuid.uuid4(), **VALID_KWARGS
        )
        visible = await branch_service.list_branches(nursery_id=nursery_id)
        assert len(visible) == 1
        assert visible[0].nursery_id == nursery_id
