"""session.updated broadcasts: membership changes reach connected members over WS."""
from __future__ import annotations

from starlette.testclient import TestClient

from tests.conftest import create_session


def _ws_headers(token: str) -> dict[str, str]:
    return {"sec-websocket-protocol": f"bearer,{token}"}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _recv_until(ws, msg_type: str, *, max_frames: int = 5) -> dict:
    """Drain frames (welcome, pings, ...) until one of msg_type arrives."""
    for _ in range(max_frames):
        msg = ws.receive_json()
        if msg["type"] == msg_type:
            return msg
    raise AssertionError(f"did not receive {msg_type} within {max_frames} frames")


def test_join_broadcasts_session_updated(
    client: TestClient, user_pair: tuple
) -> None:
    (_host_id, host_token), (guest_id, guest_token) = user_pair
    session_id = create_session(client, host_token)

    with client.websocket_connect(
        f"/ws/sessions/{session_id}",
        headers=_ws_headers(host_token),
    ) as host_ws:
        host_ws.receive_json()  # welcome

        # Guest joins via REST -> host should receive a session.updated frame.
        join_resp = client.post(
            f"/api/v1/sessions/{session_id}/join",
            headers=_auth(guest_token),
        )
        assert join_resp.status_code == 200

        msg = _recv_until(host_ws, "session.updated")
        session = msg["payload"]["session"]
        assert session["id"] == session_id
        assert session["member_count"] == 2
        assert msg["payload"]["session"]["your_role"] is None  # recipient-derived
        assert any(m["user_id"] == guest_id for m in session["members"])
        assert isinstance(msg["seq"], int)


def test_start_broadcasts_status_change(
    client: TestClient, user_pair: tuple
) -> None:
    (_host_id, host_token), (_guest_id, guest_token) = user_pair
    session_id = create_session(client, host_token)
    client.post(f"/api/v1/sessions/{session_id}/join", headers=_auth(guest_token))

    with client.websocket_connect(
        f"/ws/sessions/{session_id}",
        headers=_ws_headers(host_token),
    ) as host_ws:
        host_ws.receive_json()  # welcome

        start_resp = client.post(
            f"/api/v1/sessions/{session_id}/start",
            headers=_auth(host_token),
        )
        assert start_resp.status_code == 200

        msg = _recv_until(host_ws, "session.updated")
        assert msg["payload"]["session"]["status"] == "in_progress"
