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

    if phase == TurnPhase.JAIL_DECISION:
        return ActionSet(
            can_roll=True,
            can_pay_jail_fine=player.balance >= JAIL_FINE,
            can_use_jail_card=player.get_out_of_jail_cards > 0,
        )

    if phase == TurnPhase.PRE_ROLL:
        can_build = has_any_buildable(state, pid)
        return ActionSet(
            can_roll=True,
            can_build=can_build,
            can_mortgage=has_any_mortgageable(state, pid),
            can_unmortgage=has_any_unmortgageable(state, pid),
            can_trade=state.trade is None and state.status.value == "in_progress",
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
        )

    if phase == TurnPhase.MUST_PAY_RENT:
        return ActionSet(can_end_turn=True)

    if phase == TurnPhase.AUCTION:
        return ActionSet(can_bid=True)

    if phase == TurnPhase.TRADE_NEGOTIATION:
        return ActionSet(can_trade=True)

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
