from __future__ import annotations

from starlette.testclient import TestClient

from domain.game.enums import TurnPhase
from domain.game.schemas.state import BankruptcyState, GameState, JailStatus, PlayerState
from tests.gateway.game_helpers import (
    GameSetup,
    discover_current_token,
    envelope,
    load_game_state,
    mutate_game_state,
    other_token_for_current,
    recv_error,
    recv_game_state,
    setup_two_player_game,
    start_session,
    ws_headers,
)
from tests.domain.game.conftest import (
    monopoly_brown,
    with_phase,
)


def _current_player(state: GameState) -> PlayerState:
    return next(p for p in state.players if p.id == state.turn.current_player_id)


def _token_for_player(setup: GameSetup, player: PlayerState) -> str:
    return setup.tokens_by_user[player.user_id]


def _started_game(client: TestClient) -> tuple[GameSetup, str]:
    setup = setup_two_player_game(client)
    token = discover_current_token(client, setup)
    return setup, token


def _roll_until_can_buy(ws, max_rolls: int = 25) -> dict:
    for _ in range(max_rolls):
        ws.send_text(envelope("game.roll_dice"))
        msg = recv_game_state(ws)
        turn = msg["payload"]["turn"]
        if turn["actions_available"]["can_buy"]:
            return msg
        if turn["actions_available"]["can_end_turn"]:
            ws.send_text(envelope("game.end_turn"))
            recv_game_state(ws)
    raise AssertionError("never reached a purchasable property")


def test_roll_dice_intent(client: TestClient) -> None:
    setup, token = _started_game(client)
    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(token),
    ) as ws:
        ws.receive_json()
        recv_game_state(ws)
        ws.send_text(envelope("game.roll_dice"))
        msg = recv_game_state(ws)
        assert msg["payload"]["turn"]["dice_roll"] is not None


def test_buy_property_intent(client: TestClient) -> None:
    setup, token = _started_game(client)
    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(token),
    ) as ws:
        ws.receive_json()
        roll_msg = _roll_until_can_buy(ws)
        position = roll_msg["payload"]["turn"]["pending_buy_position"]
        ws.send_text(envelope("game.buy_property", {"position": position}))
        buy_msg = recv_game_state(ws)
        assert buy_msg["payload"]["spaces"][position]["owner_id"] is not None


def test_buy_property_wrong_position(client: TestClient) -> None:
    setup, token = _started_game(client)
    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(token),
    ) as ws:
        ws.receive_json()
        _roll_until_can_buy(ws)
        ws.send_text(envelope("game.buy_property", {"position": 99}))
        err = recv_error(ws)


def test_pass_buy_starts_auction(client: TestClient) -> None:
    setup, token = _started_game(client)
    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(token),
    ) as ws:
        ws.receive_json()
        _roll_until_can_buy(ws)
        ws.send_text(envelope("game.pass_buy"))
        msg = recv_game_state(ws)
        assert msg["payload"]["auction"] is not None


def test_pass_buy_without_pending_buy_rejected(client: TestClient) -> None:
    setup, token = _started_game(client)
    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(token),
    ) as ws:
        ws.receive_json()
        recv_game_state(ws)
        ws.send_text(envelope("game.pass_buy"))
        err = recv_error(ws)
        assert err["payload"]["code"] == "illegal_action"


def test_end_turn_intent(client: TestClient) -> None:
    setup, token = _started_game(client)
    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(token),
    ) as ws:
        ws.receive_json()
        ws.send_text(envelope("game.roll_dice"))
        roll_msg = recv_game_state(ws)
        if roll_msg["payload"]["turn"]["actions_available"]["can_end_turn"]:
            ws.send_text(envelope("game.end_turn"))
            end_msg = recv_game_state(ws)
            assert end_msg["seq"] > roll_msg["seq"]


def test_pay_jail_fine_intent(client: TestClient) -> None:
    setup = setup_two_player_game(client)
    start_session(client, setup.session_id, setup.host_token)
    base = load_game_state(client, setup.session_id)
    current = _current_player(base)

    def jailed(state: GameState) -> GameState:
        jailed_player = current.model_copy(
            update={"jail_status": JailStatus(turns_remaining=3)}
        )
        players = list(state.players)
        idx = next(i for i, p in enumerate(players) if p.id == current.id)
        players[idx] = jailed_player
        return state.model_copy(
            update={
                "players": tuple(players),
                "turn": state.turn.model_copy(
                    update={"phase": TurnPhase.JAIL_DECISION, "current_player_id": current.id}
                ),
            }
        )

    state = mutate_game_state(client, setup.session_id, jailed)
    token = _token_for_player(setup, _current_player(state))
    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(token),
    ) as ws:
        ws.receive_json()
        recv_game_state(ws)
        ws.send_text(envelope("game.pay_jail_fine"))
        msg = recv_game_state(ws)
        player = next(p for p in msg["payload"]["players"] if p["id"] == current.id)
        assert player["jail_status"] is None


def test_use_jail_card_intent(client: TestClient) -> None:
    setup = setup_two_player_game(client)
    start_session(client, setup.session_id, setup.host_token)
    base = load_game_state(client, setup.session_id)
    current = _current_player(base)

    def with_card(state: GameState) -> GameState:
        jailed = current.model_copy(
            update={
                "jail_status": JailStatus(turns_remaining=3),
                "get_out_of_jail_cards": 1,
            }
        )
        players = list(state.players)
        idx = next(i for i, p in enumerate(players) if p.id == current.id)
        players[idx] = jailed
        return state.model_copy(
            update={
                "players": tuple(players),
                "turn": state.turn.model_copy(
                    update={"phase": TurnPhase.JAIL_DECISION, "current_player_id": current.id}
                ),
            }
        )

    state = mutate_game_state(client, setup.session_id, with_card)
    token = _token_for_player(setup, _current_player(state))
    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(token),
    ) as ws:
        ws.receive_json()
        recv_game_state(ws)
        ws.send_text(envelope("game.use_jail_card"))
        msg = recv_game_state(ws)
        player = next(p for p in msg["payload"]["players"] if p["id"] == current.id)
        assert player["get_out_of_jail_cards"] == 0


def test_build_house_intent(client: TestClient) -> None:
    setup = setup_two_player_game(client)
    start_session(client, setup.session_id, setup.host_token)
    base = load_game_state(client, setup.session_id)
    current = _current_player(base)

    def seeded(state: GameState) -> GameState:
        s = monopoly_brown(state, current.id)
        return with_phase(s, TurnPhase.POST_ROLL, current_player_id=current.id)

    state = mutate_game_state(client, setup.session_id, seeded)
    token = _token_for_player(setup, current)
    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(token),
    ) as ws:
        ws.receive_json()
        recv_game_state(ws)
        ws.send_text(envelope("game.build_house", {"position": 1}))
        msg = recv_game_state(ws)
        assert msg["payload"]["spaces"][1]["houses"] == 1


def test_build_house_even_build_violation(client: TestClient) -> None:
    setup = setup_two_player_game(client)
    start_session(client, setup.session_id, setup.host_token)
    base = load_game_state(client, setup.session_id)
    current = _current_player(base)

    def seeded(state: GameState) -> GameState:
        s = monopoly_brown(state, current.id)
        spaces = list(s.spaces)
        spaces[1] = spaces[1].model_copy(update={"houses": 1})
        s = s.model_copy(update={"spaces": tuple(spaces)})
        return with_phase(s, TurnPhase.POST_ROLL, current_player_id=current.id)

    mutate_game_state(client, setup.session_id, seeded)
    token = _token_for_player(setup, current)
    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(token),
    ) as ws:
        ws.receive_json()
        recv_game_state(ws)
        ws.send_text(envelope("game.build_house", {"position": 3}))
        err = recv_error(ws)
        assert err["payload"]["code"] == "illegal_action"


def test_sell_house_intent(client: TestClient) -> None:
    setup = setup_two_player_game(client)
    start_session(client, setup.session_id, setup.host_token)
    base = load_game_state(client, setup.session_id)
    current = _current_player(base)

    def seeded(state: GameState) -> GameState:
        s = monopoly_brown(state, current.id)
        spaces = list(s.spaces)
        spaces[1] = spaces[1].model_copy(update={"houses": 2})
        spaces[3] = spaces[3].model_copy(update={"houses": 1})
        s = s.model_copy(update={"spaces": tuple(spaces), "bank_houses": 30})
        return with_phase(s, TurnPhase.POST_ROLL, current_player_id=current.id)

    mutate_game_state(client, setup.session_id, seeded)
    token = _token_for_player(setup, current)
    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(token),
    ) as ws:
        ws.receive_json()
        recv_game_state(ws)
        ws.send_text(envelope("game.sell_house", {"position": 1}))
        msg = recv_game_state(ws)
        assert msg["payload"]["spaces"][1]["houses"] == 1


def test_mortgage_and_unmortgage_intents(client: TestClient) -> None:
    setup = setup_two_player_game(client)
    start_session(client, setup.session_id, setup.host_token)
    base = load_game_state(client, setup.session_id)
    current = _current_player(base)

    def seeded(state: GameState) -> GameState:
        s = monopoly_brown(state, current.id)
        return with_phase(s, TurnPhase.POST_ROLL, current_player_id=current.id)

    mutate_game_state(client, setup.session_id, seeded)
    token = _token_for_player(setup, current)
    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(token),
    ) as ws:
        ws.receive_json()
        recv_game_state(ws)
        ws.send_text(envelope("game.mortgage", {"position": 1}))
        mort_msg = recv_game_state(ws)
        assert mort_msg["payload"]["spaces"][1]["is_mortgaged"] is True

        ws.send_text(envelope("game.unmortgage", {"position": 1}))
        unmort_msg = recv_game_state(ws)
        assert unmort_msg["payload"]["spaces"][1]["is_mortgaged"] is False


def test_propose_and_respond_trade_intents(client: TestClient) -> None:
    setup = setup_two_player_game(client)
    start_session(client, setup.session_id, setup.host_token)
    state = load_game_state(client, setup.session_id)
    proposer = _current_player(state)
    target = next(p for p in state.players if p.id != proposer.id)
    proposer_token = _token_for_player(setup, proposer)
    target_token = _token_for_player(setup, target)

    def seeded(s: GameState) -> GameState:
        return with_phase(s, TurnPhase.POST_ROLL, current_player_id=proposer.id)

    mutate_game_state(client, setup.session_id, seeded)

    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(proposer_token),
    ) as host_ws:
        host_ws.receive_json()
        recv_game_state(host_ws)
        host_ws.send_text(
            envelope(
                "game.propose_trade",
                {
                    "target_id": target.id,
                    "proposer_offer": {"money": 10, "positions": [], "get_out_of_jail_cards": 0},
                    "target_request": {"money": 0, "positions": [], "get_out_of_jail_cards": 0},
                },
            )
        )
        propose_msg = recv_game_state(host_ws)
        trade_id = propose_msg["payload"]["trade"]["id"]

    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(target_token),
    ) as guest_ws:
        guest_ws.receive_json()
        recv_game_state(guest_ws)
        guest_ws.send_text(
            envelope(
                "game.respond_trade",
                {"trade_id": trade_id, "response": "reject"},
            )
        )
        reject_msg = recv_game_state(guest_ws)
        assert reject_msg["payload"]["trade"] is None


def test_place_bid_intent(client: TestClient) -> None:
    setup, token = _started_game(client)
    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(token),
    ) as ws:
        ws.receive_json()
        _roll_until_can_buy(ws)
        ws.send_text(envelope("game.pass_buy"))
        auction_msg = recv_game_state(ws)
        assert auction_msg["payload"]["auction"] is not None

        ws.send_text(envelope("game.place_bid", {"amount": 60}))
        bid_msg = recv_game_state(ws)
        assert bid_msg["payload"]["auction"]["highest_bid"] == 60


def test_place_bid_too_low_rejected(client: TestClient) -> None:
    setup, token = _started_game(client)
    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(token),
    ) as ws:
        ws.receive_json()
        _roll_until_can_buy(ws)
        ws.send_text(envelope("game.pass_buy"))
        recv_game_state(ws)
        ws.send_text(envelope("game.place_bid", {"amount": 60}))
        recv_game_state(ws)
        ws.send_text(envelope("game.place_bid", {"amount": 50}))
        err = recv_error(ws)
        assert err["payload"]["code"] == "illegal_action"


def test_declare_bankruptcy_intent(client: TestClient) -> None:
    setup = setup_two_player_game(client)
    start_session(client, setup.session_id, setup.host_token)
    state = load_game_state(client, setup.session_id)
    debtor = _current_player(state)

    def bankrupt(s: GameState) -> GameState:
        return s.model_copy(
            update={
                "bankruptcy": BankruptcyState(
                    debtor_id=debtor.id, creditor_id=None, amount_owed=100
                ),
                "turn": s.turn.model_copy(
                    update={
                        "phase": TurnPhase.BANKRUPT_RESOLUTION,
                        "current_player_id": debtor.id,
                    }
                ),
            }
        )

    mutate_game_state(client, setup.session_id, bankrupt)
    token = _token_for_player(setup, debtor)
    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(token),
    ) as ws:
        ws.receive_json()
        recv_game_state(ws)
        ws.send_text(envelope("game.declare_bankruptcy"))
        msg = recv_game_state(ws)
        player = next(p for p in msg["payload"]["players"] if p["id"] == debtor.id)
        assert player["is_bankrupt"] is True


def test_malformed_position_rejected(client: TestClient) -> None:
    setup, token = _started_game(client)
    with client.websocket_connect(
        f"/ws/sessions/{setup.session_id}",
        headers=ws_headers(token),
    ) as ws:
        ws.receive_json()
        recv_game_state(ws)
        ws.send_text(envelope("game.build_house", {"position": 99}))
        err = recv_error(ws)
        assert err["payload"]["code"] == "malformed"
