from __future__ import annotations

from domain.game.constants import JAIL_FINE
from domain.game.enums import TurnPhase
from domain.game.schemas.state import ActionSet, GameState
from domain.game.rules.building import (
    can_build_on,
    can_mortgage,
    can_unmortgage,
    has_any_buildable,
    has_any_mortgageable,
    has_any_unmortgageable,
)
from domain.game.rules.helpers import get_player_by_id_from_state


def compute_actions(state: GameState, player_id: str | None = None) -> ActionSet:
    pid = player_id or state.turn.current_player_id
    phase = state.turn.phase
    player = get_player_by_id_from_state(state, pid)
    is_current = pid == state.turn.current_player_id

    if phase == TurnPhase.AUCTION:
        can_bid = (
            not player.is_bankrupt
            and state.auction is not None
            and state.auction.highest_bidder_id != pid
            and player.balance > state.auction.highest_bid
        )
        return ActionSet(can_bid=can_bid)

    if phase == TurnPhase.TRADE_NEGOTIATION:
        return ActionSet()

    if not is_current:
        return ActionSet()

    if phase == TurnPhase.JAIL_DECISION:
        return ActionSet(
            can_roll=True,
            can_pay_jail_fine=player.balance >= JAIL_FINE,
            can_use_jail_card=player.get_out_of_jail_cards > 0,
            can_surrender=True,
        )

    if phase == TurnPhase.PRE_ROLL:
        can_build = has_any_buildable(state, pid)
        return ActionSet(
            can_roll=True,
            can_build=can_build,
            can_mortgage=has_any_mortgageable(state, pid),
            can_unmortgage=has_any_unmortgageable(state, pid),
            can_trade=state.trade is None and state.status.value == "in_progress",
            can_surrender=True,
        )

    if phase == TurnPhase.POST_ROLL:
        pending = state.turn.pending_buy_position
        can_buy = pending is not None and state.spaces[pending].owner_id is None
        return ActionSet(
            can_buy=can_buy,
            can_build=has_any_buildable(state, pid),
            can_mortgage=has_any_mortgageable(state, pid),
            can_unmortgage=has_any_unmortgageable(state, pid),
            can_trade=state.trade is None,
            can_end_turn=pending is None,
            can_surrender=True,
        )

    if phase == TurnPhase.MUST_PAY_RENT:
        return ActionSet(can_end_turn=True, can_surrender=True)

    if phase == TurnPhase.BANKRUPT_RESOLUTION:
        return ActionSet(
            can_build=has_any_buildable(state, pid),
            can_mortgage=has_any_mortgageable(state, pid),
            can_unmortgage=has_any_unmortgageable(state, pid),
            can_declare_bankruptcy=True,
            can_end_turn=state.bankruptcy is None,
        )

    return ActionSet()


def with_actions(state: GameState, player_id: str | None = None) -> GameState:
    actions = compute_actions(state, player_id)
    return state.model_copy(
        update={"turn": state.turn.model_copy(update={"actions_available": actions})}
    )
