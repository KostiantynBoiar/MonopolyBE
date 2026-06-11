from __future__ import annotations

from domain.game.constants import (
    MAX_RAILROADS_OWNED,
    MONOPOLY_RENT_MULTIPLIER,
    RAILROAD_RENTS,
    UTILITY_RENT_MULTIPLIER_ONE,
    UTILITY_RENT_MULTIPLIER_TWO,
)
from domain.game.board_data import get_board_space
from domain.game.enums import SpaceType
from domain.game.schemas.state import GameState
from domain.game.rules.helpers import (
    count_owned_railroads,
    count_owned_utilities,
    get_player_by_id,
    player_has_rent_monopoly,
    space_at,
)


def calculate_rent(
    *,
    state: GameState,
    position: int,
    dice_total: int,
    rent_multiplier: int = 1,
) -> int:
    ownership = space_at(state.spaces, position)
    if ownership.owner_id is None or ownership.is_mortgaged:
        return 0

    owner = get_player_by_id(state.players, ownership.owner_id)
    board_space = get_board_space(position, state.game_mode)

    if board_space.type == SpaceType.RAILROAD:
        count = count_owned_railroads(owner, state.spaces, state.game_mode)
        base = RAILROAD_RENTS[min(count, MAX_RAILROADS_OWNED) - 1]
        return base * rent_multiplier

    if board_space.type == SpaceType.UTILITY:
        count = count_owned_utilities(owner, state.spaces, state.game_mode)
        multiplier = UTILITY_RENT_MULTIPLIER_ONE if count == 1 else UTILITY_RENT_MULTIPLIER_TWO
        return multiplier * dice_total

    if board_space.type == SpaceType.PROPERTY and board_space.rent is not None:
        amount = board_space.rent.amount_for(ownership.houses, ownership.has_hotel)
        if (
            ownership.houses == 0
            and not ownership.has_hotel
            and board_space.color_group is not None
            and player_has_rent_monopoly(
                owner,
                board_space.color_group.value,
                state.spaces,
                state.game_mode,
            )
        ):
            return amount * MONOPOLY_RENT_MULTIPLIER
        return amount * rent_multiplier

    return 0
