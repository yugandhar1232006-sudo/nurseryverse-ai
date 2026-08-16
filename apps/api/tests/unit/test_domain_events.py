"""
Unit tests for app/domain_events/ -- Module 4's required domain event
types and the DomainEventPublisher that persists them.
"""
from __future__ import annotations

import uuid

import pytest

from app.domain_events import (
    BranchCreated,
    DomainEventPublisher,
    EmployeeInvited,
    EmployeeRemoved,
    NurseryCreated,
    NurseryUpdated,
)
from tests.fakes.repositories import FakeDomainEventRepository

pytestmark = pytest.mark.unit


async def test_publish_persists_the_envelope_fields():
    repo = FakeDomainEventRepository()
    publisher = DomainEventPublisher(repo)
    nursery_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    event = NurseryCreated(
        aggregate_id=nursery_id,
        nursery_id=nursery_id,
        actor_user_id=actor_id,
        name="Green Thumb Nursery",
        contact_email="owner@greenthumb.example",
    )

    await publisher.publish(event, request_id="req-1")

    assert len(repo.events) == 1
    row = repo.events[0]
    assert row.event_type == "nursery.created"
    assert row.aggregate_type == "Nursery"
    assert row.aggregate_id == nursery_id
    assert row.nursery_id == nursery_id
    assert row.actor_user_id == actor_id
    assert row.request_id == "req-1"
    assert row.occurred_at is not None
    assert row.id is not None


async def test_publish_payload_excludes_envelope_fields_and_includes_domain_fields():
    repo = FakeDomainEventRepository()
    publisher = DomainEventPublisher(repo)
    nursery_id = uuid.uuid4()

    await publisher.publish(
        NurseryCreated(
            aggregate_id=nursery_id, nursery_id=nursery_id, actor_user_id=None,
            name="Green Thumb Nursery", contact_email="owner@greenthumb.example",
        )
    )

    payload = repo.events[0].payload
    assert payload == {"name": "Green Thumb Nursery", "contact_email": "owner@greenthumb.example"}
    assert "aggregate_id" not in payload
    assert "nursery_id" not in payload
    assert "actor_user_id" not in payload


async def test_publish_serializes_uuids_and_tuples_to_json_safe_types():
    repo = FakeDomainEventRepository()
    publisher = DomainEventPublisher(repo)
    nursery_id = uuid.uuid4()
    branch_a, branch_b = uuid.uuid4(), uuid.uuid4()

    await publisher.publish(
        EmployeeInvited(
            aggregate_id=uuid.uuid4(),
            nursery_id=nursery_id,
            actor_user_id=uuid.uuid4(),
            email="new.hire@example.com",
            role_code="branch_manager",
            branch_ids=(branch_a, branch_b),
        )
    )

    payload = repo.events[0].payload
    assert payload["branch_ids"] == [str(branch_a), str(branch_b)]
    assert all(isinstance(v, str) for v in payload["branch_ids"])


async def test_publish_without_request_id_defaults_to_none():
    repo = FakeDomainEventRepository()
    publisher = DomainEventPublisher(repo)

    await publisher.publish(
        NurseryUpdated(
            aggregate_id=uuid.uuid4(), nursery_id=uuid.uuid4(), actor_user_id=None,
            changed_fields=("name",),
        )
    )

    assert repo.events[0].request_id is None


async def test_branch_created_event_shape():
    event = BranchCreated(
        aggregate_id=uuid.uuid4(), nursery_id=uuid.uuid4(), actor_user_id=uuid.uuid4(),
        name="Downtown Branch", branch_id=uuid.uuid4(),
    )
    assert event.event_type == "branch.created"
    assert event.aggregate_type == "Branch"


async def test_employee_removed_event_reason_is_optional():
    event = EmployeeRemoved(
        aggregate_id=uuid.uuid4(), nursery_id=uuid.uuid4(), actor_user_id=uuid.uuid4(),
        employee_id=uuid.uuid4(),
    )
    assert event.reason is None
    assert event.event_type == "employee.removed"


async def test_multiple_publishes_each_get_their_own_row():
    repo = FakeDomainEventRepository()
    publisher = DomainEventPublisher(repo)
    nursery_id = uuid.uuid4()

    for i in range(3):
        await publisher.publish(
            NurseryUpdated(
                aggregate_id=nursery_id, nursery_id=nursery_id, actor_user_id=None,
                changed_fields=(f"field_{i}",),
            )
        )

    assert len(repo.events) == 3
    assert len({row.id for row in repo.events}) == 3
