"""Animation timeline over the wire: game.state carries the timeline, and
game.animation_continue is authorized to the current player and fanned out to all."""
from __future__ import annotations

from domain.game.cards_data import ALL_CARDS
from domain.game.schemas.cards import ActiveCard
from domain.game.schemas.state import GameState
from tests.gateway.game_helpers import (
    assert_dual_broadcast,
    envelope,
    mutate_game_state,
    setup_two_player_game,
    start_session,
    ws_headers,
)

_CARD = next(iter(ALL_CARDS.values()))


def _recv_type(ws, expected: str) -> dict:
    """Next frame of `expected` type, skipping pings/session.updated."""
    while True:
        msg = ws.receive_json()
        if msg["type"] in ("connection.ping", "session.updated"):
            continue
        assert msg["type"] == expected, msg
        return msg


def test_roll_frame_carries_animation_timeline(client) -> None:
    setup = setup_two_player_game(client)
    start_session(client, setup.session_id, setup.host_token)

    frame = assert_dual_broadcast(
        client,
        setup,
        lambda cur_ws, _other: cur_ws.send_text(envelope("game.roll_dice")),
    )

    timeline = frame["payload"]["animation_timeline"]
    assert isinstance(timeline, list)
    assert timeline[0]["type"] == "roll_dice"  # a roll always leads with the dice spin


def _seed_active_card(client, setup) -> str:
    """Put an active card (drawn by the current player) into the game state. Returns the
    current player's user token."""
    def _mutate(state: GameState) -> GameState:
        cur = state.turn.current_player_id
        return state.model_copy(
            update={
                "active_card": ActiveCard(
                    id=_CARD.id,
                    kind=_CARD.kind,
                    text=_CARD.text,
                    effect=_CARD.effect,
                    drawer_id=cur,
                )
            }
        )

    state = mutate_game_state(client, setup.session_id, _mutate)
    cur = state.turn.current_player_id
    user_by_player = {p.id: p.user_id for p in state.players}
    return setup.tokens_by_user[user_by_player[cur]]


def test_animation_continue_authorized_and_broadcast(client) -> None:
    setup = setup_two_player_game(client)
    start_session(client, setup.session_id, setup.host_token)
    current_token = _seed_active_card(client, setup)
    other_token = next(
        t for t in (setup.host_token, setup.guest_token) if t != current_token
    )

    with (
        client.websocket_connect(
            f"/ws/sessions/{setup.session_id}", headers=ws_headers(current_token)
        ) as cur_ws,
        client.websocket_connect(
            f"/ws/sessions/{setup.session_id}", headers=ws_headers(other_token)
        ) as other_ws,
    ):
        cur_ws.receive_json()   # welcome
        other_ws.receive_json()
        _recv_type(cur_ws, "game.state")
        _recv_type(other_ws, "game.state")

        cur_ws.send_text(envelope("game.animation_continue", {"interaction_id": "abc123"}))

        # Fanned out to BOTH clients so everyone un-pauses the same gate.
        m_cur = _recv_type(cur_ws, "game.animation_continue")
        m_other = _recv_type(other_ws, "game.animation_continue")
        assert m_cur["payload"]["interaction_id"] == "abc123"
        assert m_other["payload"]["interaction_id"] == "abc123"


def test_animation_continue_rejected_for_non_current_player(client) -> None:
    setup = setup_two_player_game(client)
    start_session(client, setup.session_id, setup.host_token)
    current_token = _seed_active_card(client, setup)
    other_token = next(
        t for t in (setup.host_token, setup.guest_token) if t != current_token
    )

    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}", headers=ws_headers(other_token)
    ) as ws:
        ws.receive_json()  # welcome
        _recv_type(ws, "game.state")

        ws.send_text(envelope("game.animation_continue", {"interaction_id": "abc123"}))
        err = _recv_type(ws, "system.error")
        assert err["payload"]["code"] == "illegal_action"
