"""
Unit tests for Module 9's `CustomerService` -- Customer Profiles,
Contacts, Addresses, Tags, Notes, Communication History, Purchase
History, and Customer Analytics.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.core.exceptions import ValidationError
from app.db.enums import CommunicationChannel, CommunicationDirection, CustomerType
from app.services.sales_service import LineItemInput

pytestmark = pytest.mark.unit


def _ids():
    return uuid.uuid4(), uuid.uuid4()  # nursery, branch


async def test_create_customer(harness):
    org_id, branch_id = _ids()
    customer = await harness.customer_service.create_customer(
        nursery_id=org_id, branch_id=branch_id, actor_user_id=uuid.uuid4(), name="  Jane Doe  ",
        email="Jane@Example.com", customer_type=CustomerType.RETAIL,
    )
    assert customer.name == "Jane Doe"
    assert customer.email == "jane@example.com"  # normalized


async def test_create_customer_blank_name_rejected(harness):
    org_id, branch_id = _ids()
    with pytest.raises(ValidationError):
        await harness.customer_service.create_customer(
            nursery_id=org_id, branch_id=branch_id, actor_user_id=uuid.uuid4(), name="   "
        )


async def test_update_customer_noop_when_nothing_changes(harness):
    org_id, branch_id = _ids()
    customer = await harness.customer_service.create_customer(
        nursery_id=org_id, branch_id=branch_id, actor_user_id=uuid.uuid4(), name="Jane Doe"
    )
    before_audit_count = len(harness.audit_logs.rows)
    await harness.customer_service.update_customer(customer, actor_user_id=uuid.uuid4(), name="Jane Doe")
    assert len(harness.audit_logs.rows) == before_audit_count


async def test_contacts_addresses_tags_notes_communications(harness):
    org_id, branch_id = _ids()
    customer = await harness.customer_service.create_customer(
        nursery_id=org_id, branch_id=branch_id, actor_user_id=uuid.uuid4(), name="Jane Doe"
    )

    contact = await harness.customer_service.add_contact(customer, name="Primary Contact", is_primary=True)
    assert (await harness.customer_service.list_contacts(customer.id))[0].id == contact.id

    address = await harness.customer_service.add_address(
        customer, line1="123 Garden Rd", city="Springfield", country="US"
    )
    assert (await harness.customer_service.list_addresses(customer.id))[0].id == address.id

    tag = await harness.customer_service.add_tag(customer, " VIP ")
    assert tag.tag == "vip"
    # Adding the same tag again is idempotent, not a duplicate row.
    again = await harness.customer_service.add_tag(customer, "vip")
    assert again.id == tag.id
    assert len(await harness.customer_service.list_tags(customer.id)) == 1
    await harness.customer_service.remove_tag(customer, "vip")
    assert await harness.customer_service.list_tags(customer.id) == []

    note = await harness.customer_service.add_note(customer, actor_user_id=uuid.uuid4(), note="Prefers succulents")
    notes, total = await harness.customer_service.list_notes(customer.id, offset=0, limit=10)
    assert total == 1
    assert notes[0].id == note.id

    comm = await harness.customer_service.log_communication(
        customer, actor_user_id=uuid.uuid4(), channel=CommunicationChannel.EMAIL,
        direction=CommunicationDirection.OUTBOUND, subject="Order confirmation",
    )
    comms, total = await harness.customer_service.list_communications(customer.id, offset=0, limit=10)
    assert total == 1
    assert comms[0].id == comm.id


async def test_add_tag_rejects_blank(harness):
    org_id, branch_id = _ids()
    customer = await harness.customer_service.create_customer(
        nursery_id=org_id, branch_id=branch_id, actor_user_id=uuid.uuid4(), name="Jane Doe"
    )
    with pytest.raises(ValidationError):
        await harness.customer_service.add_tag(customer, "   ")


async def test_purchase_history_and_analytics(harness):
    from datetime import datetime, timezone

    from app.models.catalog import Species
    from app.models.organization import Branch

    org_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    branch = Branch(
        id=uuid.uuid4(), nursery_id=org_id, name="Main", address_line1="123 St", city="Springfield",
        country="US", timezone="UTC", created_at=now, updated_at=now,
    )
    species = Species(
        id=uuid.uuid4(), nursery_id=org_id, category_id=uuid.uuid4(), common_name="Fig",
        botanical_name="Ficus lyrata", created_at=now, updated_at=now,
    )
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species

    customer = await harness.customer_service.create_customer(
        nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), name="Jane Doe"
    )

    plant1 = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    plant2 = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )

    order1 = await harness.sales_order_service.create_order(
        nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), customer_id=customer.id,
        items=[LineItemInput(quantity=1, unit_price=Decimal("40.00"), plant_id=plant1.id)],
    )
    await harness.sales_order_service.checkout(order1, actor_user_id=uuid.uuid4())

    order2 = await harness.sales_order_service.create_order(
        nursery_id=org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), customer_id=customer.id,
        items=[LineItemInput(quantity=1, unit_price=Decimal("60.00"), plant_id=plant2.id)],
    )
    await harness.sales_order_service.checkout(order2, actor_user_id=uuid.uuid4())

    sales, total = await harness.customer_service.purchase_history(customer, offset=0, limit=10)
    assert total == 2

    analytics = await harness.customer_service.customer_analytics(customer)
    assert analytics.total_orders == 2
    assert analytics.total_spent == 100.0
    assert analytics.average_order_value == 50.0
    assert analytics.last_purchase_at is not None
