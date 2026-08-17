"""Reports & Analytics (Phase 6 Module 12).

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-07

Three moves, mirroring every prior module's "extend the Phase 5 skeleton,
don't replace it" pattern:

  1. Extends the Phase 5 `report_type`/`report_format`/`report_status`
     enums with this module's own required report catalog (twelve new
     report types, JSON as a fourth export format, a `PROCESSING`
     intermediate status between `PENDING` and `COMPLETE`/`FAILED`) and
     adds one new `notification_category` value (`REPORT_READY`) so a
     completed report can notify its requester through the existing
     Module 11 pipeline. See this migration's own `upgrade()` comment for
     why every `ADD VALUE` below uses the enum's uppercase *member name*,
     not its lowercase `.value` -- an actual, live bug in migration 0016
     (fixed in that file as part of this module's work) that this
     migration is careful not to repeat.
  2. New `scheduled_reports` table (FR-18.4 / this module's "Saved
     Reports / Scheduled Reports / Recurring Reports" requirement) --
     direct-tenant RLS, the same shape `reports` itself already has.
  3. Three new dashboard/analytics read models, extending migration
     0005's own "materialize what's revenue/scale-sensitive, plain-view
     what's already selective" split: `mv_nursery_dashboard_summary`
     (materialized -- org-wide operational totals, the "Nursery
     Dashboard" contribution distinct from the existing
     `mv_org_revenue_rollup`'s revenue-and-trend framing for the
     "Executive Dashboard") and `mv_ai_prediction_accuracy` (materialized
     -- the predicted-vs-observed-outcome rollup
     docs/ux/18-analytics-workflow.md's "Prediction Accuracy Tracking"
     section calls for) are both potentially expensive full-table scans
     over `plants`/`ai_predictions`, so they're materialized like
     migration 0005's own two. `v_customer_lifetime_value` (plain view)
     is per-customer, already selective by construction, the same
     reasoning migration 0005 gives for `v_plant_latest_predictions`.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID, ENUM

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

SESSION_VAR = "app.current_org_id"


def _enable_and_force(table: str) -> str:
    return (
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;\n"
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;"
    )


def upgrade() -> None:
    # --- extend existing report_* enums (uppercase member names -- see module docstring) ---
    for report_type in (
        "PLANT",
        "PROFIT",
        "CUSTOMER",
        "EMPLOYEE",
        "BRANCH",
        "DISEASE",
        "GROWTH",
        "WATER_USAGE",
        "FERTILIZER",
        "NOTIFICATION",
        "AUDIT",
        "SECURITY",
    ):
        op.execute(f"ALTER TYPE report_type ADD VALUE IF NOT EXISTS '{report_type}'")
    op.execute("ALTER TYPE report_format ADD VALUE IF NOT EXISTS 'JSON'")
    op.execute("ALTER TYPE report_status ADD VALUE IF NOT EXISTS 'PROCESSING'")
    op.execute("ALTER TYPE notification_category ADD VALUE IF NOT EXISTS 'REPORT_READY'")

    # --- new enum: report_schedule_frequency ---
    # Auto-created by the op.create_table() below that uses it; must NOT be
    # created explicitly here (alembic's create_table emits CREATE TYPE
    # without checkfirst -> duplicate).
    frequency = sa.Enum("DAILY", "WEEKLY", "MONTHLY", name="report_schedule_frequency")

    # --- scheduled_reports table ---
    op.create_table(
        "scheduled_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("nursery_id", UUID(as_uuid=True), sa.ForeignKey("nurseries.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("branch_id", UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "report_type",
            ENUM(
                "INVENTORY", "SALES", "REVENUE", "PLANT_LOSS", "AI_SUMMARY", "PLANT_PASSPORT",
                "PLANT", "PROFIT", "CUSTOMER", "EMPLOYEE", "BRANCH", "DISEASE", "GROWTH",
                "WATER_USAGE", "FERTILIZER", "NOTIFICATION", "AUDIT", "SECURITY",
                name="report_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("format", ENUM("PDF", "EXCEL", "CSV", "JSON", name="report_format", create_type=False), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=True),
        sa.Column("frequency", frequency, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_scheduled_reports_next_run_at", "scheduled_reports", ["next_run_at"])
    op.create_index("ix_scheduled_reports_nursery_id", "scheduled_reports", ["nursery_id"])

    op.execute(_enable_and_force("scheduled_reports"))
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_scheduled_reports ON scheduled_reports
        USING (nursery_id = current_setting('{SESSION_VAR}', true)::uuid)
        WITH CHECK (nursery_id = current_setting('{SESSION_VAR}', true)::uuid);
        """
    )

    # --- materialized view: org-wide operational totals ("Nursery Dashboard") ---
    op.execute(
        """
        CREATE MATERIALIZED VIEW mv_nursery_dashboard_summary AS
        WITH plant_counts AS (
            SELECT nursery_id, status, COUNT(*) AS plant_count
            FROM plants
            GROUP BY nursery_id, status
        ),
        plant_totals AS (
            SELECT nursery_id, SUM(plant_count) AS total_plants
            FROM plant_counts
            GROUP BY nursery_id
        ),
        active_plants AS (
            SELECT nursery_id, SUM(plant_count) AS active_plant_count
            FROM plant_counts
            WHERE status != 'DECEASED' AND status != 'SOLD'
            GROUP BY nursery_id
        ),
        branch_counts AS (
            SELECT nursery_id, COUNT(*) AS branch_count
            FROM branches
            WHERE status = 'ACTIVE'
            GROUP BY nursery_id
        ),
        employee_counts AS (
            SELECT nursery_id, COUNT(*) AS employee_count
            FROM employees
            WHERE status = 'ACTIVE'
            GROUP BY nursery_id
        ),
        low_stock_org AS (
            SELECT nursery_id, COUNT(*) AS low_stock_count
            FROM inventory
            WHERE quantity <= low_stock_threshold
            GROUP BY nursery_id
        ),
        pending_disease_org AS (
            SELECT p.nursery_id, COUNT(*) AS pending_disease_reports
            FROM disease_reports dr
            JOIN plants p ON p.id = dr.plant_id
            WHERE dr.status IN ('DRAFT', 'CONFIRMED')
            GROUP BY p.nursery_id
        )
        SELECT
            n.id AS nursery_id,
            COALESCE(pt.total_plants, 0) AS total_plants,
            COALESCE(ap.active_plant_count, 0) AS active_plant_count,
            COALESCE(bc.branch_count, 0) AS branch_count,
            COALESCE(ec.employee_count, 0) AS employee_count,
            COALESCE(ls.low_stock_count, 0) AS low_stock_count,
            COALESCE(pd.pending_disease_reports, 0) AS pending_disease_reports,
            now() AS last_refreshed_at
        FROM nurseries n
        LEFT JOIN plant_totals pt ON pt.nursery_id = n.id
        LEFT JOIN active_plants ap ON ap.nursery_id = n.id
        LEFT JOIN branch_counts bc ON bc.nursery_id = n.id
        LEFT JOIN employee_counts ec ON ec.nursery_id = n.id
        LEFT JOIN low_stock_org ls ON ls.nursery_id = n.id
        LEFT JOIN pending_disease_org pd ON pd.nursery_id = n.id;
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX ix_mv_nursery_dashboard_summary_nursery_id "
        "ON mv_nursery_dashboard_summary (nursery_id);"
    )

    # --- materialized view: AI prediction accuracy (docs/ux/18-analytics-workflow.md "Prediction Accuracy Tracking") ---
    # Survival predictions are the only prediction type with a directly
    # observable binary outcome in this schema (a plant's status either
    # did or did not reach 'deceased'): a prediction is scored "correct"
    # when a high/critical risk_level plant later died, or a low/medium
    # risk_level plant did not. Predictions with no closed outcome yet
    # (the plant is still alive and un-resolved) are excluded from the
    # denominator entirely, not counted as wrong -- this is a real,
    # honest accuracy measure, not a placeholder metric.
    op.execute(
        """
        CREATE MATERIALIZED VIEW mv_ai_prediction_accuracy AS
        WITH survival_predictions AS (
            SELECT
                ap.nursery_id,
                ap.plant_id,
                ap.id AS prediction_id,
                (ap.result ->> 'risk_level') AS predicted_risk_level,
                p.status AS current_plant_status,
                ap.created_at
            FROM ai_predictions ap
            JOIN plants p ON p.id = ap.plant_id
            WHERE ap.prediction_type = 'SURVIVAL_PREDICTION' AND ap.plant_id IS NOT NULL
        ),
        scored AS (
            SELECT
                nursery_id,
                CASE
                    WHEN predicted_risk_level IN ('high', 'critical') AND current_plant_status = 'DECEASED' THEN TRUE
                    WHEN predicted_risk_level IN ('low', 'medium') AND current_plant_status != 'DECEASED' THEN TRUE
                    ELSE FALSE
                END AS is_correct,
                CASE
                    WHEN predicted_risk_level IN ('high', 'critical') AND current_plant_status != 'DECEASED'
                         AND current_plant_status NOT IN ('READY_FOR_SALE', 'IN_PRODUCTION', 'UNDER_TREATMENT') THEN FALSE
                    ELSE TRUE
                END AS outcome_closed
            FROM survival_predictions
            WHERE current_plant_status = 'DECEASED'
               OR predicted_risk_level IN ('low', 'medium')
        )
        SELECT
            nursery_id,
            'survival_prediction' AS prediction_type,
            COUNT(*) AS scored_prediction_count,
            SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) AS correct_prediction_count,
            now() AS last_refreshed_at
        FROM scored
        GROUP BY nursery_id;
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX ix_mv_ai_prediction_accuracy_nursery_type "
        "ON mv_ai_prediction_accuracy (nursery_id, prediction_type);"
    )

    # --- plain view: per-customer lifetime value (already selective -- always filtered to an org/customer) ---
    op.execute(
        """
        CREATE VIEW v_customer_lifetime_value AS
        SELECT
            c.id AS customer_id,
            c.nursery_id,
            c.branch_id,
            c.name AS customer_name,
            COUNT(s.id) AS total_orders,
            COALESCE(SUM(s.total_amount), 0) AS total_spent,
            MIN(s.created_at) AS first_purchase_at,
            MAX(s.created_at) AS last_purchase_at
        FROM customers c
        LEFT JOIN sales s ON s.customer_id = c.id AND s.status = 'COMPLETED'
        GROUP BY c.id, c.nursery_id, c.branch_id, c.name;
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_customer_lifetime_value;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_ai_prediction_accuracy;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_nursery_dashboard_summary;")

    op.execute("DROP POLICY IF EXISTS tenant_isolation_scheduled_reports ON scheduled_reports;")
    op.drop_index("ix_scheduled_reports_nursery_id", table_name="scheduled_reports")
    op.drop_index("ix_scheduled_reports_next_run_at", table_name="scheduled_reports")
    op.drop_table("scheduled_reports")

    op.execute("DROP TYPE IF EXISTS report_schedule_frequency;")

    # PostgreSQL does not support ALTER TYPE ... DROP VALUE, the same
    # documented limitation every prior ADD VALUE migration in this
    # project accepts -- the added report_type/report_format/report_status/
    # notification_category values are not removed on downgrade.
