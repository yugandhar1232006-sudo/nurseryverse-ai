"""
`RollupRefreshService.refresh_dirty()` -- the on-demand substitute for the
Celery Beat scheduled `REFRESH MATERIALIZED VIEW CONCURRENTLY` job
`docs/ux/18-analytics-workflow.md`'s Aggregation Pipeline diagram
describes (no Celery worker exists anywhere in this codebase). Reachable
via `POST /analytics/refresh-rollups`, the same "on-demand sweep, callers
decide the cadence" shape `POST /notifications/retry-due` (Module 11) and
`POST /ai/recommendations/refresh` (Module 10) already established for
this codebase's identical, disclosed background-job-infrastructure gap.

Only refreshes views `AnalyticsEventHandler` has actually marked dirty
since the last refresh -- an idle nursery with no writes since the last
call does zero work, not a blind refresh-everything sweep.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.reporting.analytics_event_handler import ALL_MATERIALIZED_VIEWS
from app.reporting.rollup_tracker import RollupRefreshTracker

logger = get_logger(__name__)


class RollupRefreshService:
    def __init__(self, *, db: AsyncSession, tracker: RollupRefreshTracker) -> None:
        self._db = db
        self._tracker = tracker

    async def refresh_dirty(self) -> list[str]:
        """Refreshes every currently-dirty materialized view and returns the list of view names actually refreshed."""
        dirty = [v for v in ALL_MATERIALIZED_VIEWS if self._tracker.is_dirty(v)]
        for view in dirty:
            # View names come only from this module's own fixed
            # `ALL_MATERIALIZED_VIEWS` set (never user input), so this is
            # not a SQL-injection surface despite the f-string -- the same
            # reasoning `_enable_and_force`/`_join_tenant_policy` in the
            # migrations already rely on for DDL identifiers, which
            # `text()` bind parameters cannot substitute for anyway
            # (Postgres does not allow object names as bind parameters).
            await self._db.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"))
            logger.info("rollup_refreshed", view=view)
        self._tracker.clear(*dirty)
        return dirty
