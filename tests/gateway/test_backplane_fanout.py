"""Cross-node fan-out: two separate app instances sharing one Redis."""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from httpx_ws import aconnect_ws

from core.config import get_settings
from core.security import create_access_token, hash_password
from main import create_app


@pytest.fixture
async def two_apps():
    """Two fully independent app instances pointing at the same Redis/Mongo."""
    app1 = create_app()
    app2 = create_app()
    async with LifespanManager(app1) as m1, LifespanManager(app2) as m2:
        yield m1.app, m2.app


@pytest.fixture
async def cross_node_user(two_apps: tuple):
    """Create a user in the shared Mongo and return (app1, app2, user_id, token)."""
    app1, app2 = two_apps
    settings = get_settings()

    repo_class = None
    from infra.mongo.users.repository import UserRepository

    repo = UserRepository(app1.state.mongo.db)
    user = await repo.create(
        email="fanout_test@example.com",
        display_name="FanOut User",
        password_hash=hash_password("password123"),
    )
    token = create_access_token(user.id, settings).access_token
    yield app1, app2, user.id, token
    await app1.state.mongo.db.users.delete_one({"_id": user.id})


async def _recv_json(ws) -> dict:
    msg = await ws.receive_text()
    return json.loads(msg)


async def test_cross_node_chat_fanout(cross_node_user: tuple) -> None:
    """Message sent via app1 is received by client connected to app2."""
    app1, app2, user_id, token = cross_node_user
    session = "fanout-session"

    async with AsyncClient(
        transport=ASGITransport(app=app1), base_url="http://test"
    ) as client1:
        async with AsyncClient(
            transport=ASGITransport(app=app2), base_url="http://test"
        ) as client2:
            async with aconnect_ws(
                f"/ws/sessions/{session}",
                client1,
                headers={"sec-websocket-protocol": f"bearer,{token}"},
            ) as ws1:
                async with aconnect_ws(
                    f"/ws/sessions/{session}",
                    client2,
                    headers={"sec-websocket-protocol": f"bearer,{token}"},
                ) as ws2:
                    await _recv_json(ws1)  # welcome from app1
                    await _recv_json(ws2)  # welcome from app2

                    # Wait briefly for both SUBSCRIBE acks to propagate in Redis
                    await asyncio.sleep(0.15)

                    await ws1.send_text(json.dumps({
                        "v": 1,
                        "type": "chat.send",
                        "ts": datetime.now(UTC).isoformat(),
                        "idempotency_key": "fanout-key-1",
                        "payload": {"text": "cross-node hello"},
                    }))

                    # app1's client receives via local fan-out
                    msg1 = await _recv_json(ws1)
                    # app2's client receives via Redis pub/sub → app2's backplane
                    msg2 = await _recv_json(ws2)

                    assert msg1["type"] == "chat.message"
                    assert msg2["type"] == "chat.message"
                    assert msg1["payload"]["text"] == "cross-node hello"
                    assert msg2["payload"]["text"] == "cross-node hello"
                    # Both nodes receive the same seq from Redis INCR
                    assert msg1["seq"] == msg2["seq"]
                    assert msg1["payload"]["from_user_id"] == user_id
                    assert msg2["payload"]["from_user_id"] == user_id


async def test_disconnect_unsubscribes(cross_node_user: tuple) -> None:
    """After all clients disconnect from a session, the node unsubscribes from Redis."""
    app1, app2, user_id, token = cross_node_user
    session = "unsubscribe-session"

    async with AsyncClient(
        transport=ASGITransport(app=app1), base_url="http://test"
    ) as client1:
        async with aconnect_ws(
            f"/ws/sessions/{session}",
            client1,
            headers={"sec-websocket-protocol": f"bearer,{token}"},
        ) as ws1:
            await _recv_json(ws1)  # welcome
            assert app1.state.manager.count(session) == 1

        # After context exit the connection is closed; give lifespan tasks a tick
        await asyncio.sleep(0.05)

    # Manager should have no connections for this session on app1
    assert app1.state.manager.count(session) == 0
    # Backplane refcount should be zero → Redis unsubscribed
    assert app1.state.backplane._subscriptions.get(session, 0) == 0
