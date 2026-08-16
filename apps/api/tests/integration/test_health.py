"""
Integration tests for the health endpoints, exercised through the real
FastAPI app (ASGI transport, not calling route functions directly) --
this is what confirms middleware, exception handlers, and routing are all
actually wired together correctly, not just that each piece works in
isolation.
"""
from __future__ import annotations

import pytest


@pytest.mark.integration
async def test_healthz_never_touches_the_database(client):
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.integration
async def test_healthz_sets_request_id_header(client):
    response = await client.get("/healthz")
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) == 32  # uuid4().hex


@pytest.mark.integration
async def test_healthz_echoes_inbound_request_id(client):
    response = await client.get("/healthz", headers={"X-Request-ID": "trace-abc-123"})
    assert response.headers["x-request-id"] == "trace-abc-123"


@pytest.mark.integration
async def test_readyz_reports_unavailable_without_a_reachable_database(client):
    # This sandbox (and most CI runners without a DB service container)
    # has no reachable Postgres -- readyz must fail informatively (503 +
    # the standard error envelope), never with a raw connection traceback.
    response = await client.get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["database"] == "unreachable"


@pytest.mark.integration
async def test_unmatched_route_returns_standard_error_envelope(client):
    response = await client.get("/this-route-does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "http_error"
    assert "request_id" in body


@pytest.mark.integration
async def test_unhandled_exception_still_carries_request_id():
    """
    Regression test for a bug found via a live smoke test: the generic
    `Exception` handler is dispatched by Starlette's ServerErrorMiddleware,
    which sits *outside* RequestContextMiddleware in the stack -- by the
    time it runs, that middleware's own `finally` has already reset the
    request_id contextvar back to None, so a real 500 response was coming
    back with `request_id: null`. Fixed by also stashing the id on
    `request.state` (survives past the contextvar reset) and having
    error_handlers.py prefer that. This test forces a bare, unhandled
    exception out of a route (bypassing every AppError/HTTPException
    handler, which all run *inside* the middleware and were never
    affected) to confirm the fix.
    """
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    app = create_app()

    async def _boom():
        raise RuntimeError("simulated unhandled failure")

    for route in app.routes:
        if getattr(route, "path", None) == "/healthz":
            route.dependant.call = _boom

    # Starlette's ServerErrorMiddleware sends the 500 response *and*
    # re-raises the original exception afterwards (so it still surfaces
    # to server-side logs/error trackers even though the client already
    # got a response -- confirmed against a real uvicorn process, which
    # returns the JSON body fine while also logging the traceback).
    # httpx's ASGITransport defaults to re-raising that same exception
    # into the test instead of just returning the response that was
    # already sent; raise_app_exceptions=False makes it behave like the
    # real server does here.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        response = await ac.get("/healthz")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert body["request_id"] is not None


@pytest.mark.integration
async def test_metrics_endpoint_exposes_prometheus_format(client):
    """
    Phase 6 Module 14 (Production Readiness) — docs/architecture/09-infrastructure.md
    §7. Confirms the endpoint is live, correctly content-typed for a
    Prometheus scrape, and that a request this same test just made is
    already reflected in the exposition -- proving the middleware
    instrumentation (app/core/middleware.py) and this route
    (app/core/metrics.py) are actually wired together, not just each
    independently importable.
    """
    await client.get("/healthz")
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert "http_requests_total" in body
    assert 'path_template="/healthz"' in body


@pytest.mark.integration
async def test_metrics_endpoint_uses_route_template_not_raw_path_with_ids(client):
    """A parameterized route's requests must all collapse onto ONE label series (the path template), never one series per distinct id -- the unbounded-cardinality footgun app/core/metrics.py's `route_template` docstring explains."""
    import re
    import uuid

    id_a, id_b = uuid.uuid4(), uuid.uuid4()
    await client.get(f"/api/v1/employees/{id_a}", headers={"Authorization": "Bearer not-a-real-token"})
    await client.get(f"/api/v1/employees/{id_b}", headers={"Authorization": "Bearer not-a-real-token"})
    response = await client.get("/metrics")
    body = response.text
    assert 'path_template="/api/v1/employees/{id}"' in body
    assert str(id_a) not in body
    assert str(id_b) not in body
    # No `path_template=` label value anywhere in the exposition contains a UUID.
    uuid_pattern = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
    for line in body.splitlines():
        if line.startswith("http_request") and "path_template=" in line:
            assert not uuid_pattern.search(line), f"found a raw UUID in a metrics label line: {line}"


@pytest.mark.integration
async def test_metrics_endpoint_not_in_openapi_schema(client):
    response = await client.get("/openapi.json")
    schema = response.json()
    assert "/metrics" not in schema["paths"]


@pytest.mark.integration
async def test_openapi_schema_is_generated(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "NurseryVerse AI API"
    assert "/healthz" in schema["paths"]
    assert "/readyz" in schema["paths"]
