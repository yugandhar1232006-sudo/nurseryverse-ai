"""
Executive/Nursery/Branch/Plant/Inventory/Sales/Customer/AI/Financial
Dashboards. A thin, read-only pass-through to `ReportingRepository` --
this module's own CQRS read side (app/repositories/interfaces.py's
`ReportingRepository` Protocol docstring) -- deliberately with no
business logic of its own: every number a dashboard shows is either a
pre-aggregated materialized-view row or a purpose-built aggregate query,
computed once in the repository layer, not recomputed here. Authorization
(the `reports:read` permission + tenant-ownership of `nursery_id`/
`branch_id`) is enforced at the route layer, the same split every other
module in this codebase already uses -- services assume the caller has
already been authorized for the org/branch they're passing in.
"""
from __future__ import annotations

import uuid

from app.repositories.interfaces import ReportingRepository


class DashboardService:
    def __init__(self, *, reporting_repo: ReportingRepository) -> None:
        self._reporting = reporting_repo

    async def executive_dashboard(self, nursery_id: uuid.UUID) -> dict:
        return await self._reporting.executive_dashboard(nursery_id)

    async def nursery_dashboard(self, nursery_id: uuid.UUID) -> dict:
        return await self._reporting.nursery_dashboard(nursery_id)

    async def branch_dashboard(self, nursery_id: uuid.UUID, branch_id: uuid.UUID) -> dict:
        return await self._reporting.branch_dashboard(nursery_id, branch_id)

    async def plant_dashboard(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict:
        return await self._reporting.plant_dashboard(nursery_id, branch_id)

    async def inventory_dashboard(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict:
        return await self._reporting.inventory_dashboard(nursery_id, branch_id)

    async def sales_dashboard(
        self,
        nursery_id: uuid.UUID,
        branch_id: uuid.UUID | None = None,
        date_from=None,
        date_to=None,
    ) -> dict:
        return await self._reporting.sales_dashboard(nursery_id, branch_id, date_from, date_to)

    async def customer_dashboard(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict:
        return await self._reporting.customer_dashboard(nursery_id, branch_id)

    async def ai_dashboard(self, nursery_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> dict:
        return await self._reporting.ai_dashboard(nursery_id, branch_id)

    async def financial_dashboard(
        self,
        nursery_id: uuid.UUID,
        branch_id: uuid.UUID | None = None,
        date_from=None,
        date_to=None,
    ) -> dict:
        return await self._reporting.financial_dashboard(nursery_id, branch_id, date_from, date_to)
