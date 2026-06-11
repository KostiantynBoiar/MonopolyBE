from __future__ import annotations

import pytest

from domain.game.enums import GameStatus, TurnPhase
from domain.game.exceptions import IllegalMove
from domain.game.rng import FixedClock
from domain.game.rules.bankruptcy import check_win_condition
from domain.game.rules.helpers import space_at
from domain.game.rules.payments import try_settle_debt
from domain.game.schemas.commands import DeclareBankruptcy, EndTurn, Mortgage, RollDice
from domain.game.schemas.state import BankruptcyState, GameState
from tests.domain.game.conftest import (
    apply_cmd,
    monopoly_brown,
    owned_by_p2,
    with_ownership,
    with_phase,
)


def test_rent_exceeds_balance_enters_bankruptcy(
    two_player_game: GameState, clock: FixedClock
) -> None:
    p1 = two_player_game.players[0]
    state = owned_by_p2(two_player_game, 2)
    broke = p1.model_copy(update={"balance": 1})
    players = (broke, state.players[1])
    state = state.model_copy(update={"players": players})
    state = with_phase(state, TurnPhase.PRE_ROLL, current_player_id=p1.id)

    new_state, _ = apply_cmd(state, RollDice(player_id=p1.id), clock, rng_values=[1, 0])
    assert new_state.bankruptcy is not None
    assert new_state.turn.phase == TurnPhase.BANKRUPT_RESOLUTION


def test_settle_debt_after_mortgage(two_player_game: GameState, clock: FixedClock) -> None:
    p1 = two_player_game.players[0]
    state = monopoly_brown(two_player_game, p1.id)
    bankruptcy = BankruptcyState(debtor_id=p1.id, creditor_id=None, amount_owed=100)
    state = state.model_copy(
        update={
            "bankruptcy": bankruptcy,
            "turn": state.turn.model_copy(update={"phase": TurnPhase.BANKRUPT_RESOLUTION}),
        }
    )

    mortgaged, _ = apply_cmd(state, Mortgage(player_id=p1.id, position=2), clock)
    settled = try_settle_debt(mortgaged)
    assert settled.bankruptcy is None
    assert settled.turn.phase == TurnPhase.POST_ROLL


def test_bankruptcy_to_player_transfers_assets(
    two_player_game: GameState, clock: FixedClock
) -> None:
    p1, p2 = two_player_game.players
    # with_ownership updates the state's players so p1 has owned_positions=(2,).
    state = with_ownership(two_player_game, 2, p1.id, is_mortgaged=True)
    # Fetch the updated p1 from the state (it now has owned_positions=(2,)).
    p1_updated = state.players[0]
    p1_broke = p1_updated.model_copy(update={"balance": 10, "get_out_of_jail_cards": 1})
    players = (p1_broke, p2)
    bankruptcy = BankruptcyState(debtor_id=p1.id, creditor_id=p2.id, amount_owed=500)
    state = state.model_copy(
        update={
            "players": players,
            "bankruptcy": bankruptcy,
            "turn": state.turn.model_copy(update={"phase": TurnPhase.BANKRUPT_RESOLUTION}),
        }
    )

    resolved, _ = apply_cmd(state, DeclareBankruptcy(player_id=p1.id), clock)
    assert resolved.players[0].is_bankrupt
    assert 2 in resolved.players[1].owned_positions
    assert resolved.players[1].get_out_of_jail_cards == 1


def test_bankruptcy_to_bank_clears_properties(
    two_player_game: GameState, clock: FixedClock
) -> None:
    state = with_ownership(two_player_game, 2, two_player_game.players[0].id)
    # Fetch the updated p1 from the state (it now has owned_positions=(2,)).
    p1_updated = state.players[0]
    p1_broke = p1_updated.model_copy(update={"balance": 0, "get_out_of_jail_cards": 1})
    players = (p1_broke, state.players[1])
    bankruptcy = BankruptcyState(debtor_id=p1_updated.id, creditor_id=None, amount_owed=100)
    state = state.model_copy(
        update={
            "players": players,
            "bankruptcy": bankruptcy,
            "turn": state.turn.model_copy(update={"phase": TurnPhase.BANKRUPT_RESOLUTION}),
        }
    )
    chest_before = len(state.chest_deck)

    resolved, _ = apply_cmd(state, DeclareBankruptcy(player_id=p1_updated.id), clock)
    assert resolved.players[0].is_bankrupt
    assert space_at(resolved.spaces, 2).owner_id is None
    assert len(resolved.chest_deck) >= chest_before


def test_win_condition_single_survivor(two_player_game: GameState) -> None:
    p1, p2 = two_player_game.players
    bankrupt_p2 = p2.model_copy(update={"is_bankrupt": True})
    state = two_player_game.model_copy(update={"players": (p1, bankrupt_p2)})

    finished = check_win_condition(state)
    assert finished.status == GameStatus.FINISHED
    assert finished.winner_id == p1.id
    assert finished.turn.phase == TurnPhase.GAME_OVER


def test_end_turn_during_bankruptcy_rejected(two_player_game: GameState, clock: FixedClock) -> None:
    p1 = two_player_game.players[0]
    bankruptcy = BankruptcyState(debtor_id=p1.id, creditor_id=None, amount_owed=100)
    state = two_player_game.model_copy(
        update={
            "bankruptcy": bankruptcy,
            "turn": two_player_game.turn.model_copy(
                update={"phase": TurnPhase.BANKRUPT_RESOLUTION, "current_player_id": p1.id}
            ),
        }
    )

    with pytest.raises(IllegalMove, match="bankruptcy"):
        apply_cmd(state, EndTurn(player_id=p1.id), clock)
