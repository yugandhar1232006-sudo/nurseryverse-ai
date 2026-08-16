"""
This module's own "WebSocket notification hub" / "Live unread count"
requirement. `InMemoryNotificationHub` is an in-process connection
registry -- the same in-memory-first, disclosed-Redis-upgrade-path
pattern `InMemoryCache`/`InMemoryRateLimiter` already established in
Module 3 (see app/core/cache.py / app/core/rate_limit.py's own
docstrings): correct for the single-process deployment this project runs
today, and swapping it for a Redis pub/sub-backed hub later (to fan out
across multiple API worker processes) requires no change to any caller
-- `NotificationService` only ever calls `push_to_user`/`broadcast_to_org`
on the `NotificationHub` Protocol below, never touches a raw WebSocket.

One connection == one browser tab/device; a user may hold several at
once (multiple tabs, phone + desktop), so `_connections` maps
`user_id -> set[WebSocket]`, not a single socket.
"""
from __future__ import annotations

import uuid
from typing import Protocol

from fastapi import WebSocket

from app.core.logging import get_logger

logger = get_logger(__name__)


class NotificationHub(Protocol):
    async def connect(self, user_id: uuid.UUID, websocket: WebSocket) -> None: ...
    async def disconnect(self, user_id: uuid.UUID, websocket: WebSocket) -> None: ...
    async def push_to_user(self, user_id: uuid.UUID, payload: dict) -> int:
        """Returns how many live connections the payload was actually delivered to (0 if the user has none open)."""
        ...


class InMemoryNotificationHub:
    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, set[WebSocket]] = {}

    async def connect(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        self._connections.setdefault(user_id, set()).add(websocket)
        logger.info("notification_ws_connected", user_id=str(user_id), connection_count=len(self._connections[user_id]))

    async def disconnect(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        sockets = self._connections.get(user_id)
        if sockets is None:
            return
        sockets.discard(websocket)
        if not sockets:
            del self._connections[user_id]
        logger.info("notification_ws_disconnected", user_id=str(user_id))

    async def push_to_user(self, user_id: uuid.UUID, payload: dict) -> int:
        sockets = list(self._connections.get(user_id, ()))
        delivered = 0
        for socket in sockets:
            try:
                await socket.send_json(payload)
                delivered += 1
            except Exception:  # noqa: BLE001 -- a dead/closing socket must never break delivery to a user's other connections.
                logger.warning("notification_ws_push_failed", user_id=str(user_id))
                await self.disconnect(user_id, socket)
        return delivered

    def connection_count(self, user_id: uuid.UUID) -> int:
        """Test/ops introspection -- how many live sockets this user currently holds."""
        return len(self._connections.get(user_id, ()))
