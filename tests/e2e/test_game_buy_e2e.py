"""E2E: buy property when landing on an unowned space."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
import websockets

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8002").rstrip("/")
WS_URL = os.environ.get("E2E_WS_URL", "ws://localhost:8002").rstrip("/")
RECV_TIMEOUT = 5.0
MAX_ROLLS = 25


def _envelope(msg_type: str, payload: dict | None = None) -> str:
    return json.dumps({
        "v": 1,
        "type": msg_type,
        "ts": datetime.now(UTC).isoformat(),
        "payload": payload or {},
    })


async def _recv(ws, expected_type: str) -> dict:
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=RECV_TIMEOUT))
        if msg["type"] == "connection.ping":
            await ws.send(_envelope("connection.pong", {}))
            continue
        assert msg["type"] == expected_type, msg
        return msg


async def _recv_state(ws) -> dict:
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=RECV_TIMEOUT))
        if msg["type"] == "connection.ping":
            await ws.send(_envelope("connection.pong", {}))
            continue
        if msg["type"] == "session.updated":
            continue
        assert msg["type"] == "game.state", msg
        return msg


async def _register(http: httpx.AsyncClient, label: str) -> tuple[str, str]:
    resp = await http.post(
        f"{BASE_URL}/api/v1/auth/register",
        json={
            "email": f"{label}_{uuid4().hex[:8]}@e2e.example",
            "password": "password123",
            "display_name": label.title(),
        },
    )
    resp.raise_for_status()
    body = resp.json()
    return body["user"]["id"], body["token"]["access_token"]


def _connect(session_id: str, token: str):
    return websockets.connect(
        f"{WS_URL}/ws/sessions/{session_id}",
        subprotocols=["bearer", token],
        open_timeout=RECV_TIMEOUT,
    )


async def run_buy_flow() -> None:
    async with httpx.AsyncClient(timeout=10.0) as http:
        host_id, host_token = await _register(http, "buyhost")
        guest_id, guest_token = await _register(http, "buyguest")
        host_auth = {"Authorization": f"Bearer {host_token}"}
        guest_auth = {"Authorization": f"Bearer {guest_token}"}

        resp = await http.post(
            f"{BASE_URL}/api/v1/sessions", headers=host_auth, json={"visibility": "public"}
        )
        resp.raise_for_status()
        session_id = resp.json()["session"]["id"]
        (await http.post(f"{BASE_URL}/api/v1/sessions/{session_id}/join", headers=guest_auth)).raise_for_status()

        async with _connect(session_id, host_token) as host_ws, _connect(
            session_id, guest_token
        ) as guest_ws:
            await _recv(host_ws, "system.welcome")
            await _recv(guest_ws, "system.welcome")

            (await http.post(f"{BASE_URL}/api/v1/sessions/{session_id}/start", headers=host_auth)).raise_for_status()
            start_msg = await _recv_state(host_ws)
            await _recv_state(guest_ws)

            snap = start_msg["payload"]
            ws_by_user = {host_id: host_ws, guest_id: guest_ws}
            user_by_player = {p["id"]: p["user_id"] for p in snap["players"]}
            current_user = user_by_player[snap["turn"]["current_player_id"]]
            cur_ws = ws_by_user[current_user]
            other_ws = guest_ws if cur_ws is host_ws else host_ws

            bought = False
            for _ in range(MAX_ROLLS):
                actions = snap["turn"]["actions_available"]
                if actions["can_roll"]:
                    await cur_ws.send(_envelope("game.roll_dice"))
                    cur_frame = await _recv_state(cur_ws)
                    guest_frame = await _recv_state(other_ws)
                    assert cur_frame["seq"] == guest_frame["seq"]
                    snap = cur_frame["payload"]
                    if snap["turn"]["actions_available"]["can_buy"]:
                        position = snap["turn"]["pending_buy_position"]
                        await cur_ws.send(_envelope("game.buy_property", {"position": position}))
                        buy_frame = await _recv_state(cur_ws)
                        await _recv_state(other_ws)
                        assert buy_frame["payload"]["spaces"][position]["owner_id"] is not None
                        bought = True
                        break
                    if snap["turn"]["actions_available"]["can_end_turn"]:
                        await cur_ws.send(_envelope("game.end_turn"))
                        await _recv_state(cur_ws)
                        await _recv_state(other_ws)
                        break
                else:
                    break

            assert bought, "did not land on a purchasable property within roll limit"


@pytest.mark.e2e
def test_game_buy_e2e() -> None:
    try:
        httpx.get(f"{BASE_URL}/health", timeout=2.0).raise_for_status()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"server not reachable at {BASE_URL} ({exc}); start it to run E2E")
    asyncio.run(run_buy_flow())
