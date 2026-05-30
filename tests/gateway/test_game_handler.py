from __future__ import annotations

from starlette.testclient import TestClient

from tests.gateway.game_helpers import (
    discover_current_token,
    envelope,
    recv_error,
    recv_game_state,
    setup_two_player_game,
    start_session,
    ws_headers,
)


def test_game_state_on_start(client: TestClient) -> None:
    setup = setup_two_player_game(client)

    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(setup.host_token),
    ) as ws:
        ws.receive_json()
        start_session(client, setup.session_id, setup.host_token)

        session_updated = ws.receive_json()
        assert session_updated["type"] == "session.updated"

        game_state_msg = ws.receive_json()
        assert game_state_msg["type"] == "game.state"
        payload = game_state_msg["payload"]
        assert payload["status"] == "in_progress"
        assert payload["session_code"]
        assert len(payload["players"]) == 2
        assert isinstance(game_state_msg["seq"], int)


def test_roll_dice_and_end_turn(client: TestClient) -> None:
    setup = setup_two_player_game(client)
    current_token = discover_current_token(client, setup)

    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(current_token),
    ) as ws:
        ws.receive_json()
        recv_game_state(ws)

        ws.send_text(envelope("game.roll_dice"))
        roll_msg = recv_game_state(ws)
        assert roll_msg["payload"]["turn"]["dice_roll"] is not None

        turn = roll_msg["payload"]["turn"]
        if turn["actions_available"]["can_end_turn"]:
            ws.send_text(envelope("game.end_turn"))
            end_msg = recv_game_state(ws)
            assert end_msg["seq"] > roll_msg["seq"]


def test_out_of_turn_roll_rejected(client: TestClient) -> None:
    setup = setup_two_player_game(client)
    current_token = discover_current_token(client, setup)

    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(setup.host_token),
    ) as probe:
        probe.receive_json()
        snapshot = recv_game_state(probe)["payload"]

    from tests.gateway.game_helpers import other_token_for_current

    other_token = other_token_for_current(setup, snapshot)

    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(other_token),
    ) as ws:
        ws.receive_json()
        recv_game_state(ws)

        ws.send_text(envelope("game.roll_dice"))
        err = recv_error(ws)
        assert err["payload"]["code"] == "illegal_action"


def test_game_state_includes_extended_fields(client: TestClient) -> None:
    setup = setup_two_player_game(client)
    start_session(client, setup.session_id, setup.host_token)

    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(setup.host_token),
    ) as ws:
        ws.receive_json()
        msg = recv_game_state(ws)
        payload = msg["payload"]
        # Deck order is server-only and must never reach clients.
        assert "chance_deck" not in payload
        assert "chest_deck" not in payload
        # Public game info is present.
        assert "bank_houses" in payload
        assert "bank_hotels" in payload
        assert payload.get("active_card") is None
        assert payload.get("auction") is None
        assert payload.get("trade") is None
        assert "viewer_id" in payload
