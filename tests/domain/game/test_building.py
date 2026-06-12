from __future__ import annotations

import pytest

from domain.game.exceptions import IllegalMove
from domain.game.rng import FixedClock
from domain.game.rules.helpers import replace_space, space_at
from domain.game.schemas.commands import BuildHouse, Mortgage, SellHouse, Unmortgage
from domain.game.schemas.state import GameState
from tests.domain.game.conftest import apply_cmd, monopoly_brown


def test_even_build(two_player_game: GameState, clock: FixedClock) -> None:
    state = monopoly_brown(two_player_game)
    p1 = state.players[0]

    # Build on pos 2 (Mediterranean, 0->1). pos 4 (Baltic) still at 0; gap = 1.
    s1, _ = apply_cmd(state, BuildHouse(player_id=p1.id, position=2), clock)
    assert space_at(s1.spaces, 2).houses == 1
    assert s1.bank_houses == 31

    # Build on pos 2 again while pos 4 is still at 0; gap would be 2.
    with pytest.raises(IllegalMove):
        apply_cmd(s1, BuildHouse(player_id=p1.id, position=2), clock)


def test_hotel_conversion(two_player_game: GameState, clock: FixedClock) -> None:
    # Both properties in the brown group must have 4 houses before a hotel can be built.
    state = monopoly_brown(two_player_game)
    p1 = state.players[0]
    spaces = list(state.spaces)
    replace_space(spaces, 2, space_at(spaces, 2).model_copy(update={"houses": 4}))
    replace_space(spaces, 4, space_at(spaces, 4).model_copy(update={"houses": 4}))
    state = state.model_copy(update={"spaces": tuple(spaces), "bank_houses": 24})

    new_state, _ = apply_cmd(state, BuildHouse(player_id=p1.id, position=2), clock)
    assert space_at(new_state.spaces, 2).has_hotel
    assert space_at(new_state.spaces, 2).houses == 0
    assert new_state.bank_hotels == 11
    assert new_state.bank_houses == 28  # 24 + 4 returned from pos 2


def test_sell_house_even_sell(two_player_game: GameState, clock: FixedClock) -> None:
    state = monopoly_brown(two_player_game)
    p1 = state.players[0]
    spaces = list(state.spaces)
    replace_space(spaces, 2, space_at(spaces, 2).model_copy(update={"houses": 2}))
    replace_space(spaces, 4, space_at(spaces, 4).model_copy(update={"houses": 1}))
    state = state.model_copy(update={"spaces": tuple(spaces), "bank_houses": 30})
    balance_before = state.players[0].balance

    new_state, _ = apply_cmd(state, SellHouse(player_id=p1.id, position=2), clock)
    assert space_at(new_state.spaces, 2).houses == 1
    assert new_state.players[0].balance == balance_before + 25
    assert new_state.bank_houses == 31


def test_build_blocked_no_bank_houses(two_player_game: GameState, clock: FixedClock) -> None:
    state = monopoly_brown(two_player_game)
    p1 = state.players[0]
    state = state.model_copy(update={"bank_houses": 0})

    with pytest.raises(IllegalMove):
        apply_cmd(state, BuildHouse(player_id=p1.id, position=2), clock)


def test_build_blocked_group_mate_mortgaged(two_player_game: GameState, clock: FixedClock) -> None:
    state = monopoly_brown(two_player_game)
    p1 = state.players[0]
    spaces = list(state.spaces)
    replace_space(spaces, 4, space_at(spaces, 4).model_copy(update={"is_mortgaged": True}))
    state = state.model_copy(update={"spaces": tuple(spaces)})

    with pytest.raises(IllegalMove):
        apply_cmd(state, BuildHouse(player_id=p1.id, position=2), clock)


def test_mortgage_blocked_with_buildings(two_player_game: GameState, clock: FixedClock) -> None:
    state = monopoly_brown(two_player_game)
    p1 = state.players[0]
    spaces = list(state.spaces)
    replace_space(spaces, 2, space_at(spaces, 2).model_copy(update={"houses": 1}))
    state = state.model_copy(update={"spaces": tuple(spaces)})

    with pytest.raises(IllegalMove):
        apply_cmd(state, Mortgage(player_id=p1.id, position=4), clock)


def test_unmortgage_interest(two_player_game: GameState, clock: FixedClock) -> None:
    # Mediterranean Ave: price=60, mortgage_value=30. After mortgage: 2000+30=2030.
    # Unmortgage cost = ceil(30 * 1.10) = ceil(33.0) = 33. Final balance = 2030-33 = 1997.
    state = monopoly_brown(two_player_game)
    p1 = state.players[0]

    mortgaged, _ = apply_cmd(state, Mortgage(player_id=p1.id, position=2), clock)
    assert mortgaged.players[0].balance == 2030

    final, _ = apply_cmd(mortgaged, Unmortgage(player_id=p1.id, position=2), clock)
    assert not space_at(final.spaces, 2).is_mortgaged
    assert final.players[0].balance == 1997


def test_mortgage_and_unmortgage(two_player_game: GameState, clock: FixedClock) -> None:
    state = monopoly_brown(two_player_game)
    p1 = state.players[0]

    mortgaged, _ = apply_cmd(state, Mortgage(player_id=p1.id, position=2), clock)
    assert space_at(mortgaged.spaces, 2).is_mortgaged

    mortgaged2, _ = apply_cmd(mortgaged, Mortgage(player_id=p1.id, position=4), clock)
    final, _ = apply_cmd(mortgaged2, Unmortgage(player_id=p1.id, position=2), clock)
    assert not space_at(final.spaces, 2).is_mortgaged
