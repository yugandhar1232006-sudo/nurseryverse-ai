"""
Phase 6 Module 12 (Reports & Analytics) — the read side of this codebase's
CQRS split.

Nothing in `app/services/*.py` (the write side -- Plants, Inventory,
Sales, ...) imports anything from this package, and nothing in this
package ever writes to an operational table: `AnalyticsEventHandler`
below is a passive subscriber that only flags pre-aggregated rollups as
stale, `DashboardService`/`AnalyticsService` (this module's services) only
ever read (through `ReportingRepository`, never a raw operational
repository or inline query), and `ReportGenerationService` writes
exclusively to its own `reports`/`scheduled_reports` tables plus whatever
export file it produces -- never back into `plants`/`sales`/`inventory`/
etc. This is the same "business modules publish events, they never call
into this module" shape Module 11 established for Notifications, applied
to the read/reporting side instead of the write/delivery side.

`AnalyticsEventHandler` (`analytics_event_handler.py`) is registered on
the same `EventDispatcher` as `DigitalTwinEventHandler`/
`NotificationEventHandler` and reacts to domain events by marking the
affected materialized view(s) dirty in an in-memory `RollupRefreshTracker`
(`rollup_tracker.py`) -- it does NOT run `REFRESH MATERIALIZED VIEW`
synchronously inside the event-handling path. Refreshing a materialized
view is an O(full table scan) operation; doing it on every single
sale/plant/inventory write would reintroduce exactly the "every write
triggers an O(branches) recompute" anti-pattern migration 0005's own
docstring calls out as the reason pre-aggregation exists in the first
place. Instead, `RollupRefreshService.refresh_dirty()` -- callable
on-demand via `POST /analytics/refresh-rollups` -- is this codebase's
usual substitute for the Celery Beat scheduled refresh
`docs/ux/18-analytics-workflow.md` describes (no Celery worker
infrastructure exists anywhere in this codebase; see Module 10/11's
identical, already-disclosed substitution for `POST /ai/recommendations/
refresh` and `POST /notifications/retry-due`).
"""
