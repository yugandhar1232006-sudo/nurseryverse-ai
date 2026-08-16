"""Integration tests for Module 8's Inventory & Stock Management REST API (app/api/routes/inventory.py)."""
from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


async def _make_line(harness, *, nursery_id, branch_id, actor=None, initial_quantity=20, **kw):
    return await harness.inventory_service.create_inventory_line(
        nursery_id=nursery_id, branch_id=branch_id, category_id=uuid.uuid4(), unit_id=uuid.uuid4(),
        name=kw.pop("name", "Basil 4in"), initial_quantity=initial_quantity, actor_user_id=actor or uuid.uuid4(),
        **kw,
    )


# ------------------------------------------------------------------
# Auth / permission gating
# ------------------------------------------------------------------


async def test_list_inventory_requires_auth(auth_client):
    response = await auth_client.get("/api/v1/inventory")
    assert response.status_code == 401


async def test_list_inventory_without_org_membership_returns_empty_page(authenticated_client):
    ac, user = authenticated_client
    response = await ac.get("/api/v1/inventory")
    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_list_inventory_denied_without_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=[])
    response = await ac.get("/api/v1/inventory")
    assert response.status_code == 403


# ------------------------------------------------------------------
# Units (real defect fixed while building 7I -- see UnitRepository's docstring)
# ------------------------------------------------------------------


async def test_list_units_requires_auth(auth_client):
    response = await auth_client.get("/api/v1/units")
    assert response.status_code == 401


async def test_list_units_requires_inventory_read_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=[])
    response = await ac.get("/api/v1/units")
    assert response.status_code == 403


async def test_list_units_returns_real_seeded_reference_data(authenticated_client, harness):
    from app.models.catalog import Unit

    ac, user = authenticated_client
    org_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["inventory:read"])
    each = Unit(id=uuid.uuid4(), code="each", name="Each", unit_type="count")
    harness.units.units[each.id] = each

    response = await ac.get("/api/v1/units")

    assert response.status_code == 200
    body = response.json()
    assert {"id": str(each.id), "code": "each", "name": "Each", "unit_type": "count"} in body


# ------------------------------------------------------------------
# Locations
# ------------------------------------------------------------------


async def test_create_and_get_location(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["inventory:read", "inventory:write"])

    response = await ac.post(
        "/api/v1/inventory-locations",
        json={"branch_id": str(branch_id), "location_type": "greenhouse", "name": "GH1"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "GH1"

    get_response = await ac.get(f"/api/v1/inventory-locations/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "GH1"


async def test_create_location_denied_for_wrong_branch_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    other_branch_id = uuid.uuid4()
    harness.grant_role(
        user, org_id=org_id, role_code="horticulturist", permission_codes=["inventory:write"],
        branch_ids=[other_branch_id],
    )
    response = await ac.post(
        "/api/v1/inventory-locations",
        json={"branch_id": str(branch_id), "location_type": "zone", "name": "Z1"},
    )
    assert response.status_code == 403


async def test_list_and_deactivate_location(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["inventory:read", "inventory:write"])

    create_response = await ac.post(
        "/api/v1/inventory-locations", json={"branch_id": str(branch_id), "location_type": "rack", "name": "R1"}
    )
    location_id = create_response.json()["id"]

    list_response = await ac.get("/api/v1/inventory-locations", params={"branch_id": str(branch_id)})
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    deactivate_response = await ac.post(f"/api/v1/inventory-locations/{location_id}/deactivate")
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["is_active"] is False

    list_after = await ac.get("/api/v1/inventory-locations", params={"branch_id": str(branch_id)})
    assert list_after.json() == []


# ------------------------------------------------------------------
# Inventory CRUD
# ------------------------------------------------------------------


async def test_create_and_get_inventory_line(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    category_id = uuid.uuid4()
    unit_id = uuid.uuid4()
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["inventory:read", "inventory:write"])

    response = await ac.post(
        "/api/v1/inventory",
        json={
            "branch_id": str(branch_id), "category_id": str(category_id), "unit_id": str(unit_id),
            "name": "Basil 4in", "initial_quantity": 12, "unit_cost": 1.5, "unit_price": 4.0,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["quantity"] == 12
    assert body["available_quantity"] == 12

    get_response = await ac.get(f"/api/v1/inventory/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Basil 4in"


async def test_get_inventory_cross_tenant_rejected(authenticated_client, harness):
    ac, user = authenticated_client
    own_org_id = uuid.uuid4()
    foreign_org_id = uuid.uuid4()
    foreign_branch_id = uuid.uuid4()
    item = await _make_line(harness, nursery_id=foreign_org_id, branch_id=foreign_branch_id)
    harness.grant_role(user, org_id=own_org_id, role_code="owner", permission_codes=["inventory:read"])

    response = await ac.get(f"/api/v1/inventory/{item.id}")
    assert response.status_code == 403
    assert response.json()["error"]["context"]["reason"] == "cross_tenant_org"


async def test_get_inventory_not_found(authenticated_client, harness):
    ac, user = authenticated_client
    response = await ac.get(f"/api/v1/inventory/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_list_inventory_filters_by_branch_and_search(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    await _make_line(harness, nursery_id=org_id, branch_id=branch_id, name="Fig Tree")
    await _make_line(harness, nursery_id=org_id, branch_id=branch_id, name="Basil Pot")
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["inventory:read"])

    response = await ac.get("/api/v1/inventory", params={"branch_id": str(branch_id), "search": "Fig"})
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total_items"] == 1
    assert body["items"][0]["name"] == "Fig Tree"


# ------------------------------------------------------------------
# Mutating actions
# ------------------------------------------------------------------


async def test_receive_stock_route(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    item = await _make_line(harness, nursery_id=org_id, branch_id=branch_id, initial_quantity=5)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["inventory:read", "inventory:write"])

    response = await ac.post(f"/api/v1/inventory/{item.id}/receive", json={"quantity": 10})
    assert response.status_code == 200
    assert response.json()["quantity"] == 15


async def test_transfer_stock_route_cross_branch_requires_dest_branch_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch_a = uuid.uuid4()
    branch_b = uuid.uuid4()
    item = await _make_line(harness, nursery_id=org_id, branch_id=branch_a, initial_quantity=10)
    # Branch-scoped role that only covers branch_a -- branch_b write should be denied.
    harness.grant_role(
        user, org_id=org_id, role_code="horticulturist", permission_codes=["inventory:read", "inventory:write"],
        branch_ids=[branch_a],
    )
    response = await ac.post(
        f"/api/v1/inventory/{item.id}/transfer", json={"quantity": 4, "to_branch_id": str(branch_b)}
    )
    assert response.status_code == 403


async def test_transfer_stock_route_success(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    location = await harness.inventory_location_service.create_location(
        nursery_id=org_id, branch_id=branch_id, location_type=__import__("app.db.enums", fromlist=["InventoryLocationType"]).InventoryLocationType.BENCH,
        name="Bench1", actor_user_id=uuid.uuid4(),
    )
    item = await _make_line(harness, nursery_id=org_id, branch_id=branch_id, initial_quantity=10)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["inventory:read", "inventory:write"])

    response = await ac.post(
        f"/api/v1/inventory/{item.id}/transfer", json={"quantity": 10, "to_location_id": str(location.id)}
    )
    assert response.status_code == 200
    assert response.json()["location_id"] == str(location.id)


async def test_reserve_and_release_routes(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    item = await _make_line(harness, nursery_id=org_id, branch_id=branch_id, initial_quantity=10)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["inventory:read", "inventory:write", "inventory:adjust"])

    reserve_response = await ac.post(f"/api/v1/inventory/{item.id}/reserve", json={"quantity": 3})
    assert reserve_response.status_code == 200
    reservation_id = reserve_response.json()["id"]

    release_response = await ac.post(f"/api/v1/stock-reservations/{reservation_id}/release")
    assert release_response.status_code == 200
    assert release_response.json()["status"] == "released"


async def test_fulfill_reservation_route(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    item = await _make_line(harness, nursery_id=org_id, branch_id=branch_id, initial_quantity=10)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["inventory:read", "inventory:write", "inventory:adjust"])

    reserve_response = await ac.post(f"/api/v1/inventory/{item.id}/reserve", json={"quantity": 3})
    reservation_id = reserve_response.json()["id"]

    fulfill_response = await ac.post(f"/api/v1/stock-reservations/{reservation_id}/fulfill", json={})
    assert fulfill_response.status_code == 200
    assert fulfill_response.json()["status"] == "fulfilled"

    inv_response = await ac.get(f"/api/v1/inventory/{item.id}")
    assert inv_response.json()["quantity"] == 7


async def test_adjust_stock_requires_adjust_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    item = await _make_line(harness, nursery_id=org_id, branch_id=branch_id, initial_quantity=10)
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=["inventory:read", "inventory:write"])

    response = await ac.post(
        f"/api/v1/inventory/{item.id}/adjust", json={"quantity_delta": 5, "reason": "correction"}
    )
    assert response.status_code == 403


async def test_adjust_stock_route_success(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    item = await _make_line(harness, nursery_id=org_id, branch_id=branch_id, initial_quantity=10)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["inventory:read", "inventory:adjust"])

    response = await ac.post(
        f"/api/v1/inventory/{item.id}/adjust", json={"quantity_delta": -3, "reason": "correction"}
    )
    assert response.status_code == 200
    assert response.json()["quantity"] == 7


async def test_damage_and_dispose_routes(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    item = await _make_line(harness, nursery_id=org_id, branch_id=branch_id, initial_quantity=10)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["inventory:read", "inventory:adjust"])

    damage_response = await ac.post(f"/api/v1/inventory/{item.id}/damage", json={"quantity": 2})
    assert damage_response.status_code == 200
    assert damage_response.json()["damaged_quantity"] == 2

    dispose_response = await ac.post(
        f"/api/v1/inventory/{item.id}/dispose", json={"quantity": 2, "from_damaged": True}
    )
    assert dispose_response.status_code == 200
    body = dispose_response.json()
    assert body["damaged_quantity"] == 0
    assert body["disposed_quantity"] == 2


async def test_sell_stock_route(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    item = await _make_line(harness, nursery_id=org_id, branch_id=branch_id, initial_quantity=10)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["inventory:read", "inventory:write"])

    response = await ac.post(f"/api/v1/inventory/{item.id}/sell", json={"quantity": 4})
    assert response.status_code == 200
    assert response.json()["quantity"] == 6


async def test_archive_route(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    item = await _make_line(harness, nursery_id=org_id, branch_id=branch_id, initial_quantity=10)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["inventory:read", "inventory:adjust"])

    response = await ac.post(f"/api/v1/inventory/{item.id}/archive", json={"reason": "season end"})
    assert response.status_code == 200
    assert response.json()["archived_at"] is not None


# ------------------------------------------------------------------
# Movements / reservations for one line
# ------------------------------------------------------------------


async def test_line_movements_and_reservations_routes(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    item = await _make_line(harness, nursery_id=org_id, branch_id=branch_id, initial_quantity=10)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["inventory:read", "inventory:write"])

    await ac.post(f"/api/v1/inventory/{item.id}/reserve", json={"quantity": 2})

    movements_response = await ac.get(f"/api/v1/inventory/{item.id}/movements")
    assert movements_response.status_code == 200
    assert movements_response.json()["meta"]["total_items"] >= 2  # initial receive + reservation

    reservations_response = await ac.get(f"/api/v1/inventory/{item.id}/reservations")
    assert reservations_response.status_code == 200
    assert len(reservations_response.json()) == 1


# ------------------------------------------------------------------
# Reports (registered before /inventory/{id} -- prove no route-shadowing bug)
# ------------------------------------------------------------------


async def test_reporting_routes(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    item = await _make_line(harness, nursery_id=org_id, branch_id=branch_id, initial_quantity=10, low_stock_threshold=50, unit_cost=1.0, unit_price=2.0)
    await harness.inventory_service.dispose_stock(inventory_id=item.id, quantity=1, actor_user_id=uuid.uuid4())
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["inventory:read"])

    summary = await ac.get("/api/v1/inventory/summary")
    assert summary.status_code == 200
    assert summary.json()["line_count"] == 1

    low_stock = await ac.get("/api/v1/inventory/low-stock")
    assert low_stock.status_code == 200
    assert len(low_stock.json()) == 1

    valuation = await ac.get("/api/v1/inventory/valuation")
    assert valuation.status_code == 200
    assert valuation.json()["total_cost_value"] == 9.0  # 9 remaining after 1 disposed

    waste = await ac.get("/api/v1/inventory/waste-report")
    assert waste.status_code == 200
    assert waste.json()["movement_count"] == 1

    transfers = await ac.get("/api/v1/inventory/transfer-report")
    assert transfers.status_code == 200

    movements = await ac.get("/api/v1/inventory/movements")
    assert movements.status_code == 200
    assert movements.json()["meta"]["total_items"] >= 2

    reservations = await ac.get("/api/v1/inventory/reservations")
    assert reservations.status_code == 200


async def test_create_inventory_line_without_org_membership_rejected(authenticated_client, harness):
    ac, user = authenticated_client
    response = await ac.post(
        "/api/v1/inventory",
        json={
            "branch_id": str(uuid.uuid4()), "category_id": str(uuid.uuid4()), "unit_id": str(uuid.uuid4()),
            "name": "X",
        },
    )
    assert response.status_code == 422


async def test_create_inventory_location_without_org_membership_rejected(authenticated_client, harness):
    ac, user = authenticated_client
    response = await ac.post(
        "/api/v1/inventory-locations",
        json={"branch_id": str(uuid.uuid4()), "location_type": "zone", "name": "Z1"},
    )
    assert response.status_code == 422


async def test_get_location_denied_without_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    location = await harness.inventory_location_service.create_location(
        nursery_id=org_id, branch_id=branch_id,
        location_type=__import__("app.db.enums", fromlist=["InventoryLocationType"]).InventoryLocationType.ZONE,
        name="Z1", actor_user_id=uuid.uuid4(),
    )
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=[])
    response = await ac.get(f"/api/v1/inventory-locations/{location.id}")
    assert response.status_code == 403


async def test_release_reservation_denied_without_permission(authenticated_client, harness):
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    item = await _make_line(harness, nursery_id=org_id, branch_id=branch_id, initial_quantity=10)
    # Reservation created directly through the service (not HTTP) so the
    # HTTP-authenticated user can be granted a no-permission role from the
    # start -- proves `_authorize_reservation`'s denied branch specifically.
    reservation = await harness.inventory_service.reserve_stock(
        inventory_id=item.id, quantity=2, actor_user_id=uuid.uuid4()
    )
    harness.grant_role(user, org_id=org_id, role_code="sales_staff", permission_codes=[])
    response = await ac.post(f"/api/v1/stock-reservations/{reservation.id}/release")
    assert response.status_code == 403


async def test_report_routes_without_org_membership_return_empty(authenticated_client, harness):
    ac, user = authenticated_client
    for path in (
        "/api/v1/inventory/summary", "/api/v1/inventory/low-stock", "/api/v1/inventory/valuation",
        "/api/v1/inventory/waste-report", "/api/v1/inventory/transfer-report", "/api/v1/inventory/movements",
        "/api/v1/inventory/reservations",
    ):
        response = await ac.get(path)
        assert response.status_code == 200, path


async def test_no_write_routes_exist_at_top_level_inventory_get(authenticated_client, harness):
    """Structural proof: PUT is never a supported method anywhere in this module."""
    ac, user = authenticated_client
    org_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    item = await _make_line(harness, nursery_id=org_id, branch_id=branch_id)
    harness.grant_role(user, org_id=org_id, role_code="owner", permission_codes=["inventory:read", "inventory:write"])

    response = await ac.put(f"/api/v1/inventory/{item.id}", json={})
    assert response.status_code == 405
