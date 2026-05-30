from __future__ import annotations

import pytest

from domain.game.enums import TurnPhase
from domain.game.exceptions import IllegalMove
from domain.game.rng import FixedClock
from domain.game.schemas.commands import PayJailFine, RollDice, UseJailCard
from domain.game.schemas.state import GameState, JailStatus
from tests.domain.game.conftest import (
    apply_cmd,
    with_jailed,
    with_phase,
)


def test_doubles_in_jail_leaves_and_moves(two_player_game: GameState, clock: FixedClock) -> None:
    p1 = two_player_game.players[0]
    state = with_jailed(two_player_game, p1.id, turns_remaining=3)
    state = with_phase(state, TurnPhase.JAIL_DECISION, current_player_id=p1.id)

    new_state, _ = apply_cmd(state, RollDice(player_id=p1.id), clock, rng_values=[3, 3])
    assert new_state.players[0].jail_status is None
    assert new_state.players[0].position != 10
    assert new_state.turn.phase == TurnPhase.POST_ROLL


def test_non_doubles_decrements_turns(two_player_game: GameState, clock: FixedClock) -> None:
    p1 = two_player_game.players[0]
    state = with_jailed(two_player_game, p1.id, turns_remaining=3)
    state = with_phase(state, TurnPhase.JAIL_DECISION, current_player_id=p1.id)

    new_state, _ = apply_cmd(state, RollDice(player_id=p1.id), clock, rng_values=[2, 3])
    assert new_state.players[0].jail_status is not None
    assert new_state.players[0].jail_status.turns_remaining == 2
    assert new_state.turn.phase == TurnPhase.POST_ROLL


def test_third_failed_roll_auto_pays_and_moves(two_player_game: GameState, clock: FixedClock) -> None:
    p1 = two_player_game.players[0]
    state = with_jailed(two_player_game, p1.id, turns_remaining=1)
    state = with_phase(state, TurnPhase.JAIL_DECISION, current_player_id=p1.id)

    new_state, _ = apply_cmd(state, RollDice(player_id=p1.id), clock, rng_values=[2, 3])
    assert new_state.players[0].jail_status is None
    assert new_state.players[0].balance == 1450
    assert new_state.players[0].position != 10


def test_use_jail_card(two_player_game: GameState, clock: FixedClock) -> None:
    p1 = two_player_game.players[0]
    jailed = p1.model_copy(
        update={"jail_status": JailStatus(turns_remaining=3), "get_out_of_jail_cards": 1}
    )
    players = (jailed, two_player_game.players[1])
    state = two_player_game.model_copy(update={"players": players})
    state = with_phase(state, TurnPhase.JAIL_DECISION, current_player_id=p1.id)

    new_state, _ = apply_cmd(state, UseJailCard(player_id=p1.id), clock)
    assert new_state.players[0].jail_status is None
    assert new_state.players[0].get_out_of_jail_cards == 0
    assert new_state.turn.phase == TurnPhase.PRE_ROLL


def test_cannot_roll_pre_roll_while_jailed(two_player_game: GameState, clock: FixedClock) -> None:
    p1 = two_player_game.players[0]
    state = with_jailed(two_player_game, p1.id)
    state = with_phase(state, TurnPhase.PRE_ROLL, current_player_id=p1.id)

    with pytest.raises(IllegalMove, match="must resolve jail"):
        apply_cmd(state, RollDice(player_id=p1.id), clock, rng_values=[1, 1])


def test_pay_jail_fine_insufficient_funds(two_player_game: GameState, clock: FixedClock) -> None:
    p1 = two_player_game.players[0]
    broke = p1.model_copy(update={"jail_status": JailStatus(turns_remaining=3), "balance": 30})
    players = (broke, two_player_game.players[1])
    state = two_player_game.model_copy(update={"players": players})
    state = with_phase(state, TurnPhase.JAIL_DECISION, current_player_id=p1.id)

    with pytest.raises(IllegalMove, match="insufficient"):
        apply_cmd(state, PayJailFine(player_id=p1.id), clock)
