"""Connection lifecycle tests: auth, welcome, heartbeat, error handling."""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from httpx_ws import aconnect_ws


async def _ws_connect(app: FastAPI, session_id: str, token: str):
    """Context manager that yields an open WebSocket connection."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        async with aconnect_ws(
            f"/ws/sessions/{session_id}",
            client,
            headers={"sec-websocket-protocol": f"bearer,{token}"},
        ) as ws:
            yield ws


async def _recv_json(ws) -> dict:
    msg = await ws.receive_text()
    return json.loads(msg)


# ---------------------------------------------------------------------------
# Auth rejection
# ---------------------------------------------------------------------------

async def test_auth_fail_no_header(app: FastAPI) -> None:
    """Missing Sec-WebSocket-Protocol header results in connection rejection."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        with pytest.raises(Exception):
            async with aconnect_ws("/ws/sessions/test-session", client):
                pass


async def test_auth_fail_bad_token(app: FastAPI) -> None:
    """Invalid JWT results in connection rejection."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        with pytest.raises(Exception):
            async with aconnect_ws(
                "/ws/sessions/test-session",
                client,
                headers={"sec-websocket-protocol": "bearer,not-a-valid-jwt"},
            ):
                pass


# ---------------------------------------------------------------------------
# Successful connection → welcome message
# ---------------------------------------------------------------------------

async def test_auth_success_welcome(app: FastAPI, registered_user: tuple) -> None:
    user_id, token = registered_user
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        async with aconnect_ws(
            "/ws/sessions/test-session",
            client,
            headers={"sec-websocket-protocol": f"bearer,{token}"},
        ) as ws:
            msg = await _recv_json(ws)
            assert msg["v"] == 1
            assert msg["type"] == "system.welcome"
            assert msg["payload"]["session_id"] == "test-session"
            assert "your_seq_start" in msg["payload"]


# ---------------------------------------------------------------------------
# Malformed / unknown / version mismatch
# ---------------------------------------------------------------------------

async def test_malformed_json_keeps_connection(
    app: FastAPI, registered_user: tuple
) -> None:
    user_id, token = registered_user
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        async with aconnect_ws(
            "/ws/sessions/test-session",
            client,
            headers={"sec-websocket-protocol": f"bearer,{token}"},
        ) as ws:
            await _recv_json(ws)  # welcome

            await ws.send_text("not valid json at all")
            error = await _recv_json(ws)
            assert error["type"] == "system.error"
            assert error["payload"]["code"] == "malformed"

            # Connection is still alive — send another bad message
            await ws.send_text("{}")
            error2 = await _recv_json(ws)
            assert error2["type"] == "system.error"
            assert error2["payload"]["code"] == "malformed"


async def test_unknown_type_keeps_connection(
    app: FastAPI, registered_user: tuple
) -> None:
    user_id, token = registered_user
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        async with aconnect_ws(
            "/ws/sessions/test-session",
            client,
            headers={"sec-websocket-protocol": f"bearer,{token}"},
        ) as ws:
            await _recv_json(ws)  # welcome

            msg = json.dumps({
                "v": 1,
                "type": "totally.unknown",
                "ts": datetime.now(UTC).isoformat(),
                "payload": {},
            })
            await ws.send_text(msg)
            error = await _recv_json(ws)
            assert error["type"] == "system.error"
            assert error["payload"]["code"] == "unknown_type"


async def test_version_mismatch_closes(
    app: FastAPI, registered_user: tuple
) -> None:
    user_id, token = registered_user
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        async with aconnect_ws(
            "/ws/sessions/test-session",
            client,
            headers={"sec-websocket-protocol": f"bearer,{token}"},
        ) as ws:
            await _recv_json(ws)  # welcome

            msg = json.dumps({
                "v": 99,
                "type": "chat.send",
                "ts": datetime.now(UTC).isoformat(),
                "payload": {"text": "hello"},
            })
            await ws.send_text(msg)
            error = await _recv_json(ws)
            assert error["type"] == "system.error"
            assert error["payload"]["code"] == "unsupported_version"


async def test_malformed_payload_shape_keeps_connection(
    app: FastAPI, registered_user: tuple
) -> None:
    """Valid envelope but wrong payload shape → malformed, no close."""
    user_id, token = registered_user
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        async with aconnect_ws(
            "/ws/sessions/test-session",
            client,
            headers={"sec-websocket-protocol": f"bearer,{token}"},
        ) as ws:
            await _recv_json(ws)  # welcome

            msg = json.dumps({
                "v": 1,
                "type": "chat.send",
                "ts": datetime.now(UTC).isoformat(),
                "payload": {"wrong_field": 123},
            })
            await ws.send_text(msg)
            error = await _recv_json(ws)
            assert error["type"] == "system.error"
            assert error["payload"]["code"] == "malformed"


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------

async def test_heartbeat_ping_received(
    app: FastAPI, registered_user: tuple
) -> None:
    """Server sends connection.ping within one heartbeat interval."""
    user_id, token = registered_user
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Patch the interval to 0.1s so the test doesn't wait 20s
        with patch("gateway.connection.HEARTBEAT_INTERVAL_S", 0.1):
            async with aconnect_ws(
                "/ws/sessions/test-session",
                client,
                headers={"sec-websocket-protocol": f"bearer,{token}"},
            ) as ws:
                await _recv_json(ws)  # welcome
                ping = await _recv_json(ws)
                assert ping["type"] == "connection.ping"

                # Respond with pong — connection should stay alive
                pong = json.dumps({
                    "v": 1,
                    "type": "connection.pong",
                    "ts": datetime.now(UTC).isoformat(),
                    "payload": {},
                })
                await ws.send_text(pong)
                # No close frame — connection is healthy
