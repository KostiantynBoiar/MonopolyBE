"""Connection lifecycle tests: auth, welcome, heartbeat, error handling."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def _ws_headers(token: str) -> dict[str, str]:
    return {"sec-websocket-protocol": f"bearer,{token}"}


def test_auth_fail_no_header(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/sessions/test-session"):
            pass


def test_auth_fail_bad_token(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/ws/sessions/test-session",
            headers={"sec-websocket-protocol": "bearer,not-a-valid-jwt"},
        ):
            pass


def test_auth_success_welcome(client: TestClient, registered_user: tuple) -> None:
    _user_id, token, session_id = registered_user
    with client.websocket_connect(
        f"/ws/sessions/{session_id}",
        headers=_ws_headers(token),
    ) as ws:
        msg = ws.receive_json()
        assert msg["v"] == 1
        assert msg["type"] == "system.welcome"
        assert msg["payload"]["session_id"] == session_id
        assert "your_seq_start" in msg["payload"]


def test_malformed_json_keeps_connection(
    client: TestClient, registered_user: tuple
) -> None:
    _user_id, token, session_id = registered_user
    with client.websocket_connect(
        f"/ws/sessions/{session_id}",
        headers=_ws_headers(token),
    ) as ws:
        ws.receive_json()  # welcome

        ws.send_text("not valid json at all")
        error = ws.receive_json()
        assert error["type"] == "system.error"
        assert error["payload"]["code"] == "malformed"

        ws.send_text("{}")
        error2 = ws.receive_json()
        assert error2["type"] == "system.error"
        assert error2["payload"]["code"] == "malformed"


def test_unknown_type_keeps_connection(
    client: TestClient, registered_user: tuple
) -> None:
    _user_id, token, session_id = registered_user
    with client.websocket_connect(
        f"/ws/sessions/{session_id}",
        headers=_ws_headers(token),
    ) as ws:
        ws.receive_json()  # welcome

        msg = json.dumps({
            "v": 1,
            "type": "totally.unknown",
            "ts": datetime.now(UTC).isoformat(),
            "payload": {},
        })
        ws.send_text(msg)
        error = ws.receive_json()
        assert error["type"] == "system.error"
        assert error["payload"]["code"] == "unknown_type"


def test_version_mismatch_closes(client: TestClient, registered_user: tuple) -> None:
    _user_id, token, session_id = registered_user
    with client.websocket_connect(
        f"/ws/sessions/{session_id}",
        headers=_ws_headers(token),
    ) as ws:
        ws.receive_json()  # welcome

        msg = json.dumps({
            "v": 99,
            "type": "chat.send",
            "ts": datetime.now(UTC).isoformat(),
            "payload": {"text": "hello"},
        })
        ws.send_text(msg)
        error = ws.receive_json()
        assert error["type"] == "system.error"
        assert error["payload"]["code"] == "unsupported_version"

        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_malformed_payload_shape_keeps_connection(
    client: TestClient, registered_user: tuple
) -> None:
    _user_id, token, session_id = registered_user
    with client.websocket_connect(
        f"/ws/sessions/{session_id}",
        headers=_ws_headers(token),
    ) as ws:
        ws.receive_json()  # welcome

        msg = json.dumps({
            "v": 1,
            "type": "chat.send",
            "ts": datetime.now(UTC).isoformat(),
            "payload": {"wrong_field": 123},
        })
        ws.send_text(msg)
        error = ws.receive_json()
        assert error["type"] == "system.error"
        assert error["payload"]["code"] == "malformed"


def test_heartbeat_ping_received(client: TestClient, registered_user: tuple) -> None:
    _user_id, token, session_id = registered_user
    with patch("gateway.connection.WS_HEARTBEAT_INTERVAL_S", 0.1):
        with client.websocket_connect(
            f"/ws/sessions/{session_id}",
            headers=_ws_headers(token),
        ) as ws:
            ws.receive_json()  # welcome
            ping = ws.receive_json()
            assert ping["type"] == "connection.ping"

            pong = json.dumps({
                "v": 1,
                "type": "connection.pong",
                "ts": datetime.now(UTC).isoformat(),
                "payload": {},
            })
            ws.send_text(pong)
