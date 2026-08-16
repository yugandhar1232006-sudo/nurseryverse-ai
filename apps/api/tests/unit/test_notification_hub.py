"""WebSocket Tests (unit layer) -- `InMemoryNotificationHub` connection registry semantics."""
from __future__ import annotations

import uuid

import pytest

from app.notifications.hub import InMemoryNotificationHub

pytestmark = pytest.mark.unit


class _FakeWebSocket:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.frames: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        if self.fail:
            raise RuntimeError("connection closed")
        self.frames.append(payload)


async def test_push_to_user_with_no_connections_delivers_to_nobody():
    hub = InMemoryNotificationHub()
    delivered = await hub.push_to_user(uuid.uuid4(), {"type": "test"})
    assert delivered == 0


async def test_connect_then_push_delivers_the_frame():
    hub = InMemoryNotificationHub()
    user_id = uuid.uuid4()
    socket = _FakeWebSocket()
    await hub.connect(user_id, socket)

    delivered = await hub.push_to_user(user_id, {"type": "notification", "unread_count": 1})

    assert delivered == 1
    assert socket.frames == [{"type": "notification", "unread_count": 1}]


async def test_one_user_with_multiple_connections_all_receive_the_push():
    hub = InMemoryNotificationHub()
    user_id = uuid.uuid4()
    tab_a, tab_b = _FakeWebSocket(), _FakeWebSocket()
    await hub.connect(user_id, tab_a)
    await hub.connect(user_id, tab_b)

    delivered = await hub.push_to_user(user_id, {"type": "unread_count", "unread_count": 3})

    assert delivered == 2
    assert tab_a.frames == [{"type": "unread_count", "unread_count": 3}]
    assert tab_b.frames == [{"type": "unread_count", "unread_count": 3}]


async def test_push_only_reaches_the_targeted_user():
    hub = InMemoryNotificationHub()
    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    socket_a, socket_b = _FakeWebSocket(), _FakeWebSocket()
    await hub.connect(user_a, socket_a)
    await hub.connect(user_b, socket_b)

    await hub.push_to_user(user_a, {"type": "notification"})

    assert socket_a.frames == [{"type": "notification"}]
    assert socket_b.frames == []


async def test_disconnect_removes_the_connection():
    hub = InMemoryNotificationHub()
    user_id = uuid.uuid4()
    socket = _FakeWebSocket()
    await hub.connect(user_id, socket)
    await hub.disconnect(user_id, socket)

    delivered = await hub.push_to_user(user_id, {"type": "notification"})
    assert delivered == 0
    assert hub.connection_count(user_id) == 0


async def test_a_dead_socket_is_pruned_and_does_not_break_delivery_to_other_connections():
    hub = InMemoryNotificationHub()
    user_id = uuid.uuid4()
    dead_socket = _FakeWebSocket(fail=True)
    live_socket = _FakeWebSocket()
    await hub.connect(user_id, dead_socket)
    await hub.connect(user_id, live_socket)

    delivered = await hub.push_to_user(user_id, {"type": "notification"})

    assert delivered == 1
    assert live_socket.frames == [{"type": "notification"}]
    assert hub.connection_count(user_id) == 1  # dead_socket was pruned


async def test_disconnecting_an_already_removed_socket_is_a_no_op():
    hub = InMemoryNotificationHub()
    user_id = uuid.uuid4()
    socket = _FakeWebSocket()
    # never connected -- disconnect must not raise
    await hub.disconnect(user_id, socket)
    assert hub.connection_count(user_id) == 0
