from __future__ import annotations

import json
from datetime import UTC, datetime

from starlette.testclient import TestClient

from tests.conftest import create_session, register_user


def _ws_headers(token: str) -> dict[str, str]:
    return {"sec-websocket-protocol": f"bearer,{token}"}


def _envelope(msg_type: str, payload: dict | None = None) -> str:
    return json.dumps({
        "v": 1,
        "type": msg_type,
        "ts": datetime.now(UTC).isoformat(),
        "payload": payload or {},
    })


def _start_session(client: TestClient, session_id: str, host_token: str) -> None:
    resp = client.post(
        f"/api/v1/sessions/{session_id}/start",
        headers={"Authorization": f"Bearer {host_token}"},
    )
    assert resp.status_code == 200, resp.text


def test_game_state_on_start(client: TestClient) -> None:
    host_id, host_token = register_user(client, "host")
    guest_id, guest_token = register_user(client, "guest")
    session_id = create_session(client, host_token)

    client.post(
        f"/api/v1/sessions/{session_id}/join",
        headers={"Authorization": f"Bearer {guest_token}"},
    )

    with client.websocket_connect(
        f"/ws/sessions/{session_id}",
        headers=_ws_headers(host_token),
    ) as ws:
        ws.receive_json()  # welcome
        _start_session(client, session_id, host_token)

        session_updated = ws.receive_json()
        assert session_updated["type"] == "session.updated"

        game_state_msg = ws.receive_json()
        assert game_state_msg["type"] == "game.state"
        payload = game_state_msg["payload"]
        assert payload["status"] == "in_progress"
        assert payload["session_code"]
        assert len(payload["players"]) == 2
        assert isinstance(game_state_msg["seq"], int)


def _recv_game_state(ws) -> dict:
    """Skip heartbeats; return the next game.state frame."""
    while True:
        msg = ws.receive_json()
        if msg["type"] == "connection.ping":
            continue
        assert msg["type"] == "game.state", msg
        return msg


def test_roll_dice_and_end_turn(client: TestClient) -> None:
    host_id, host_token = register_user(client, "host")
    guest_id, guest_token = register_user(client, "guest")
    session_id = create_session(client, host_token)
    client.post(
        f"/api/v1/sessions/{session_id}/join",
        headers={"Authorization": f"Bearer {guest_token}"},
    )

    # Turn order is shuffled at game creation, so discover who goes first from the
    # snapshot and act as that player (otherwise the roll is correctly rejected).
    _start_session(client, session_id, host_token)
    token_by_user = {host_id: host_token, guest_id: guest_token}

    with client.websocket_connect(
        f"/ws/sessions/{session_id}",
        headers=_ws_headers(host_token),
    ) as probe:
        probe.receive_json()  # welcome
        snapshot = _recv_game_state(probe)["payload"]
    current_player_id = snapshot["turn"]["current_player_id"]
    user_by_player = {p["id"]: p["user_id"] for p in snapshot["players"]}
    current_token = token_by_user[user_by_player[current_player_id]]

    with client.websocket_connect(
        f"/ws/sessions/{session_id}",
        headers=_ws_headers(current_token),
    ) as ws:
        ws.receive_json()  # welcome
        _recv_game_state(ws)  # connect-time snapshot

        ws.send_text(_envelope("game.roll_dice"))
        roll_msg = _recv_game_state(ws)
        assert roll_msg["payload"]["turn"]["dice_roll"] is not None

        turn = roll_msg["payload"]["turn"]
        if turn["actions_available"]["can_end_turn"]:
            ws.send_text(_envelope("game.end_turn"))
            end_msg = _recv_game_state(ws)
            assert end_msg["seq"] > roll_msg["seq"]


def test_out_of_turn_roll_rejected(client: TestClient) -> None:
    host_id, host_token = register_user(client, "host")
    guest_id, guest_token = register_user(client, "guest")
    session_id = create_session(client, host_token)
    client.post(
        f"/api/v1/sessions/{session_id}/join",
        headers={"Authorization": f"Bearer {guest_token}"},
    )
    _start_session(client, session_id, host_token)
    token_by_user = {host_id: host_token, guest_id: guest_token}

    # Discover the current player, then roll as the OTHER player so the move is
    # genuinely out of turn (turn order is randomized at game creation).
    with client.websocket_connect(
        f"/ws/sessions/{session_id}",
        headers=_ws_headers(host_token),
    ) as probe:
        probe.receive_json()  # welcome
        snapshot = _recv_game_state(probe)["payload"]
    current_player_id = snapshot["turn"]["current_player_id"]
    user_by_player = {p["id"]: p["user_id"] for p in snapshot["players"]}
    current_user = user_by_player[current_player_id]
    other_user = next(uid for uid in token_by_user if uid != current_user)
    other_token = token_by_user[other_user]

    with client.websocket_connect(
        f"/ws/sessions/{session_id}",
        headers=_ws_headers(other_token),
    ) as ws:
        ws.receive_json()  # welcome
        _recv_game_state(ws)  # connect-time snapshot

        ws.send_text(_envelope("game.roll_dice"))
        while True:
            msg = ws.receive_json()
            if msg["type"] == "connection.ping":
                continue
            assert msg["type"] == "system.error", msg
            assert msg["payload"]["code"] == "illegal_action"
            break
