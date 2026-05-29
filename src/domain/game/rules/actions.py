from __future__ import annotations

from domain.game.enums import TurnPhase
from domain.game.schemas.state import ActionSet, GameState


def compute_actions(state: GameState) -> ActionSet:
    phase = state.turn.phase

    if phase == TurnPhase.PRE_ROLL:
        return ActionSet(can_roll=True)

    if phase == TurnPhase.POST_ROLL:
        pending = state.turn.pending_buy_position
        can_buy = pending is not None and state.spaces[pending].owner_id is None
        # A pending buy must be resolved (buy or pass) before the turn can end —
        # mirror the guard in engine._handle_end_turn so the ActionSet stays honest.
        return ActionSet(can_buy=can_buy, can_end_turn=pending is None)

    if phase == TurnPhase.MUST_PAY_RENT:
        return ActionSet(can_end_turn=True)

    return ActionSet()


def with_actions(state: GameState) -> GameState:
    actions = compute_actions(state)
    return state.model_copy(
        update={"turn": state.turn.model_copy(update={"actions_available": actions})}
    )
