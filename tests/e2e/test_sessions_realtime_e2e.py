"""End-to-end smoke test for sessions + realtime chat against a RUNNING server.

Unlike the in-process tests (which use Starlette's TestClient), this drives the
real network stack a browser/FE client uses: HTTP for auth + sessions, and a real
WebSocket with the `bearer, <jwt>` subprotocol. It exercises the full path:

    register x2 -> create session -> connect host WS -> chat -> sticker
    -> invalid sticker rejected -> guest joins (REST) -> session.updated
    -> host starts (REST) -> session.updated(status=in_progress)

Run it two ways:

    # 1. As a standalone script (prints PASS/FAIL per step)
    python tests/e2e/test_sessions_realtime_e2e.py

    # 2. Under pytest (auto-skips if the server isn't reachable)
    pytest tests/e2e/test_sessions_realtime_e2e.py -v

Point it at a non-default server with env vars:
    E2E_BASE_URL=http://localhost:8002   (REST base, no trailing slash)
    E2E_WS_URL=ws://localhost:8002       (WS base, no trailing slash)

Prerequisites: the API must be running (uvicorn) with Mongo + Redis up, e.g.
    docker compose -f docker-compose.dev.yml up -d
    uvicorn main:create_app --factory --port 8002   # with src on PYTHONPATH
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


def _envelope(msg_type: str, payload: dict) -> str:
    return json.dumps({
        "v": 1,
        "type": msg_type,
        "ts": datetime.now(UTC).isoformat(),
        "payload": payload,
    })


async def _recv(ws, expected_type: str) -> dict:
    """Receive frames until one of expected_type arrives, skipping heartbeats."""
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=RECV_TIMEOUT)
        msg = json.loads(raw)
        if msg["type"] == "connection.ping":
            await ws.send(_envelope("connection.pong", {}))
            continue
        assert msg["type"] == expected_type, f"expected {expected_type}, got {msg['type']}: {msg}"
        return msg


async def _register(http: httpx.AsyncClient, label: str) -> tuple[str, str, str]:
    """Returns (user_id, token, display_name)."""
    display_name = label.title()
    resp = await http.post(
        f"{BASE_URL}/api/v1/auth/register",
        json={
            "email": f"{label}_{uuid4().hex[:8]}@e2e.example",
            "password": "password123",
            "display_name": display_name,
        },
    )
    resp.raise_for_status()
    body = resp.json()
    return body["user"]["id"], body["token"]["access_token"], display_name


async def run_flow() -> None:
    async with httpx.AsyncClient(timeout=10.0) as http:
        # 1. Auth: two users.
        host_id, host_token, host_name = await _register(http, "host")
        guest_id, guest_token, _ = await _register(http, "guest")
        host_auth = {"Authorization": f"Bearer {host_token}"}
        guest_auth = {"Authorization": f"Bearer {guest_token}"}
        print(f"[ok] registered host={host_id} guest={guest_id}")

        # 2. Host creates a session.
        resp = await http.post(
            f"{BASE_URL}/api/v1/sessions",
            headers=host_auth,
            json={"visibility": "public"},
        )
        resp.raise_for_status()
        session = resp.json()["session"]
        session_id = session["id"]
        assert session["invite_code"].startswith("TYC-")
        print(f"[ok] created session={session_id} code={session['invite_code']}")

        # 3. Host connects the real WebSocket (bearer subprotocol).
        async with websockets.connect(
            f"{WS_URL}/ws/sessions/{session_id}",
            subprotocols=["bearer", host_token],
            open_timeout=RECV_TIMEOUT,
        ) as ws:
            welcome = await _recv(ws, "system.welcome")
            assert welcome["payload"]["session_id"] == session_id
            print("[ok] system.welcome received")

            # 4. Chat round-trip with enriched payload.
            await ws.send(_envelope("chat.send", {"text": "Hello, world!"}))
            chat = await _recv(ws, "chat.message")
            cp = chat["payload"]
            assert cp["text"] == "Hello, world!"
            assert cp["from_user_id"] == host_id
            assert cp["display_name"] == host_name
            assert cp["message_id"] and isinstance(cp["message_id"], str)
            assert cp["ts"] and isinstance(cp["ts"], str)
            assert isinstance(chat["seq"], int)
            print(f"[ok] chat.message enriched (seq={chat['seq']}, id={cp['message_id'][:8]}…)")

            # 5. Sticker round-trip.
            await ws.send(_envelope("chat.sticker_send", {"sticker_url": "/stickers/kolobki/012.tgs"}))
            sticker = await _recv(ws, "chat.sticker")
            sp = sticker["payload"]
            assert sp["sticker_url"] == "/stickers/kolobki/012.tgs"
            assert sp["from_user_id"] == host_id
            assert sp["display_name"] == host_name
            print(f"[ok] chat.sticker received (seq={sticker['seq']})")

            # 6. Invalid sticker URL -> malformed error.
            await ws.send(_envelope("chat.sticker_send", {"sticker_url": "http://evil.example/x.png"}))
            err = await _recv(ws, "system.error")
            assert err["payload"]["code"] == "malformed"
            print("[ok] invalid sticker rejected (malformed)")

            # 7. Guest joins via REST -> host WS receives session.updated.
            resp = await http.post(
                f"{BASE_URL}/api/v1/sessions/{session_id}/join",
                headers=guest_auth,
            )
            resp.raise_for_status()
            updated = await _recv(ws, "session.updated")
            usession = updated["payload"]["session"]
            assert usession["member_count"] == 2
            assert usession["your_role"] is None  # broadcast: recipient derives role
            assert any(m["user_id"] == guest_id for m in usession["members"])
            print(f"[ok] session.updated on join (member_count={usession['member_count']})")

            # 8. Host starts the game -> session.updated with status change.
            resp = await http.post(
                f"{BASE_URL}/api/v1/sessions/{session_id}/start",
                headers=host_auth,
            )
            resp.raise_for_status()
            started = await _recv(ws, "session.updated")
            assert started["payload"]["session"]["status"] == "in_progress"
            print("[ok] session.updated on start (status=in_progress)")

    print("\nE2E PASSED ✅")


# --------------------------------------------------------------------------- #
# pytest entrypoint (skips when no server is listening)
# --------------------------------------------------------------------------- #
def test_sessions_realtime_e2e() -> None:
    import pytest

    try:
        httpx.get(f"{BASE_URL}/health", timeout=2.0).raise_for_status()
    except Exception as exc:  # noqa: BLE001 - any connection failure -> skip
        pytest.skip(f"server not reachable at {BASE_URL} ({exc}); start it to run E2E")

    asyncio.run(run_flow())


if __name__ == "__main__":
    try:
        asyncio.run(run_flow())
    except AssertionError as exc:
        print(f"\nE2E FAILED ❌\n  {exc}")
        raise SystemExit(1) from exc
    except Exception as exc:  # noqa: BLE001
        print(f"\nE2E ERROR ❌ ({type(exc).__name__}): {exc}")
        print(f"  Is the server running at {BASE_URL} / {WS_URL} with Mongo + Redis up?")
        raise SystemExit(2) from exc
