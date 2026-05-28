"""Chat handler: single-node round-trip, seq ordering."""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from httpx_ws import aconnect_ws


async def _recv_json(ws) -> dict:
    msg = await ws.receive_text()
    return json.loads(msg)


def _chat_send(text: str) -> str:
    return json.dumps({
        "v": 1,
        "type": "chat.send",
        "ts": datetime.now(UTC).isoformat(),
        "idempotency_key": "test-key-1",
        "payload": {"text": text},
    })


async def test_chat_round_trip_single_node(
    app: FastAPI, registered_user: tuple
) -> None:
    """Sender receives their own message back via backplane fan-out."""
    user_id, token = registered_user
    session = "chat-session-single"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        async with aconnect_ws(
            f"/ws/sessions/{session}",
            client,
            headers={"sec-websocket-protocol": f"bearer,{token}"},
        ) as ws:
            await _recv_json(ws)  # welcome

            await ws.send_text(_chat_send("Hello, world!"))
            msg = await _recv_json(ws)

            assert msg["type"] == "chat.message"
            assert msg["payload"]["text"] == "Hello, world!"
            assert msg["payload"]["from_user_id"] == user_id
            assert isinstance(msg["seq"], int)


async def test_chat_delivered_to_both_clients(
    app: FastAPI, registered_user: tuple
) -> None:
    """Two clients in the same session both receive the message in seq order."""
    user_id, token = registered_user
    session = "chat-session-two"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client_a:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client_b:
            async with aconnect_ws(
                f"/ws/sessions/{session}",
                client_a,
                headers={"sec-websocket-protocol": f"bearer,{token}"},
            ) as ws_a:
                async with aconnect_ws(
                    f"/ws/sessions/{session}",
                    client_b,
                    headers={"sec-websocket-protocol": f"bearer,{token}"},
                ) as ws_b:
                    await _recv_json(ws_a)  # welcome A
                    await _recv_json(ws_b)  # welcome B

                    await ws_a.send_text(_chat_send("from A"))

                    msg_a = await _recv_json(ws_a)
                    msg_b = await _recv_json(ws_b)

                    assert msg_a["type"] == "chat.message"
                    assert msg_b["type"] == "chat.message"
                    assert msg_a["payload"]["text"] == "from A"
                    assert msg_b["payload"]["text"] == "from A"
                    # Both see the same server-assigned seq
                    assert msg_a["seq"] == msg_b["seq"]


async def test_seq_increases_monotonically(
    app: FastAPI, registered_user: tuple
) -> None:
    user_id, token = registered_user
    session = "chat-session-seq"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        async with aconnect_ws(
            f"/ws/sessions/{session}",
            client,
            headers={"sec-websocket-protocol": f"bearer,{token}"},
        ) as ws:
            await _recv_json(ws)  # welcome

            for i in range(3):
                await ws.send_text(_chat_send(f"msg {i}"))

            seqs = []
            for _ in range(3):
                msg = await _recv_json(ws)
                assert msg["type"] == "chat.message"
                seqs.append(msg["seq"])

            assert seqs == sorted(seqs)
            assert len(set(seqs)) == 3  # all distinct
