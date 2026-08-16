"""
Module 8 (Inventory & Stock Management) -- `InventoryLocationService`
(Location Management) and `InventoryService` (the bulk-stock bounded
context: Receiving, Transfers, Reservations, Waste, Damage, Adjustment,
Sale-decrement, Archive, plus Reporting/Search).

Bounded-context boundary (see app/models/inventory.py's module docstring
for the full reasoning): this service NEVER reads or writes a `plants`
row, and never subscribes to Plant lifecycle domain events. The one
narrow, deliberate coupling point to the Digital Twin (Module 7) is
`InventoryMovementRecorded` -- published only when a caller explicitly
attaches a `plant_id` to a stock movement (the rare "plant demoted from
individual tracking" case docs/ux/16-inventory-workflow.md's own
flowchart documents), never inferred automatically.

Single write-path pattern (LLD's "Module: Inventory" -- `InventoryService.
apply_change()` is the sole write path other modules call, never direct
row updates): every public mutation method below funnels through
`_apply_change()`, which is the only place `Inventory.quantity`/
`reserved_quantity`/`damaged_quantity`/`disposed_quantity` are ever
written, and which always pairs the mutation with exactly one immutable
`StockMovement` row in the same call.

Concurrency: "minimal locking" (the module's own requirement) is met with
optimistic concurrency, not a pessimistic `SELECT ... FOR UPDATE` held for
the request's duration -- `InventoryRepository.update()` conditions the
write on `version` and returns `None` if another writer got there first,
which `_apply_change()` turns into `ConflictError` (context reason
"version_conflict") for the caller to retry. This trades a rare, cheap
retry-the-request for never blocking a concurrent reader/writer on a held
row lock, which is the right tradeoff for a bulk-stock ledger that's
written far more often, by far more concurrent branch staff, than an
individual Plant record ever is.

`InsufficientStockError` (the LLD's own named error, "typed, 409"): this
codebase's exception hierarchy is deliberately closed (app/core/
exceptions.py's own docstring: "a small, closed hierarchy of categories,
not one exception per business rule") -- satisfied here by raising the
existing `ConflictError` (already 409) with `context={"reason":
"insufficient_stock", ...}`, the same discriminated-context pattern every
other module's "typed" error already uses (e.g. `cross_tenant_org` on
`PermissionDeniedError`), not a new subclass.

Authorization: like every module since Module 6, this service contains
NO `AuthorizationService` calls -- `AuthorizationService.authorize()` is
called at the route layer (app/api/routes/inventory.py), branch-scoped,
before a service method is ever invoked. Services receive an
already-authorized `nursery_id`/`branch_id`/`actor_user_id`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.enums import InventoryAdjustmentReason, InventoryLocationType, StockMovementType, StockReservationStatus
from app.domain_events import (
    DomainEventPublisher,
    InventoryArchived,
    InventoryLocationCreated,
    InventoryMovementRecorded,
    StockAdjusted,
    StockDamaged,
    StockDisposed,
    StockReceived,
    StockReleased,
    StockReserved,
    StockSold,
    StockTransferred,
)
from app.models.catalog import Unit
from app.models.inventory import Inventory, InventoryLocation, StockMovement, StockReservation
from app.models.platform import AuditLog
from app.repositories.interfaces import (
    AuditLogRepository,
    InventoryLocationRepository,
    InventoryRepository,
    StockMovementRepository,
    StockReservationRepository,
    UnitRepository,
)


def _as_float(value: object) -> float:
    """
    `Inventory.unit_cost`/`unit_price` (and every other Numeric column in
    this codebase, e.g. commerce.py's/purchasing.py's own money columns)
    are declared `Mapped[Numeric | None]` -- reusing the SQLAlchemy
    `Numeric` *type engine* class as the Python-side annotation, a
    pre-existing Phase 5 imprecision (the real runtime value is a
    `decimal.Decimal`) that predates this module and spans several other
    models' files, so it's not fixed here as a side effect of Module 8's
    own reporting code. This module is simply the first caller to do
    arithmetic with one of these columns, which is what surfaces it to
    mypy. One centralized, documented `# type: ignore` beats scattering
    the same suppression at every call site below.
    """
    return float(value or 0)  # type: ignore[arg-type]


class InventoryLocationService:
    """
    `unit_repo` is a second, unrelated piece of read-only reference data
    (`GET /units`) riding along on this service rather than getting its
    own single-method service class -- the same "doesn't warrant its own
    service" judgment call `SpeciesService.list_categories()` already made
    for `GET /plant-categories`. It's wired here (not on `InventoryService`)
    because this service is already the home for Module 8's other pure
    reference-data read (`list_locations`), and `InventoryService`'s
    constructor is depended on by several other modules' services
    (SalesOrderService, ReturnService, AssistantToolRegistry) that have no
    reason to also carry a `UnitRepository`.
    """

    def __init__(
        self,
        *,
        location_repo: InventoryLocationRepository,
        unit_repo: UnitRepository,
        audit_repo: AuditLogRepository,
        event_publisher: DomainEventPublisher,
    ) -> None:
        self._locations = location_repo
        self._units = unit_repo
        self._audit = audit_repo
        self._events = event_publisher

    async def create_location(
        self,
        *,
        nursery_id: uuid.UUID,
        branch_id: uuid.UUID,
        location_type: InventoryLocationType,
        name: str,
        code: str | None = None,
        parent_location_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None,
        request_id: str | None = None,
    ) -> InventoryLocation:
        if not name or not name.strip():
            raise ValidationError("Location name is required.")
        if parent_location_id is not None:
            parent = await self._locations.get_by_id(parent_location_id)
            if parent is None or parent.branch_id != branch_id:
                raise ValidationError(f"'{parent_location_id}' is not a recognized location in this branch.")

        location = InventoryLocation(
            nursery_id=nursery_id,
            branch_id=branch_id,
            parent_location_id=parent_location_id,
            location_type=location_type,
            name=name.strip(),
            code=code,
            is_active=True,
        )
        location = await self._locations.add(location)

        await self._audit.log(
            AuditLog(
                nursery_id=nursery_id, actor_user_id=actor_user_id, action="inventory_location.created",
                entity_type="InventoryLocation", entity_id=location.id,
                diff={"after": {"name": location.name, "location_type": location_type.value, "branch_id": str(branch_id)}},
                request_id=request_id, created_at=datetime.now(timezone.utc),
            )
        )
        await self._events.publish(
            InventoryLocationCreated(
                aggregate_id=location.id, nursery_id=nursery_id, actor_user_id=actor_user_id,
                branch_id=branch_id, location_type=location_type.value, name=location.name,
                parent_location_id=parent_location_id,
            ),
            request_id=request_id,
        )
        return location

    async def get_location(self, location_id: uuid.UUID) -> InventoryLocation:
        location = await self._locations.get_by_id(location_id)
        if location is None:
            raise NotFoundError(f"Inventory location '{location_id}' not found.")
        return location

    async def list_locations(self, branch_id: uuid.UUID, *, include_inactive: bool = False) -> list[InventoryLocation]:
        return await self._locations.list_for_branch(branch_id, include_inactive=include_inactive)

    async def deactivate_location(
        self, location_id: uuid.UUID, *, actor_user_id: uuid.UUID | None, request_id: str | None = None
    ) -> InventoryLocation:
        location = await self.get_location(location_id)
        location.is_active = False
        location = await self._locations.update(location)
        await self._audit.log(
            AuditLog(
                nursery_id=location.nursery_id, actor_user_id=actor_user_id, action="inventory_location.deactivated",
                entity_type="InventoryLocation", entity_id=location.id, diff={"after": {"is_active": False}},
                request_id=request_id, created_at=datetime.now(timezone.utc),
            )
        )
        return location

    async def list_units(self) -> list[Unit]:
        return await self._units.list_all()


class InventoryService:
    def __init__(
        self,
        *,
        inventory_repo: InventoryRepository,
        location_repo: InventoryLocationRepository,
        movement_repo: StockMovementRepository,
        reservation_repo: StockReservationRepository,
        audit_repo: AuditLogRepository,
        event_publisher: DomainEventPublisher,
    ) -> None:
        self._inventory = inventory_repo
        self._locations = location_repo
        self._movements = movement_repo
        self._reservations = reservation_repo
        self._audit = audit_repo
        self._events = event_publisher

    # ------------------------------------------------------------------
    # The one write path.
    # ------------------------------------------------------------------

    async def _apply_change(
        self,
        inventory: Inventory,
        *,
        movement_type: StockMovementType,
        quantity_delta: int = 0,
        reserved_delta: int = 0,
        damaged_delta: int = 0,
        disposed_delta: int = 0,
        reason: InventoryAdjustmentReason | None = None,
        from_location_id: uuid.UUID | None = None,
        to_location_id: uuid.UUID | None = None,
        move_location: bool = False,
        plant_id: uuid.UUID | None = None,
        reservation_id: uuid.UUID | None = None,
        transfer_group_id: uuid.UUID | None = None,
        reference_sale_id: uuid.UUID | None = None,
        reference_purchase_order_id: uuid.UUID | None = None,
        note: str | None = None,
        actor_user_id: uuid.UUID | None,
    ) -> tuple[Inventory, StockMovement]:
        new_quantity = inventory.quantity + quantity_delta
        new_reserved = inventory.reserved_quantity + reserved_delta
        new_damaged = inventory.damaged_quantity + damaged_delta
        new_disposed = inventory.disposed_quantity + disposed_delta

        if new_quantity < 0:
            raise ConflictError(
                f"Insufficient stock on inventory line '{inventory.id}': "
                f"{-quantity_delta} requested, {inventory.quantity} on hand.",
                context={"reason": "insufficient_stock", "inventory_id": str(inventory.id)},
            )
        if new_reserved < 0:
            raise ConflictError(
                f"Cannot release/fulfill more than is currently reserved on inventory line '{inventory.id}'.",
                context={"reason": "insufficient_stock", "inventory_id": str(inventory.id)},
            )
        if new_damaged < 0 or new_disposed < 0:
            raise ValidationError("Resulting damaged/disposed quantity cannot be negative.")
        if new_reserved + new_damaged > new_quantity:
            raise ConflictError(
                f"Insufficient available stock on inventory line '{inventory.id}' for this reservation/damage change.",
                context={"reason": "insufficient_stock", "inventory_id": str(inventory.id)},
            )

        expected_version = inventory.version
        inventory.quantity = new_quantity
        inventory.reserved_quantity = new_reserved
        inventory.damaged_quantity = new_damaged
        inventory.disposed_quantity = new_disposed
        if move_location:
            inventory.location_id = to_location_id

        updated = await self._inventory.update(inventory, expected_version=expected_version)
        if updated is None:
            raise ConflictError(
                f"Inventory line '{inventory.id}' was modified concurrently by another request -- retry.",
                context={"reason": "version_conflict", "inventory_id": str(inventory.id)},
            )

        movement = await self._movements.add(
            StockMovement(
                inventory_id=updated.id,
                movement_type=movement_type,
                quantity_delta=quantity_delta,
                quantity_after=updated.quantity,
                reason=reason,
                from_location_id=from_location_id,
                to_location_id=to_location_id,
                plant_id=plant_id,
                reservation_id=reservation_id,
                transfer_group_id=transfer_group_id,
                reference_sale_id=reference_sale_id,
                reference_purchase_order_id=reference_purchase_order_id,
                note=note,
                performed_by_user_id=actor_user_id,
            )
        )
        return updated, movement

    async def _publish_movement_link(
        self, *, movement: StockMovement, nursery_id: uuid.UUID, actor_user_id: uuid.UUID | None, request_id: str | None
    ) -> None:
        """The one, narrow Digital Twin coupling point -- see module docstring."""
        if movement.plant_id is None:
            return
        await self._events.publish(
            InventoryMovementRecorded(
                aggregate_id=movement.plant_id, nursery_id=nursery_id, actor_user_id=actor_user_id,
                movement_id=movement.id, inventory_id=movement.inventory_id,
                movement_type=movement.movement_type.value, quantity=abs(movement.quantity_delta),
            ),
            request_id=request_id,
        )

    async def _log_audit(
        self, *, nursery_id: uuid.UUID, actor_user_id: uuid.UUID | None, action: str, entity_id: uuid.UUID,
        diff: dict, request_id: str | None,
    ) -> None:
        await self._audit.log(
            AuditLog(
                nursery_id=nursery_id, actor_user_id=actor_user_id, action=action, entity_type="Inventory",
                entity_id=entity_id, diff=diff, request_id=request_id, created_at=datetime.now(timezone.utc),
            )
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_inventory(self, inventory_id: uuid.UUID) -> Inventory:
        item = await self._inventory.get_by_id(inventory_id)
        if item is None:
            raise NotFoundError(f"Inventory line '{inventory_id}' not found.")
        return item

    async def list_inventory(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        branch_id: uuid.UUID | None = None,
        category_id: uuid.UUID | None = None,
        species_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        search: str | None = None,
        low_stock_only: bool = False,
        include_archived: bool = False,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> tuple[list[Inventory], int]:
        return await self._inventory.list_for_nursery(
            nursery_id, offset=offset, limit=limit, branch_id=branch_id, category_id=category_id,
            species_id=species_id, location_id=location_id, search=search, low_stock_only=low_stock_only,
            include_archived=include_archived, sort_by=sort_by, sort_dir=sort_dir,
        )

    async def list_movements(
        self, inventory_id: uuid.UUID, *, offset: int, limit: int,
        movement_type: StockMovementType | None = None, sort_dir: str = "desc",
    ) -> tuple[list[StockMovement], int]:
        return await self._movements.list_for_inventory(
            inventory_id, offset=offset, limit=limit, movement_type=movement_type, sort_dir=sort_dir
        )

    async def list_reservations(
        self, inventory_id: uuid.UUID, *, status: StockReservationStatus | None = None
    ) -> list[StockReservation]:
        return await self._reservations.list_for_inventory(inventory_id, status=status)

    async def get_reservation(self, reservation_id: uuid.UUID) -> StockReservation:
        reservation = await self._reservations.get_by_id(reservation_id)
        if reservation is None:
            raise NotFoundError(f"Stock reservation '{reservation_id}' not found.")
        return reservation

    # ------------------------------------------------------------------
    # Creation / Receiving
    # ------------------------------------------------------------------

    async def create_inventory_line(
        self,
        *,
        nursery_id: uuid.UUID,
        branch_id: uuid.UUID,
        category_id: uuid.UUID,
        unit_id: uuid.UUID,
        name: str,
        species_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        unit_cost: float | None = None,
        unit_price: float | None = None,
        low_stock_threshold: int = 10,
        initial_quantity: int = 0,
        actor_user_id: uuid.UUID | None,
        request_id: str | None = None,
    ) -> Inventory:
        """PG-36 "Create inventory line" -- manual initial stock entry, per docs/ux/16-inventory-workflow.md's flowchart."""
        if not name or not name.strip():
            raise ValidationError("Inventory line name is required.")
        if initial_quantity < 0:
            raise ValidationError("initial_quantity cannot be negative.")
        existing = await self._inventory.get_by_branch_and_name(branch_id, name.strip())
        if existing is not None:
            raise ConflictError(
                f"An inventory line named '{name}' already exists for this branch.",
                context={"reason": "duplicate_name", "inventory_id": str(existing.id)},
            )
        if location_id is not None:
            location = await self._locations.get_by_id(location_id)
            if location is None or location.branch_id != branch_id:
                raise ValidationError(f"'{location_id}' is not a recognized location in this branch.")

        inventory = Inventory(
            nursery_id=nursery_id, branch_id=branch_id, category_id=category_id, unit_id=unit_id,
            species_id=species_id, location_id=location_id, name=name.strip(), quantity=0,
            reserved_quantity=0, damaged_quantity=0, disposed_quantity=0,
            unit_cost=unit_cost, unit_price=unit_price, low_stock_threshold=low_stock_threshold, version=1,
        )
        inventory = await self._inventory.add(inventory)

        await self._log_audit(
            nursery_id=nursery_id, actor_user_id=actor_user_id, action="inventory.line_created",
            entity_id=inventory.id, diff={"after": {"name": inventory.name, "branch_id": str(branch_id)}},
            request_id=request_id,
        )

        if initial_quantity > 0:
            inventory, _movement = await self.receive_stock(
                inventory_id=inventory.id, quantity=initial_quantity, actor_user_id=actor_user_id,
                request_id=request_id,
            )
        return inventory

    async def receive_stock(
        self,
        *,
        inventory_id: uuid.UUID,
        quantity: int,
        to_location_id: uuid.UUID | None = None,
        reference_purchase_order_id: uuid.UUID | None = None,
        note: str | None = None,
        actor_user_id: uuid.UUID | None,
        request_id: str | None = None,
    ) -> tuple[Inventory, StockMovement]:
        if quantity <= 0:
            raise ValidationError("Received quantity must be positive.")
        inventory = await self.get_inventory(inventory_id)
        updated, movement = await self._apply_change(
            inventory, movement_type=StockMovementType.INCOMING, quantity_delta=quantity,
            to_location_id=to_location_id, move_location=to_location_id is not None,
            reason=InventoryAdjustmentReason.PURCHASE_ORDER_RECEIPT if reference_purchase_order_id else None,
            reference_purchase_order_id=reference_purchase_order_id, note=note, actor_user_id=actor_user_id,
        )
        await self._log_audit(
            nursery_id=updated.nursery_id, actor_user_id=actor_user_id, action="inventory.stock_received",
            entity_id=updated.id, diff={"quantity_delta": quantity, "quantity_after": updated.quantity},
            request_id=request_id,
        )
        await self._events.publish(
            StockReceived(
                aggregate_id=updated.id, nursery_id=updated.nursery_id, actor_user_id=actor_user_id,
                movement_id=movement.id, quantity=quantity, quantity_after=updated.quantity,
                to_location_id=to_location_id, reference_purchase_order_id=reference_purchase_order_id,
            ),
            request_id=request_id,
        )
        return updated, movement

    # ------------------------------------------------------------------
    # Transfers
    # ------------------------------------------------------------------

    async def transfer_stock(
        self,
        *,
        inventory_id: uuid.UUID,
        quantity: int,
        to_location_id: uuid.UUID | None = None,
        to_branch_id: uuid.UUID | None = None,
        note: str | None = None,
        actor_user_id: uuid.UUID | None,
        request_id: str | None = None,
    ) -> tuple[Inventory, StockMovement]:
        """
        Two shapes, both going through this one method: a same-branch
        location move (`to_branch_id` omitted -- one Inventory row, one
        StockMovement, `location_id` updated in place) or a cross-branch
        transfer (`to_branch_id` given -- the source line is decremented,
        a destination line is found-or-created in the target branch and
        incremented, and both StockMovement rows share one
        `transfer_group_id` correlating them as one logical transfer).
        """
        if quantity <= 0:
            raise ValidationError("Transfer quantity must be positive.")
        source = await self.get_inventory(inventory_id)
        if to_branch_id is None or to_branch_id == source.branch_id:
            if to_location_id is not None:
                location = await self._locations.get_by_id(to_location_id)
                if location is None or location.branch_id != source.branch_id:
                    raise ValidationError(f"'{to_location_id}' is not a recognized location in this branch.")
            group_id = uuid.uuid4()
            updated, movement = await self._apply_change(
                source, movement_type=StockMovementType.TRANSFER, quantity_delta=0,
                from_location_id=source.location_id, to_location_id=to_location_id,
                move_location=to_location_id is not None, transfer_group_id=group_id, note=note,
                actor_user_id=actor_user_id,
            )
            await self._log_audit(
                nursery_id=updated.nursery_id, actor_user_id=actor_user_id, action="inventory.stock_transferred",
                entity_id=updated.id, diff={"to_location_id": str(to_location_id) if to_location_id else None},
                request_id=request_id,
            )
            await self._events.publish(
                StockTransferred(
                    aggregate_id=updated.id, nursery_id=updated.nursery_id, actor_user_id=actor_user_id,
                    movement_id=movement.id, quantity=quantity, transfer_group_id=group_id,
                    from_location_id=movement.from_location_id, to_location_id=to_location_id,
                ),
                request_id=request_id,
            )
            return updated, movement

        # Cross-branch: decrement source, find-or-create + increment destination.
        group_id = uuid.uuid4()
        updated_source, source_movement = await self._apply_change(
            source, movement_type=StockMovementType.TRANSFER, quantity_delta=-quantity,
            from_location_id=source.location_id, transfer_group_id=group_id, note=note,
            actor_user_id=actor_user_id,
        )
        await self._log_audit(
            nursery_id=updated_source.nursery_id, actor_user_id=actor_user_id, action="inventory.stock_transferred_out",
            entity_id=updated_source.id, diff={"quantity_delta": -quantity, "to_branch_id": str(to_branch_id)},
            request_id=request_id,
        )
        await self._events.publish(
            StockTransferred(
                aggregate_id=updated_source.id, nursery_id=updated_source.nursery_id, actor_user_id=actor_user_id,
                movement_id=source_movement.id, quantity=quantity, transfer_group_id=group_id,
                from_location_id=source.location_id, destination_inventory_id=None,
            ),
            request_id=request_id,
        )

        destination = await self._inventory.get_by_branch_and_name(to_branch_id, source.name)
        if destination is None:
            destination = await self._inventory.add(
                Inventory(
                    nursery_id=source.nursery_id, branch_id=to_branch_id, category_id=source.category_id,
                    unit_id=source.unit_id, species_id=source.species_id, location_id=to_location_id,
                    name=source.name, quantity=0, reserved_quantity=0, damaged_quantity=0, disposed_quantity=0,
                    unit_cost=source.unit_cost, unit_price=source.unit_price,
                    low_stock_threshold=source.low_stock_threshold, version=1,
                )
            )
        updated_destination, dest_movement = await self._apply_change(
            destination, movement_type=StockMovementType.TRANSFER, quantity_delta=quantity,
            to_location_id=to_location_id, move_location=to_location_id is not None,
            transfer_group_id=group_id, note=note, actor_user_id=actor_user_id,
        )
        await self._log_audit(
            nursery_id=updated_destination.nursery_id, actor_user_id=actor_user_id, action="inventory.stock_transferred_in",
            entity_id=updated_destination.id, diff={"quantity_delta": quantity, "from_inventory_id": str(source.id)},
            request_id=request_id,
        )
        await self._events.publish(
            StockTransferred(
                aggregate_id=updated_destination.id, nursery_id=updated_destination.nursery_id, actor_user_id=actor_user_id,
                movement_id=dest_movement.id, quantity=quantity, transfer_group_id=group_id,
                to_location_id=to_location_id, destination_inventory_id=updated_destination.id,
            ),
            request_id=request_id,
        )
        return updated_destination, dest_movement

    # ------------------------------------------------------------------
    # Reservations
    # ------------------------------------------------------------------

    async def reserve_stock(
        self,
        *,
        inventory_id: uuid.UUID,
        quantity: int,
        reference_type: str | None = None,
        reference_id: uuid.UUID | None = None,
        expires_at: datetime | None = None,
        note: str | None = None,
        actor_user_id: uuid.UUID | None,
        request_id: str | None = None,
    ) -> StockReservation:
        if quantity <= 0:
            raise ValidationError("Reservation quantity must be positive.")
        inventory = await self.get_inventory(inventory_id)

        reservation = await self._reservations.add(
            StockReservation(
                nursery_id=inventory.nursery_id, branch_id=inventory.branch_id, inventory_id=inventory.id,
                quantity=quantity, status=StockReservationStatus.ACTIVE, reference_type=reference_type,
                reference_id=reference_id, reserved_by_user_id=actor_user_id, expires_at=expires_at, note=note,
            )
        )
        updated, movement = await self._apply_change(
            inventory, movement_type=StockMovementType.RESERVATION, reserved_delta=quantity,
            reservation_id=reservation.id, note=note, actor_user_id=actor_user_id,
        )
        await self._log_audit(
            nursery_id=updated.nursery_id, actor_user_id=actor_user_id, action="inventory.stock_reserved",
            entity_id=updated.id, diff={"quantity": quantity, "reservation_id": str(reservation.id)},
            request_id=request_id,
        )
        await self._events.publish(
            StockReserved(
                aggregate_id=updated.id, nursery_id=updated.nursery_id, actor_user_id=actor_user_id,
                reservation_id=reservation.id, quantity=quantity, reference_type=reference_type,
                reference_id=reference_id,
            ),
            request_id=request_id,
        )
        return reservation

    async def release_reservation(
        self, *, reservation_id: uuid.UUID, actor_user_id: uuid.UUID | None, request_id: str | None = None
    ) -> StockReservation:
        reservation = await self.get_reservation(reservation_id)
        if reservation.status != StockReservationStatus.ACTIVE:
            raise ConflictError(
                f"Reservation '{reservation_id}' is not active (status={reservation.status.value}).",
                context={"reason": "invalid_reservation_state"},
            )
        inventory = await self.get_inventory(reservation.inventory_id)
        updated, movement = await self._apply_change(
            inventory, movement_type=StockMovementType.RELEASE, reserved_delta=-reservation.quantity,
            reservation_id=reservation.id, actor_user_id=actor_user_id,
        )
        reservation.status = StockReservationStatus.RELEASED
        reservation.released_at = datetime.now(timezone.utc)
        reservation = await self._reservations.update(reservation)

        await self._log_audit(
            nursery_id=updated.nursery_id, actor_user_id=actor_user_id, action="inventory.stock_released",
            entity_id=updated.id, diff={"reservation_id": str(reservation.id), "quantity": reservation.quantity},
            request_id=request_id,
        )
        await self._events.publish(
            StockReleased(
                aggregate_id=updated.id, nursery_id=updated.nursery_id, actor_user_id=actor_user_id,
                reservation_id=reservation.id, quantity=reservation.quantity,
            ),
            request_id=request_id,
        )
        return reservation

    async def fulfill_reservation(
        self,
        *,
        reservation_id: uuid.UUID,
        reference_sale_id: uuid.UUID | None = None,
        plant_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None,
        request_id: str | None = None,
    ) -> StockReservation:
        """Converts a hold into an actual departure of stock -- the reservation's quantity leaves `quantity` for real."""
        reservation = await self.get_reservation(reservation_id)
        if reservation.status != StockReservationStatus.ACTIVE:
            raise ConflictError(
                f"Reservation '{reservation_id}' is not active (status={reservation.status.value}).",
                context={"reason": "invalid_reservation_state"},
            )
        inventory = await self.get_inventory(reservation.inventory_id)
        updated, movement = await self._apply_change(
            inventory, movement_type=StockMovementType.SALE, quantity_delta=-reservation.quantity,
            reserved_delta=-reservation.quantity, reason=InventoryAdjustmentReason.SALE,
            reservation_id=reservation.id, reference_sale_id=reference_sale_id, plant_id=plant_id,
            actor_user_id=actor_user_id,
        )
        reservation.status = StockReservationStatus.FULFILLED
        reservation.released_at = datetime.now(timezone.utc)
        reservation = await self._reservations.update(reservation)

        await self._log_audit(
            nursery_id=updated.nursery_id, actor_user_id=actor_user_id, action="inventory.stock_sold",
            entity_id=updated.id, diff={"reservation_id": str(reservation.id), "quantity": reservation.quantity},
            request_id=request_id,
        )
        await self._events.publish(
            StockSold(
                aggregate_id=updated.id, nursery_id=updated.nursery_id, actor_user_id=actor_user_id,
                movement_id=movement.id, quantity=reservation.quantity, reservation_id=reservation.id,
                reference_sale_id=reference_sale_id,
            ),
            request_id=request_id,
        )
        await self._publish_movement_link(
            movement=movement, nursery_id=updated.nursery_id, actor_user_id=actor_user_id, request_id=request_id
        )
        return reservation

    async def sell_stock_direct(
        self,
        *,
        inventory_id: uuid.UUID,
        quantity: int,
        reference_sale_id: uuid.UUID | None = None,
        plant_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None,
        request_id: str | None = None,
    ) -> tuple[Inventory, StockMovement]:
        """Decrement without a prior reservation (walk-up sale, no cart hold)."""
        if quantity <= 0:
            raise ValidationError("Sale quantity must be positive.")
        inventory = await self.get_inventory(inventory_id)
        updated, movement = await self._apply_change(
            inventory, movement_type=StockMovementType.SALE, quantity_delta=-quantity,
            reason=InventoryAdjustmentReason.SALE, reference_sale_id=reference_sale_id, plant_id=plant_id,
            actor_user_id=actor_user_id,
        )
        await self._log_audit(
            nursery_id=updated.nursery_id, actor_user_id=actor_user_id, action="inventory.stock_sold",
            entity_id=updated.id, diff={"quantity_delta": -quantity}, request_id=request_id,
        )
        await self._events.publish(
            StockSold(
                aggregate_id=updated.id, nursery_id=updated.nursery_id, actor_user_id=actor_user_id,
                movement_id=movement.id, quantity=quantity, reference_sale_id=reference_sale_id,
            ),
            request_id=request_id,
        )
        await self._publish_movement_link(
            movement=movement, nursery_id=updated.nursery_id, actor_user_id=actor_user_id, request_id=request_id
        )
        return updated, movement

    # ------------------------------------------------------------------
    # Damage / Waste / Adjustment / Archive
    # ------------------------------------------------------------------

    async def mark_damaged(
        self, *, inventory_id: uuid.UUID, quantity: int, note: str | None = None,
        actor_user_id: uuid.UUID | None, request_id: str | None = None,
    ) -> tuple[Inventory, StockMovement]:
        if quantity <= 0:
            raise ValidationError("Damaged quantity must be positive.")
        inventory = await self.get_inventory(inventory_id)
        updated, movement = await self._apply_change(
            inventory, movement_type=StockMovementType.DAMAGE, damaged_delta=quantity,
            reason=InventoryAdjustmentReason.DAMAGE, note=note, actor_user_id=actor_user_id,
        )
        await self._log_audit(
            nursery_id=updated.nursery_id, actor_user_id=actor_user_id, action="inventory.stock_damaged",
            entity_id=updated.id, diff={"quantity": quantity}, request_id=request_id,
        )
        await self._events.publish(
            StockDamaged(
                aggregate_id=updated.id, nursery_id=updated.nursery_id, actor_user_id=actor_user_id,
                movement_id=movement.id, quantity=quantity, note=note,
            ),
            request_id=request_id,
        )
        return updated, movement

    async def dispose_stock(
        self,
        *,
        inventory_id: uuid.UUID,
        quantity: int,
        from_damaged: bool = False,
        plant_id: uuid.UUID | None = None,
        note: str | None = None,
        actor_user_id: uuid.UUID | None,
        request_id: str | None = None,
    ) -> tuple[Inventory, StockMovement]:
        """Waste -- permanent removal (spoilage/expiry, or disposal of previously-marked-damaged stock)."""
        if quantity <= 0:
            raise ValidationError("Disposed quantity must be positive.")
        inventory = await self.get_inventory(inventory_id)
        updated, movement = await self._apply_change(
            inventory, movement_type=StockMovementType.WASTE, quantity_delta=-quantity,
            damaged_delta=-quantity if from_damaged else 0, disposed_delta=quantity,
            reason=InventoryAdjustmentReason.DAMAGE if from_damaged else InventoryAdjustmentReason.OTHER,
            plant_id=plant_id, note=note, actor_user_id=actor_user_id,
        )
        await self._log_audit(
            nursery_id=updated.nursery_id, actor_user_id=actor_user_id, action="inventory.stock_disposed",
            entity_id=updated.id, diff={"quantity": quantity, "from_damaged": from_damaged}, request_id=request_id,
        )
        await self._events.publish(
            StockDisposed(
                aggregate_id=updated.id, nursery_id=updated.nursery_id, actor_user_id=actor_user_id,
                movement_id=movement.id, quantity=quantity, reason=note,
            ),
            request_id=request_id,
        )
        await self._publish_movement_link(
            movement=movement, nursery_id=updated.nursery_id, actor_user_id=actor_user_id, request_id=request_id
        )
        return updated, movement

    async def adjust_stock(
        self,
        *,
        inventory_id: uuid.UUID,
        quantity_delta: int,
        reason: InventoryAdjustmentReason,
        note: str | None = None,
        actor_user_id: uuid.UUID | None,
        request_id: str | None = None,
    ) -> tuple[Inventory, StockMovement]:
        """Manual correction (stocktake, count correction, internal use, other) -- reason is required, per docs/ux/16-inventory-workflow.md's "not free-text-optional" rule."""
        if quantity_delta == 0:
            raise ValidationError("quantity_delta must be non-zero for an adjustment.")
        inventory = await self.get_inventory(inventory_id)
        updated, movement = await self._apply_change(
            inventory, movement_type=StockMovementType.ADJUSTMENT, quantity_delta=quantity_delta,
            reason=reason, note=note, actor_user_id=actor_user_id,
        )
        await self._log_audit(
            nursery_id=updated.nursery_id, actor_user_id=actor_user_id, action="inventory.stock_adjusted",
            entity_id=updated.id, diff={"quantity_delta": quantity_delta, "reason": reason.value}, request_id=request_id,
        )
        await self._events.publish(
            StockAdjusted(
                aggregate_id=updated.id, nursery_id=updated.nursery_id, actor_user_id=actor_user_id,
                movement_id=movement.id, quantity_delta=quantity_delta, quantity_after=updated.quantity,
                reason=reason.value,
            ),
            request_id=request_id,
        )
        return updated, movement

    async def archive_inventory_line(
        self, *, inventory_id: uuid.UUID, reason: str | None = None,
        actor_user_id: uuid.UUID | None, request_id: str | None = None,
    ) -> Inventory:
        inventory = await self.get_inventory(inventory_id)
        if inventory.archived_at is not None:
            return inventory  # idempotent no-op, matching PlantService's own archive precedent
        updated, movement = await self._apply_change(
            inventory, movement_type=StockMovementType.ARCHIVE, note=reason, actor_user_id=actor_user_id,
        )
        updated.archived_at = datetime.now(timezone.utc)
        recorded = await self._inventory.update(updated, expected_version=updated.version)
        if recorded is not None:
            updated = recorded

        await self._log_audit(
            nursery_id=updated.nursery_id, actor_user_id=actor_user_id, action="inventory.archived",
            entity_id=updated.id, diff={"reason": reason}, request_id=request_id,
        )
        await self._events.publish(
            InventoryArchived(
                aggregate_id=updated.id, nursery_id=updated.nursery_id, actor_user_id=actor_user_id, reason=reason,
            ),
            request_id=request_id,
        )
        return updated

    # ------------------------------------------------------------------
    # Reporting (LLD "Module: Inventory" responsibilities: threshold-based
    # alerting + the module's own named reports). Aggregated by paging
    # through `InventoryRepository.list_for_nursery`/`StockMovementRepository.
    # list_for_nursery` rather than a dedicated SQL SUM() -- correct for
    # any dataset size, though a dedicated aggregate query would be the
    # next performance step if these reports need to run at very large
    # scale; documented here rather than silently left as a scaling gap.
    # ------------------------------------------------------------------

    async def _all_inventory(
        self, nursery_id: uuid.UUID, *, branch_id: uuid.UUID | None = None, low_stock_only: bool = False
    ) -> list[Inventory]:
        page_size = 200
        offset = 0
        collected: list[Inventory] = []
        while True:
            rows, total = await self._inventory.list_for_nursery(
                nursery_id, offset=offset, limit=page_size, branch_id=branch_id, low_stock_only=low_stock_only,
            )
            collected.extend(rows)
            offset += page_size
            if offset >= total or not rows:
                break
        return collected

    async def _all_movements(
        self,
        nursery_id: uuid.UUID,
        *,
        branch_id: uuid.UUID | None = None,
        movement_type: StockMovementType | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[StockMovement]:
        page_size = 200
        offset = 0
        collected: list[StockMovement] = []
        while True:
            rows, total = await self._movements.list_for_nursery(
                nursery_id, offset=offset, limit=page_size, branch_id=branch_id, movement_type=movement_type,
                date_from=date_from, date_to=date_to,
            )
            collected.extend(rows)
            offset += page_size
            if offset >= total or not rows:
                break
        return collected

    async def inventory_summary(self, nursery_id: uuid.UUID, *, branch_id: uuid.UUID | None = None) -> dict:
        items = await self._all_inventory(nursery_id, branch_id=branch_id)
        total_quantity = sum(item.quantity for item in items)
        total_reserved = sum(item.reserved_quantity for item in items)
        total_damaged = sum(item.damaged_quantity for item in items)
        total_disposed = sum(item.disposed_quantity for item in items)
        low_stock_count = sum(1 for item in items if item.quantity <= item.low_stock_threshold)
        valuation = sum(_as_float(item.unit_cost) * item.quantity for item in items)
        return {
            "line_count": len(items),
            "total_quantity": total_quantity,
            "total_reserved_quantity": total_reserved,
            "total_damaged_quantity": total_damaged,
            "total_disposed_quantity": total_disposed,
            "total_available_quantity": total_quantity - total_reserved - total_damaged,
            "low_stock_count": low_stock_count,
            "total_valuation": valuation,
        }

    async def low_stock_report(self, nursery_id: uuid.UUID, *, branch_id: uuid.UUID | None = None) -> list[Inventory]:
        return await self._all_inventory(nursery_id, branch_id=branch_id, low_stock_only=True)

    async def waste_report(
        self, nursery_id: uuid.UUID, *, branch_id: uuid.UUID | None = None,
        date_from: datetime | None = None, date_to: datetime | None = None,
    ) -> dict:
        movements = await self._all_movements(
            nursery_id, branch_id=branch_id, movement_type=StockMovementType.WASTE,
            date_from=date_from, date_to=date_to,
        )
        return {
            "movement_count": len(movements),
            "total_quantity_disposed": sum(-m.quantity_delta for m in movements),
            "movements": movements,
        }

    async def transfer_report(
        self, nursery_id: uuid.UUID, *, branch_id: uuid.UUID | None = None,
        date_from: datetime | None = None, date_to: datetime | None = None,
    ) -> dict:
        movements = await self._all_movements(
            nursery_id, branch_id=branch_id, movement_type=StockMovementType.TRANSFER,
            date_from=date_from, date_to=date_to,
        )
        return {"movement_count": len(movements), "movements": movements}

    async def stock_valuation(self, nursery_id: uuid.UUID, *, branch_id: uuid.UUID | None = None) -> dict:
        items = await self._all_inventory(nursery_id, branch_id=branch_id)
        cost_value = sum(_as_float(item.unit_cost) * item.quantity for item in items)
        retail_value = sum(_as_float(item.unit_price) * item.quantity for item in items)
        return {
            "line_count": len(items),
            "total_cost_value": cost_value,
            "total_retail_value": retail_value,
            "potential_margin": retail_value - cost_value,
        }

    async def reservation_report(
        self, nursery_id: uuid.UUID, *, branch_id: uuid.UUID | None = None, offset: int = 0, limit: int = 50
    ) -> tuple[list[StockReservation], int]:
        return await self._reservations.list_active_for_nursery(
            nursery_id, offset=offset, limit=limit, branch_id=branch_id
        )

    async def movement_history(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        branch_id: uuid.UUID | None = None,
        movement_type: StockMovementType | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[StockMovement], int]:
        return await self._movements.list_for_nursery(
            nursery_id, offset=offset, limit=limit, branch_id=branch_id, movement_type=movement_type,
            date_from=date_from, date_to=date_to,
        )
