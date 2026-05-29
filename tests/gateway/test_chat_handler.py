"""Chat handler: single-node round-trip, seq ordering."""
from __future__ import annotations

import json
from datetime import UTC, datetime

from starlette.testclient import TestClient


def _ws_headers(token: str) -> dict[str, str]:
    return {"sec-websocket-protocol": f"bearer,{token}"}


def _chat_send(text: str) -> str:
    return json.dumps({
        "v": 1,
        "type": "chat.send",
        "ts": datetime.now(UTC).isoformat(),
        "idempotency_key": "test-key-1",
        "payload": {"text": text},
    })


def test_chat_round_trip_single_node(
    client: TestClient, registered_user: tuple
) -> None:
    user_id, token, session_id = registered_user
    with client.websocket_connect(
        f"/ws/sessions/{session_id}",
        headers=_ws_headers(token),
    ) as ws:
        ws.receive_json()  # welcome

        ws.send_text(_chat_send("Hello, world!"))
        msg = ws.receive_json()

        assert msg["type"] == "chat.message"
        assert msg["payload"]["text"] == "Hello, world!"
        assert msg["payload"]["from_user_id"] == user_id
        assert isinstance(msg["seq"], int)


def test_chat_delivered_to_both_clients(
    client: TestClient, registered_user: tuple
) -> None:
    user_id, token, session_id = registered_user
    with client.websocket_connect(
        f"/ws/sessions/{session_id}",
        headers=_ws_headers(token),
    ) as ws_a:
        with client.websocket_connect(
            f"/ws/sessions/{session_id}",
            headers=_ws_headers(token),
        ) as ws_b:
            ws_a.receive_json()  # welcome A
            ws_b.receive_json()  # welcome B

            ws_a.send_text(_chat_send("from A"))

            msg_a = ws_a.receive_json()
            msg_b = ws_b.receive_json()

            assert msg_a["type"] == "chat.message"
            assert msg_b["type"] == "chat.message"
            assert msg_a["payload"]["text"] == "from A"
            assert msg_b["payload"]["text"] == "from A"
            assert msg_a["seq"] == msg_b["seq"]


def test_seq_increases_monotonically(
    client: TestClient, registered_user: tuple
) -> None:
    _user_id, token, session_id = registered_user
    with client.websocket_connect(
        f"/ws/sessions/{session_id}",
        headers=_ws_headers(token),
    ) as ws:
        ws.receive_json()  # welcome

        for i in range(3):
            ws.send_text(_chat_send(f"msg {i}"))

        seqs = []
        for _ in range(3):
            msg = ws.receive_json()
            assert msg["type"] == "chat.message"
            seqs.append(msg["seq"])

        assert seqs == sorted(seqs)
        assert len(set(seqs)) == 3
