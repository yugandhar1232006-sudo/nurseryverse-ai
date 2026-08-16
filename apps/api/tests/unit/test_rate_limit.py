"""Unit tests for app/core/rate_limit.py's InMemoryRateLimiter."""
from __future__ import annotations

import pytest

from app.core.exceptions import RateLimitError
from app.core.rate_limit import InMemoryRateLimiter


@pytest.mark.unit
async def test_allows_requests_under_the_limit():
    limiter = InMemoryRateLimiter()
    for _ in range(5):
        await limiter.check("key", limit=5, window_seconds=60)


@pytest.mark.unit
async def test_blocks_requests_over_the_limit():
    limiter = InMemoryRateLimiter()
    for _ in range(5):
        await limiter.check("key", limit=5, window_seconds=60)
    with pytest.raises(RateLimitError):
        await limiter.check("key", limit=5, window_seconds=60)


@pytest.mark.unit
async def test_different_keys_have_independent_buckets():
    limiter = InMemoryRateLimiter()
    for _ in range(5):
        await limiter.check("key-a", limit=5, window_seconds=60)
    # key-b's bucket is untouched -- must not raise.
    await limiter.check("key-b", limit=5, window_seconds=60)


@pytest.mark.unit
async def test_window_resets_after_expiry():
    limiter = InMemoryRateLimiter()
    for _ in range(3):
        await limiter.check("key", limit=3, window_seconds=0)
    # window_seconds=0 means every subsequent call is already past the
    # window boundary, so the bucket resets each time -- must not raise.
    await limiter.check("key", limit=3, window_seconds=0)
