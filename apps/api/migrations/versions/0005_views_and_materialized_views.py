"""Views and materialized views — dashboard/reporting rollups.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-05

Implements docs/ux/18-analytics-workflow.md's "Aggregation Pipeline" and
the dashboard-vs-report performance split from
docs/architecture/09-infrastructure.md / NFR-1.3 (dashboard content within
2 seconds): dashboards read from a materialized view refreshed on a short
interval, not a live aggregate query over the full sales/ai_predictions
history, per the documented tradeoff (near-real-time freshness for
guaranteed responsiveness). Refresh is triggered by a scheduled Celery
Beat job (`app/workers/beat_schedule.py`, Phase 6) calling
`REFRESH MATERIALIZED VIEW CONCURRENTLY`, not by a database trigger — a
trigger-per-write refresh would defeat the entire point of pre-aggregation
by turning every sale/prediction insert into an O(branches) recompute.

Plain (non-materialized) views are used for the plant-level query patterns
that are already selective (single-plant lookups) and don't need
pre-aggregation to meet the performance budget.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # --- Materialized view: per-branch dashboard summary (PG-08) ---
    # Refreshed every ~15 minutes by Celery Beat (docs/ux/18-analytics-workflow.md
    # "Why Pre-Aggregation"). Watering-overdue counts are deliberately NOT
    # included here: they depend on each branch's configurable
    # default_watering_overdue_hours threshold (branches table), which
    # makes them a per-request computed value in the service layer rather
    # than a pre-aggregable rollup with a single fixed interpretation.
    op.execute(
        """
        CREATE MATERIALIZED VIEW mv_branch_dashboard_summary AS
        WITH revenue_today AS (
            SELECT branch_id, COALESCE(SUM(total_amount), 0) AS revenue_today
            FROM sales
            WHERE status = 'COMPLETED'
              AND created_at >= date_trunc('day', now())
            GROUP BY branch_id
        ),
        revenue_mtd AS (
            SELECT branch_id, COALESCE(SUM(total_amount), 0) AS revenue_mtd
            FROM sales
            WHERE status = 'COMPLETED'
              AND created_at >= date_trunc('month', now())
            GROUP BY branch_id
        ),
        latest_survival_prediction AS (
            SELECT DISTINCT ON (plant_id) plant_id, branch_id, result, confidence
            FROM ai_predictions
            WHERE prediction_type = 'SURVIVAL_PREDICTION' AND plant_id IS NOT NULL
            ORDER BY plant_id, created_at DESC
        ),
        at_risk_counts AS (
            SELECT branch_id, COUNT(*) AS at_risk_plant_count
            FROM latest_survival_prediction
            WHERE (result ->> 'risk_level') IN ('high', 'critical')
            GROUP BY branch_id
        ),
        low_stock AS (
            SELECT branch_id, COUNT(*) AS low_stock_count
            FROM inventory
            WHERE quantity <= low_stock_threshold
            GROUP BY branch_id
        ),
        pending_disease AS (
            SELECT p.branch_id, COUNT(*) AS pending_disease_reports
            FROM disease_reports dr
            JOIN plants p ON p.id = dr.plant_id
            WHERE dr.status IN ('DRAFT', 'CONFIRMED')
            GROUP BY p.branch_id
        )
        SELECT
            b.id AS branch_id,
            b.nursery_id,
            COALESCE(rt.revenue_today, 0) AS revenue_today,
            COALESCE(rm.revenue_mtd, 0) AS revenue_mtd,
            COALESCE(ar.at_risk_plant_count, 0) AS at_risk_plant_count,
            COALESCE(ls.low_stock_count, 0) AS low_stock_count,
            COALESCE(pd.pending_disease_reports, 0) AS pending_disease_reports,
            now() AS last_refreshed_at
        FROM branches b
        LEFT JOIN revenue_today rt ON rt.branch_id = b.id
        LEFT JOIN revenue_mtd rm ON rm.branch_id = b.id
        LEFT JOIN at_risk_counts ar ON ar.branch_id = b.id
        LEFT JOIN low_stock ls ON ls.branch_id = b.id
        LEFT JOIN pending_disease pd ON pd.branch_id = b.id
        WHERE b.status = 'ACTIVE';
        """
    )
    # A unique index is required for CONCURRENTLY refresh (Postgres
    # requirement — without it, REFRESH MATERIALIZED VIEW CONCURRENTLY
    # fails; this is not optional).
    op.execute(
        "CREATE UNIQUE INDEX ix_mv_branch_dashboard_summary_branch_id "
        "ON mv_branch_dashboard_summary (branch_id);"
    )

    # --- Materialized view: org-wide revenue rollup (PG-07) ---
    op.execute(
        """
        CREATE MATERIALIZED VIEW mv_org_revenue_rollup AS
        SELECT
            n.id AS nursery_id,
            date_trunc('day', s.created_at) AS day,
            SUM(s.total_amount) AS revenue,
            COUNT(*) AS sale_count
        FROM sales s
        JOIN branches b ON b.id = s.branch_id
        JOIN nurseries n ON n.id = b.nursery_id
        WHERE s.status = 'COMPLETED'
        GROUP BY n.id, date_trunc('day', s.created_at);
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX ix_mv_org_revenue_rollup_nursery_day "
        "ON mv_org_revenue_rollup (nursery_id, day);"
    )

    # --- Plain view: plant digital twin overview (PG-22 Overview tab) ---
    # Selective by construction (always filtered to a single plant_id by
    # the caller), so no materialization needed — this view exists purely
    # to keep the "latest prediction per module" DISTINCT ON pattern in
    # one reusable place instead of duplicated across repository queries.
    op.execute(
        """
        CREATE VIEW v_plant_latest_predictions AS
        SELECT DISTINCT ON (plant_id, prediction_type)
            plant_id,
            prediction_type,
            id AS prediction_id,
            model_version,
            result,
            confidence,
            explanation,
            created_at
        FROM ai_predictions
        WHERE plant_id IS NOT NULL
        ORDER BY plant_id, prediction_type, created_at DESC;
        """
    )

    # --- Plain view: low-stock inventory (PG-36 attention banner) ---
    op.execute(
        """
        CREATE VIEW v_low_stock_inventory AS
        SELECT i.*
        FROM inventory i
        WHERE i.quantity <= i.low_stock_threshold;
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_low_stock_inventory;")
    op.execute("DROP VIEW IF EXISTS v_plant_latest_predictions;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_org_revenue_rollup;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_branch_dashboard_summary;")
