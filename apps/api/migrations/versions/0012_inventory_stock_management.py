"""Inventory & Stock Management (Phase 6 Module 8).

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-06

Evolves the Phase 5 `inventory`/`inventory_adjustments` skeleton into the
full bounded context Module 8's spec requires -- the same "first module to
actually build on a pre-existing table" pattern Module 5 applied to
species/categories and Module 6 applied to plants (see
app/models/inventory.py's module docstring for the full reasoning).

Four moves:
  1. New `inventory_locations` table (sub-branch physical hierarchy: Zone,
     Greenhouse, Outdoor Area, Rack, Bench, Section).
  2. `inventory` gains `location_id`, `reserved_quantity`,
     `damaged_quantity`, `disposed_quantity` (the "Real-Time Stock" model),
     `archived_at`, and `version` (optimistic-concurrency column).
  3. `inventory_adjustments` is renamed to `stock_movements` and
     generalized: `movement_type` (ten values), `from_location_id`/
     `to_location_id`, `plant_id` (nullable Digital Twin linkage -- see
     app/models/inventory.py), `reservation_id`, `transfer_group_id`;
     `adjusted_by_user_id` renamed to `performed_by_user_id`; `reason`
     becomes nullable (only ADJUSTMENT/WASTE/DAMAGE movements carry one).
     Existing rows are backfilled with `movement_type='adjustment'`.
     Immutability enforcement (REVOKE UPDATE/DELETE + trigger, the same
     pattern migration 0004 gave `audit_logs` and migration 0011 gave
     `domain_events`/`digital_twin_versions`) is added here -- "every
     movement must be immutable" is this module's own named requirement.
  4. New `stock_reservations` table (hold-without-decrementing workflow).

RLS: `inventory_adjustments`'s existing join-based policy (migration 0003)
follows the table rename automatically (Postgres policies are bound to the
table's OID, not its name); it's dropped and recreated under the new name
purely for naming clarity, not because it stopped working. Two new
direct-tenant policies are added for `inventory_locations` and
`stock_reservations`.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

APP_ROLE = "nurseryverse_api"
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


def upgrade() -> None:
    # --- new enums ---
    # These are NOT created explicitly here: each is used as a column type
    # in exactly one op.create_table() below, which auto-creates the type
    # (without checkfirst). An explicit `.create()` here would emit CREATE
    # TYPE twice and fail.
    location_type = sa.Enum(
        "ZONE", "GREENHOUSE", "OUTDOOR_AREA", "RACK", "BENCH", "SECTION", name="inventory_location_type"
    )

    movement_type = sa.Enum(
        "INCOMING", "OUTGOING", "TRANSFER", "ADJUSTMENT", "WASTE", "DAMAGE",
        "RESERVATION", "RELEASE", "SALE", "ARCHIVE", name="stock_movement_type",
    )
    # movement_type is added to the pre-existing `stock_movements` table via
    # op.add_column() below (NOT a create_table), so it must be created
    # explicitly here.
    movement_type.create(op.get_bind(), checkfirst=True)

    reservation_status = sa.Enum(
        "ACTIVE", "RELEASED", "FULFILLED", "EXPIRED", name="stock_reservation_status"
    )

    op.execute("ALTER TYPE inventory_adjustment_reason ADD VALUE IF NOT EXISTS 'RETURN'")

    # --- inventory_locations ---
    op.create_table(
        "inventory_locations",
        sa.Column("nursery_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("parent_location_id", sa.UUID(), nullable=True),
        sa.Column("location_type", location_type, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["nursery_id"], ["nurseries.id"], name=op.f("fk_inventory_locations_nursery_id_nurseries"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"], name=op.f("fk_inventory_locations_branch_id_branches"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["parent_location_id"], ["inventory_locations.id"],
            name=op.f("fk_inventory_locations_parent_location_id_inventory_locations"), ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inventory_locations")),
    )
    op.create_index(
        "ix_inventory_locations_nursery_branch", "inventory_locations", ["nursery_id", "branch_id"], unique=False
    )
    op.create_index(
        "ix_inventory_locations_parent", "inventory_locations", ["parent_location_id"], unique=False
    )

    # --- inventory: Real-Time Stock + location + archive + concurrency columns ---
    op.add_column("inventory", sa.Column("location_id", sa.UUID(), nullable=True))
    op.add_column(
        "inventory", sa.Column("reserved_quantity", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "inventory", sa.Column("damaged_quantity", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "inventory", sa.Column("disposed_quantity", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column("inventory", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("inventory", sa.Column("version", sa.Integer(), server_default="1", nullable=False))
    op.create_foreign_key(
        op.f("fk_inventory_location_id_inventory_locations"),
        "inventory", "inventory_locations", ["location_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_inventory_location_id", "inventory", ["location_id"], unique=False)
    op.create_check_constraint(
        op.f("ck_inventory_reserved_quantity_non_negative"), "inventory", "reserved_quantity >= 0"
    )
    op.create_check_constraint(
        op.f("ck_inventory_damaged_quantity_non_negative"), "inventory", "damaged_quantity >= 0"
    )
    op.create_check_constraint(
        op.f("ck_inventory_disposed_quantity_non_negative"), "inventory", "disposed_quantity >= 0"
    )
    op.create_check_constraint(
        op.f("ck_inventory_reserved_damaged_le_quantity"),
        "inventory",
        "reserved_quantity + damaged_quantity <= quantity",
    )

    # --- stock_reservations (created before stock_movements so the latter's FK can reference it) ---
    op.create_table(
        "stock_reservations",
        sa.Column("nursery_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("inventory_id", sa.UUID(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", reservation_status, server_default="ACTIVE", nullable=False),
        sa.Column("reference_type", sa.String(length=50), nullable=True),
        sa.Column("reference_id", sa.UUID(), nullable=True),
        sa.Column("reserved_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reserved_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_stock_reservations_quantity_positive")),
        sa.ForeignKeyConstraint(
            ["nursery_id"], ["nurseries.id"], name=op.f("fk_stock_reservations_nursery_id_nurseries"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["branches.id"], name=op.f("fk_stock_reservations_branch_id_branches"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["inventory_id"], ["inventory.id"], name=op.f("fk_stock_reservations_inventory_id_inventory"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reserved_by_user_id"], ["users.id"], name=op.f("fk_stock_reservations_reserved_by_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_reservations")),
    )
    op.create_index(
        "ix_stock_reservations_inventory_status", "stock_reservations", ["inventory_id", "status"], unique=False
    )

    # --- inventory_adjustments -> stock_movements: rename + generalize ---
    op.rename_table("inventory_adjustments", "stock_movements")
    op.alter_column("stock_movements", "adjusted_by_user_id", new_column_name="performed_by_user_id")
    op.alter_column("stock_movements", "reason", nullable=True)
    op.add_column("stock_movements", sa.Column("movement_type", movement_type, nullable=True))
    op.execute("UPDATE stock_movements SET movement_type = 'ADJUSTMENT' WHERE movement_type IS NULL")
    op.alter_column("stock_movements", "movement_type", nullable=False)
    op.add_column("stock_movements", sa.Column("from_location_id", sa.UUID(), nullable=True))
    op.add_column("stock_movements", sa.Column("to_location_id", sa.UUID(), nullable=True))
    op.add_column("stock_movements", sa.Column("plant_id", sa.UUID(), nullable=True))
    op.add_column("stock_movements", sa.Column("reservation_id", sa.UUID(), nullable=True))
    op.add_column("stock_movements", sa.Column("transfer_group_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_stock_movements_from_location_id_inventory_locations"),
        "stock_movements", "inventory_locations", ["from_location_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_stock_movements_to_location_id_inventory_locations"),
        "stock_movements", "inventory_locations", ["to_location_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_stock_movements_plant_id_plants"),
        "stock_movements", "plants", ["plant_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_stock_movements_reservation_id_stock_reservations"),
        "stock_movements", "stock_reservations", ["reservation_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_stock_movements_movement_type", "stock_movements", ["movement_type"], unique=False)
    op.create_index("ix_stock_movements_plant_id", "stock_movements", ["plant_id"], unique=False)
    op.create_index(
        "ix_stock_movements_transfer_group", "stock_movements", ["transfer_group_id"], unique=False
    )
    op.drop_index("ix_inventory_adjustments_inventory_id", table_name="stock_movements")
    op.create_index(
        "ix_stock_movements_inventory_created", "stock_movements", ["inventory_id", "created_at"], unique=False
    )

    op.execute("ALTER TABLE stock_movements RENAME CONSTRAINT pk_inventory_adjustments TO pk_stock_movements")
    op.execute(
        "ALTER TABLE stock_movements RENAME CONSTRAINT "
        "fk_inventory_adjustments_inventory_id_inventory TO fk_stock_movements_inventory_id_inventory"
    )
    op.execute(
        "ALTER TABLE stock_movements RENAME CONSTRAINT "
        "fk_inventory_adjustments_adjusted_by_user_id_users TO fk_stock_movements_performed_by_user_id_users"
    )
    # The purchase_order FK was created in 0001 with a 66-char name
    # (fk_inventory_adjustments_reference_purchase_order_id_purchase_orders).
    # Postgres truncates over-long constraint names to 63 chars as
    # "<58 chars>_<4-hex-hash>", so its real stored name is
    # fk_inventory_adjustments_reference_purchase_order_id_pu_cc7c. The
    # intended rename target would ALSO exceed 63 chars, so RENAME can never
    # match. Drop it and re-create with a valid short name instead.
    op.execute(
        "ALTER TABLE stock_movements DROP CONSTRAINT "
        "fk_inventory_adjustments_reference_purchase_order_id_pu_cc7c"
    )
    op.create_foreign_key(
        op.f("fk_stock_movements_reference_purchase_order_id"),
        "stock_movements",
        "purchase_orders",
        ["reference_purchase_order_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        "ALTER TABLE stock_movements RENAME CONSTRAINT "
        "fk_inventory_adjustments_reference_sale_id_sales TO fk_stock_movements_reference_sale_id_sales"
    )

    # --- stock_movements: immutability (append-only ledger, migration 0004/0011 pattern) ---
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                REVOKE UPDATE, DELETE ON TABLE stock_movements FROM {APP_ROLE};
                GRANT INSERT, SELECT ON TABLE stock_movements TO {APP_ROLE};
            ELSE
                RAISE NOTICE 'Role % does not exist in this environment — skipping stock_movements grant revocation (expected in local dev connecting as superuser).', '{APP_ROLE}';
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION reject_stock_movement_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'stock_movements is immutable — % is not permitted (every movement must be immutable)', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_stock_movements_immutable
        BEFORE UPDATE OR DELETE ON stock_movements
        FOR EACH ROW EXECUTE FUNCTION reject_stock_movement_mutation();
        """
    )

    # --- RLS: rename the existing inventory_adjustments policy, add two new direct-tenant policies ---
    op.execute("ALTER POLICY tenant_isolation_inventory_adjustments ON stock_movements RENAME TO tenant_isolation_stock_movements")

    op.execute(_enable_and_force("inventory_locations"))
    op.execute(_direct_tenant_policy("inventory_locations"))

    op.execute(_enable_and_force("stock_reservations"))
    op.execute(_direct_tenant_policy("stock_reservations"))


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_stock_reservations ON stock_reservations;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_inventory_locations ON inventory_locations;")
    op.execute(
        "ALTER POLICY tenant_isolation_stock_movements ON stock_movements RENAME TO tenant_isolation_inventory_adjustments"
    )

    op.execute("DROP TRIGGER IF EXISTS trg_stock_movements_immutable ON stock_movements;")
    op.execute("DROP FUNCTION IF EXISTS reject_stock_movement_mutation();")
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                GRANT UPDATE, DELETE ON TABLE stock_movements TO {APP_ROLE};
            END IF;
        END
        $$;
        """
    )

    op.execute(
        "ALTER TABLE stock_movements RENAME CONSTRAINT "
        "fk_stock_movements_reference_sale_id_sales TO fk_inventory_adjustments_reference_sale_id_sales"
    )
    op.execute(
        "ALTER TABLE stock_movements DROP CONSTRAINT fk_stock_movements_reference_purchase_order_id"
    )
    op.execute(
        "ALTER TABLE stock_movements ADD CONSTRAINT "
        "fk_inventory_adjustments_reference_purchase_order_id_purchase_orders "
        "FOREIGN KEY (reference_purchase_order_id) REFERENCES purchase_orders (id) ON DELETE SET NULL"
    )
    op.execute(
        "ALTER TABLE stock_movements RENAME CONSTRAINT "
        "fk_stock_movements_performed_by_user_id_users TO fk_inventory_adjustments_adjusted_by_user_id_users"
    )
    op.execute(
        "ALTER TABLE stock_movements RENAME CONSTRAINT "
        "fk_stock_movements_inventory_id_inventory TO fk_inventory_adjustments_inventory_id_inventory"
    )
    op.execute("ALTER TABLE stock_movements RENAME CONSTRAINT pk_stock_movements TO pk_inventory_adjustments")

    op.drop_index("ix_stock_movements_inventory_created", table_name="stock_movements")
    op.create_index(
        "ix_inventory_adjustments_inventory_id", "stock_movements", ["inventory_id"], unique=False
    )
    op.drop_index("ix_stock_movements_transfer_group", table_name="stock_movements")
    op.drop_index("ix_stock_movements_plant_id", table_name="stock_movements")
    op.drop_index("ix_stock_movements_movement_type", table_name="stock_movements")
    op.drop_constraint(
        op.f("fk_stock_movements_reservation_id_stock_reservations"), "stock_movements", type_="foreignkey"
    )
    op.drop_constraint(op.f("fk_stock_movements_plant_id_plants"), "stock_movements", type_="foreignkey")
    op.drop_constraint(
        op.f("fk_stock_movements_to_location_id_inventory_locations"), "stock_movements", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("fk_stock_movements_from_location_id_inventory_locations"), "stock_movements", type_="foreignkey"
    )
    op.drop_column("stock_movements", "transfer_group_id")
    op.drop_column("stock_movements", "reservation_id")
    op.drop_column("stock_movements", "plant_id")
    op.drop_column("stock_movements", "to_location_id")
    op.drop_column("stock_movements", "from_location_id")
    op.drop_column("stock_movements", "movement_type")
    op.alter_column("stock_movements", "reason", nullable=False)
    op.alter_column("stock_movements", "performed_by_user_id", new_column_name="adjusted_by_user_id")
    op.rename_table("stock_movements", "inventory_adjustments")

    op.drop_index("ix_stock_reservations_inventory_status", table_name="stock_reservations")
    op.drop_table("stock_reservations")

    op.drop_constraint(op.f("ck_inventory_reserved_damaged_le_quantity"), "inventory", type_="check")
    op.drop_constraint(op.f("ck_inventory_disposed_quantity_non_negative"), "inventory", type_="check")
    op.drop_constraint(op.f("ck_inventory_damaged_quantity_non_negative"), "inventory", type_="check")
    op.drop_constraint(op.f("ck_inventory_reserved_quantity_non_negative"), "inventory", type_="check")
    op.drop_index("ix_inventory_location_id", table_name="inventory")
    op.drop_constraint(op.f("fk_inventory_location_id_inventory_locations"), "inventory", type_="foreignkey")
    op.drop_column("inventory", "version")
    op.drop_column("inventory", "archived_at")
    op.drop_column("inventory", "disposed_quantity")
    op.drop_column("inventory", "damaged_quantity")
    op.drop_column("inventory", "reserved_quantity")
    op.drop_column("inventory", "location_id")

    op.drop_index("ix_inventory_locations_parent", table_name="inventory_locations")
    op.drop_index("ix_inventory_locations_nursery_branch", table_name="inventory_locations")
    op.drop_table("inventory_locations")

    sa.Enum(name="stock_reservation_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="stock_movement_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="inventory_location_type").drop(op.get_bind(), checkfirst=True)
    # Note: 'RETURN' value added to inventory_adjustment_reason is not removed on
    # downgrade -- PostgreSQL does not support removing enum values (ALTER TYPE ...
    # DROP VALUE does not exist); this is the same documented limitation every
    # prior ADD VALUE migration in this project accepts.
