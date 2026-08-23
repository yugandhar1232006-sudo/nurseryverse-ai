"""
Phase 6 Module 14 (Production Readiness) — application-level metrics.

`docs/architecture/09-infrastructure.md` §7 calls for "Application-level
metrics (AI inference latency/error rate per module, Celery queue depth
per queue, per-tenant usage against plan limits) ... exposed via a
`/metrics` endpoint on the API (Prometheus-compatible format) —
collection/dashboarding tooling (Prometheus + Grafana, or a managed
equivalent) is a deployment-time choice layered on top of this endpoint,
not baked into the application image itself." This module supplies that
endpoint plus the one metric every request already passes through
(HTTP request count + latency), instrumented once in
`RequestContextMiddleware` (the same place the existing structured
per-request log line is emitted, so both come from a single source of
truth about what a "request" is) — matching the "metrics endpoint,
not a metrics *pipeline*" scope this doc describes: per-module business
metrics (AI inference latency by capability, notification delivery
success rate, etc.) are additive Counters/Histograms any later module
can register against this same `REGISTRY` without touching this file.

Uses the default `prometheus_client` global `REGISTRY` (not a private
`CollectorRegistry`) deliberately: this process serves exactly one
`/metrics` endpoint for its own lifetime, and every `prometheus_client`
metric object is itself a module-level singleton (the same shape
`app/core/config.py`'s cached `Settings` singleton already establishes) —
a private per-app-instance registry would need threading through
`create_app()` and every test that builds an app, for no benefit this
single-process API needs. Tests instead assert against the specific
counter/histogram samples they care about, not the full registry dump.
"""
from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests processed, labeled by method/route template/status code.",
    labelnames=("method", "path_template", "status_code"),
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds, labeled by method/route template.",
    labelnames=("method", "path_template"),
)


def record_request(*, method: str, path_template: str, status_code: int, duration_seconds: float) -> None:
    """
    Called once per request from `RequestContextMiddleware.dispatch` (both
    the success and exception paths — an unhandled exception is still a
    real request that took real time and should still show up in
    `http_requests_total`/`http_request_duration_seconds`, labeled with
    whatever status code the exception handler ultimately produced).
    """
    HTTP_REQUESTS_TOTAL.labels(method=method, path_template=path_template, status_code=str(status_code)).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path_template=path_template).observe(duration_seconds)


def route_template(request) -> str:
    """
    The matched route's path *template* (e.g. `/api/v1/employees/{id}`),
    not the raw request path -- using the raw path would give every
    distinct UUID/id a permanently-retained, unbounded-cardinality
    Prometheus label series (a well-known Prometheus footgun). Starlette
    populates `request.scope["route"]` once routing resolves, which by
    the time `RequestContextMiddleware`'s `call_next` returns has already
    happened (middleware wraps the router, but `scope` is the same mutable
    dict threaded through the whole ASGI call chain). Falls back to the
    literal path for the small set of cases routing never resolves a route
    for at all (a genuine 404 on an unregistered path) -- an unmatched
    path has no template to report, and the raw 404 path space is bounded
    by whatever an attacker/typo throws at the API, not by real traffic
    volume, so the cardinality concern doesn't apply there.

    FastAPI 0.141.1+ stores the fully-qualified path template in
    ``scope["fastapi"]["effective_route_context"].path``, which includes
    all ancestor router prefixes (e.g. ``/api/v1/employees/{id}`` rather
    than just ``/{id}``). We prefer that over ``scope["route"].path``
    which only carries the local sub-router path.
    """
    fastapi_scope = request.scope.get("fastapi", {})
    effective_ctx = fastapi_scope.get("effective_route_context") if isinstance(fastapi_scope, dict) else getattr(fastapi_scope, "effective_route_context", None)
    if effective_ctx is not None and getattr(effective_ctx, "path", None):
        return effective_ctx.path
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    return request.url.path


def render_latest() -> tuple[bytes, str]:
    """Returns (body, content_type) for the `/metrics` route -- a thin wrapper so the route itself has zero `prometheus_client` import surface beyond this module."""
    return generate_latest(), CONTENT_TYPE_LATEST
