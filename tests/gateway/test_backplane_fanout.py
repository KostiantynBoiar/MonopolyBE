"""Cross-node fan-out: two separate app instances sharing one Redis."""
from __future__ import annotations

import json
import time
from datetime import UTC, datetime

import pytest
from starlette.testclient import TestClient

from main import create_app
from tests.conftest import create_session, register_user


def _ws_headers(token: str) -> dict[str, str]:
    return {"sec-websocket-protocol": f"bearer,{token}"}


@pytest.fixture
def cross_node_user():
    """Two TestClients (separate gateway nodes) sharing Mongo/Redis."""
    with TestClient(create_app()) as client1, TestClient(create_app()) as client2:
        user_id, token = register_user(client1, "fanout")
        session_id = create_session(client1, token)
        yield client1, client2, user_id, token, session_id


def test_cross_node_chat_fanout(cross_node_user: tuple) -> None:
    client1, client2, user_id, token, session_id = cross_node_user

    with client1.websocket_connect(
        f"/ws/sessions/{session_id}",
        headers=_ws_headers(token),
    ) as ws1:
        with client2.websocket_connect(
            f"/ws/sessions/{session_id}",
            headers=_ws_headers(token),
        ) as ws2:
            ws1.receive_json()
            ws2.receive_json()

            time.sleep(0.15)

            ws1.send_text(json.dumps({
                "v": 1,
                "type": "chat.send",
                "ts": datetime.now(UTC).isoformat(),
                "idempotency_key": "fanout-key-1",
                "payload": {"text": "cross-node hello"},
            }))

            msg1 = ws1.receive_json()
            msg2 = ws2.receive_json()

            assert msg1["type"] == "chat.message"
            assert msg2["type"] == "chat.message"
            assert msg1["payload"]["text"] == "cross-node hello"
            assert msg2["payload"]["text"] == "cross-node hello"
            assert msg1["seq"] == msg2["seq"]
            assert msg1["payload"]["from_user_id"] == user_id


def test_disconnect_unsubscribes(cross_node_user: tuple) -> None:
    client1, _client2, _user_id, token, session_id = cross_node_user

    with client1.websocket_connect(
        f"/ws/sessions/{session_id}",
        headers=_ws_headers(token),
    ) as ws1:
        ws1.receive_json()
        assert client1.app.state.manager.count(session_id) == 1

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if client1.app.state.manager.count(session_id) == 0:
            break
        time.sleep(0.05)

    assert client1.app.state.manager.count(session_id) == 0
    assert client1.app.state.backplane._subscriptions.get(session_id, 0) == 0
