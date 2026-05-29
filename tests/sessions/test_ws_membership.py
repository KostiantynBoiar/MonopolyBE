from __future__ import annotations

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tests.conftest import create_session


def _ws_headers(token: str) -> dict[str, str]:
    return {"sec-websocket-protocol": f"bearer,{token}"}


def test_ws_rejects_non_member(client: TestClient, user_pair: tuple) -> None:
    (_, host_token), (_, guest_token) = user_pair

    session_id = create_session(client, host_token)

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            f"/ws/sessions/{session_id}",
            headers=_ws_headers(guest_token),
        ):
            pass


def test_ws_accepts_member_after_join(client: TestClient, user_pair: tuple) -> None:
    (_, host_token), (_, guest_token) = user_pair

    session_id = create_session(client, host_token)

    join_resp = client.post(
        f"/api/v1/sessions/{session_id}/join",
        headers={"Authorization": f"Bearer {guest_token}"},
    )
    assert join_resp.status_code == 200

    with client.websocket_connect(
        f"/ws/sessions/{session_id}",
        headers=_ws_headers(guest_token),
    ) as ws:
        msg = ws.receive_json()
        assert msg["type"] == "system.welcome"
        assert msg["payload"]["session_id"] == session_id
