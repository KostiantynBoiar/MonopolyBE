"""End-to-end smoke test for the GAME engine against a RUNNING server.

Drives the real network path the FE will use (HTTP for auth/sessions, a real
WebSocket on /ws/sessions/{id} with the bearer subprotocol, game.* messages):

    register x2 -> create + join -> connect both -> start (REST)
    -> both receive game.state snapshot
    -> out-of-turn roll is rejected (private system.error)
    -> current player plays a full turn (roll / pass / end_turn), driven by the
       ActionSet, until the turn rotates to the other player
    -> both sockets stay in sync on every broadcast

Run it two ways:

    python tests/e2e/test_game_realtime_e2e.py          # standalone, prints PASS/FAIL
    pytest tests/e2e/test_game_realtime_e2e.py -v        # auto-skips if no server

Targets http://localhost:8002 by default; override with E2E_BASE_URL / E2E_WS_URL.
Prereqs: API running (uvicorn) with Mongo + Redis up.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import websockets

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8002").rstrip("/")
WS_URL = os.environ.get("E2E_WS_URL", "ws://localhost:8002").rstrip("/")
RECV_TIMEOUT = 5.0
MAX_TURN_STEPS = 12  # doubles cap + buy/pass + end_turn is a handful of steps


def _envelope(msg_type: str, payload: dict | None = None) -> str:
    return json.dumps({
        "v": 1,
        "type": msg_type,
        "ts": datetime.now(UTC).isoformat(),
        "payload": payload or {},
    })


async def _recv(ws, expected_type: str) -> dict:
    """Receive the next frame of expected_type, replying to pings, asserting otherwise."""
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=RECV_TIMEOUT))
        if msg["type"] == "connection.ping":
            await ws.send(_envelope("connection.pong", {}))
            continue
        assert msg["type"] == expected_type, f"expected {expected_type}, got {msg['type']}: {msg}"
        return msg


async def _recv_state(ws) -> dict:
    """Return the next game.state, skipping heartbeats and session.updated frames."""
    while True:
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=RECV_TIMEOUT))
        if msg["type"] == "connection.ping":
            await ws.send(_envelope("connection.pong", {}))
            continue
        if msg["type"] == "session.updated":
            continue
        assert msg["type"] == "game.state", f"expected game.state, got {msg['type']}: {msg}"
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


async def run_game_flow() -> None:
    async with httpx.AsyncClient(timeout=10.0) as http:
        # 1. Two users, one session, both joined.
        host_id, host_token = await _register(http, "host")
        guest_id, guest_token = await _register(http, "guest")
        host_auth = {"Authorization": f"Bearer {host_token}"}
        guest_auth = {"Authorization": f"Bearer {guest_token}"}

        resp = await http.post(
            f"{BASE_URL}/api/v1/sessions", headers=host_auth, json={"visibility": "public"}
        )
        resp.raise_for_status()
        session_id = resp.json()["session"]["id"]
        (await http.post(f"{BASE_URL}/api/v1/sessions/{session_id}/join", headers=guest_auth)).raise_for_status()
        print(f"[ok] session {session_id} with host + guest")

        # 2. Both connect before start so both get the opening snapshot.
        async with _connect(session_id, host_token) as host_ws, _connect(session_id, guest_token) as guest_ws:
            await _recv(host_ws, "system.welcome")
            await _recv(guest_ws, "system.welcome")

            # 3. Host starts the game (REST) -> game.state broadcast to both.
            (await http.post(f"{BASE_URL}/api/v1/sessions/{session_id}/start", headers=host_auth)).raise_for_status()
            host_state = await _recv_state(host_ws)
            await _recv_state(guest_ws)
            snap = host_state["payload"]
            assert snap["status"] == "in_progress"
            assert len(snap["players"]) == 2
            assert all(p["balance"] == 1500 for p in snap["players"])
            print("[ok] game.state on start (in_progress, 2 players, $1500 each)")

            # Identify which socket controls the current player.
            ws_by_user = {host_id: host_ws, guest_id: guest_ws}
            user_by_player = {p["id"]: p["user_id"] for p in snap["players"]}
            current_user = user_by_player[snap["turn"]["current_player_id"]]
            other_user = guest_id if current_user == host_id else host_id
            cur_ws, other_ws = ws_by_user[current_user], ws_by_user[other_user]

            # 4. Out-of-turn roll -> private system.error, no broadcast.
            await other_ws.send(_envelope("game.roll_dice"))
            err = await _recv(other_ws, "system.error")
            assert err["payload"]["code"] == "illegal_action"
            print("[ok] out-of-turn roll rejected (illegal_action, private)")

            # 5. Play the current player's turn to completion, driven by the ActionSet.
            #    Every applied command broadcasts to both sockets; keep them in sync.
            state = snap
            start_player = state["turn"]["current_player_id"]
            for _ in range(MAX_TURN_STEPS):
                actions = state["turn"]["actions_available"]
                if actions["can_roll"]:
                    intent = "game.roll_dice"
                elif actions["can_buy"]:
                    intent = "game.pass_buy"  # decline to keep cash flow simple
                elif actions["can_end_turn"]:
                    intent = "game.end_turn"
                else:
                    raise AssertionError(f"no actionable move in {actions}")

                await cur_ws.send(_envelope(intent))
                cur_frame = await _recv_state(cur_ws)
                await _recv_state(other_ws)  # drain the broadcast on the other socket
                state = cur_frame["payload"]

                if intent == "game.roll_dice":
                    assert state["turn"]["dice_roll"] is not None
                if intent == "game.end_turn":
                    break

            assert state["turn"]["current_player_id"] != start_player, "turn did not rotate"
            print(f"[ok] full turn played; turn rotated to {state['turn']['current_player_id'][:8]}…")

    print("\nGAME E2E PASSED ✅")


def test_game_realtime_e2e() -> None:
    import pytest

    try:
        httpx.get(f"{BASE_URL}/health", timeout=2.0).raise_for_status()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"server not reachable at {BASE_URL} ({exc}); start it to run E2E")
    asyncio.run(run_game_flow())


if __name__ == "__main__":
    try:
        asyncio.run(run_game_flow())
    except AssertionError as exc:
        print(f"\nGAME E2E FAILED ❌\n  {exc}")
        raise SystemExit(1) from exc
    except Exception as exc:  # noqa: BLE001
        print(f"\nGAME E2E ERROR ❌ ({type(exc).__name__}): {exc}")
        print(f"  Is the server running at {BASE_URL} / {WS_URL} with Mongo + Redis up?")
        raise SystemExit(2) from exc
