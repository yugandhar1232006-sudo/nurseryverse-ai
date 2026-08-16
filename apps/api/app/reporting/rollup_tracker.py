"""
`RollupRefreshTracker` -- an in-memory "which materialized views are
stale" registry. Same in-process, single-worker-first pattern
`InMemoryCache`/`InMemoryRateLimiter` (Module 3) and `InMemoryNotificationHub`
(Module 11) already established: correct for this project's current
single-process deployment, swappable for a Redis-backed (or, for this
specific case, a `last_dirtied_at` column-based) tracker later with zero
change to any caller, since every caller only ever talks to the
`RollupRefreshTracker` Protocol below.
"""
from __future__ import annotations

from typing import Protocol


class RollupRefreshTracker(Protocol):
    def mark_dirty(self, *view_names: str) -> None: ...
    def is_dirty(self, view_name: str) -> bool: ...
    def dirty_views(self) -> frozenset[str]: ...
    def clear(self, *view_names: str) -> None: ...


class InMemoryRollupRefreshTracker:
    def __init__(self) -> None:
        self._dirty: set[str] = set()

    def mark_dirty(self, *view_names: str) -> None:
        self._dirty.update(view_names)

    def is_dirty(self, view_name: str) -> bool:
        return view_name in self._dirty

    def dirty_views(self) -> frozenset[str]:
        return frozenset(self._dirty)

    def clear(self, *view_names: str) -> None:
        self._dirty.difference_update(view_names)
