"""
Generic Attachments — polymorphic file attachments for entities that need
document uploads beyond the specialized PlantImage (plant photos are
common/high-volume enough to warrant their own typed table; everything
else — a supplier contract PDF, a purchase-order scanned invoice, an
employee document — goes through this generic table instead of adding a
one-off attachments table per entity type).

Maps to the Phase 5 master-table list ("Attachments"). Not tied to a
single LLD module — used by Suppliers & Purchasing, Employees, and
Settings, per the `entity_type` discriminator.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, UUIDPKMixin


class Attachment(UUIDPKMixin, TenantMixin, Base):
    """
    Polymorphic association via (entity_type, entity_id) rather than a
    dedicated FK column per possible parent — deliberate, since the set of
    attachable entities is open-ended (Suppliers today, potentially
    Purchase Orders or Employees tomorrow) and a new FK column per entity
    type would require a migration for every addition. Referential
    integrity for the polymorphic association is enforced at the service
    layer (the entity_type value is drawn from a fixed allow-list checked
    in AttachmentService), not by a database FK — the one deliberate
    exception to this schema's general FK-everywhere posture, and it's
    documented here specifically so it isn't mistaken for an oversight.
    """

    __tablename__ = "attachments"
    __table_args__ = (Index("ix_attachments_entity_type_entity_id", "entity_type", "entity_id"),)

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "supplier", "purchase_order"
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(server_default="now()", nullable=False)
