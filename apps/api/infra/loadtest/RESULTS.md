# Load/Stress Test Results

Phase 6 Module 14 (Production Readiness), Task #164. Real run against a live `uvicorn` process (not the ASGI test client) in the development sandbox this module was built in, using `load_test.py` in this directory.

## Run configuration

- Command: `python infra/loadtest/load_test.py --base-url http://127.0.0.1:8124 --concurrency 30 --duration 8`
- Server: `uvicorn app.main:app --host 127.0.0.1 --port 8124 --workers 1`, `APP_ENV=test`
- Endpoints exercised (weighted mix -- see `load_test.py`'s own `ENDPOINTS` list): `GET /healthz` (40%), `GET /api/v1/admin/roles` no-token (20%), `GET /api/v1/plants` no-token (20%), `GET /metrics` (10%), `GET /openapi.json` (10%)

## SCOPE (disclosed)

This development sandbox has no live Postgres (disclosed throughout this project, restated in `docs/architecture/30-module14-production-readiness.md`). Every endpoint above answers without touching a database -- `/healthz` by design, `/metrics`/`/openapi.json` by design, and the two admin/plants requests specifically because they're sent with **no bearer token**, so they're rejected by `app/api/deps.py`'s `get_current_user` dependency before any repository is ever reached. That still exercises a real, meaningful slice of the request path under concurrency: `RequestContextMiddleware` (request-id assignment, structured logging, Prometheus instrumentation -- this module's own `app/core/middleware.py`), FastAPI's routing/dependency-injection resolution, and the JWT-absent rejection path. It does **not** exercise query execution, connection-pool contention, or ORM overhead under load -- that requires a real Postgres and is the natural next extension of this script (add authenticated, DB-touching endpoints such as `GET /api/v1/plants` with a real bearer token once a target environment has one), not something this run can honestly claim to have covered.

## Results

```
total_requests: 5775
requests_per_second: 721.9
correct_status_count: 5775
correct_status_pct: 100.0
transport_errors: 0
unexpected_status_count: 0
latency_ms_p50: 28.55
latency_ms_p95: 116.99
latency_ms_p99: 189.67
latency_ms_max: 337.49
latency_ms_mean: 41.61
```

Per-endpoint:

```
/api/v1/admin/roles: n=1155 correct=1155/1155 p95_ms=103.85
/api/v1/plants:      n=1140 correct=1140/1140 p95_ms=122.61
/healthz:             n=2320 correct=2320/2320 p95_ms=111.80
/metrics:             n=580  correct=580/580  p95_ms=118.80
/openapi.json:        n=580  correct=580/580  p95_ms=139.37
```

## Interpretation

100% of 5,775 requests returned their expected status code under 30 concurrent workers sustained for 8 seconds, with zero transport-level errors (connection resets, timeouts) -- the request-lifecycle middleware, routing, dependency injection, and JWT-rejection path all held up correctly under concurrent load, not just sequentially (every prior module's integration tests exercise these one request at a time). ~722 req/s and p95 ≈ 117ms against a **single uvicorn worker process** (`--workers 1`, no gunicorn multi-worker fan-out, no Nginx in front, running inside a constrained development sandbox, not dedicated hardware) -- these numbers are not a production capacity claim; they're a correctness-under-concurrency check. A real capacity/throughput benchmark needs the actual production topology (gunicorn with multiple uvicorn workers per `infra/docker/api.Dockerfile`, behind Nginx, against a real Postgres) and dedicated, isolated hardware -- both unavailable in this sandbox, and both a reasonable follow-up once a staging environment exists (docs/architecture/10-devops.md §7's three-environment strategy).

`/openapi.json` had the highest p95 (139ms) of the five endpoints -- expected, since it serializes the entire OpenAPI schema (every route across all 14 modules) on every request rather than caching it; FastAPI does cache this internally after the first call in a real deployment, but under this test's cold-worker-per-request-burst pattern that cache benefit is muted. Not treated as a defect: this endpoint is fetched rarely in real usage (API-doc consumers, not per-request traffic), unlike `/healthz`, which is the one endpoint real infrastructure (an orchestrator's liveness probe) would call at meaningful frequency, and it had a comparable p95 (111.80ms) to the rest of the mix despite being the plurality of traffic in this run.

## Re-running this test

```bash
cd apps/api
export PYTHONPATH=. APP_ENV=test
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
python infra/loadtest/load_test.py --base-url http://127.0.0.1:8000 --concurrency 50 --duration 30
```

Increase `--concurrency`/`--duration` for a heavier run once against a real staging deployment (production topology, real Postgres) rather than this sandbox.
