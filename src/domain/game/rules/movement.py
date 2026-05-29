from __future__ import annotations

from domain.game.board_data import get_board_space, is_purchasable
from domain.game.constants import BOARD_SIZE, JAIL_POSITION, JAIL_TURNS_INITIAL
from domain.game.enums import CornerVariant, SpaceType, TurnPhase
from domain.game.schemas.events import PassedGo, RentPaid, SentToJail, TaxPaid
from domain.game.schemas.state import (
    DiceRoll,
    GameState,
    JailStatus,
    PlayerState,
    TurnState,
)
from domain.game.rules.helpers import (
    get_player_by_id_from_state,
    refresh_all_net_worth,
    update_player_net_worth,
)
from domain.game.rules.rent import calculate_rent


def advance_position(from_pos: int, steps: int) -> tuple[int, bool]:
    """Return (new_position, passed_go)."""
    new_pos = (from_pos + steps) % BOARD_SIZE
    passed_go = from_pos + steps >= BOARD_SIZE
    return new_pos, passed_go


def send_to_jail(player: PlayerState) -> PlayerState:
    return player.model_copy(
        update={
            "position": JAIL_POSITION,
            "jail_status": JailStatus(turns_remaining=JAIL_TURNS_INITIAL),
        }
    )


def resolve_landing(
    state: GameState,
    player: PlayerState,
    dice_roll: DiceRoll,
    *,
    go_salary: int,
) -> tuple[GameState, list]:
    events: list = []
    board_space = get_board_space(player.position)
    players = list(state.players)
    spaces = list(state.spaces)
    turn = state.turn
    pending_buy: int | None = None
    phase = TurnPhase.POST_ROLL

    if board_space.corner == CornerVariant.GOTO_JAIL:
        idx = _player_index(players, player.id)
        jailed = send_to_jail(player)
        players[idx] = update_player_net_worth(jailed, tuple(spaces))
        events.append(
            SentToJail(
                player_id=player.id,
                player_name=player.display_name,
                reason="landed on Go to Jail",
            )
        )
        turn = turn.model_copy(update={"pending_buy_position": None, "phase": phase})
        return _finalize(state, players, spaces, turn, events)

    if board_space.type == SpaceType.TAX and board_space.tax_amount is not None:
        idx = _player_index(players, player.id)
        updated = player.model_copy(update={"balance": player.balance - board_space.tax_amount})
        players[idx] = update_player_net_worth(updated, tuple(spaces))
        events.append(
            TaxPaid(
                player_id=player.id,
                player_name=player.display_name,
                position=player.position,
                tax_name=board_space.name,
                amount=board_space.tax_amount,
            )
        )
        turn = turn.model_copy(update={"pending_buy_position": None, "phase": phase})
        return _finalize(state, players, spaces, turn, events)

    ownership = spaces[player.position]
    if (
        is_purchasable(player.position)
        and ownership.owner_id is not None
        and ownership.owner_id != player.id
        and not ownership.is_mortgaged
    ):
        owner = get_player_by_id_from_state(state, ownership.owner_id)
        rent = calculate_rent(
            position=player.position,
            spaces=tuple(spaces),
            players=state.players,
            dice_total=dice_roll.die1 + dice_roll.die2,
        )
        payer_idx = _player_index(players, player.id)
        owner_idx = _player_index(players, owner.id)
        payer = players[payer_idx].model_copy(update={"balance": player.balance - rent})
        receiver = players[owner_idx].model_copy(update={"balance": owner.balance + rent})
        players[payer_idx] = update_player_net_worth(payer, tuple(spaces))
        players[owner_idx] = update_player_net_worth(receiver, tuple(spaces))
        events.append(
            RentPaid(
                payer_id=player.id,
                payer_name=player.display_name,
                owner_id=owner.id,
                owner_name=owner.display_name,
                position=player.position,
                property_name=board_space.name,
                amount=rent,
            )
        )
        phase = TurnPhase.MUST_PAY_RENT

    elif is_purchasable(player.position) and ownership.owner_id is None:
        pending_buy = player.position

    turn = turn.model_copy(
        update={
            "pending_buy_position": pending_buy,
            "phase": phase,
        }
    )
    return _finalize(state, players, spaces, turn, events)


def apply_go_salary(
    state: GameState,
    player: PlayerState,
    amount: int,
) -> tuple[GameState, PassedGo]:
    players = list(state.players)
    idx = _player_index(players, player.id)
    updated = player.model_copy(update={"balance": player.balance + amount})
    players[idx] = update_player_net_worth(updated, state.spaces)
    event = PassedGo(
        player_id=player.id,
        player_name=player.display_name,
        amount=amount,
    )
    new_state = state.model_copy(update={"players": tuple(players)})
    return new_state, event


def _player_index(players: list[PlayerState], player_id: str) -> int:
    for i, p in enumerate(players):
        if p.id == player_id:
            return i
    raise KeyError(player_id)


def _finalize(
    state: GameState,
    players: list[PlayerState],
    spaces: list,
    turn: TurnState,
    events: list,
) -> tuple[GameState, list]:
    new_state = state.model_copy(
        update={
            "players": refresh_all_net_worth(
                state.model_copy(update={"players": tuple(players), "spaces": tuple(spaces)})
            ),
            "spaces": tuple(spaces),
            "turn": turn,
        }
    )
    return new_state, events
