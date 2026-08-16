"""
Liveness/readiness endpoints. Split per Kubernetes/Docker Compose
convention (docs/architecture/09-infrastructure.md §6): `/healthz`
answers "is the process up" and never touches the database, so it can't
be dragged down by a database outage the orchestrator should be treating
as a *different* signal than "restart this container". `/readyz` answers
"can this instance actually serve traffic" and does touch the database --
it is the one place in Module 1 allowed to fail because Postgres is
unreachable, and it fails informatively rather than throwing a raw
connection error at the caller.
"""
from __future__ import annotations

from fastapi import APIRouter, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.api.deps import get_db
from app.core.logging import get_logger
from app.core.metrics import render_latest

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/healthz", summary="Liveness probe")
async def healthz() -> dict:
    return {"status": "ok"}


@router.get("/readyz", summary="Readiness probe (checks database connectivity)")
async def readyz(response: Response, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 -- deliberately broad: any DB failure means "not ready"
        logger.warning("readiness_check_failed", error=str(exc))
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "database": "unreachable"}
    return {"status": "ok", "database": "reachable"}


@router.get(
    "/metrics",
    summary="Prometheus-format application metrics",
    response_class=Response,
    include_in_schema=False,
)
async def metrics() -> Response:
    """
    Phase 6 Module 14 (Production Readiness) — docs/architecture/09-infrastructure.md
    §7. Mounted unprefixed, same convention as `/healthz`/`/readyz` above
    (orchestrators and Prometheus scrape configs both expect metrics
    endpoints at a bare, predictable path, not under `/api/v1`). No
    authentication -- matching the same edge-scoped-not-application-scoped
    reasoning `/healthz`/`/readyz` already apply; a production deployment
    restricts scrape access at the network/Nginx layer, not by making
    Prometheus authenticate as an application user. Excluded from the
    OpenAPI schema (`include_in_schema=False`) since this is a scrape
    target for infrastructure tooling, not a documented API resource.
    """
    body, content_type = render_latest()
    return Response(content=body, media_type=content_type)
