from __future__ import annotations

from domain.game.board_data import get_board_space
from domain.game.constants import INCOME_TAX_AMOUNT, LUXURY_TAX_AMOUNT
from domain.game.enums import TurnPhase
from domain.game.rng import FixedClock
from domain.game.rules.rent import calculate_rent
from domain.game.schemas.commands import RollDice
from domain.game.schemas.state import GameState
from tests.domain.game.conftest import (
    apply_cmd,
    owned_by_p2,
    with_monopoly,
    with_ownership,
    with_phase,
    with_player_at,
)


def test_monopoly_double_rent(two_player_game: GameState) -> None:
    p2 = two_player_game.players[1]
    state = with_monopoly(two_player_game, p2.id, (2, 4))
    rent = calculate_rent(
        state=state,
        position=2,
        dice_total=7,
    )
    assert rent == 4


def test_mortgaged_property_no_rent(two_player_game: GameState) -> None:
    p2 = two_player_game.players[1]
    state = with_ownership(two_player_game, 2, p2.id, is_mortgaged=True)
    rent = calculate_rent(
        state=state,
        position=2,
        dice_total=7,
    )
    assert rent == 0


def test_railroad_rent_tiers(two_player_game: GameState) -> None:
    p2 = two_player_game.players[1]
    for count, expected in enumerate([25, 50, 100, 200], start=1):
        state = two_player_game
        for pos in (6, 16, 26, 36)[:count]:
            state = with_ownership(state, pos, p2.id)
        rent = calculate_rent(
            state=state,
            position=6,
            dice_total=7,
        )
        assert rent == expected


def test_utility_rent_multipliers(two_player_game: GameState) -> None:
    p2 = two_player_game.players[1]
    state = with_ownership(two_player_game, 13, p2.id)
    rent_one = calculate_rent(
        state=state,
        position=13,
        dice_total=7,
    )
    assert rent_one == 28

    state = with_ownership(state, 29, p2.id)
    rent_two = calculate_rent(
        state=state,
        position=13,
        dice_total=7,
    )
    assert rent_two == 70


def test_house_rent_tiers(two_player_game: GameState) -> None:
    p2 = two_player_game.players[1]
    state = with_ownership(two_player_game, 2, p2.id, houses=3)
    rent = calculate_rent(
        state=state,
        position=2,
        dice_total=7,
    )
    board = get_board_space(2)
    assert board.rent is not None
    assert rent == board.rent.three_houses


def test_income_tax(two_player_game: GameState, clock: FixedClock) -> None:
    # Start at pos 3, roll [1,1]=2 -> pos 5 (Income Tax).
    p1 = two_player_game.players[0]
    state = with_player_at(two_player_game, 0, 3)
    state = with_phase(state, TurnPhase.PRE_ROLL, current_player_id=p1.id)

    new_state, events = apply_cmd(state, RollDice(player_id=p1.id), clock, rng_values=[1, 1])
    assert new_state.players[0].balance == 1500 - INCOME_TAX_AMOUNT
    assert any(e.__class__.__name__ == "TaxPaid" for e in events)


def test_luxury_tax(two_player_game: GameState, clock: FixedClock) -> None:
    # Luxury Tax is pos 39. Start at pos 37 (Chance), roll [1,1]=2 -> pos 39.
    p1 = two_player_game.players[0]
    state = with_player_at(two_player_game, 0, 37)
    state = with_phase(state, TurnPhase.PRE_ROLL, current_player_id=p1.id)

    new_state, _ = apply_cmd(state, RollDice(player_id=p1.id), clock, rng_values=[1, 1])
    assert new_state.players[0].balance == 1500 - LUXURY_TAX_AMOUNT


def test_free_parking_no_change(two_player_game: GameState, clock: FixedClock) -> None:
    p1 = two_player_game.players[0]
    state = with_player_at(two_player_game, 0, 19)
    state = with_phase(state, TurnPhase.PRE_ROLL, current_player_id=p1.id)

    new_state, _ = apply_cmd(state, RollDice(player_id=p1.id), clock, rng_values=[1, 1])
    assert new_state.players[0].balance == 1500
    assert new_state.players[0].position == 21


def test_rent_on_landing(two_player_game: GameState, clock: FixedClock) -> None:
    # Use p2 owning pos 7 so landing triggers rent after roll [2,4] from start.
    # Oriental Ave base rent = 6.
    state = owned_by_p2(two_player_game, 7)
    p1 = state.players[0]
    state = with_phase(state, TurnPhase.PRE_ROLL, current_player_id=p1.id)

    new_state, _ = apply_cmd(state, RollDice(player_id=p1.id), clock, rng_values=[2, 4])
    assert new_state.players[0].balance == 1494
    assert new_state.turn.phase == TurnPhase.MUST_PAY_RENT
