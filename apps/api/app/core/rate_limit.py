"""
Rate limiting for Module 2's brute-force-protection requirement. A small
`RateLimiter` protocol with two implementations:

- `RedisRateLimiter` — production. Fixed-window counter via `INCR` +
  `EXPIRE`, the standard low-overhead Redis rate-limiting pattern. Fixed-
  window (not sliding-window/token-bucket) is a deliberate simplicity
  choice: it allows a burst of up to 2x the limit across a window
  boundary in the worst case, which is an acceptable tradeoff for a login
  endpoint (the account-lockout counter in AuthService is the actual hard
  brute-force defense; this rate limiter's job is to blunt scripted
  high-volume attempts before they even reach the lockout logic, not to be
  a perfectly precise limiter).
- `InMemoryRateLimiter` — dev/test fallback when no Redis is reachable
  (this sandbox has none; see docs/architecture/14-phase5-database-implementation.md
  for the same constraint applied to Postgres). Same interface, same
  semantics, process-local storage only — not correct across multiple API
  processes, which is fine for local development and is exactly why
  production must use `RedisRateLimiter`.

`get_rate_limiter()` (app/api/deps.py) is what decides which
implementation a running process gets, based on whether Redis is
reachable — not hardcoded per environment, so a developer without Redis
running locally still gets working (single-process) rate limiting instead
of the feature silently being disabled.
"""
from __future__ import annotations

import time
from typing import Protocol

from app.core.exceptions import RateLimitError


class RateLimiter(Protocol):
    async def check(self, key: str, *, limit: int, window_seconds: int) -> None:
        """Raises RateLimitError if `key` has exceeded `limit` hits within `window_seconds`."""
        ...


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, tuple[int, float]] = {}  # key -> (count, window_start)

    async def check(self, key: str, *, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        count, window_start = self._buckets.get(key, (0, now))
        if now - window_start >= window_seconds:
            count, window_start = 0, now
        count += 1
        self._buckets[key] = (count, window_start)
        if count > limit:
            raise RateLimitError(
                f"Too many requests. Try again in {int(window_seconds - (now - window_start))}s.",
                context={"limit": limit, "window_seconds": window_seconds},
            )


class RedisRateLimiter:
    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    async def check(self, key: str, *, limit: int, window_seconds: int) -> None:
        redis_key = f"ratelimit:{key}"
        count = await self._redis.incr(redis_key)
        if count == 1:
            await self._redis.expire(redis_key, window_seconds)
        if count > limit:
            ttl = await self._redis.ttl(redis_key)
            raise RateLimitError(
                f"Too many requests. Try again in {max(ttl, 0)}s.",
                context={"limit": limit, "window_seconds": window_seconds},
            )
