"""
Generic cache abstraction for Module 3's Permission Cache requirement.
Two implementations, same pattern already established by
app/core/rate_limit.py (RedisRateLimiter / InMemoryRateLimiter): a real
Redis-backed cache for production/multi-process correctness, and a real
(not mocked) in-process fallback for dev/test when Redis is unreachable —
both satisfy the same `Cache` protocol, so callers never branch on which
one they got.

This is deliberately generic (get/set/delete-by-prefix, string keys/
values) rather than permission-specific — app/services/permission_service.py
builds the permission-shaped cache (serializing ResolvedAccess to/from
JSON) on top of this, so the caching mechanism itself is reusable by any
future module that needs the same "cache in Redis, degrade to in-process,
support targeted invalidation" pattern.
"""
from __future__ import annotations

import time
from typing import Protocol


class Cache(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, *, ttl_seconds: int) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def delete_prefix(self, prefix: str) -> None:
        """Invalidate every key starting with `prefix` (e.g. `perm:user:{id}:*`)."""
        ...


class InMemoryCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float]] = {}  # key -> (value, expires_at_monotonic)

    async def get(self, key: str) -> str | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() >= expires_at:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: str, *, ttl_seconds: int) -> None:
        self._store[key] = (value, time.monotonic() + ttl_seconds)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def delete_prefix(self, prefix: str) -> None:
        for key in [k for k in self._store if k.startswith(prefix)]:
            del self._store[key]


class RedisCache:
    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    async def get(self, key: str) -> str | None:
        value = await self._redis.get(key)
        return value.decode("utf-8") if isinstance(value, bytes) else value

    async def set(self, key: str, value: str, *, ttl_seconds: int) -> None:
        await self._redis.set(key, value, ex=ttl_seconds)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def delete_prefix(self, prefix: str) -> None:
        # SCAN, not KEYS -- KEYS blocks the whole Redis instance on a large
        # keyspace; SCAN is the production-safe iteration primitive.
        async for key in self._redis.scan_iter(match=f"{prefix}*"):
            await self._redis.delete(key)
