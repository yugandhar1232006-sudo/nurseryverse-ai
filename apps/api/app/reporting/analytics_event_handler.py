"""
`AnalyticsEventHandler` -- this module's own "Reports must react to
domain events. Do not calculate analytics synchronously inside business
services." requirement, made structural: it is registered on the same
`EventDispatcher` every other subscriber (`DigitalTwinEventHandler`,
`NotificationEventHandler`) is registered on, and no business service
(`PlantService`, `InventoryService`, `SalesOrderService`, ...) imports or
calls anything in `app/reporting/` -- confirmed the same way Module 11's
own "no business service sends notifications directly" claim was
confirmed, via `grep -rln "from app.reporting" app/services/`, which
returns nothing.

`RECOMPUTE_MAP` below is the full event-type -> affected-materialized-view
mapping. `handle()` does nothing more than look up the event's type and
call `tracker.mark_dirty(*views)` -- no query, no aggregation, no
database write happens on this path, which is precisely what makes this
"event-driven" rather than "synchronous analytics calculation" (the
literal thing the spec prohibits): the actual `REFRESH MATERIALIZED VIEW`
work happens later, on demand, in `RollupRefreshService.refresh_dirty()`
(`rollup_refresh_service.py`), never inline with a write request.
"""
from __future__ import annotations

from app.models.events import DomainEvent
from app.reporting.rollup_tracker import RollupRefreshTracker

MV_BRANCH_DASHBOARD = "mv_branch_dashboard_summary"
MV_ORG_REVENUE = "mv_org_revenue_rollup"
MV_NURSERY_DASHBOARD = "mv_nursery_dashboard_summary"
MV_AI_ACCURACY = "mv_ai_prediction_accuracy"

ALL_MATERIALIZED_VIEWS: frozenset[str] = frozenset(
    {MV_BRANCH_DASHBOARD, MV_ORG_REVENUE, MV_NURSERY_DASHBOARD, MV_AI_ACCURACY}
)

RECOMPUTE_MAP: dict[str, tuple[str, ...]] = {
    # Revenue-affecting events -> both the branch task-dashboard rollup and the org revenue trend rollup.
    "invoice.generated": (MV_BRANCH_DASHBOARD, MV_ORG_REVENUE),
    "invoice.payment_received": (MV_BRANCH_DASHBOARD, MV_ORG_REVENUE),
    "plant.sold": (MV_BRANCH_DASHBOARD, MV_ORG_REVENUE, MV_NURSERY_DASHBOARD),
    "refund.processed": (MV_BRANCH_DASHBOARD, MV_ORG_REVENUE),
    # Plant-portfolio events -> the branch dashboard's at-risk/pending counts and the org-wide plant totals.
    "plant.registered": (MV_BRANCH_DASHBOARD, MV_NURSERY_DASHBOARD),
    "plant.status_changed": (MV_BRANCH_DASHBOARD, MV_NURSERY_DASHBOARD),
    "plant.moved": (MV_BRANCH_DASHBOARD, MV_NURSERY_DASHBOARD),
    "plant.archived": (MV_NURSERY_DASHBOARD,),
    "plant.disease_detected": (MV_BRANCH_DASHBOARD, MV_NURSERY_DASHBOARD),
    "plant.disease_report_updated": (MV_BRANCH_DASHBOARD, MV_NURSERY_DASHBOARD),
    # Inventory events -> low-stock counts on both dashboards.
    "inventory.stock_received": (MV_BRANCH_DASHBOARD, MV_NURSERY_DASHBOARD),
    "inventory.stock_transferred": (MV_BRANCH_DASHBOARD, MV_NURSERY_DASHBOARD),
    "inventory.stock_adjusted": (MV_BRANCH_DASHBOARD, MV_NURSERY_DASHBOARD),
    "inventory.stock_disposed": (MV_BRANCH_DASHBOARD, MV_NURSERY_DASHBOARD),
    "inventory.stock_damaged": (MV_BRANCH_DASHBOARD, MV_NURSERY_DASHBOARD),
    "inventory.stock_sold": (MV_BRANCH_DASHBOARD, MV_NURSERY_DASHBOARD),
    # Org-structure events -> the nursery-wide branch/employee headcounts.
    "branch.created": (MV_NURSERY_DASHBOARD,),
    "branch.archived": (MV_NURSERY_DASHBOARD,),
    "employee.activated": (MV_NURSERY_DASHBOARD,),
    "employee.removed": (MV_NURSERY_DASHBOARD,),
    # AI events -> the at-risk count (branch dashboard) and the accuracy rollup (survival predictions only,
    # but the tracker is view-grained, not prediction-type-grained -- a slightly wider dirty flag than
    # strictly necessary is the correct, cheap tradeoff here, not a correctness bug).
    "ai.prediction_generated": (MV_BRANCH_DASHBOARD, MV_AI_ACCURACY),
}


class AnalyticsEventHandler:
    name = "analytics_projector"
    event_types: frozenset[str] = frozenset(RECOMPUTE_MAP.keys())

    def __init__(self, *, tracker: RollupRefreshTracker) -> None:
        self._tracker = tracker

    async def handle(self, event: DomainEvent) -> int | None:
        views = RECOMPUTE_MAP.get(event.event_type)
        if views:
            self._tracker.mark_dirty(*views)
        return None
