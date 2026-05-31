from __future__ import annotations

import math

from domain.game.board_data import get_board_space, is_purchasable
from domain.game.constants import BANK_HOTELS, BANK_HOUSES, HOUSE_SELL_RATIO, MORTGAGE_INTEREST
from domain.game.enums import SpaceType
from domain.game.exceptions import IllegalMove
from domain.game.schemas.state import GameState, PlayerState, SpaceOwnership
from domain.game.rules.helpers import (
    get_player_by_id_from_state,
    positions_in_color_group,
    refresh_all_net_worth,
    update_player_net_worth,
)


def player_owns_monopoly(
    player: PlayerState,
    color_group: str,
    spaces: tuple[SpaceOwnership, ...],
) -> bool:
    group_positions = positions_in_color_group(color_group)
    if not group_positions:
        return False
    for pos in group_positions:
        ownership = spaces[pos]
        if ownership.owner_id != player.id or ownership.is_mortgaged:
            return False
    return True


def _building_level(ownership: SpaceOwnership) -> int:
    if ownership.has_hotel:
        return 5
    return ownership.houses


def can_build_on(state: GameState, player_id: str, position: int) -> bool:
    player = get_player_by_id_from_state(state, player_id)
    ownership = state.spaces[position]
    if ownership.owner_id != player.id:
        return False
    board_space = get_board_space(position)
    if board_space.type != SpaceType.PROPERTY or board_space.color_group is None:
        return False
    if ownership.is_mortgaged or ownership.has_hotel:
        return False
    if not player_owns_monopoly(player, board_space.color_group.value, state.spaces):
        return False
    group_positions = positions_in_color_group(board_space.color_group.value)
    levels = [_building_level(state.spaces[p]) for p in group_positions]
    min_level = min(levels)
    if _building_level(ownership) > min_level:
        return False
    if _building_level(ownership) >= 4:
        if state.bank_hotels <= 0:
            return False
    elif state.bank_houses <= 0:
        return False
    house_cost = board_space.house_cost or 0
    return player.balance >= house_cost


def can_sell_on(state: GameState, player_id: str, position: int) -> bool:
    player = get_player_by_id_from_state(state, player_id)
    ownership = state.spaces[position]
    if ownership.owner_id != player.id:
        return False
    board_space = get_board_space(position)
    if board_space.type != SpaceType.PROPERTY or board_space.color_group is None:
        return False
    if ownership.houses == 0 and not ownership.has_hotel:
        return False
    group_positions = positions_in_color_group(board_space.color_group.value)
    levels = [_building_level(state.spaces[p]) for p in group_positions]
    max_level = max(levels)
    return _building_level(ownership) == max_level


def build_house(state: GameState, player_id: str, position: int) -> GameState:
    if not can_build_on(state, player_id, position):
        raise IllegalMove("cannot build on this property")
    player = get_player_by_id_from_state(state, player_id)
    ownership = state.spaces[position]
    board_space = get_board_space(position)
    house_cost = board_space.house_cost or 0
    spaces = list(state.spaces)
    bank_houses = state.bank_houses
    bank_hotels = state.bank_hotels

    if ownership.houses == 4:
        spaces[position] = ownership.model_copy(update={"houses": 0, "has_hotel": True})
        bank_houses += 4
        bank_hotels -= 1
    else:
        spaces[position] = ownership.model_copy(update={"houses": ownership.houses + 1})
        bank_houses -= 1

    players = list(state.players)
    idx = next(i for i, p in enumerate(players) if p.id == player_id)
    players[idx] = update_player_net_worth(
        player.model_copy(update={"balance": player.balance - house_cost}),
        tuple(spaces),
    )
    return state.model_copy(
        update={
            "players": refresh_all_net_worth(
                state.model_copy(update={"players": tuple(players), "spaces": tuple(spaces)})
            ),
            "spaces": tuple(spaces),
            "bank_houses": bank_houses,
            "bank_hotels": bank_hotels,
        }
    )


def sell_house(state: GameState, player_id: str, position: int) -> GameState:
    if not can_sell_on(state, player_id, position):
        raise IllegalMove("cannot sell on this property")
    player = get_player_by_id_from_state(state, player_id)
    ownership = state.spaces[position]
    board_space = get_board_space(position)
    house_cost = board_space.house_cost or 0
    credit = int(house_cost * HOUSE_SELL_RATIO)
    spaces = list(state.spaces)
    bank_houses = state.bank_houses
    bank_hotels = state.bank_hotels

    if ownership.has_hotel:
        spaces[position] = ownership.model_copy(update={"houses": 4, "has_hotel": False})
        bank_houses -= 4
        bank_hotels += 1
    else:
        spaces[position] = ownership.model_copy(update={"houses": ownership.houses - 1})
        bank_houses += 1

    players = list(state.players)
    idx = next(i for i, p in enumerate(players) if p.id == player_id)
    players[idx] = update_player_net_worth(
        player.model_copy(update={"balance": player.balance + credit}),
        tuple(spaces),
    )
    return state.model_copy(
        update={
            "players": refresh_all_net_worth(
                state.model_copy(update={"players": tuple(players), "spaces": tuple(spaces)})
            ),
            "spaces": tuple(spaces),
            "bank_houses": bank_houses,
            "bank_hotels": bank_hotels,
        }
    )


def has_any_buildable(state: GameState, player_id: str) -> bool:
    player = get_player_by_id_from_state(state, player_id)
    for pos in player.owned_positions:
        if can_build_on(state, player_id, pos):
            return True
    return False


def can_mortgage(state: GameState, player_id: str, position: int) -> bool:
    player = get_player_by_id_from_state(state, player_id)
    ownership = state.spaces[position]
    if ownership.owner_id != player.id or ownership.is_mortgaged:
        return False
    if ownership.houses > 0 or ownership.has_hotel:
        return False
    board_space = get_board_space(position)
    if board_space.type == SpaceType.PROPERTY and board_space.color_group is not None:
        for pos in positions_in_color_group(board_space.color_group.value):
            mate = state.spaces[pos]
            if mate.houses > 0 or mate.has_hotel:
                return False
    return is_purchasable(position)


def can_unmortgage(state: GameState, player_id: str, position: int) -> bool:
    player = get_player_by_id_from_state(state, player_id)
    ownership = state.spaces[position]
    if ownership.owner_id != player.id or not ownership.is_mortgaged:
        return False
    board_space = get_board_space(position)
    cost = unmortgage_cost(board_space.mortgage_value or 0)
    return player.balance >= cost


def unmortgage_cost(mortgage_value: int) -> int:
    return math.ceil(mortgage_value * (1 + MORTGAGE_INTEREST))


def mortgage_property(state: GameState, player_id: str, position: int) -> GameState:
    if not can_mortgage(state, player_id, position):
        raise IllegalMove("cannot mortgage this property")
    player = get_player_by_id_from_state(state, player_id)
    board_space = get_board_space(position)
    value = board_space.mortgage_value or 0
    spaces = list(state.spaces)
    spaces[position] = state.spaces[position].model_copy(update={"is_mortgaged": True})
    players = list(state.players)
    idx = next(i for i, p in enumerate(players) if p.id == player_id)
    players[idx] = update_player_net_worth(
        player.model_copy(update={"balance": player.balance + value}),
        tuple(spaces),
    )
    return state.model_copy(
        update={
            "players": refresh_all_net_worth(
                state.model_copy(update={"players": tuple(players), "spaces": tuple(spaces)})
            ),
            "spaces": tuple(spaces),
        }
    )


def unmortgage_property(state: GameState, player_id: str, position: int) -> GameState:
    if not can_unmortgage(state, player_id, position):
        raise IllegalMove("cannot unmortgage this property")
    player = get_player_by_id_from_state(state, player_id)
    board_space = get_board_space(position)
    cost = unmortgage_cost(board_space.mortgage_value or 0)
    spaces = list(state.spaces)
    spaces[position] = state.spaces[position].model_copy(update={"is_mortgaged": False})
    players = list(state.players)
    idx = next(i for i, p in enumerate(players) if p.id == player_id)
    players[idx] = update_player_net_worth(
        player.model_copy(update={"balance": player.balance - cost}),
        tuple(spaces),
    )
    return state.model_copy(
        update={
            "players": refresh_all_net_worth(
                state.model_copy(update={"players": tuple(players), "spaces": tuple(spaces)})
            ),
            "spaces": tuple[SpaceOwnership, ...](spaces),
        }
    )


def has_any_mortgageable(state: GameState, player_id: str) -> bool:
    player = get_player_by_id_from_state(state, player_id)
    for pos in player.owned_positions:
        if can_mortgage(state, player_id, pos):
            return True
    return False


def has_any_unmortgageable(state: GameState, player_id: str) -> bool:
    player = get_player_by_id_from_state(state, player_id)
    for pos in player.owned_positions:
        if can_unmortgage(state, player_id, pos):
            return True
    return False
