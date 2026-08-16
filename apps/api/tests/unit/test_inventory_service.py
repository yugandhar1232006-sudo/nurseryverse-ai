"""
Unit tests for Module 8's `InventoryLocationService` and `InventoryService`
-- exercised directly (not through HTTP), the same split every prior
module's unit test files use.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.enums import InventoryAdjustmentReason, InventoryLocationType, StockMovementType, StockReservationStatus
from app.models.inventory import Inventory

pytestmark = pytest.mark.unit


def _ids():
    return uuid.uuid4(), uuid.uuid4(), uuid.uuid4()  # nursery, branch, actor


async def _make_line(harness, *, nursery_id, branch_id, actor, initial_quantity=20, low_stock_threshold=5, **kw):
    return await harness.inventory_service.create_inventory_line(
        nursery_id=nursery_id, branch_id=branch_id, category_id=uuid.uuid4(), unit_id=uuid.uuid4(),
        name=kw.pop("name", "Basil 4in"), initial_quantity=initial_quantity, low_stock_threshold=low_stock_threshold,
        actor_user_id=actor, **kw,
    )


# ------------------------------------------------------------------
# InventoryLocationService
# ------------------------------------------------------------------


async def test_create_location(harness):
    nursery_id, branch_id, actor = _ids()
    location = await harness.inventory_location_service.create_location(
        nursery_id=nursery_id, branch_id=branch_id, location_type=InventoryLocationType.GREENHOUSE,
        name="GH1", actor_user_id=actor,
    )
    assert location.id is not None
    assert location.is_active is True
    fetched = await harness.inventory_location_service.get_location(location.id)
    assert fetched.name == "GH1"


async def test_create_location_blank_name_rejected(harness):
    nursery_id, branch_id, actor = _ids()
    with pytest.raises(ValidationError):
        await harness.inventory_location_service.create_location(
            nursery_id=nursery_id, branch_id=branch_id, location_type=InventoryLocationType.ZONE,
            name="   ", actor_user_id=actor,
        )


async def test_create_location_with_unknown_parent_rejected(harness):
    nursery_id, branch_id, actor = _ids()
    with pytest.raises(ValidationError):
        await harness.inventory_location_service.create_location(
            nursery_id=nursery_id, branch_id=branch_id, location_type=InventoryLocationType.BENCH,
            name="B1", parent_location_id=uuid.uuid4(), actor_user_id=actor,
        )


async def test_create_location_with_valid_parent(harness):
    nursery_id, branch_id, actor = _ids()
    parent = await harness.inventory_location_service.create_location(
        nursery_id=nursery_id, branch_id=branch_id, location_type=InventoryLocationType.GREENHOUSE,
        name="GH2", actor_user_id=actor,
    )
    child = await harness.inventory_location_service.create_location(
        nursery_id=nursery_id, branch_id=branch_id, location_type=InventoryLocationType.BENCH,
        name="Bench A", parent_location_id=parent.id, actor_user_id=actor,
    )
    assert child.parent_location_id == parent.id


async def test_get_location_not_found(harness):
    with pytest.raises(NotFoundError):
        await harness.inventory_location_service.get_location(uuid.uuid4())


async def test_list_locations_excludes_inactive_by_default(harness):
    nursery_id, branch_id, actor = _ids()
    active = await harness.inventory_location_service.create_location(
        nursery_id=nursery_id, branch_id=branch_id, location_type=InventoryLocationType.ZONE,
        name="Z1", actor_user_id=actor,
    )
    inactive = await harness.inventory_location_service.create_location(
        nursery_id=nursery_id, branch_id=branch_id, location_type=InventoryLocationType.ZONE,
        name="Z2", actor_user_id=actor,
    )
    await harness.inventory_location_service.deactivate_location(inactive.id, actor_user_id=actor)

    visible = await harness.inventory_location_service.list_locations(branch_id)
    assert [loc.id for loc in visible] == [active.id]

    all_locations = await harness.inventory_location_service.list_locations(branch_id, include_inactive=True)
    assert {loc.id for loc in all_locations} == {active.id, inactive.id}


async def test_list_units_returns_seeded_reference_data_sorted_by_name(harness):
    """
    Real defect found while building 7I (frontend): `CreateInventoryLineRequest.
    unit_id` had no route a caller could use to discover valid ids, unlike
    `category_id`'s `GET /plant-categories`. `InventoryLocationService.list_units()`
    is the fix -- mirrors `SpeciesService.list_categories()` exactly.
    """
    from app.models.catalog import Unit

    each = Unit(id=uuid.uuid4(), code="each", name="Each", unit_type="count")
    bag = Unit(id=uuid.uuid4(), code="bag", name="Bag", unit_type="count")
    harness.units.units[each.id] = each
    harness.units.units[bag.id] = bag

    units = await harness.inventory_location_service.list_units()

    assert [u.name for u in units] == ["Bag", "Each"]


async def test_deactivate_location(harness):
    nursery_id, branch_id, actor = _ids()
    location = await harness.inventory_location_service.create_location(
        nursery_id=nursery_id, branch_id=branch_id, location_type=InventoryLocationType.RACK,
        name="R1", actor_user_id=actor,
    )
    deactivated = await harness.inventory_location_service.deactivate_location(location.id, actor_user_id=actor)
    assert deactivated.is_active is False


# ------------------------------------------------------------------
# InventoryService: creation / receiving
# ------------------------------------------------------------------


async def test_create_inventory_line_with_initial_quantity_also_receives_stock(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=15)
    assert item.quantity == 15
    assert item.version == 2  # create (v1) + one receive movement (v2)
    rows, total = await harness.inventory_service.list_movements(item.id, offset=0, limit=10)
    assert total == 1
    assert rows[0].movement_type == StockMovementType.INCOMING


async def test_create_inventory_line_zero_initial_quantity_no_movement(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=0)
    assert item.quantity == 0
    assert item.version == 1
    _rows, total = await harness.inventory_service.list_movements(item.id, offset=0, limit=10)
    assert total == 0


async def test_create_inventory_line_blank_name_rejected(harness):
    nursery_id, branch_id, actor = _ids()
    with pytest.raises(ValidationError):
        await harness.inventory_service.create_inventory_line(
            nursery_id=nursery_id, branch_id=branch_id, category_id=uuid.uuid4(), unit_id=uuid.uuid4(),
            name="  ", actor_user_id=actor,
        )


async def test_create_inventory_line_duplicate_name_conflicts(harness):
    nursery_id, branch_id, actor = _ids()
    await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, name="Basil 4in")
    with pytest.raises(ConflictError) as exc:
        await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, name="Basil 4in")
    assert exc.value.context["reason"] == "duplicate_name"


async def test_create_inventory_line_negative_initial_quantity_rejected(harness):
    nursery_id, branch_id, actor = _ids()
    with pytest.raises(ValidationError):
        await harness.inventory_service.create_inventory_line(
            nursery_id=nursery_id, branch_id=branch_id, category_id=uuid.uuid4(), unit_id=uuid.uuid4(),
            name="X", initial_quantity=-1, actor_user_id=actor,
        )


async def test_receive_stock_increments_quantity_and_version(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=0)
    updated, movement = await harness.inventory_service.receive_stock(
        inventory_id=item.id, quantity=25, actor_user_id=actor,
    )
    assert updated.quantity == 25
    assert movement.quantity_delta == 25
    assert movement.quantity_after == 25


async def test_receive_stock_zero_or_negative_rejected(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor)
    with pytest.raises(ValidationError):
        await harness.inventory_service.receive_stock(inventory_id=item.id, quantity=0, actor_user_id=actor)


async def test_get_inventory_not_found(harness):
    with pytest.raises(NotFoundError):
        await harness.inventory_service.get_inventory(uuid.uuid4())


# ------------------------------------------------------------------
# Transfers
# ------------------------------------------------------------------


async def test_same_branch_transfer_moves_location_without_changing_quantity(harness):
    nursery_id, branch_id, actor = _ids()
    location = await harness.inventory_location_service.create_location(
        nursery_id=nursery_id, branch_id=branch_id, location_type=InventoryLocationType.GREENHOUSE,
        name="GH-Dest", actor_user_id=actor,
    )
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=10)
    updated, movement = await harness.inventory_service.transfer_stock(
        inventory_id=item.id, quantity=10, to_location_id=location.id, actor_user_id=actor,
    )
    assert updated.quantity == 10
    assert updated.location_id == location.id
    assert movement.movement_type == StockMovementType.TRANSFER
    assert movement.quantity_delta == 0


async def test_cross_branch_transfer_decrements_source_and_creates_destination(harness):
    nursery_id, branch_a, actor = _ids()
    branch_b = uuid.uuid4()
    source = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_a, actor=actor, initial_quantity=20)

    destination, movement = await harness.inventory_service.transfer_stock(
        inventory_id=source.id, quantity=8, to_branch_id=branch_b, actor_user_id=actor,
    )
    refreshed_source = await harness.inventory_service.get_inventory(source.id)

    assert refreshed_source.quantity == 12
    assert destination.branch_id == branch_b
    assert destination.quantity == 8
    assert destination.name == source.name
    assert movement.transfer_group_id is not None

    # Both legs of the transfer share the same group id.
    source_rows, _ = await harness.inventory_service.list_movements(source.id, offset=0, limit=10)
    transfer_leg = [m for m in source_rows if m.movement_type == StockMovementType.TRANSFER][0]
    assert transfer_leg.transfer_group_id == movement.transfer_group_id


async def test_cross_branch_transfer_reuses_existing_destination_line(harness):
    nursery_id, branch_a, actor = _ids()
    branch_b = uuid.uuid4()
    source = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_a, actor=actor, initial_quantity=20, name="Fern 6in")
    existing_dest = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_b, actor=actor, initial_quantity=3, name="Fern 6in")

    destination, _movement = await harness.inventory_service.transfer_stock(
        inventory_id=source.id, quantity=5, to_branch_id=branch_b, actor_user_id=actor,
    )
    assert destination.id == existing_dest.id
    assert destination.quantity == 8  # 3 existing + 5 transferred in


async def test_transfer_zero_quantity_rejected(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor)
    with pytest.raises(ValidationError):
        await harness.inventory_service.transfer_stock(inventory_id=item.id, quantity=0, actor_user_id=actor)


async def test_transfer_more_than_on_hand_raises_insufficient_stock(harness):
    nursery_id, branch_a, actor = _ids()
    branch_b = uuid.uuid4()
    source = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_a, actor=actor, initial_quantity=5)
    with pytest.raises(ConflictError) as exc:
        await harness.inventory_service.transfer_stock(
            inventory_id=source.id, quantity=100, to_branch_id=branch_b, actor_user_id=actor,
        )
    assert exc.value.context["reason"] == "insufficient_stock"


# ------------------------------------------------------------------
# Reservations
# ------------------------------------------------------------------


async def test_reserve_stock_increments_reserved_quantity(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=10)
    reservation = await harness.inventory_service.reserve_stock(inventory_id=item.id, quantity=4, actor_user_id=actor)
    assert reservation.status == StockReservationStatus.ACTIVE
    updated = await harness.inventory_service.get_inventory(item.id)
    assert updated.reserved_quantity == 4
    assert updated.quantity == 10  # on-hand unchanged by a reservation


async def test_reserve_more_than_available_raises_insufficient_stock(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=5)
    with pytest.raises(ConflictError) as exc:
        await harness.inventory_service.reserve_stock(inventory_id=item.id, quantity=6, actor_user_id=actor)
    assert exc.value.context["reason"] == "insufficient_stock"


async def test_release_reservation_gives_back_reserved_quantity(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=10)
    reservation = await harness.inventory_service.reserve_stock(inventory_id=item.id, quantity=4, actor_user_id=actor)

    released = await harness.inventory_service.release_reservation(reservation_id=reservation.id, actor_user_id=actor)
    assert released.status == StockReservationStatus.RELEASED
    assert released.released_at is not None
    updated = await harness.inventory_service.get_inventory(item.id)
    assert updated.reserved_quantity == 0


async def test_release_non_active_reservation_rejected(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=10)
    reservation = await harness.inventory_service.reserve_stock(inventory_id=item.id, quantity=4, actor_user_id=actor)
    await harness.inventory_service.release_reservation(reservation_id=reservation.id, actor_user_id=actor)
    with pytest.raises(ConflictError) as exc:
        await harness.inventory_service.release_reservation(reservation_id=reservation.id, actor_user_id=actor)
    assert exc.value.context["reason"] == "invalid_reservation_state"


async def test_fulfill_reservation_decrements_quantity_and_reserved(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=10)
    reservation = await harness.inventory_service.reserve_stock(inventory_id=item.id, quantity=4, actor_user_id=actor)

    fulfilled = await harness.inventory_service.fulfill_reservation(reservation_id=reservation.id, actor_user_id=actor)
    assert fulfilled.status == StockReservationStatus.FULFILLED
    updated = await harness.inventory_service.get_inventory(item.id)
    assert updated.quantity == 6
    assert updated.reserved_quantity == 0


async def test_fulfill_reservation_with_plant_id_publishes_digital_twin_linkage(harness):
    """The one narrow Digital Twin coupling point -- see inventory_service.py's module docstring."""
    from app.models.catalog import Species
    from app.models.organization import Branch

    org_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    branch = Branch(
        id=uuid.uuid4(), nursery_id=org_id, name="Main", address_line1="1 St", city="Town",
        country="US", timezone="UTC", created_at=now, updated_at=now,
    )
    species = Species(
        id=uuid.uuid4(), nursery_id=org_id, category_id=uuid.uuid4(), common_name="Fig", botanical_name="Ficus lyrata",
        created_at=now, updated_at=now,
    )
    harness.branches.branches[branch.id] = branch
    harness.species.species[species.id] = species
    plant = await harness.plant_service.register_plant(
        nursery_id=org_id, branch_id=branch.id, species_id=species.id, actor_user_id=uuid.uuid4()
    )

    item = await _make_line(harness, nursery_id=org_id, branch_id=branch.id, actor=uuid.uuid4(), initial_quantity=10)
    reservation = await harness.inventory_service.reserve_stock(inventory_id=item.id, quantity=1, actor_user_id=uuid.uuid4())

    await harness.inventory_service.fulfill_reservation(
        reservation_id=reservation.id, plant_id=plant.id, actor_user_id=uuid.uuid4()
    )

    twin = await harness.digital_twin_service.get_current_twin(plant.id)
    assert twin.snapshot["counts"]["inventory_movements"] == 1
    assert twin.snapshot["latest"]["inventory_movement"]["inventory_id"] == str(item.id)


async def test_sell_stock_direct_decrements_quantity(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=10)
    updated, movement = await harness.inventory_service.sell_stock_direct(
        inventory_id=item.id, quantity=3, actor_user_id=actor,
    )
    assert updated.quantity == 7
    assert movement.movement_type == StockMovementType.SALE


# ------------------------------------------------------------------
# Damage / Waste / Adjustment / Archive
# ------------------------------------------------------------------


async def test_mark_damaged_does_not_change_quantity(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=10)
    updated, movement = await harness.inventory_service.mark_damaged(
        inventory_id=item.id, quantity=3, actor_user_id=actor,
    )
    assert updated.quantity == 10
    assert updated.damaged_quantity == 3
    assert movement.movement_type == StockMovementType.DAMAGE


async def test_dispose_stock_from_damaged_decrements_both(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=10)
    await harness.inventory_service.mark_damaged(inventory_id=item.id, quantity=3, actor_user_id=actor)
    updated, movement = await harness.inventory_service.dispose_stock(
        inventory_id=item.id, quantity=3, from_damaged=True, actor_user_id=actor,
    )
    assert updated.quantity == 7
    assert updated.damaged_quantity == 0
    assert updated.disposed_quantity == 3
    assert movement.movement_type == StockMovementType.WASTE


async def test_dispose_stock_not_from_damaged_only_decrements_quantity(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=10)
    updated, _movement = await harness.inventory_service.dispose_stock(
        inventory_id=item.id, quantity=2, actor_user_id=actor,
    )
    assert updated.quantity == 8
    assert updated.damaged_quantity == 0
    assert updated.disposed_quantity == 2


async def test_adjust_stock_zero_delta_rejected(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor)
    with pytest.raises(ValidationError):
        await harness.inventory_service.adjust_stock(
            inventory_id=item.id, quantity_delta=0, reason=InventoryAdjustmentReason.CORRECTION, actor_user_id=actor,
        )


async def test_adjust_stock_negative_resulting_quantity_rejected(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=5)
    with pytest.raises(ConflictError):
        await harness.inventory_service.adjust_stock(
            inventory_id=item.id, quantity_delta=-10, reason=InventoryAdjustmentReason.CORRECTION, actor_user_id=actor,
        )


async def test_adjust_stock_positive_delta(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=5)
    updated, movement = await harness.inventory_service.adjust_stock(
        inventory_id=item.id, quantity_delta=10, reason=InventoryAdjustmentReason.CORRECTION, actor_user_id=actor,
    )
    assert updated.quantity == 15
    assert movement.reason == InventoryAdjustmentReason.CORRECTION


async def test_archive_inventory_line_is_idempotent(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor)
    archived = await harness.inventory_service.archive_inventory_line(inventory_id=item.id, actor_user_id=actor)
    assert archived.archived_at is not None
    again = await harness.inventory_service.archive_inventory_line(inventory_id=item.id, actor_user_id=actor)
    assert again.archived_at == archived.archived_at


async def test_archived_lines_excluded_from_default_listing(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor)
    await harness.inventory_service.archive_inventory_line(inventory_id=item.id, actor_user_id=actor)

    rows, total = await harness.inventory_service.list_inventory(nursery_id, offset=0, limit=10, branch_id=branch_id)
    assert total == 0

    rows, total = await harness.inventory_service.list_inventory(
        nursery_id, offset=0, limit=10, branch_id=branch_id, include_archived=True
    )
    assert total == 1


# ------------------------------------------------------------------
# Concurrency (optimistic locking) -- see FakeInventoryRepository's own
# docstring: single-threaded fakes can't reproduce a true concurrent
# write race, only the version-mismatch *logic* itself, exactly like
# Module 7's own documented disclosure for its replay/idempotency tests.
# ------------------------------------------------------------------


async def test_stale_version_write_raises_conflict_error(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=10)

    # "Reader 2" captured the inventory line at its version *before* "writer 1" ran.
    stale_copy = Inventory(
        id=item.id, nursery_id=item.nursery_id, branch_id=item.branch_id, category_id=item.category_id,
        unit_id=item.unit_id, name=item.name, quantity=item.quantity, reserved_quantity=0, damaged_quantity=0,
        disposed_quantity=0, low_stock_threshold=item.low_stock_threshold, version=item.version,
    )

    # Writer 1 succeeds and bumps the real row's version.
    await harness.inventory_service.adjust_stock(
        inventory_id=item.id, quantity_delta=5, reason=InventoryAdjustmentReason.CORRECTION, actor_user_id=actor,
    )

    # Writer 2 (stale) attempts a change against the version it originally read.
    with pytest.raises(ConflictError) as exc:
        await harness.inventory_service._apply_change(
            stale_copy, movement_type=StockMovementType.ADJUSTMENT, quantity_delta=1, actor_user_id=actor,
        )
    assert exc.value.context["reason"] == "version_conflict"


async def test_apply_change_rejects_negative_damaged_or_disposed(harness):
    nursery_id, branch_id, actor = _ids()
    item = await harness.inventory_service.get_inventory(
        (await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=10)).id
    )
    with pytest.raises(ValidationError):
        await harness.inventory_service._apply_change(
            item, movement_type=StockMovementType.WASTE, damaged_delta=-1, actor_user_id=actor,
        )


# ------------------------------------------------------------------
# Reporting
# ------------------------------------------------------------------


async def test_inventory_summary_aggregates_across_lines(harness):
    nursery_id, branch_id, actor = _ids()
    await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=10, name="A", unit_cost=1.0)
    await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=20, name="B", unit_cost=2.0)

    summary = await harness.inventory_service.inventory_summary(nursery_id, branch_id=branch_id)
    assert summary["line_count"] == 2
    assert summary["total_quantity"] == 30
    assert summary["total_valuation"] == 10 * 1.0 + 20 * 2.0


async def test_low_stock_report_returns_only_lines_at_or_below_threshold(harness):
    nursery_id, branch_id, actor = _ids()
    low = await _make_line(
        harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=2, low_stock_threshold=5, name="Low"
    )
    await _make_line(
        harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=50, low_stock_threshold=5, name="High"
    )
    report = await harness.inventory_service.low_stock_report(nursery_id, branch_id=branch_id)
    assert [item.id for item in report] == [low.id]


async def test_waste_report_sums_disposed_quantity(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=10)
    await harness.inventory_service.dispose_stock(inventory_id=item.id, quantity=2, actor_user_id=actor)
    await harness.inventory_service.dispose_stock(inventory_id=item.id, quantity=3, actor_user_id=actor)

    report = await harness.inventory_service.waste_report(nursery_id, branch_id=branch_id)
    assert report["movement_count"] == 2
    assert report["total_quantity_disposed"] == 5


async def test_transfer_report_lists_transfer_movements(harness):
    nursery_id, branch_a, actor = _ids()
    branch_b = uuid.uuid4()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_a, actor=actor, initial_quantity=10)
    await harness.inventory_service.transfer_stock(inventory_id=item.id, quantity=4, to_branch_id=branch_b, actor_user_id=actor)

    report = await harness.inventory_service.transfer_report(nursery_id)
    assert report["movement_count"] >= 1


async def test_stock_valuation_computes_cost_and_retail(harness):
    nursery_id, branch_id, actor = _ids()
    await _make_line(
        harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=10, name="X",
        unit_cost=1.5, unit_price=4.0,
    )
    valuation = await harness.inventory_service.stock_valuation(nursery_id, branch_id=branch_id)
    assert valuation["total_cost_value"] == 15.0
    assert valuation["total_retail_value"] == 40.0
    assert valuation["potential_margin"] == 25.0


async def test_reservation_report_lists_only_active(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=10)
    reservation = await harness.inventory_service.reserve_stock(inventory_id=item.id, quantity=2, actor_user_id=actor)
    other = await harness.inventory_service.reserve_stock(inventory_id=item.id, quantity=1, actor_user_id=actor)
    await harness.inventory_service.release_reservation(reservation_id=other.id, actor_user_id=actor)

    rows, total = await harness.inventory_service.reservation_report(nursery_id, branch_id=branch_id)
    assert total == 1
    assert rows[0].id == reservation.id


async def test_get_reservation_not_found(harness):
    with pytest.raises(NotFoundError):
        await harness.inventory_service.get_reservation(uuid.uuid4())


async def test_create_inventory_line_with_unknown_location_rejected(harness):
    nursery_id, branch_id, actor = _ids()
    with pytest.raises(ValidationError):
        await harness.inventory_service.create_inventory_line(
            nursery_id=nursery_id, branch_id=branch_id, category_id=uuid.uuid4(), unit_id=uuid.uuid4(),
            name="X", location_id=uuid.uuid4(), actor_user_id=actor,
        )


async def test_same_branch_transfer_with_unknown_location_rejected(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=10)
    with pytest.raises(ValidationError):
        await harness.inventory_service.transfer_stock(
            inventory_id=item.id, quantity=5, to_location_id=uuid.uuid4(), actor_user_id=actor,
        )


async def test_reserve_stock_zero_quantity_rejected(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=10)
    with pytest.raises(ValidationError):
        await harness.inventory_service.reserve_stock(inventory_id=item.id, quantity=0, actor_user_id=actor)


async def test_fulfill_non_active_reservation_rejected(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=10)
    reservation = await harness.inventory_service.reserve_stock(inventory_id=item.id, quantity=2, actor_user_id=actor)
    await harness.inventory_service.fulfill_reservation(reservation_id=reservation.id, actor_user_id=actor)
    with pytest.raises(ConflictError) as exc:
        await harness.inventory_service.fulfill_reservation(reservation_id=reservation.id, actor_user_id=actor)
    assert exc.value.context["reason"] == "invalid_reservation_state"


async def test_sell_stock_direct_zero_quantity_rejected(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=10)
    with pytest.raises(ValidationError):
        await harness.inventory_service.sell_stock_direct(inventory_id=item.id, quantity=0, actor_user_id=actor)


async def test_mark_damaged_zero_quantity_rejected(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=10)
    with pytest.raises(ValidationError):
        await harness.inventory_service.mark_damaged(inventory_id=item.id, quantity=0, actor_user_id=actor)


async def test_dispose_stock_zero_quantity_rejected(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=10)
    with pytest.raises(ValidationError):
        await harness.inventory_service.dispose_stock(inventory_id=item.id, quantity=0, actor_user_id=actor)


async def test_release_more_than_reserved_raises_insufficient_stock(harness):
    """Exercises `_apply_change`'s `new_reserved < 0` guard directly -- unreachable through the public release/fulfill
    methods (they always release exactly what was reserved), but a real defensive invariant worth its own proof."""
    nursery_id, branch_id, actor = _ids()
    item = await harness.inventory_service.get_inventory(
        (await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=10)).id
    )
    with pytest.raises(ConflictError) as exc:
        await harness.inventory_service._apply_change(
            item, movement_type=StockMovementType.RELEASE, reserved_delta=-5, actor_user_id=actor,
        )
    assert exc.value.context["reason"] == "insufficient_stock"


async def test_movement_history_filters_by_type(harness):
    nursery_id, branch_id, actor = _ids()
    item = await _make_line(harness, nursery_id=nursery_id, branch_id=branch_id, actor=actor, initial_quantity=10)
    await harness.inventory_service.adjust_stock(
        inventory_id=item.id, quantity_delta=1, reason=InventoryAdjustmentReason.CORRECTION, actor_user_id=actor
    )
    rows, total = await harness.inventory_service.movement_history(
        nursery_id, offset=0, limit=10, movement_type=StockMovementType.ADJUSTMENT
    )
    assert total == 1
    assert rows[0].movement_type == StockMovementType.ADJUSTMENT
