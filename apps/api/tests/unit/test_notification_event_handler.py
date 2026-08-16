"""
Unit tests for `NotificationEventHandler` -- the event-driven core of
Module 11's ARCHITECTURE requirement. Every test publishes a real domain
event through `harness.event_publisher` (the same dispatcher production
wires up) and asserts on the resulting `Notification` rows, proving
notifications are driven by events, not by direct calls.
"""
from __future__ import annotations

import uuid

import pytest

from app.core.security import hash_password
from app.db.enums import EmployeeStatus, NotificationCategory
from app.domain_events import (
    AIRecommendationGenerated,
    DiseaseDetected,
    EmailVerificationRequested,
    EmployeeInvited,
    InvoiceGenerated,
    PasswordResetRequested,
    PaymentReceived,
    PlantMoved,
    PlantRegistered,
    PlantSold,
    PlantStatusChanged,
    ReservationCreated,
    StockReceived,
    StockSold,
    StockTransferred,
    SystemAlertRaised,
)
from app.models.commerce import Invoice, SalesOrder
from app.models.identity import User
from app.models.inventory import Inventory
from app.models.organization import Employee
from app.models.plants import Plant

pytestmark = pytest.mark.unit


async def _user(harness, email: str) -> User:
    return await harness.users.add(
        User(id=uuid.uuid4(), email=email, password_hash=hash_password("Correct-Horse12"), full_name="T", is_active=True)
    )


async def _plant(harness, *, nursery_id: uuid.UUID, branch_id: uuid.UUID) -> Plant:
    return await harness.plants.add(
        Plant(
            id=uuid.uuid4(), nursery_id=nursery_id, branch_id=branch_id, species_id=uuid.uuid4(),
            qr_code_token=str(uuid.uuid4()), common_label="Fiddle Leaf Fig",
        )
    )


async def _inventory(harness, *, nursery_id, branch_id, threshold=10, quantity=50) -> Inventory:
    return await harness.inventory.add(
        Inventory(
            id=uuid.uuid4(), nursery_id=nursery_id, branch_id=branch_id, category_id=uuid.uuid4(), unit_id=uuid.uuid4(),
            name="Rose Pots", quantity=quantity, reserved_quantity=0, damaged_quantity=0, low_stock_threshold=threshold,
        )
    )


async def notifications_for(harness, user_id: uuid.UUID) -> list:
    return [n for n in harness.notifications.notifications.values() if n.recipient_user_id == user_id]


async def test_plant_registered_notifies_users_with_plants_write_in_that_branch(harness):
    org_id, branch_id = uuid.uuid4(), uuid.uuid4()
    grower = await _user(harness, "grower@example.com")
    harness.grant_role(grower, org_id=org_id, role_code="horticulturist", permission_codes=["plants:write"], branch_ids=[branch_id])
    plant = await _plant(harness, nursery_id=org_id, branch_id=branch_id)

    await harness.event_publisher.publish(
        PlantRegistered(aggregate_id=plant.id, nursery_id=org_id, actor_user_id=None, branch_id=branch_id, species_id=uuid.uuid4(), qr_code_token=plant.qr_code_token)
    )

    rows = await notifications_for(harness, grower.id)
    assert len(rows) == 1
    assert rows[0].category == NotificationCategory.PLANT_REGISTERED
    assert "Fiddle Leaf Fig" in rows[0].message


async def test_plant_registered_does_not_notify_users_in_a_different_branch(harness):
    org_id, branch_id, other_branch = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    grower = await _user(harness, "grower@example.com")
    harness.grant_role(grower, org_id=org_id, role_code="horticulturist", permission_codes=["plants:write"], branch_ids=[other_branch])
    plant = await _plant(harness, nursery_id=org_id, branch_id=branch_id)

    await harness.event_publisher.publish(
        PlantRegistered(aggregate_id=plant.id, nursery_id=org_id, actor_user_id=None, branch_id=branch_id, species_id=uuid.uuid4(), qr_code_token=plant.qr_code_token)
    )

    assert await notifications_for(harness, grower.id) == []


async def test_plant_registered_excludes_the_actor(harness):
    org_id, branch_id = uuid.uuid4(), uuid.uuid4()
    grower = await _user(harness, "grower@example.com")
    harness.grant_role(grower, org_id=org_id, role_code="horticulturist", permission_codes=["plants:write"])
    plant = await _plant(harness, nursery_id=org_id, branch_id=branch_id)

    await harness.event_publisher.publish(
        PlantRegistered(aggregate_id=plant.id, nursery_id=org_id, actor_user_id=grower.id, branch_id=branch_id, species_id=uuid.uuid4(), qr_code_token=plant.qr_code_token)
    )

    assert await notifications_for(harness, grower.id) == []


async def test_plant_status_changed_to_ready_for_sale(harness):
    org_id, branch_id = uuid.uuid4(), uuid.uuid4()
    sales_staff = await _user(harness, "sales@example.com")
    harness.grant_role(sales_staff, org_id=org_id, role_code="horticulturist", permission_codes=["plants:write"])
    plant = await _plant(harness, nursery_id=org_id, branch_id=branch_id)

    await harness.event_publisher.publish(
        PlantStatusChanged(aggregate_id=plant.id, nursery_id=org_id, actor_user_id=None, from_status="in_production", to_status="ready_for_sale")
    )

    rows = await notifications_for(harness, sales_staff.id)
    assert len(rows) == 1
    assert rows[0].category == NotificationCategory.PLANT_READY_FOR_SALE


async def test_plant_status_changed_to_under_treatment(harness):
    org_id, branch_id = uuid.uuid4(), uuid.uuid4()
    grower = await _user(harness, "grower@example.com")
    harness.grant_role(grower, org_id=org_id, role_code="horticulturist", permission_codes=["plants:write"])
    plant = await _plant(harness, nursery_id=org_id, branch_id=branch_id)

    await harness.event_publisher.publish(
        PlantStatusChanged(aggregate_id=plant.id, nursery_id=org_id, actor_user_id=None, from_status="in_production", to_status="under_treatment")
    )

    rows = await notifications_for(harness, grower.id)
    assert len(rows) == 1
    assert rows[0].category == NotificationCategory.PLANT_UNDER_TREATMENT


async def test_plant_status_changed_to_an_uncovered_status_notifies_nobody(harness):
    org_id, branch_id = uuid.uuid4(), uuid.uuid4()
    grower = await _user(harness, "grower@example.com")
    harness.grant_role(grower, org_id=org_id, role_code="horticulturist", permission_codes=["plants:write"])
    plant = await _plant(harness, nursery_id=org_id, branch_id=branch_id)

    await harness.event_publisher.publish(
        PlantStatusChanged(aggregate_id=plant.id, nursery_id=org_id, actor_user_id=None, from_status="ready_for_sale", to_status="sold")
    )

    assert await notifications_for(harness, grower.id) == []


async def test_disease_detected_notifies_disease_write_holders(harness):
    org_id, branch_id = uuid.uuid4(), uuid.uuid4()
    horticulturist = await _user(harness, "h@example.com")
    harness.grant_role(horticulturist, org_id=org_id, role_code="horticulturist", permission_codes=["disease:write"])
    plant = await _plant(harness, nursery_id=org_id, branch_id=branch_id)

    await harness.event_publisher.publish(
        DiseaseDetected(aggregate_id=plant.id, nursery_id=org_id, actor_user_id=None, disease_report_id=uuid.uuid4(), condition_name="Root Rot", severity="high")
    )

    rows = await notifications_for(harness, horticulturist.id)
    assert len(rows) == 1
    assert rows[0].category == NotificationCategory.DISEASE_CONFIRMED
    assert "Root Rot" in rows[0].message


async def test_plant_sold_notifies_sales_read_holders(harness):
    org_id, branch_id = uuid.uuid4(), uuid.uuid4()
    sales_staff = await _user(harness, "sales@example.com")
    harness.grant_role(sales_staff, org_id=org_id, role_code="sales_staff", permission_codes=["sales:read"])
    plant = await _plant(harness, nursery_id=org_id, branch_id=branch_id)

    await harness.event_publisher.publish(
        PlantSold(aggregate_id=plant.id, nursery_id=org_id, actor_user_id=None, sale_id=uuid.uuid4(), sale_item_id=uuid.uuid4(), customer_id=None, unit_price="25.00")
    )

    rows = await notifications_for(harness, sales_staff.id)
    assert len(rows) == 1
    assert rows[0].category == NotificationCategory.PLANT_SOLD
    assert "25.00" in rows[0].message


async def test_plant_moved_notifies_holders_in_the_destination_branch(harness):
    org_id, from_branch, to_branch = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    receiving_staff = await _user(harness, "recv@example.com")
    harness.grant_role(receiving_staff, org_id=org_id, role_code="horticulturist", permission_codes=["plants:write"], branch_ids=[to_branch])
    plant = await _plant(harness, nursery_id=org_id, branch_id=from_branch)

    await harness.event_publisher.publish(
        PlantMoved(aggregate_id=plant.id, nursery_id=org_id, actor_user_id=None, from_branch_id=from_branch, to_branch_id=to_branch)
    )

    rows = await notifications_for(harness, receiving_staff.id)
    assert len(rows) == 1
    assert rows[0].category == NotificationCategory.PLANT_TRANSFERRED


async def test_reservation_created_notifies_sales_write_holders_at_order_branch(harness):
    org_id, branch_id = uuid.uuid4(), uuid.uuid4()
    sales_staff = await _user(harness, "sales@example.com")
    harness.grant_role(sales_staff, org_id=org_id, role_code="sales_staff", permission_codes=["sales:write"])
    order = await harness.sales_orders.add(
        SalesOrder(id=uuid.uuid4(), nursery_id=org_id, branch_id=branch_id, customer_id=uuid.uuid4())
    )

    await harness.event_publisher.publish(
        ReservationCreated(aggregate_id=order.id, nursery_id=org_id, actor_user_id=None, order_item_id=uuid.uuid4(), inventory_reservation_id=uuid.uuid4(), quantity=3)
    )

    rows = await notifications_for(harness, sales_staff.id)
    assert len(rows) == 1
    assert rows[0].category == NotificationCategory.RESERVATION_CREATED


async def test_invoice_generated_notifies_invoices_read_holders(harness):
    org_id, branch_id = uuid.uuid4(), uuid.uuid4()
    biller = await _user(harness, "biller@example.com")
    harness.grant_role(biller, org_id=org_id, role_code="branch_manager", permission_codes=["invoices:read"])

    await harness.event_publisher.publish(
        InvoiceGenerated(aggregate_id=uuid.uuid4(), nursery_id=org_id, actor_user_id=None, branch_id=branch_id, customer_id=uuid.uuid4(), total_amount="199.99")
    )

    rows = await notifications_for(harness, biller.id)
    assert len(rows) == 1
    assert rows[0].category == NotificationCategory.INVOICE_GENERATED


async def test_payment_received_notifies_invoices_read_holders_at_invoice_branch(harness):
    org_id, branch_id = uuid.uuid4(), uuid.uuid4()
    biller = await _user(harness, "biller@example.com")
    harness.grant_role(biller, org_id=org_id, role_code="branch_manager", permission_codes=["invoices:read"])
    invoice = await harness.invoices.add(
        Invoice(id=uuid.uuid4(), nursery_id=org_id, branch_id=branch_id, customer_id=uuid.uuid4(), invoice_number="INV-1", total_amount=100)
    )

    await harness.event_publisher.publish(
        PaymentReceived(aggregate_id=invoice.id, nursery_id=org_id, actor_user_id=None, payment_id=uuid.uuid4(), amount="100.00", method="card", invoice_fully_paid=True)
    )

    rows = await notifications_for(harness, biller.id)
    assert len(rows) == 1
    assert rows[0].category == NotificationCategory.PAYMENT_RECEIVED


async def test_stock_transferred_notifies_inventory_write_holders(harness):
    org_id, branch_id = uuid.uuid4(), uuid.uuid4()
    warehouse_staff = await _user(harness, "wh@example.com")
    harness.grant_role(warehouse_staff, org_id=org_id, role_code="branch_manager", permission_codes=["inventory:write"])
    inventory = await _inventory(harness, nursery_id=org_id, branch_id=branch_id, threshold=5, quantity=50)

    await harness.event_publisher.publish(
        StockTransferred(aggregate_id=inventory.id, nursery_id=org_id, actor_user_id=None, movement_id=uuid.uuid4(), quantity=10, transfer_group_id=uuid.uuid4())
    )

    rows = await notifications_for(harness, warehouse_staff.id)
    categories = {r.category for r in rows}
    assert NotificationCategory.INVENTORY_TRANSFER in categories
    # Stock still well above threshold -- no low-stock alert expected.
    assert NotificationCategory.LOW_STOCK not in categories


async def test_stock_sold_below_threshold_triggers_low_stock_alert(harness):
    org_id, branch_id = uuid.uuid4(), uuid.uuid4()
    warehouse_staff = await _user(harness, "wh@example.com")
    harness.grant_role(warehouse_staff, org_id=org_id, role_code="branch_manager", permission_codes=["inventory:write"])
    inventory = await _inventory(harness, nursery_id=org_id, branch_id=branch_id, threshold=10, quantity=8)

    await harness.event_publisher.publish(
        StockSold(aggregate_id=inventory.id, nursery_id=org_id, actor_user_id=None, movement_id=uuid.uuid4(), quantity=2)
    )

    rows = await notifications_for(harness, warehouse_staff.id)
    assert any(r.category == NotificationCategory.LOW_STOCK for r in rows)


async def test_stock_sold_above_threshold_does_not_trigger_low_stock_alert(harness):
    org_id, branch_id = uuid.uuid4(), uuid.uuid4()
    warehouse_staff = await _user(harness, "wh@example.com")
    harness.grant_role(warehouse_staff, org_id=org_id, role_code="branch_manager", permission_codes=["inventory:write"])
    inventory = await _inventory(harness, nursery_id=org_id, branch_id=branch_id, threshold=5, quantity=100)

    await harness.event_publisher.publish(
        StockSold(aggregate_id=inventory.id, nursery_id=org_id, actor_user_id=None, movement_id=uuid.uuid4(), quantity=2)
    )

    rows = await notifications_for(harness, warehouse_staff.id)
    assert not any(r.category == NotificationCategory.LOW_STOCK for r in rows)


async def test_stock_received_with_purchase_order_notifies_purchase_order_receivers(harness):
    org_id, branch_id = uuid.uuid4(), uuid.uuid4()
    receiver = await _user(harness, "recv@example.com")
    harness.grant_role(receiver, org_id=org_id, role_code="branch_manager", permission_codes=["purchase_orders:receive"])
    inventory = await _inventory(harness, nursery_id=org_id, branch_id=branch_id)

    await harness.event_publisher.publish(
        StockReceived(aggregate_id=inventory.id, nursery_id=org_id, actor_user_id=None, movement_id=uuid.uuid4(), quantity=20, quantity_after=70, reference_purchase_order_id=uuid.uuid4())
    )

    rows = await notifications_for(harness, receiver.id)
    assert any(r.category == NotificationCategory.PURCHASE_ORDER_RECEIVED for r in rows)


async def test_stock_received_without_purchase_order_does_not_notify(harness):
    org_id, branch_id = uuid.uuid4(), uuid.uuid4()
    receiver = await _user(harness, "recv@example.com")
    harness.grant_role(receiver, org_id=org_id, role_code="branch_manager", permission_codes=["purchase_orders:receive"])
    inventory = await _inventory(harness, nursery_id=org_id, branch_id=branch_id)

    await harness.event_publisher.publish(
        StockReceived(aggregate_id=inventory.id, nursery_id=org_id, actor_user_id=None, movement_id=uuid.uuid4(), quantity=20, quantity_after=70, reference_purchase_order_id=None)
    )

    assert await notifications_for(harness, receiver.id) == []


async def test_system_alert_broadcasts_to_every_active_employee(harness):
    org_id = uuid.uuid4()
    active_1 = await _user(harness, "active1@example.com")
    active_2 = await _user(harness, "active2@example.com")
    deactivated = await _user(harness, "gone@example.com")
    await harness.employees.add(Employee(id=uuid.uuid4(), nursery_id=org_id, user_id=active_1.id, status=EmployeeStatus.ACTIVE))
    await harness.employees.add(Employee(id=uuid.uuid4(), nursery_id=org_id, user_id=active_2.id, status=EmployeeStatus.ACTIVE))
    await harness.employees.add(Employee(id=uuid.uuid4(), nursery_id=org_id, user_id=deactivated.id, status=EmployeeStatus.DEACTIVATED))

    await harness.event_publisher.publish(
        SystemAlertRaised(aggregate_id=uuid.uuid4(), nursery_id=org_id, actor_user_id=None, title="Irrigation offline", message="Riverside branch", severity="critical")
    )

    assert len(await notifications_for(harness, active_1.id)) == 1
    assert len(await notifications_for(harness, active_2.id)) == 1
    assert await notifications_for(harness, deactivated.id) == []


async def test_system_alert_excludes_the_broadcasting_actor(harness):
    org_id = uuid.uuid4()
    admin = await _user(harness, "admin@example.com")
    await harness.employees.add(Employee(id=uuid.uuid4(), nursery_id=org_id, user_id=admin.id, status=EmployeeStatus.ACTIVE))

    await harness.event_publisher.publish(
        SystemAlertRaised(aggregate_id=uuid.uuid4(), nursery_id=org_id, actor_user_id=admin.id, title="Test", message="Test", severity="info")
    )

    assert await notifications_for(harness, admin.id) == []


async def test_ai_recommendation_generated_notifies_branch_scoped_ai_readers(harness):
    org_id, branch_id = uuid.uuid4(), uuid.uuid4()
    manager = await _user(harness, "mgr@example.com")
    harness.grant_role(manager, org_id=org_id, role_code="branch_manager", permission_codes=["ai_predictions:read"], branch_ids=[branch_id])

    await harness.event_publisher.publish(
        AIRecommendationGenerated(aggregate_id=branch_id, nursery_id=org_id, actor_user_id=None, recommendation_id=uuid.uuid4(), priority="high")
    )

    rows = await notifications_for(harness, manager.id)
    assert len(rows) == 1
    assert rows[0].category == NotificationCategory.AI_RECOMMENDATION_READY


async def test_employee_invited_confirms_to_the_inviter_not_the_invitee(harness):
    """The invitee has no User row yet -- only the actor (inviter) gets an in-app confirmation."""
    org_id = uuid.uuid4()
    inviter = await _user(harness, "owner@example.com")

    await harness.event_publisher.publish(
        EmployeeInvited(aggregate_id=uuid.uuid4(), nursery_id=org_id, actor_user_id=inviter.id, email="new-hire@example.com", role_code="sales_staff", branch_ids=())
    )

    rows = await notifications_for(harness, inviter.id)
    assert len(rows) == 1
    assert rows[0].category == NotificationCategory.EMPLOYEE_INVITE
    assert "new-hire@example.com" in rows[0].message


async def test_password_reset_requested_creates_in_app_only_audit_record(harness):
    org_id = uuid.uuid4()
    target = await _user(harness, "forgetful@example.com")

    await harness.event_publisher.publish(
        PasswordResetRequested(aggregate_id=target.id, nursery_id=org_id, actor_user_id=None, requested_ip="127.0.0.1")
    )

    rows = await notifications_for(harness, target.id)
    assert len(rows) == 1
    assert rows[0].category == NotificationCategory.PASSWORD_RESET
    # No email was sent through this pipeline -- that happens directly in AuthService, not here.
    assert harness.email_provider.sent == []


async def test_email_verification_requested_creates_in_app_only_audit_record(harness):
    org_id = uuid.uuid4()
    target = await _user(harness, "unverified@example.com")

    await harness.event_publisher.publish(
        EmailVerificationRequested(aggregate_id=target.id, nursery_id=org_id, actor_user_id=None)
    )

    rows = await notifications_for(harness, target.id)
    assert len(rows) == 1
    assert rows[0].category == NotificationCategory.EMAIL_VERIFICATION
