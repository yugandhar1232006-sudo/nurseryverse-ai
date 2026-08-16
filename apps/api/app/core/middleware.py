"""
Request-lifecycle middleware. Deliberately minimal in this module: request
ID assignment/propagation and a structured access log. Tenant-context
(RLS session variable) wiring belongs to Module 3 (Authorization), since it
needs the authenticated user's org membership to know what to set --
Module 1 only guarantees every request has a request_id before anything
else runs, including auth failures.
"""
from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from app.core.context import new_request_id, request_id_var
from app.core.logging import get_logger
from app.core.metrics import record_request, route_template

logger = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Assigns a request ID (reusing an inbound `X-Request-ID` if the caller
    already set one, e.g. an upstream load balancer or the frontend's own
    tracing) and logs one structured line per request: method, path,
    status, and duration. Every log emitted deeper in the call stack during
    this request automatically carries the same request_id via the
    contextvar (app/core/logging.py's `_add_request_context` processor).
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        incoming_id = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming_id or new_request_id()
        token = request_id_var.set(request_id)
        # Also stashed on request.state: if a handler raises, Starlette's
        # ServerErrorMiddleware (which sits *outside* this middleware, in
        # the same task) invokes our registered exception handlers only
        # after this method's `finally` has already reset the contextvar
        # -- by then `request_id_var.get()` is back to None. request.state
        # survives that, since it lives on the Request object itself, not
        # in task-local context.
        request.state.request_id = request_id

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_s = time.perf_counter() - start
            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration_s * 1000, 2),
            )
            # A request that ended in an unhandled exception still took
            # real time and still needs to show up in `/metrics` -- the
            # eventual status code is whatever `register_exception_handlers`
            # produces (500, almost always), but that response is built
            # *outside* this middleware (Starlette's ServerErrorMiddleware
            # sits above it), so it isn't observable here. Recorded as 500
            # rather than skipped, since "silently missing from the metrics
            # entirely" would understate the API's real error rate more
            # than a slightly-approximate status label would.
            record_request(
                method=request.method, path_template=route_template(request),
                status_code=500, duration_seconds=duration_s,
            )
            raise
        else:
            duration_s = time.perf_counter() - start
            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_s * 1000, 2),
            )
            record_request(
                method=request.method, path_template=route_template(request),
                status_code=response.status_code, duration_seconds=duration_s,
            )
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            request_id_var.reset(token)
