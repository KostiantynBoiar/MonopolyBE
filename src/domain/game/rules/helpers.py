from __future__ import annotations

from domain.game.constants import (
    HOTEL_HOUSE_COUNT,
    RAILROAD_POSITIONS,
    UTILITY_POSITIONS,
)
from domain.game.board_data import BOARD, get_board_space
from domain.game.schemas.state import GameState, PlayerState, SpaceOwnership


def compute_net_worth(player: PlayerState, spaces: tuple[SpaceOwnership, ...]) -> int:
    total = player.balance
    for pos in player.owned_positions:
        space = get_board_space(pos)
        ownership = spaces[pos]
        if ownership.is_mortgaged:
            continue
        if space.price is not None:
            total += space.price
        if ownership.has_hotel:
            total += (space.house_cost or 0) * HOTEL_HOUSE_COUNT
        else:
            total += (space.house_cost or 0) * ownership.houses
    return total


def update_player_net_worth(
    player: PlayerState,
    spaces: tuple[SpaceOwnership, ...],
) -> PlayerState:
    return player.model_copy(update={"net_worth": compute_net_worth(player, spaces)})


def refresh_all_net_worth(
    state: GameState,
) -> tuple[PlayerState, ...]:
    return tuple(update_player_net_worth(p, state.spaces) for p in state.players)


def positions_in_color_group(color_group: str) -> tuple[int, ...]:
    return tuple(
        space.position
        for space in BOARD
        if space.color_group is not None and space.color_group.value == color_group
    )


def player_owns_full_color_group(
    player: PlayerState,
    color_group: str,
    spaces: tuple[SpaceOwnership, ...],
) -> bool:
    """True if player owns all properties in a color group with no buildings."""
    group_positions = positions_in_color_group(color_group)
    if not group_positions:
        return False
    for pos in group_positions:
        ownership = spaces[pos]
        if ownership.owner_id != player.id:
            return False
        if ownership.houses > 0 or ownership.has_hotel:
            return False
    return True


def player_has_rent_monopoly(
    player: PlayerState,
    color_group: str,
    spaces: tuple[SpaceOwnership, ...],
) -> bool:
    """True if player owns all unmortgaged properties in a color group."""
    group_positions = positions_in_color_group(color_group)
    if not group_positions:
        return False
    for pos in group_positions:
        ownership = spaces[pos]
        if ownership.owner_id != player.id or ownership.is_mortgaged:
            return False
    return True


def count_owned_railroads(player: PlayerState, spaces: tuple[SpaceOwnership, ...]) -> int:
    return sum(
        1
        for pos in RAILROAD_POSITIONS
        if spaces[pos].owner_id == player.id and not spaces[pos].is_mortgaged
    )


def count_owned_utilities(player: PlayerState, spaces: tuple[SpaceOwnership, ...]) -> int:
    return sum(
        1
        for pos in UTILITY_POSITIONS
        if spaces[pos].owner_id == player.id and not spaces[pos].is_mortgaged
    )


def get_player_by_id(players: tuple[PlayerState, ...], player_id: str) -> PlayerState:
    for player in players:
        if player.id == player_id:
            return player
    raise KeyError(player_id)


def get_player_by_id_from_state(state: GameState, player_id: str) -> PlayerState:
    return get_player_by_id(state.players, player_id)


def get_player_name(state: GameState, player_id: str) -> str:
    return get_player_by_id_from_state(state, player_id).display_name
