"""
Phase 6 Module 9 (Sales, CRM, Plant Passport & QR Intelligence) —
Customer CRM: Profiles, Contacts, Addresses, Tags, Notes, Communication
History, Purchase History, and Customer Analytics.

Same layering discipline as every prior module's services: takes only
repository Protocols and pure data, no FastAPI/SQLAlchemy-session
concerns; authorization is checked at the route layer
(`AuthorizationService.authorize()`), never re-checked here — a service
has no independent way to learn who the caller is beyond what the route
already resolved and passed in as `actor_user_id`.

"Purchase History"/"Customer Analytics" are read-only queries over the
pre-existing `Sale` ledger (Phase 5), not new tables — this module does
not duplicate sales data onto the Customer record, the same "don't
duplicate business logic" instruction every prior module has applied to
its own read-side rollups (Module 5's Species/plant counts, Module 8's
reporting methods).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from app.core.exceptions import NotFoundError, ValidationError
from app.db.enums import CustomerType
from app.domain_events import CustomerCreated, CustomerUpdated, DomainEventPublisher
from app.models.commerce import (
    Customer,
    CustomerAddress,
    CustomerCommunication,
    CustomerContact,
    CustomerNote,
    CustomerTag,
    Sale,
)
from app.models.platform import AuditLog
from app.repositories.interfaces import (
    AuditLogRepository,
    CustomerAddressRepository,
    CustomerCommunicationRepository,
    CustomerContactRepository,
    CustomerNoteRepository,
    CustomerRepository,
    CustomerTagRepository,
    SaleRepository,
)


def _as_float(value: object) -> float:
    """See app/services/inventory_service.py's identical helper — same pre-existing `Mapped[Numeric | None]` typing imprecision, same fix."""
    return float(value or 0)  # type: ignore[arg-type]


@dataclass(frozen=True)
class CustomerAnalytics:
    customer_id: uuid.UUID
    total_orders: int
    total_spent: float
    average_order_value: float
    last_purchase_at: datetime | None


class CustomerService:
    def __init__(
        self,
        *,
        customer_repo: CustomerRepository,
        contact_repo: CustomerContactRepository,
        address_repo: CustomerAddressRepository,
        tag_repo: CustomerTagRepository,
        note_repo: CustomerNoteRepository,
        communication_repo: CustomerCommunicationRepository,
        sale_repo: SaleRepository,
        audit_repo: AuditLogRepository,
        event_publisher: DomainEventPublisher,
    ) -> None:
        self._customers = customer_repo
        self._contacts = contact_repo
        self._addresses = address_repo
        self._tags = tag_repo
        self._notes = note_repo
        self._communications = communication_repo
        self._sales = sale_repo
        self._audit = audit_repo
        self._events = event_publisher

    # ------------------------------------------------------------------
    # Customer Profiles
    # ------------------------------------------------------------------
    async def create_customer(
        self,
        *,
        nursery_id: uuid.UUID,
        branch_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        name: str,
        email: str | None = None,
        phone: str | None = None,
        customer_type: CustomerType = CustomerType.RETAIL,
        request_id: str | None = None,
    ) -> Customer:
        if not name.strip():
            raise ValidationError("Customer name is required.")
        customer = Customer(
            nursery_id=nursery_id,
            branch_id=branch_id,
            name=name.strip(),
            email=email.strip().lower() if email else None,
            phone=phone,
            customer_type=customer_type,
        )
        await self._customers.add(customer)
        await self._log_audit(
            nursery_id=nursery_id,
            actor_user_id=actor_user_id,
            action="customer.created",
            entity_id=customer.id,
            diff={"after": {"name": customer.name, "customer_type": customer_type.value}},
            request_id=request_id,
        )
        await self._events.publish(
            CustomerCreated(
                aggregate_id=customer.id,
                nursery_id=nursery_id,
                actor_user_id=actor_user_id,
                branch_id=branch_id,
                name=customer.name,
            ),
            request_id=request_id,
        )
        return customer

    async def get_customer(self, customer_id: uuid.UUID) -> Customer:
        customer = await self._customers.get_by_id(customer_id)
        if customer is None:
            raise NotFoundError("Customer not found.")
        return customer

    async def list_customers(
        self,
        nursery_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        branch_id: uuid.UUID | None = None,
        customer_type: CustomerType | None = None,
        tag: str | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ) -> tuple[list[Customer], int]:
        return await self._customers.list_for_nursery(
            nursery_id,
            offset=offset,
            limit=limit,
            branch_id=branch_id,
            customer_type=customer_type,
            tag=tag,
            search=search,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )

    async def update_customer(
        self,
        customer: Customer,
        *,
        actor_user_id: uuid.UUID,
        name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        customer_type: CustomerType | None = None,
        request_id: str | None = None,
    ) -> Customer:
        changed: list[str] = []
        if name is not None and name.strip() and name.strip() != customer.name:
            customer.name = name.strip()
            changed.append("name")
        if email is not None and email.strip().lower() != (customer.email or ""):
            customer.email = email.strip().lower() or None
            changed.append("email")
        if phone is not None and phone != customer.phone:
            customer.phone = phone
            changed.append("phone")
        if customer_type is not None and customer_type != customer.customer_type:
            customer.customer_type = customer_type
            changed.append("customer_type")

        if not changed:
            return customer

        await self._customers.update(customer)
        await self._log_audit(
            nursery_id=customer.nursery_id,
            actor_user_id=actor_user_id,
            action="customer.updated",
            entity_id=customer.id,
            diff={"changed_fields": changed},
            request_id=request_id,
        )
        await self._events.publish(
            CustomerUpdated(
                aggregate_id=customer.id,
                nursery_id=customer.nursery_id,
                actor_user_id=actor_user_id,
                changed_fields=tuple(changed),
            ),
            request_id=request_id,
        )
        return customer

    # ------------------------------------------------------------------
    # Customer Contacts
    # ------------------------------------------------------------------
    async def add_contact(
        self,
        customer: Customer,
        *,
        name: str,
        role: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        is_primary: bool = False,
    ) -> CustomerContact:
        contact = CustomerContact(
            customer_id=customer.id, name=name.strip(), role=role, email=email, phone=phone, is_primary=is_primary
        )
        return await self._contacts.add(contact)

    async def list_contacts(self, customer_id: uuid.UUID) -> list[CustomerContact]:
        return await self._contacts.list_for_customer(customer_id)

    async def delete_contact(self, contact: CustomerContact) -> None:
        await self._contacts.delete(contact.id)

    # ------------------------------------------------------------------
    # Customer Addresses
    # ------------------------------------------------------------------
    async def add_address(self, customer: Customer, **fields: object) -> CustomerAddress:
        address = CustomerAddress(customer_id=customer.id, **fields)  # type: ignore[arg-type]
        return await self._addresses.add(address)

    async def list_addresses(self, customer_id: uuid.UUID) -> list[CustomerAddress]:
        return await self._addresses.list_for_customer(customer_id)

    async def delete_address(self, address: CustomerAddress) -> None:
        await self._addresses.delete(address.id)

    # ------------------------------------------------------------------
    # Customer Tags
    # ------------------------------------------------------------------
    async def add_tag(self, customer: Customer, tag: str) -> CustomerTag:
        clean = tag.strip().lower()
        if not clean:
            raise ValidationError("Tag must not be empty.")
        existing = await self._tags.list_for_customer(customer.id)
        if any(t.tag == clean for t in existing):
            return next(t for t in existing if t.tag == clean)
        return await self._tags.add(CustomerTag(customer_id=customer.id, tag=clean))

    async def list_tags(self, customer_id: uuid.UUID) -> list[CustomerTag]:
        return await self._tags.list_for_customer(customer_id)

    async def remove_tag(self, customer: Customer, tag: str) -> None:
        await self._tags.delete(customer.id, tag.strip().lower())

    # ------------------------------------------------------------------
    # Customer Notes
    # ------------------------------------------------------------------
    async def add_note(
        self, customer: Customer, *, actor_user_id: uuid.UUID, note: str, pinned: bool = False
    ) -> CustomerNote:
        if not note.strip():
            raise ValidationError("Note text is required.")
        return await self._notes.add(
            CustomerNote(customer_id=customer.id, author_user_id=actor_user_id, note=note.strip(), pinned=pinned)
        )

    async def list_notes(self, customer_id: uuid.UUID, *, offset: int, limit: int) -> tuple[list[CustomerNote], int]:
        return await self._notes.list_for_customer(customer_id, offset=offset, limit=limit)

    async def delete_note(self, note: CustomerNote) -> None:
        await self._notes.delete(note.id)

    # ------------------------------------------------------------------
    # Communication History
    # ------------------------------------------------------------------
    async def log_communication(
        self,
        customer: Customer,
        *,
        actor_user_id: uuid.UUID,
        channel,
        direction,
        subject: str | None = None,
        notes: str | None = None,
    ) -> CustomerCommunication:
        return await self._communications.add(
            CustomerCommunication(
                customer_id=customer.id,
                channel=channel,
                direction=direction,
                subject=subject,
                notes=notes,
                logged_by_user_id=actor_user_id,
            )
        )

    async def list_communications(
        self, customer_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[CustomerCommunication], int]:
        return await self._communications.list_for_customer(customer_id, offset=offset, limit=limit)

    # ------------------------------------------------------------------
    # Purchase History & Customer Analytics
    # ------------------------------------------------------------------
    async def purchase_history(self, customer: Customer, *, offset: int, limit: int) -> tuple[list[Sale], int]:
        return await self._sales.list_for_nursery(
            customer.nursery_id, offset=offset, limit=limit, customer_id=customer.id
        )

    async def customer_analytics(self, customer: Customer) -> CustomerAnalytics:
        """
        Full-scan over this customer's Sales, same pagination-based
        aggregation tradeoff Module 8's reporting methods already
        disclosed (correct for any volume, not a pushed-down SQL
        aggregate) — a single customer's order count is small enough that
        this is not a practical concern in the way a nursery-wide report
        would be.
        """
        page_size = 200
        offset = 0
        total_spent = Decimal("0")
        count = 0
        last_purchase_at: datetime | None = None
        while True:
            rows, total = await self._sales.list_for_nursery(
                customer.nursery_id, offset=offset, limit=page_size, customer_id=customer.id
            )
            for sale in rows:
                if sale.status.value == "voided":
                    continue
                total_spent += Decimal(str(sale.total_amount))
                count += 1
                if last_purchase_at is None or sale.created_at > last_purchase_at:
                    last_purchase_at = sale.created_at
            offset += page_size
            if offset >= total or not rows:
                break
        avg = float(total_spent) / count if count else 0.0
        return CustomerAnalytics(
            customer_id=customer.id,
            total_orders=count,
            total_spent=float(total_spent),
            average_order_value=avg,
            last_purchase_at=last_purchase_at,
        )

    async def customer_report(self, nursery_id: uuid.UUID, *, branch_id: uuid.UUID | None, top_n: int = 10) -> list[dict]:
        """Customer Reports — top customers by total spend."""
        customers, _ = await self._customers.list_for_nursery(nursery_id, offset=0, limit=10_000, branch_id=branch_id)
        results = []
        for customer in customers:
            analytics = await self.customer_analytics(customer)
            if analytics.total_orders == 0:
                continue
            results.append(
                {
                    "customer_id": customer.id,
                    "name": customer.name,
                    "total_orders": analytics.total_orders,
                    "total_spent": analytics.total_spent,
                    "average_order_value": analytics.average_order_value,
                    "last_purchase_at": analytics.last_purchase_at,
                }
            )
        results.sort(key=lambda r: _as_float(r["total_spent"]), reverse=True)
        return results[:top_n]

    # ------------------------------------------------------------------
    async def _log_audit(
        self,
        *,
        nursery_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        action: str,
        entity_id: uuid.UUID,
        diff: dict,
        request_id: str | None,
    ) -> None:
        await self._audit.log(
            AuditLog(
                nursery_id=nursery_id,
                actor_user_id=actor_user_id,
                action=action,
                entity_type="Customer",
                entity_id=entity_id,
                diff=diff,
                request_id=request_id,
                created_at=datetime.now(timezone.utc),
            )
        )
