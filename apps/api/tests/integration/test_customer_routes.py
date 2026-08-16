"""Integration tests for Module 9's Customer CRM REST API (app/api/routes/customers.py)."""
from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


async def test_list_customers_requires_auth(auth_client):
    response = await auth_client.get("/api/v1/customers")
    assert response.status_code == 401


async def test_list_customers_denied_without_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=[])
    response = await ac.get("/api/v1/customers")
    assert response.status_code == 403


async def test_create_and_get_customer(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["customers:read", "customers:write"])

    response = await ac.post(
        "/api/v1/customers", json={"branch_id": str(branch_id), "name": "Jane Doe", "email": "jane@example.com"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Jane Doe"

    get_response = await ac.get(f"/api/v1/customers/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["email"] == "jane@example.com"


async def test_get_customer_rejects_cross_tenant_access(authenticated_client, harness):
    ac, user = authenticated_client
    own_org_id = uuid.uuid4()
    foreign_org_id = uuid.uuid4()
    from app.models.commerce import Customer

    foreign_customer = Customer(
        id=uuid.uuid4(), nursery_id=foreign_org_id, branch_id=uuid.uuid4(), name="Foreign Customer",
    )
    harness.customers.customers[foreign_customer.id] = foreign_customer
    harness.grant_role(user, org_id=own_org_id, role_code="owner", permission_codes=["customers:read"])

    response = await ac.get(f"/api/v1/customers/{foreign_customer.id}")
    assert response.status_code == 403
    assert harness.denials.denials[-1].reason == "cross_tenant_org"


async def test_customer_contacts_addresses_tags_notes_workflow(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["customers:read", "customers:write"])

    create_response = await ac.post("/api/v1/customers", json={"branch_id": str(branch_id), "name": "Jane Doe"})
    customer_id = create_response.json()["id"]

    contact_response = await ac.post(f"/api/v1/customers/{customer_id}/contacts", json={"name": "Assistant"})
    assert contact_response.status_code == 201
    contacts_response = await ac.get(f"/api/v1/customers/{customer_id}/contacts")
    assert len(contacts_response.json()) == 1

    address_response = await ac.post(
        f"/api/v1/customers/{customer_id}/addresses",
        json={"line1": "123 Garden Rd", "city": "Springfield", "country": "US"},
    )
    assert address_response.status_code == 201

    tag_response = await ac.post(f"/api/v1/customers/{customer_id}/tags", json={"tag": "VIP"})
    assert tag_response.status_code == 201
    assert tag_response.json()["tag"] == "vip"

    delete_tag_response = await ac.delete(f"/api/v1/customers/{customer_id}/tags/vip")
    assert delete_tag_response.status_code == 204
    tags_response = await ac.get(f"/api/v1/customers/{customer_id}/tags")
    assert tags_response.json() == []

    note_response = await ac.post(f"/api/v1/customers/{customer_id}/notes", json={"note": "Prefers succulents"})
    assert note_response.status_code == 201

    comm_response = await ac.post(
        f"/api/v1/customers/{customer_id}/communications",
        json={"channel": "email", "direction": "outbound", "subject": "Welcome"},
    )
    assert comm_response.status_code == 201


async def test_customer_analytics_endpoint(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["customers:read", "customers:write"])
    create_response = await ac.post("/api/v1/customers", json={"branch_id": str(branch_id), "name": "Jane Doe"})
    customer_id = create_response.json()["id"]

    response = await ac.get(f"/api/v1/customers/{customer_id}/analytics")
    assert response.status_code == 200
    body = response.json()
    assert body["total_orders"] == 0
    assert body["total_spent"] == 0.0
