"""
Integration tests for Module 9's Sales, Payments, Returns & Refunds REST
API (app/api/routes/sales.py) -- Sales Workflow, Payment, Reservation,
and Cross-Tenant tests, exercised through the real FastAPI app against
`harness`'s in-memory fakes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.integration


def _species_and_branch(harness, *, org_id):
    from app.models.catalog import Species
    from app.models.organization import Branch

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
    return branch, species


async def _register_plant(harness, *, org_id, branch):
    species = next(s for s in harness.species.species.values() if s.nursery_id == org_id)
    return await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )


# ------------------------------------------------------------------
# Auth / permission gating
# ------------------------------------------------------------------


async def test_list_sales_orders_requires_auth(auth_client):
    response = await auth_client.get("/api/v1/sales-orders")
    assert response.status_code == 401


async def test_create_sales_order_denied_without_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch, species = _species_and_branch(harness, org_id=org_id)
    plant = await _register_plant(harness, org_id=org_id, branch=branch)
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=[])

    response = await ac.post(
        "/api/v1/sales-orders",
        json={
            "branch_id": str(branch.id), "customer_id": str(uuid.uuid4()),
            "items": [{"plant_id": str(plant.id), "quantity": 1, "unit_price": "10.00"}],
        },
    )
    assert response.status_code == 403


# ------------------------------------------------------------------
# Full Sales Workflow: Quotation -> convert -> confirm -> checkout -> payment -> return -> refund
# ------------------------------------------------------------------


async def test_full_sales_workflow(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch, species = _species_and_branch(harness, org_id=org_id)
    harness.grant_role(
        user, org_id=org_id, role_code="owner",
        permission_codes=[
            "sales:read", "sales:write", "sales:void", "invoices:read", "invoices:write",
            "customers:read", "customers:write",
        ],
    )
    plant = await _register_plant(harness, org_id=org_id, branch=branch)

    customer_response = await ac.post("/api/v1/customers", json={"branch_id": str(branch.id), "name": "Jane Doe"})
    customer_id = customer_response.json()["id"]

    # Quotation with tax + discount.
    quote_response = await ac.post(
        "/api/v1/quotations",
        json={
            "branch_id": str(branch.id), "customer_id": customer_id,
            "items": [{"plant_id": str(plant.id), "quantity": 1, "unit_price": "50.00"}],
            "tax_rate": 0.1, "header_discount": "0.00",
        },
    )
    assert quote_response.status_code == 201
    quotation = quote_response.json()
    assert quotation["total_amount"] == "55.00"

    send_response = await ac.post(f"/api/v1/quotations/{quotation['id']}/status", json={"status": "sent"})
    assert send_response.status_code == 200
    accept_response = await ac.post(f"/api/v1/quotations/{quotation['id']}/status", json={"status": "accepted"})
    assert accept_response.status_code == 200

    convert_response = await ac.post(f"/api/v1/quotations/{quotation['id']}/convert")
    assert convert_response.status_code == 200
    order = convert_response.json()
    assert order["order_status"] == "draft"

    confirm_response = await ac.post(f"/api/v1/sales-orders/{order['id']}/confirm")
    assert confirm_response.status_code == 200
    assert confirm_response.json()["order_status"] == "confirmed"

    checkout_response = await ac.post(f"/api/v1/sales-orders/{order['id']}/checkout")
    assert checkout_response.status_code == 200
    fulfilled = checkout_response.json()
    assert fulfilled["order_status"] == "fulfilled"
    sale_id = fulfilled["sale_id"]
    invoice_id = fulfilled["invoice_id"]

    sale_response = await ac.get(f"/api/v1/sales/{sale_id}")
    assert sale_response.status_code == 200
    sale_items_response = await ac.get(f"/api/v1/sales/{sale_id}/items")
    sale_item_id = sale_items_response.json()[0]["id"]

    # Payment: Cash then UPI (multiple/partial payments).
    pay1 = await ac.post(f"/api/v1/invoices/{invoice_id}/payments", json={"amount": "20.00", "method": "cash"})
    assert pay1.status_code == 201
    invoice_after_partial = await ac.get(f"/api/v1/invoices/{invoice_id}")
    assert invoice_after_partial.json()["payment_status"] == "partially_paid"

    pay2 = await ac.post(f"/api/v1/invoices/{invoice_id}/payments", json={"amount": "35.00", "method": "upi"})
    assert pay2.status_code == 201
    invoice_after_full = await ac.get(f"/api/v1/invoices/{invoice_id}")
    assert invoice_after_full.json()["payment_status"] == "paid"

    payments_response = await ac.get(f"/api/v1/invoices/{invoice_id}/payments")
    assert len(payments_response.json()) == 2

    # Return + Refund.
    return_response = await ac.post(
        f"/api/v1/sales/{sale_id}/returns",
        json={"customer_id": customer_id, "reason": "Wilted", "items": [{"sale_item_id": sale_item_id, "quantity": 1}]},
    )
    assert return_response.status_code == 201
    return_body = return_response.json()

    approve_response = await ac.post(f"/api/v1/returns/{return_body['id']}/approve")
    assert approve_response.status_code == 200

    complete_response = await ac.post(f"/api/v1/returns/{return_body['id']}/complete")
    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "completed"

    refund_response = await ac.post(
        "/api/v1/refunds",
        json={
            "branch_id": str(branch.id), "amount": "55.00", "method": "cash",
            "return_id": return_body["id"], "invoice_id": invoice_id, "sale_id": sale_id,
        },
    )
    assert refund_response.status_code == 201
    assert refund_response.json()["status"] == "completed"

    # Sales Report / Revenue Report reflect the completed sale.
    report_response = await ac.get("/api/v1/sales/reports/summary")
    assert report_response.status_code == 200
    assert report_response.json()["sale_count"] == 1
    assert report_response.json()["total_revenue"] == 55.0


# ------------------------------------------------------------------
# Reservations: confirm reserves, cancel releases
# ------------------------------------------------------------------


async def test_reservation_taken_on_confirm_and_released_on_cancel(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch, _ = _species_and_branch(harness, org_id=org_id)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["sales:read", "sales:write", "inventory:read"])

    line = await harness.inventory_service.create_inventory_line(
        nursery_id=org_id, branch_id=branch.id, category_id=uuid.uuid4(), unit_id=uuid.uuid4(),
        name="Basil 4in", initial_quantity=10, actor_user_id=uuid.uuid4(),
    )

    order_response = await ac.post(
        "/api/v1/sales-orders",
        json={
            "branch_id": str(branch.id), "customer_id": str(uuid.uuid4()),
            "items": [{"inventory_id": str(line.id), "quantity": 4, "unit_price": "9.99"}],
        },
    )
    assert order_response.status_code == 201
    order = order_response.json()

    confirm_response = await ac.post(f"/api/v1/sales-orders/{order['id']}/confirm")
    assert confirm_response.status_code == 200

    reserved_line = await harness.inventory_service.get_inventory(line.id)
    assert reserved_line.reserved_quantity == 4

    cancel_response = await ac.post(f"/api/v1/sales-orders/{order['id']}/cancel", json={"reason": "changed mind"})
    assert cancel_response.status_code == 200

    released_line = await harness.inventory_service.get_inventory(line.id)
    assert released_line.reserved_quantity == 0


# ------------------------------------------------------------------
# Cross-Tenant
# ------------------------------------------------------------------


async def test_get_sales_order_rejects_cross_tenant_access(authenticated_client, harness):
    ac, user = authenticated_client
    own_org_id = uuid.uuid4()
    foreign_org_id = uuid.uuid4()
    branch, species = _species_and_branch(harness, org_id=foreign_org_id)
    foreign_plant = await harness.plant_service.register_plant(
        nursery_id=foreign_org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    from app.services.sales_service import LineItemInput
    from decimal import Decimal

    foreign_order = await harness.sales_order_service.create_order(
        nursery_id=foreign_org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), customer_id=uuid.uuid4(),
        items=[LineItemInput(quantity=1, unit_price=Decimal("10.00"), plant_id=foreign_plant.id)],
    )
    harness.grant_role(user, org_id=own_org_id, role_code="owner", permission_codes=["sales:read"])

    response = await ac.get(f"/api/v1/sales-orders/{foreign_order.id}")
    assert response.status_code == 403
    assert harness.denials.denials[-1].reason == "cross_tenant_org"


async def test_get_invoice_rejects_cross_tenant_access(authenticated_client, harness):
    ac, user = authenticated_client
    own_org_id = uuid.uuid4()
    foreign_org_id = uuid.uuid4()
    branch, species = _species_and_branch(harness, org_id=foreign_org_id)
    foreign_plant = await harness.plant_service.register_plant(
        nursery_id=foreign_org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )
    from app.services.sales_service import LineItemInput
    from decimal import Decimal

    foreign_order = await harness.sales_order_service.create_order(
        nursery_id=foreign_org_id, branch_id=branch.id, actor_user_id=uuid.uuid4(), customer_id=uuid.uuid4(),
        items=[LineItemInput(quantity=1, unit_price=Decimal("10.00"), plant_id=foreign_plant.id)],
    )
    foreign_order = await harness.sales_order_service.checkout(foreign_order, actor_user_id=uuid.uuid4())
    harness.grant_role(user, org_id=own_org_id, role_code="owner", permission_codes=["invoices:read"])

    response = await ac.get(f"/api/v1/invoices/{foreign_order.invoice_id}")
    assert response.status_code == 403
    assert harness.denials.denials[-1].reason == "cross_tenant_org"
