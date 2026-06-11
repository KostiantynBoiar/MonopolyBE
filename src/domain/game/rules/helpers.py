from __future__ import annotations

from domain.game.constants import HOTEL_HOUSE_COUNT
from domain.game.board_data import get_board_space
from domain.game.enums import GameMode
from domain.game.modes import get_game_config
from domain.game.schemas.state import GameState, PlayerState, SpaceOwnership


def space_index(spaces: tuple[SpaceOwnership, ...] | list[SpaceOwnership], position: int) -> int:
    for index, ownership in enumerate(spaces):
        if ownership.position == position:
            return index
    raise KeyError(position)


def space_at(
    spaces: tuple[SpaceOwnership, ...] | list[SpaceOwnership], position: int
) -> SpaceOwnership:
    return spaces[space_index(spaces, position)]


def replace_space(
    spaces: list[SpaceOwnership],
    position: int,
    ownership: SpaceOwnership,
) -> None:
    spaces[space_index(spaces, position)] = ownership


def compute_net_worth(
    player: PlayerState,
    spaces: tuple[SpaceOwnership, ...],
    game_mode: GameMode = GameMode.NORMAL,
) -> int:
    total = player.balance
    for pos in player.owned_positions:
        space = get_board_space(pos, game_mode)
        ownership = space_at(spaces, pos)
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
    game_mode: GameMode = GameMode.NORMAL,
) -> PlayerState:
    return player.model_copy(update={"net_worth": compute_net_worth(player, spaces, game_mode)})


def refresh_all_net_worth(
    state: GameState,
) -> tuple[PlayerState, ...]:
    return tuple(update_player_net_worth(p, state.spaces, state.game_mode) for p in state.players)


def positions_in_color_group(
    color_group: str, game_mode: GameMode = GameMode.NORMAL
) -> tuple[int, ...]:
    return tuple(
        space.position
        for space in get_game_config(game_mode).board
        if space.color_group is not None and space.color_group.value == color_group
    )


def player_owns_full_color_group(
    player: PlayerState,
    color_group: str,
    spaces: tuple[SpaceOwnership, ...],
    game_mode: GameMode = GameMode.NORMAL,
) -> bool:
    """True if player owns all properties in a color group with no buildings."""
    group_positions = positions_in_color_group(color_group, game_mode)
    if not group_positions:
        return False
    for pos in group_positions:
        ownership = space_at(spaces, pos)
        if ownership.owner_id != player.id:
            return False
        if ownership.houses > 0 or ownership.has_hotel:
            return False
    return True


def player_has_rent_monopoly(
    player: PlayerState,
    color_group: str,
    spaces: tuple[SpaceOwnership, ...],
    game_mode: GameMode = GameMode.NORMAL,
) -> bool:
    """True if player owns all unmortgaged properties in a color group."""
    group_positions = positions_in_color_group(color_group, game_mode)
    if not group_positions:
        return False
    for pos in group_positions:
        ownership = space_at(spaces, pos)
        if ownership.owner_id != player.id or ownership.is_mortgaged:
            return False
    return True


def count_owned_railroads(
    player: PlayerState,
    spaces: tuple[SpaceOwnership, ...],
    game_mode: GameMode = GameMode.NORMAL,
) -> int:
    return sum(
        1
        for pos in get_game_config(game_mode).railroad_positions
        if space_at(spaces, pos).owner_id == player.id and not space_at(spaces, pos).is_mortgaged
    )


def count_owned_utilities(
    player: PlayerState,
    spaces: tuple[SpaceOwnership, ...],
    game_mode: GameMode = GameMode.NORMAL,
) -> int:
    return sum(
        1
        for pos in get_game_config(game_mode).utility_positions
        if space_at(spaces, pos).owner_id == player.id and not space_at(spaces, pos).is_mortgaged
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
