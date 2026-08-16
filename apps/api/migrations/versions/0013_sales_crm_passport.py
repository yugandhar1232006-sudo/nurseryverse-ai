"""Sales, CRM, Plant Passport & QR Intelligence (Phase 6 Module 9).

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-06

Evolves the Phase 5 `customers`/`sales`/`sale_items`/`invoices`/
`invoice_items`/`invoice_sales`/`payments`/`passports` skeleton (all
already present since migration 0001) into the full bounded context
Module 9's spec requires -- the same "first module to actually build on a
pre-existing table" pattern Module 5 applied to species/categories, Module
6 to plants, and Module 8 to inventory. See app/models/commerce.py's
Module 9 docstring block for the full architectural reasoning (why
`SalesOrder` wraps `Sale` rather than replacing it, why stock holds reuse
Module 8's `StockReservation` rather than a new reservation table).

Five moves:
  1. Customer CRM sub-tables: `customer_contacts`, `customer_addresses`,
     `customer_tags`, `customer_notes`, `customer_communications` -- all
     child tables of `customers`, no nursery_id of their own (join-scoped
     RLS through their parent, migration 0003's established pattern).
  2. Sales lifecycle: `quotations` + `quotation_items`, `sales_orders` +
     `order_items` -- the pre-completion order pipeline that culminates in
     creating one `Sale` (+ optionally one `Invoice`) row.
  3. Returns & Refunds: `returns` + `return_items`, `refunds`.
  4. `qr_scan_events` -- QR Scan Analytics source data, child of
     `passports`. Deliberately NOT given RLS, for the identical reason
     `passports` itself is exempt (migration 0003's documented exemption
     list): it is written by the one unauthenticated endpoint in the
     system, before any org context exists.
  5. `sales`/`invoices` gain a first-class `tax_amount` (and, for
     invoices, frozen `subtotal_amount`/`discount_amount` snapshot
     columns) -- Tax Calculation as a reportable line, not folded
     silently into `total_amount`.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

SESSION_VAR = "app.current_org_id"


def _enable_and_force(table: str) -> str:
    return (
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;\n"
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;"
    )


def _direct_tenant_policy(table: str) -> str:
    return f"""
    CREATE POLICY tenant_isolation_{table} ON {table}
    USING (nursery_id = current_setting('{SESSION_VAR}', true)::uuid)
    WITH CHECK (nursery_id = current_setting('{SESSION_VAR}', true)::uuid);
    """


def _join_tenant_policy(table: str, fk_col: str, parent: str) -> str:
    return f"""
    CREATE POLICY tenant_isolation_{table} ON {table}
    USING (
        {fk_col} IN (SELECT id FROM {parent} WHERE nursery_id = current_setting('{SESSION_VAR}', true)::uuid)
    )
    WITH CHECK (
        {fk_col} IN (SELECT id FROM {parent} WHERE nursery_id = current_setting('{SESSION_VAR}', true)::uuid)
    );
    """


DIRECT_TENANT_TABLES = ["quotations", "sales_orders", "returns", "refunds"]

JOIN_TENANT_TABLES = [
    ("customer_contacts", "customer_id", "customers"),
    ("customer_addresses", "customer_id", "customers"),
    ("customer_tags", "customer_id", "customers"),
    ("customer_notes", "customer_id", "customers"),
    ("customer_communications", "customer_id", "customers"),
    ("quotation_items", "quotation_id", "quotations"),
    ("order_items", "sales_order_id", "sales_orders"),
    ("return_items", "return_id", "returns"),
]


def upgrade() -> None:
    # --- new enums ---
    customer_address_type = sa.Enum("BILLING", "SHIPPING", "OTHER", name="customer_address_type")
    customer_address_type.create(op.get_bind(), checkfirst=True)
    communication_channel = sa.Enum(
        "EMAIL", "PHONE", "SMS", "IN_PERSON", "OTHER", name="communication_channel"
    )
    communication_channel.create(op.get_bind(), checkfirst=True)
    communication_direction = sa.Enum("INBOUND", "OUTBOUND", name="communication_direction")
    communication_direction.create(op.get_bind(), checkfirst=True)
    quotation_status = sa.Enum(
        "DRAFT", "SENT", "ACCEPTED", "REJECTED", "EXPIRED", "CONVERTED", name="quotation_status"
    )
    quotation_status.create(op.get_bind(), checkfirst=True)
    sales_order_status = sa.Enum(
        "DRAFT", "CONFIRMED", "PROCESSING", "FULFILLED", "CANCELLED", name="sales_order_status"
    )
    sales_order_status.create(op.get_bind(), checkfirst=True)
    order_payment_status = sa.Enum(
        "UNPAID", "PARTIALLY_PAID", "PAID", "REFUNDED", name="order_payment_status"
    )
    order_payment_status.create(op.get_bind(), checkfirst=True)
    payment_method = sa.Enum("CASH", "UPI", "CARD", "BANK_TRANSFER", "OTHER", name="payment_method")
    payment_method.create(op.get_bind(), checkfirst=True)
    return_status = sa.Enum("REQUESTED", "APPROVED", "REJECTED", "COMPLETED", name="return_status")
    return_status.create(op.get_bind(), checkfirst=True)
    return_item_condition = sa.Enum(
        "RESALABLE", "DAMAGED", "DISPOSED", name="return_item_condition"
    )
    return_item_condition.create(op.get_bind(), checkfirst=True)
    refund_status = sa.Enum("PENDING", "COMPLETED", "FAILED", name="refund_status")
    refund_status.create(op.get_bind(), checkfirst=True)

    # --- sales / invoices: tax + frozen snapshot columns ---
    op.add_column("sales", sa.Column("tax_amount", sa.Numeric(10, 2), server_default="0", nullable=False))
    op.add_column(
        "invoices", sa.Column("subtotal_amount", sa.Numeric(10, 2), server_default="0", nullable=False)
    )
    op.add_column(
        "invoices", sa.Column("discount_amount", sa.Numeric(10, 2), server_default="0", nullable=False)
    )
    op.add_column(
        "invoices", sa.Column("tax_amount", sa.Numeric(10, 2), server_default="0", nullable=False)
    )

    # --- Customer CRM sub-tables ---
    op.create_table(
        "customer_contacts",
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], name=op.f("fk_customer_contacts_customer_id_customers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customer_contacts")),
    )
    op.create_index("ix_customer_contacts_customer_id", "customer_contacts", ["customer_id"], unique=False)

    op.create_table(
        "customer_addresses",
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("address_type", customer_address_type, server_default="OTHER", nullable=False),
        sa.Column("line1", sa.String(length=255), nullable=False),
        sa.Column("line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], name=op.f("fk_customer_addresses_customer_id_customers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customer_addresses")),
    )
    op.create_index("ix_customer_addresses_customer_id", "customer_addresses", ["customer_id"], unique=False)

    op.create_table(
        "customer_tags",
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("tag", sa.String(length=50), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], name=op.f("fk_customer_tags_customer_id_customers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customer_tags")),
        sa.UniqueConstraint("customer_id", "tag", name="uq_customer_tags_customer_tag"),
    )
    op.create_index("ix_customer_tags_customer_id", "customer_tags", ["customer_id"], unique=False)

    op.create_table(
        "customer_notes",
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("author_user_id", sa.UUID(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("pinned", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], name=op.f("fk_customer_notes_customer_id_customers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_user_id"], ["users.id"], name=op.f("fk_customer_notes_author_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customer_notes")),
    )
    op.create_index(
        "ix_customer_notes_customer_id_created_at", "customer_notes", ["customer_id", "created_at"], unique=False
    )

    op.create_table(
        "customer_communications",
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("channel", communication_channel, nullable=False),
        sa.Column("direction", communication_direction, server_default="OUTBOUND", nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("logged_by_user_id", sa.UUID(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], name=op.f("fk_customer_communications_customer_id_customers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["logged_by_user_id"], ["users.id"], name=op.f("fk_customer_communications_logged_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customer_communications")),
    )
    op.create_index(
        "ix_customer_communications_customer_id_occurred_at",
        "customer_communications", ["customer_id", "occurred_at"], unique=False,
    )

    # --- Quotations ---
    op.create_table(
        "quotations",
        sa.Column("nursery_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("status", quotation_status, server_default="DRAFT", nullable=False),
        sa.Column("subtotal_amount", sa.Numeric(10, 2), server_default="0", nullable=False),
        sa.Column("discount_amount", sa.Numeric(10, 2), server_default="0", nullable=False),
        sa.Column("tax_amount", sa.Numeric(10, 2), server_default="0", nullable=False),
        sa.Column("total_amount", sa.Numeric(10, 2), server_default="0", nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["nursery_id"], ["nurseries.id"], name=op.f("fk_quotations_nursery_id_nurseries"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"], name=op.f("fk_quotations_branch_id_branches"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], name=op.f("fk_quotations_customer_id_customers"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], name=op.f("fk_quotations_created_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotations")),
    )
    op.create_index("ix_quotations_branch_status", "quotations", ["branch_id", "status"], unique=False)

    op.create_table(
        "quotation_items",
        sa.Column("quotation_id", sa.UUID(), nullable=False),
        sa.Column("plant_id", sa.UUID(), nullable=True),
        sa.Column("inventory_id", sa.UUID(), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(10, 2), server_default="0", nullable=False),
        sa.Column("line_total", sa.Numeric(10, 2), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "NOT (plant_id IS NOT NULL AND inventory_id IS NOT NULL)",
            name=op.f("ck_quotation_items_not_both_plant_and_inventory"),
        ),
        sa.ForeignKeyConstraint(
            ["quotation_id"], ["quotations.id"], name=op.f("fk_quotation_items_quotation_id_quotations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plant_id"], ["plants.id"], name=op.f("fk_quotation_items_plant_id_plants"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["inventory_id"], ["inventory.id"], name=op.f("fk_quotation_items_inventory_id_inventory"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotation_items")),
    )
    op.create_index("ix_quotation_items_quotation_id", "quotation_items", ["quotation_id"], unique=False)

    # --- Sales Orders ---
    op.create_table(
        "sales_orders",
        sa.Column("nursery_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("quotation_id", sa.UUID(), nullable=True),
        sa.Column("order_status", sales_order_status, server_default="DRAFT", nullable=False),
        sa.Column("payment_status", order_payment_status, server_default="UNPAID", nullable=False),
        sa.Column("subtotal_amount", sa.Numeric(10, 2), server_default="0", nullable=False),
        sa.Column("discount_amount", sa.Numeric(10, 2), server_default="0", nullable=False),
        sa.Column("tax_amount", sa.Numeric(10, 2), server_default="0", nullable=False),
        sa.Column("total_amount", sa.Numeric(10, 2), server_default="0", nullable=False),
        sa.Column("sale_id", sa.UUID(), nullable=True),
        sa.Column("invoice_id", sa.UUID(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["nursery_id"], ["nurseries.id"], name=op.f("fk_sales_orders_nursery_id_nurseries"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"], name=op.f("fk_sales_orders_branch_id_branches"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], name=op.f("fk_sales_orders_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["quotation_id"], ["quotations.id"], name=op.f("fk_sales_orders_quotation_id_quotations"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["sale_id"], ["sales.id"], name=op.f("fk_sales_orders_sale_id_sales"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"], ["invoices.id"], name=op.f("fk_sales_orders_invoice_id_invoices"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], name=op.f("fk_sales_orders_created_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sales_orders")),
        sa.UniqueConstraint(
            "branch_id", "idempotency_key", name="uq_sales_orders_branch_idempotency_key"
        ),
    )
    op.create_index(
        "ix_sales_orders_branch_order_status", "sales_orders", ["branch_id", "order_status"], unique=False
    )

    op.create_table(
        "order_items",
        sa.Column("sales_order_id", sa.UUID(), nullable=False),
        sa.Column("plant_id", sa.UUID(), nullable=True),
        sa.Column("inventory_id", sa.UUID(), nullable=True),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(10, 2), server_default="0", nullable=False),
        sa.Column("tax_amount", sa.Numeric(10, 2), server_default="0", nullable=False),
        sa.Column("line_total", sa.Numeric(10, 2), nullable=False),
        sa.Column("reservation_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "(plant_id IS NOT NULL AND inventory_id IS NULL) OR (plant_id IS NULL AND inventory_id IS NOT NULL)",
            name=op.f("ck_order_items_exactly_one_of_plant_or_inventory"),
        ),
        sa.ForeignKeyConstraint(
            ["sales_order_id"], ["sales_orders.id"], name=op.f("fk_order_items_sales_order_id_sales_orders"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plant_id"], ["plants.id"], name=op.f("fk_order_items_plant_id_plants"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["inventory_id"], ["inventory.id"], name=op.f("fk_order_items_inventory_id_inventory"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id"], ["stock_reservations.id"], name=op.f("fk_order_items_reservation_id_stock_reservations"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_items")),
    )
    op.create_index("ix_order_items_sales_order_id", "order_items", ["sales_order_id"], unique=False)

    # --- Returns & Refunds ---
    op.create_table(
        "returns",
        sa.Column("nursery_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("sale_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("status", return_status, server_default="REQUESTED", nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("requested_by_user_id", sa.UUID(), nullable=False),
        sa.Column("processed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["nursery_id"], ["nurseries.id"], name=op.f("fk_returns_nursery_id_nurseries"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"], name=op.f("fk_returns_branch_id_branches"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sale_id"], ["sales.id"], name=op.f("fk_returns_sale_id_sales"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], name=op.f("fk_returns_customer_id_customers"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"], ["users.id"], name=op.f("fk_returns_requested_by_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["processed_by_user_id"], ["users.id"], name=op.f("fk_returns_processed_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_returns")),
    )
    op.create_index("ix_returns_branch_status", "returns", ["branch_id", "status"], unique=False)

    op.create_table(
        "return_items",
        sa.Column("return_id", sa.UUID(), nullable=False),
        sa.Column("sale_item_id", sa.UUID(), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("restock", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("condition", return_item_condition, server_default="RESALABLE", nullable=False),
        sa.Column("line_refund_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["return_id"], ["returns.id"], name=op.f("fk_return_items_return_id_returns"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sale_item_id"], ["sale_items.id"], name=op.f("fk_return_items_sale_item_id_sale_items"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_return_items")),
    )
    op.create_index("ix_return_items_return_id", "return_items", ["return_id"], unique=False)

    op.create_table(
        "refunds",
        sa.Column("nursery_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("return_id", sa.UUID(), nullable=True),
        sa.Column("invoice_id", sa.UUID(), nullable=True),
        sa.Column("sale_id", sa.UUID(), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("method", payment_method, nullable=False),
        sa.Column("status", refund_status, server_default="PENDING", nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("processed_by_user_id", sa.UUID(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount > 0", name=op.f("ck_refunds_amount_positive")),
        sa.ForeignKeyConstraint(
            ["nursery_id"], ["nurseries.id"], name=op.f("fk_refunds_nursery_id_nurseries"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"], name=op.f("fk_refunds_branch_id_branches"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["return_id"], ["returns.id"], name=op.f("fk_refunds_return_id_returns"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id"], ["invoices.id"], name=op.f("fk_refunds_invoice_id_invoices"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["sale_id"], ["sales.id"], name=op.f("fk_refunds_sale_id_sales"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["processed_by_user_id"], ["users.id"], name=op.f("fk_refunds_processed_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refunds")),
    )
    op.create_index("ix_refunds_branch_status", "refunds", ["branch_id", "status"], unique=False)

    # --- QR Scan Events (child of passports; no RLS, see module docstring) ---
    op.create_table(
        "qr_scan_events",
        sa.Column("passport_id", sa.UUID(), nullable=False),
        sa.Column("ip_hash", sa.String(length=128), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("referrer", sa.String(length=500), nullable=True),
        sa.Column("scanned_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["passport_id"], ["passports.id"], name=op.f("fk_qr_scan_events_passport_id_passports"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_qr_scan_events")),
    )
    op.create_index(
        "ix_qr_scan_events_passport_id_scanned_at", "qr_scan_events", ["passport_id", "scanned_at"], unique=False
    )

    # --- RLS ---
    for table in DIRECT_TENANT_TABLES:
        op.execute(_enable_and_force(table))
        op.execute(_direct_tenant_policy(table))

    for table, fk_col, parent in JOIN_TENANT_TABLES:
        op.execute(_enable_and_force(table))
        op.execute(_join_tenant_policy(table, fk_col, parent))


def downgrade() -> None:
    for table, _fk_col, _parent in JOIN_TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table};")
    for table in DIRECT_TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table};")

    op.drop_index("ix_qr_scan_events_passport_id_scanned_at", table_name="qr_scan_events")
    op.drop_table("qr_scan_events")

    op.drop_index("ix_refunds_branch_status", table_name="refunds")
    op.drop_table("refunds")

    op.drop_index("ix_return_items_return_id", table_name="return_items")
    op.drop_table("return_items")

    op.drop_index("ix_returns_branch_status", table_name="returns")
    op.drop_table("returns")

    op.drop_index("ix_order_items_sales_order_id", table_name="order_items")
    op.drop_table("order_items")

    op.drop_index("ix_sales_orders_branch_order_status", table_name="sales_orders")
    op.drop_table("sales_orders")

    op.drop_index("ix_quotation_items_quotation_id", table_name="quotation_items")
    op.drop_table("quotation_items")

    op.drop_index("ix_quotations_branch_status", table_name="quotations")
    op.drop_table("quotations")

    op.drop_index(
        "ix_customer_communications_customer_id_occurred_at", table_name="customer_communications"
    )
    op.drop_table("customer_communications")

    op.drop_index("ix_customer_notes_customer_id_created_at", table_name="customer_notes")
    op.drop_table("customer_notes")

    op.drop_index("ix_customer_tags_customer_id", table_name="customer_tags")
    op.drop_table("customer_tags")

    op.drop_index("ix_customer_addresses_customer_id", table_name="customer_addresses")
    op.drop_table("customer_addresses")

    op.drop_index("ix_customer_contacts_customer_id", table_name="customer_contacts")
    op.drop_table("customer_contacts")

    op.drop_column("invoices", "tax_amount")
    op.drop_column("invoices", "discount_amount")
    op.drop_column("invoices", "subtotal_amount")
    op.drop_column("sales", "tax_amount")

    sa.Enum(name="refund_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="return_item_condition").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="return_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="payment_method").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="order_payment_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="sales_order_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="quotation_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="communication_direction").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="communication_channel").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="customer_address_type").drop(op.get_bind(), checkfirst=True)
