from __future__ import annotations

import random

from domain.game.board_data import get_board_space, is_purchasable
from domain.game.constants import JAIL_POSITION, JAIL_TURNS_INITIAL
from domain.game.enums import CardKind, CornerVariant, SpaceType, TurnPhase
from domain.game.schemas.events import PassedGo, RentPaid, SentToJail, TaxPaid
from domain.game.schemas.state import (
    DiceRoll,
    GameState,
    JailStatus,
    PlayerState,
    TurnState,
)
from domain.game.rules.payments import attempt_payment
from domain.game.rules.helpers import (
    get_player_by_id_from_state,
    refresh_all_net_worth,
    update_player_net_worth,
)
from domain.game.rules.rent import calculate_rent


def advance_position(from_pos: int, steps: int) -> tuple[int, bool]:
    """Return (new_position, passed_go)."""
    from domain.game.constants import BOARD_SIZE

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
    recursion_depth: int = 0,
    rent_multiplier: int = 1,
    rng: random.Random | None = None,
    jail_fine: int = 50,
) -> tuple[GameState, list, bool]:
    """Resolve landing. Returns (state, events, sent_to_jail)."""
    events: list = []
    sent_to_jail = False
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
        return _finalize(state, players, spaces, turn, events), events, True

    if board_space.type == SpaceType.TAX and board_space.tax_amount is not None:
        state_tmp = _finalize(state, players, spaces, turn, events)
        state_tmp, pay_events = attempt_payment(
            state_tmp, player.id, board_space.tax_amount, creditor_id=None
        )
        events.extend(pay_events)
        if state_tmp.bankruptcy is not None:
            turn = state_tmp.turn.model_copy(update={"phase": TurnPhase.BANKRUPT_RESOLUTION})
            return state_tmp.model_copy(update={"turn": turn}), events, sent_to_jail
        updated = get_player_by_id_from_state(state_tmp, player.id)
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
        return _finalize(state_tmp, list(state_tmp.players), list(state_tmp.spaces), turn, events), events, sent_to_jail

    if board_space.type in (SpaceType.CHANCE, SpaceType.CHEST) and rng is not None:
        from domain.game.rules.cards import draw_and_apply

        kind = CardKind.CHANCE if board_space.type == SpaceType.CHANCE else CardKind.COMMUNITY_CHEST
        state_tmp = _finalize(state, players, spaces, turn, events)
        state_tmp, card_events, active_card, card_jail = draw_and_apply(
            state_tmp,
            get_player_by_id_from_state(state_tmp, player.id),
            kind,
            rng=rng,
            dice_roll=dice_roll,
            go_salary=go_salary,
            jail_fine=jail_fine,
            recursion_depth=recursion_depth,
        )
        events.extend(card_events)
        turn = state_tmp.turn
        if card_jail:
            turn = turn.model_copy(update={"phase": TurnPhase.POST_ROLL, "doubles_streak": 0})
            return state_tmp.model_copy(update={"active_card": active_card, "turn": turn}), events, True
        return state_tmp.model_copy(update={"active_card": active_card}), events, sent_to_jail

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
            rent_multiplier=rent_multiplier,
        )
        state_tmp = _finalize(state, players, spaces, turn, events)
        state_tmp, pay_events = attempt_payment(
            state_tmp, player.id, rent, creditor_id=owner.id
        )
        events.extend(pay_events)
        if state_tmp.bankruptcy is not None:
            turn = state_tmp.turn.model_copy(update={"phase": TurnPhase.BANKRUPT_RESOLUTION})
            return state_tmp.model_copy(update={"turn": turn}), events, sent_to_jail
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
        # Return state_tmp (which has the deducted balances from attempt_payment),
        # not a new _finalize from original state/players which would discard them.
        final_turn = state_tmp.turn.model_copy(
            update={"pending_buy_position": None, "phase": TurnPhase.MUST_PAY_RENT}
        )
        return state_tmp.model_copy(update={"turn": final_turn}), events, sent_to_jail

    elif is_purchasable(player.position) and ownership.owner_id is None:
        pending_buy = player.position

    turn = turn.model_copy(
        update={
            "pending_buy_position": pending_buy,
            "phase": phase,
        }
    )
    return _finalize(state, players, spaces, turn, events), events, sent_to_jail


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
) -> GameState:
    new_state = state.model_copy(
        update={
            "players": refresh_all_net_worth(
                state.model_copy(update={"players": tuple(players), "spaces": tuple(spaces)})
            ),
            "spaces": tuple(spaces),
            "turn": turn,
        }
    )
    return new_state
