from __future__ import annotations

import pytest

from domain.game.enums import TurnPhase
from domain.game.exceptions import IllegalMove
from domain.game.rng import FixedClock
from domain.game.rules.helpers import space_at
from domain.game.schemas.commands import (
    BuyProperty,
    EndTurn,
    PassBuy,
    PayJailFine,
    RollDice,
)
from domain.game.schemas.state import GameState, JailStatus
from tests.domain.game.conftest import apply_cmd, owned_by_p2


def test_new_game_initial_state(two_player_game: GameState) -> None:
    state = two_player_game
    assert len(state.players) == 2
    assert len(state.spaces) == 40
    assert state.turn.phase == TurnPhase.PRE_ROLL
    assert len(state.chance_deck) == 16
    assert len(state.chest_deck) == 16
    assert state.bank_houses == 32
    assert state.bank_hotels == 12


def test_roll_moves_player(two_player_game: GameState, clock: FixedClock) -> None:
    # Roll [2,4]=6 -> pos 7 (Oriental Ave, a plain unowned property).
    player = two_player_game.players[0]
    new_state, _ = apply_cmd(
        two_player_game,
        RollDice(player_id=player.id),
        clock,
        rng_values=[2, 4],
    )
    assert new_state.players[0].position == 7
    assert new_state.turn.phase == TurnPhase.POST_ROLL


def test_passing_go_adds_salary(two_player_game: GameState, clock: FixedClock) -> None:
    player = two_player_game.players[0]
    players = list(two_player_game.players)
    players[0] = player.model_copy(update={"position": 36})
    state = two_player_game.model_copy(update={"players": tuple(players)})

    new_state, events = apply_cmd(
        state,
        RollDice(player_id=player.id),
        clock,
        rng_values=[3, 2],
    )
    assert new_state.players[0].position == 1
    assert new_state.players[0].balance == 1700
    assert any(e.__class__.__name__ == "PassedGo" for e in events)


def test_rent_payment(two_player_game: GameState, clock: FixedClock) -> None:
    # p2 owns Oriental Ave; from start pos 1, roll [2,4]=6 -> pos 7.
    state = owned_by_p2(two_player_game, 7)
    p1 = state.players[0]
    new_state, events = apply_cmd(
        state,
        RollDice(player_id=p1.id),
        clock,
        rng_values=[2, 4],
    )
    # Oriental Ave base rent = 6 (no monopoly)
    assert new_state.players[0].balance == 1494
    assert new_state.players[1].balance == 1506
    assert any(e.__class__.__name__ == "RentPaid" for e in events)
    assert new_state.turn.phase == TurnPhase.MUST_PAY_RENT


def test_buy_property(two_player_game: GameState, clock: FixedClock) -> None:
    player = two_player_game.players[0]
    turn = two_player_game.turn.model_copy(
        update={"phase": TurnPhase.POST_ROLL, "pending_buy_position": 2}
    )
    state = two_player_game.model_copy(update={"turn": turn})

    new_state, events = apply_cmd(
        state,
        BuyProperty(player_id=player.id, position=2),
        clock,
    )
    assert space_at(new_state.spaces, 2).owner_id == player.id
    assert new_state.players[0].balance == 1440
    assert any(e.__class__.__name__ == "PropertyBought" for e in events)


def test_pass_buy_starts_auction(two_player_game: GameState, clock: FixedClock) -> None:
    player = two_player_game.players[0]
    turn = two_player_game.turn.model_copy(
        update={"phase": TurnPhase.POST_ROLL, "pending_buy_position": 2}
    )
    state = two_player_game.model_copy(update={"turn": turn})

    new_state, events = apply_cmd(state, PassBuy(player_id=player.id), clock)
    assert new_state.auction is not None
    assert new_state.auction.property_position == 2
    assert new_state.turn.phase == TurnPhase.AUCTION
    assert any(e.__class__.__name__ == "BuyDeclined" for e in events)


def test_end_turn_routes_jailed_player_to_jail_decision(
    two_player_game: GameState, clock: FixedClock
) -> None:
    p1, p2 = two_player_game.players
    jailed_p2 = p2.model_copy(update={"jail_status": JailStatus(turns_remaining=3)})
    players = (p1, jailed_p2)
    turn = two_player_game.turn.model_copy(
        update={"phase": TurnPhase.POST_ROLL, "current_player_id": p1.id}
    )
    state = two_player_game.model_copy(update={"players": players, "turn": turn})

    new_state, _ = apply_cmd(state, EndTurn(player_id=p1.id), clock)
    assert new_state.turn.current_player_id == p2.id
    assert new_state.turn.phase == TurnPhase.JAIL_DECISION


def test_pay_jail_fine(two_player_game: GameState, clock: FixedClock) -> None:
    player = two_player_game.players[0]
    jailed = player.model_copy(update={"jail_status": JailStatus(turns_remaining=3)})
    players = (jailed, two_player_game.players[1])
    turn = two_player_game.turn.model_copy(
        update={"phase": TurnPhase.JAIL_DECISION, "current_player_id": player.id}
    )
    state = two_player_game.model_copy(update={"players": players, "turn": turn})

    new_state, _ = apply_cmd(state, PayJailFine(player_id=player.id), clock)
    assert new_state.players[0].jail_status is None
    assert new_state.players[0].balance == 1450
    assert new_state.turn.phase == TurnPhase.PRE_ROLL


def test_third_doubles_sends_to_jail(two_player_game: GameState, clock: FixedClock) -> None:
    player = two_player_game.players[0]
    turn = two_player_game.turn.model_copy(update={"doubles_streak": 2})
    state = two_player_game.model_copy(update={"turn": turn})

    new_state, events = apply_cmd(
        state,
        RollDice(player_id=player.id),
        clock,
        rng_values=[3, 3],
    )
    assert new_state.players[0].position == 11
    assert new_state.players[0].jail_status is not None
    assert new_state.turn.phase == TurnPhase.POST_ROLL
    assert new_state.turn.doubles_streak == 0
    assert any(e.__class__.__name__ == "SentToJail" for e in events)


def test_third_doubles_no_extra_roll(two_player_game: GameState, clock: FixedClock) -> None:
    player = two_player_game.players[0]
    turn = two_player_game.turn.model_copy(update={"doubles_streak": 2})
    state = two_player_game.model_copy(update={"turn": turn})

    new_state, _ = apply_cmd(
        state,
        RollDice(player_id=player.id),
        clock,
        rng_values=[3, 3],
    )
    assert new_state.turn.phase != TurnPhase.PRE_ROLL


def test_first_doubles_grants_extra_roll(two_player_game: GameState, clock: FixedClock) -> None:
    player = two_player_game.players[0]
    new_state, events = apply_cmd(
        two_player_game,
        RollDice(player_id=player.id),
        clock,
        rng_values=[2, 2],
    )
    assert new_state.turn.phase == TurnPhase.PRE_ROLL
    assert new_state.turn.doubles_streak == 1
    assert any(e.__class__.__name__ == "RolledDoubles" for e in events)


def test_illegal_move_wrong_player(two_player_game: GameState, clock: FixedClock) -> None:
    wrong_player = two_player_game.players[1]
    with pytest.raises(IllegalMove, match="not your turn"):
        apply_cmd(two_player_game, RollDice(player_id=wrong_player.id), clock)
