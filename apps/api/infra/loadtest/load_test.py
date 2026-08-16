"""
Phase 6 Module 14 (Production Readiness) -- concurrent load/stress test
against a real, running instance of the API (not the ASGI test client
tests/conftest.py's `client` fixture uses -- this hits an actual TCP
socket, exercising uvicorn's own connection handling, not just FastAPI's
routing).

SCOPE (disclosed): this development sandbox has no live Postgres
(disclosed throughout this project's own architecture docs, restated in
docs/architecture/30-module14-production-readiness.md) -- every endpoint
exercised here is one that genuinely does not need a database connection
to answer correctly, not a workaround. That still meaningfully load-tests
a real slice of the request path: RequestContextMiddleware (request-id
assignment, structured logging, Prometheus instrumentation -- Module 14's
own app/core/middleware.py), FastAPI's routing/dependency-injection layer,
and -- for the two auth-protected endpoints below -- the JWT decode/
rejection path (app/api/deps.py's `get_current_user`, which runs and
fails *before* ever reaching a repository). A deployment with a real
Postgres available should extend this script with authenticated,
DB-touching endpoints (e.g. `GET /api/v1/plants`) for a fuller picture --
left as a documented gap, not silently assumed equivalent to this run.

Usage:
    python infra/loadtest/load_test.py --base-url http://127.0.0.1:8000 \
        --concurrency 50 --duration 10

No third-party load-testing binary (locust/k6/wrk/hey/ab) was available
in this development sandbox to install -- this script uses only httpx
(already a project dependency, requirements/base.txt) so it runs anywhere
this project's own dev environment already does, without adding a new
tool just for this one exercise.
"""
from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass, field

import httpx


@dataclass
class EndpointSpec:
    method: str
    path: str
    expected_status: int
    weight: int  # relative frequency this endpoint is chosen, out of the total weight
    headers: dict = field(default_factory=dict)


# Weighted mix -- /healthz weighted heaviest since it's the endpoint an
# orchestrator/load-balancer would hammer most in real production traffic
# (liveness probes on a short interval, from every replica); /metrics and
# /openapi.json represent lower-frequency-but-real traffic (a Prometheus
# scrape interval, occasional API-doc consumers); the two 401 checks
# specifically load-test the auth-rejection path under concurrency (a
# malicious/misconfigured client hammering protected endpoints without a
# token is a realistic thing to want this path to stay fast under).
ENDPOINTS: list[EndpointSpec] = [
    EndpointSpec("GET", "/healthz", 200, weight=40),
    EndpointSpec("GET", "/metrics", 200, weight=10),
    EndpointSpec("GET", "/openapi.json", 200, weight=10),
    EndpointSpec("GET", "/api/v1/admin/roles", 401, weight=20),
    EndpointSpec("GET", "/api/v1/plants", 401, weight=20),
]


def _pick_endpoint(counter: list[int]) -> EndpointSpec:
    # Simple weighted round-robin over a precomputed flat list -- avoids
    # pulling in `random` weighting for what's a fixed, small endpoint set.
    return _FLAT_ENDPOINTS[counter[0] % len(_FLAT_ENDPOINTS)]


_FLAT_ENDPOINTS: list[EndpointSpec] = [ep for ep in ENDPOINTS for _ in range(ep.weight)]


@dataclass
class Result:
    status_code: int
    expected_status: int
    latency_ms: float
    path: str
    error: str | None = None


async def _worker(
    client: httpx.AsyncClient, stop_at: float, results: list[Result], counter: list[int], lock: asyncio.Lock
) -> None:
    while time.monotonic() < stop_at:
        async with lock:
            ep = _pick_endpoint(counter)
            counter[0] += 1
        start = time.monotonic()
        try:
            response = await client.request(ep.method, ep.path, headers=ep.headers, timeout=10.0)
            latency_ms = (time.monotonic() - start) * 1000
            results.append(Result(response.status_code, ep.expected_status, latency_ms, ep.path))
        except Exception as exc:  # noqa: BLE001 -- a load test must record every failure mode, not just HTTP-level ones
            latency_ms = (time.monotonic() - start) * 1000
            results.append(Result(-1, ep.expected_status, latency_ms, ep.path, error=str(exc)))


async def run_load_test(base_url: str, concurrency: int, duration_seconds: float) -> list[Result]:
    results: list[Result] = []
    counter = [0]
    lock = asyncio.Lock()
    limits = httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency)
    # trust_env=False: this script targets a specific --base-url directly
    # (typically localhost/an internal address) -- httpx's default of
    # honoring HTTP_PROXY/ALL_PROXY-style env vars is meant for a client
    # making requests to arbitrary external hosts, and in some shells
    # (e.g. this project's own CI/dev sandboxes, which set an ALL_PROXY
    # for outbound network egress control) actively breaks a local-only
    # load test with an unrelated proxy-configuration error.
    async with httpx.AsyncClient(base_url=base_url, limits=limits, trust_env=False) as client:
        stop_at = time.monotonic() + duration_seconds
        workers = [asyncio.create_task(_worker(client, stop_at, results, counter, lock)) for _ in range(concurrency)]
        await asyncio.gather(*workers)
    return results


def summarize(results: list[Result], duration_seconds: float) -> dict:
    total = len(results)
    correct = sum(1 for r in results if r.status_code == r.expected_status)
    errors = [r for r in results if r.error is not None]
    unexpected_status = [r for r in results if r.error is None and r.status_code != r.expected_status]
    latencies = sorted(r.latency_ms for r in results if r.error is None)

    def _pct(p: float) -> float:
        if not latencies:
            return 0.0
        idx = min(len(latencies) - 1, int(len(latencies) * p))
        return latencies[idx]

    return {
        "total_requests": total,
        "requests_per_second": round(total / duration_seconds, 1) if duration_seconds else 0.0,
        "correct_status_count": correct,
        "correct_status_pct": round(100 * correct / total, 2) if total else 0.0,
        "transport_errors": len(errors),
        "unexpected_status_count": len(unexpected_status),
        "latency_ms_p50": round(_pct(0.50), 2),
        "latency_ms_p95": round(_pct(0.95), 2),
        "latency_ms_p99": round(_pct(0.99), 2),
        "latency_ms_max": round(max(latencies), 2) if latencies else 0.0,
        "latency_ms_mean": round(statistics.mean(latencies), 2) if latencies else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--duration", type=float, default=10.0, help="seconds")
    args = parser.parse_args()

    print(f"Load test: {args.concurrency} concurrent workers for {args.duration}s against {args.base_url}")
    results = asyncio.run(run_load_test(args.base_url, args.concurrency, args.duration))
    summary = summarize(results, args.duration)

    print("\n--- Results ---")
    for key, value in summary.items():
        print(f"{key}: {value}")

    per_path: dict[str, list[Result]] = {}
    for r in results:
        per_path.setdefault(r.path, []).append(r)
    print("\n--- Per-endpoint ---")
    for path, path_results in sorted(per_path.items()):
        correct = sum(1 for r in path_results if r.status_code == r.expected_status)
        lat = sorted(r.latency_ms for r in path_results if r.error is None)
        p95 = lat[min(len(lat) - 1, int(len(lat) * 0.95))] if lat else 0.0
        print(f"  {path}: n={len(path_results)} correct={correct}/{len(path_results)} p95_ms={p95:.2f}")

    if summary["unexpected_status_count"] or summary["transport_errors"]:
        print("\nFAIL: unexpected statuses or transport errors occurred under load.")
        raise SystemExit(1)
    print("\nPASS: every response matched its expected status code under sustained concurrent load.")


if __name__ == "__main__":
    main()
