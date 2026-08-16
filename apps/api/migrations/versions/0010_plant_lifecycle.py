"""Plant Lifecycle Management (Phase 6 Module 6).

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-05

Why this migration exists: building the actual Plant Registration/Profile
endpoints surfaced two gaps in Phase 5's `plants`/`plant_transfers` schema
relative to Module 6's explicit requirements:

  - `plants` had no way to record "Batch", "Supplier", or "Purchase
    information" (Module 6's own Plant Profile requirement), nor any
    explicit "Plant ownership tracking" field beyond the implicit
    nursery_id/branch_id scoping every BranchScopedMixin table already
    carries. Added: `batch_number` (free-text batch/lot label -- Phase 5
    never modeled batches as their own table, and one wasn't warranted for
    a single descriptive field), `supplier_id` (FK to the `suppliers`
    table Phase 5's Suppliers & Purchasing module already created --
    reusing it rather than duplicating supplier data onto `plants`),
    `purchase_price`/`purchase_date` (the "purchase information"
    requirement), and `registered_by_user_id` (who registered/is
    accountable for this plant -- the concrete, auditable form "ownership
    tracking" takes here, consistent with every other `*_by_user_id`
    provenance column already in the schema, e.g. `WateringLog.
    recorded_by_user_id`).
  - `plants` also had no column for the API-level "Archive" action Module
    6's own spec lists alongside Create/Update/Search/Filter/Sort/
    Paginate. This is deliberately NOT a sixth `PlantStatus` value (see
    below) -- it's the same administrative "hide from default listings,
    keep forever" concept `NurseryStatus.ARCHIVED`/`BranchStatus.INACTIVE`
    already model for their own tables, expressed the same way `sold_at`/
    `deceased_at` already are on this very table: a nullable timestamp,
    not a status enum member. Added `archived_at`/`archived_reason`.
  - The five append-only Digital Twin history tables Phase 5 already
    created (`growth_timeline`, `health_history`, `watering_logs`,
    `fertilizer_logs`, `environmental_readings`) each fell short of one or
    more fields Module 6's own spec explicitly lists by name for that
    record type: Growth Records wants "Leaf count/Flower count/Fruit
    count" and "Images" (plural) alongside the existing height/spread/
    single photo_url; Health Records wants a numeric "Health score" and a
    manual-vs-AI observation distinction (mirroring `DiseaseReport.
    is_ai_sourced`'s already-established pattern) alongside the existing
    free-text status_label; Watering Records wants "Method"; Fertilizer
    Records wants "Method", "Schedule", and "Next application" alongside
    the existing product/quantity/npk_ratio; Environmental Records wants
    "pH" and "Weather snapshot" alongside the existing temperature/
    humidity/soil-moisture/light. Each gets its missing columns, all
    nullable (append-only logs never had a NOT NULL default problem to
    solve -- every new column here is optional detail on an already-
    working table, not a new required field older rows would violate).
  - `plant_transfers` only modeled branch-to-branch movement
    (`from_branch_id`/`to_branch_id`), but Module 6 also requires "Zone
    transfer", "Greenhouse movement", and "Outdoor movement" tracking with
    history. Rather than create three near-identical append-only tables
    (rejected as duplicate business logic -- see Module 6's own "Do not
    create duplicate business logic" instruction), `plant_transfers` gains
    nullable `from_zone`/`to_zone` columns and becomes the single movement-
    history table for every kind of Plant Movement: a branch transfer sets
    from/to branch with zone columns null or unchanged; a zone-only,
    greenhouse, or outdoor move sets from_branch_id = to_branch_id (the
    plant's current branch) with from_zone/to_zone populated. One table,
    one history, one query for "this plant's full movement history" --
    exactly what the requirement asks for.

No new enum type and no new business-status value: `PlantStatus` (5
values: in_production/ready_for_sale/under_treatment/sold/deceased) is
left completely unchanged. See docs/architecture/22-module6-plant-
lifecycle.md for the full reasoning on how Module 6's prompt vocabulary
(Seedling/Growing/Mature/Ready for Sale/Reserved/Sold/Quarantine/Diseased/
Disposed/Archived) maps onto the already-approved, richly-specified
5-state machine in docs/ux/13-digital-twin-lifecycle.md -- in short:
Seedling/Growing/Mature map onto the pre-existing free-text
`growth_timeline.growth_stage` column (not a Plant.status value);
Quarantine/Diseased map onto Under Treatment; Disposed maps onto Deceased;
Archived is already satisfied by Sold/Deceased being genuine terminal,
non-deleted "historical record" states per the lifecycle doc's own
language (no separate ARCHIVED value is needed -- adding one would be the
exact kind of unjustified scope creep `BranchStatus`'s docstring already
rejected for the same reason); Reserved belongs to the not-yet-built
Sales module (a point-of-sale cart hold), not the Plant lifecycle itself.

Generated mechanically (not hand-typed) for the AddColumnOp portions via
the same technique as every prior migration since 0001.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # --- plants: batch / supplier / purchase info / ownership tracking ---
    op.add_column("plants", sa.Column("batch_number", sa.String(length=100), nullable=True))
    op.add_column("plants", sa.Column("supplier_id", sa.UUID(), nullable=True))
    op.add_column("plants", sa.Column("purchase_price", sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column("plants", sa.Column("purchase_date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("plants", sa.Column("registered_by_user_id", sa.UUID(), nullable=True))
    op.add_column("plants", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("plants", sa.Column("archived_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        op.f("fk_plants_supplier_id_suppliers"),
        "plants",
        "suppliers",
        ["supplier_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_plants_registered_by_user_id_users"),
        "plants",
        "users",
        ["registered_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_plants_batch_number", "plants", ["batch_number"], unique=False)
    op.create_index("ix_plants_supplier_id", "plants", ["supplier_id"], unique=False)

    # --- plant_transfers: zone / greenhouse / outdoor movement history ---
    op.add_column("plant_transfers", sa.Column("from_zone", sa.String(length=100), nullable=True))
    op.add_column("plant_transfers", sa.Column("to_zone", sa.String(length=100), nullable=True))

    # --- growth_timeline: leaf/flower/fruit count + multi-image support ---
    op.add_column("growth_timeline", sa.Column("leaf_count", sa.Integer(), nullable=True))
    op.add_column("growth_timeline", sa.Column("flower_count", sa.Integer(), nullable=True))
    op.add_column("growth_timeline", sa.Column("fruit_count", sa.Integer(), nullable=True))
    op.add_column("growth_timeline", sa.Column("photo_urls", sa.JSON(), nullable=True))

    # --- health_history: numeric health score + manual/AI observation source ---
    op.add_column("health_history", sa.Column("health_score", sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column(
        "health_history", sa.Column("is_ai_observation", sa.Boolean(), server_default=sa.false(), nullable=False)
    )

    # --- watering_logs: application method ---
    op.add_column("watering_logs", sa.Column("method", sa.String(length=50), nullable=True))

    # --- fertilizer_logs: application method + recurring schedule + next application ---
    op.add_column("fertilizer_logs", sa.Column("method", sa.String(length=50), nullable=True))
    op.add_column("fertilizer_logs", sa.Column("schedule", sa.String(length=50), nullable=True))
    op.add_column("fertilizer_logs", sa.Column("next_application_date", sa.DateTime(timezone=True), nullable=True))

    # --- environmental_readings: pH + weather snapshot ---
    op.add_column("environmental_readings", sa.Column("ph_level", sa.Numeric(precision=4, scale=2), nullable=True))
    op.add_column("environmental_readings", sa.Column("weather_snapshot", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("environmental_readings", "weather_snapshot")
    op.drop_column("environmental_readings", "ph_level")

    op.drop_column("fertilizer_logs", "next_application_date")
    op.drop_column("fertilizer_logs", "schedule")
    op.drop_column("fertilizer_logs", "method")

    op.drop_column("watering_logs", "method")

    op.drop_column("health_history", "is_ai_observation")
    op.drop_column("health_history", "health_score")

    op.drop_column("growth_timeline", "photo_urls")
    op.drop_column("growth_timeline", "fruit_count")
    op.drop_column("growth_timeline", "flower_count")
    op.drop_column("growth_timeline", "leaf_count")

    op.drop_column("plant_transfers", "to_zone")
    op.drop_column("plant_transfers", "from_zone")

    op.drop_index("ix_plants_supplier_id", table_name="plants")
    op.drop_index("ix_plants_batch_number", table_name="plants")
    op.drop_constraint(op.f("fk_plants_registered_by_user_id_users"), "plants", type_="foreignkey")
    op.drop_constraint(op.f("fk_plants_supplier_id_suppliers"), "plants", type_="foreignkey")
    op.drop_column("plants", "archived_reason")
    op.drop_column("plants", "archived_at")
    op.drop_column("plants", "registered_by_user_id")
    op.drop_column("plants", "purchase_date")
    op.drop_column("plants", "purchase_price")
    op.drop_column("plants", "supplier_id")
    op.drop_column("plants", "batch_number")
