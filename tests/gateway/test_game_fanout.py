from __future__ import annotations

from starlette.testclient import TestClient

from tests.gateway.game_helpers import (
    assert_dual_broadcast,
    discover_current_token,
    envelope,
    recv_game_state,
    setup_two_player_game,
    ws_headers,
)


def test_roll_dice_dual_broadcast(client: TestClient) -> None:
    setup = setup_two_player_game(client)
    discover_current_token(client, setup)

    def roll(host_ws, _guest_ws) -> None:
        host_ws.send_text(envelope("game.roll_dice"))

    msg = assert_dual_broadcast(client, setup, roll)
    assert msg["payload"]["turn"]["dice_roll"] is not None


def test_end_turn_dual_broadcast(client: TestClient) -> None:
    setup = setup_two_player_game(client)
    token = discover_current_token(client, setup)

    with (
        client.websocket_connect(
            f"/ws/sessions/{setup.session_id}",
            headers=ws_headers(token),
        ) as ws,
        client.websocket_connect(
            f"/ws/sessions/{setup.session_id}",
            headers=ws_headers(setup.guest_token),
        ) as guest_ws,
    ):
        ws.receive_json()
        guest_ws.receive_json()
        recv_game_state(ws)
        recv_game_state(guest_ws)

        ws.send_text(envelope("game.roll_dice"))
        roll_msg = recv_game_state(ws)
        recv_game_state(guest_ws)

        if roll_msg["payload"]["turn"]["actions_available"]["can_end_turn"]:
            ws.send_text(envelope("game.end_turn"))
            host_msg = recv_game_state(ws)
            guest_msg = recv_game_state(guest_ws)
            assert host_msg["seq"] == guest_msg["seq"]
