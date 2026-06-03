"""Per-player turn timer.

The current player gets TURN_TIMEOUT_MS to make their next move, refreshed on every
applied command. The GameScheduler force-ends the turn once the deadline passes (recording
an AFK strike; auto-surrender at MAX_AFK_STRIKES). Auctions/trades have their own timers
and bankruptcy resolution must not be auto-resolved, so the timer only enforces during the
active player's decision phases.
"""
from __future__ import annotations

from domain.game.constants import TURN_TIMEOUT_MS
from domain.game.enums import TurnPhase
from domain.game.schemas.state import GameState

ACTIVE_TURN_PHASES = frozenset(
    {
        TurnPhase.PRE_ROLL,
        TurnPhase.JAIL_DECISION,
        TurnPhase.POST_ROLL,
        TurnPhase.MUST_PAY_RENT,
    }
)


def with_turn_deadline(state: GameState, now_ms: int) -> GameState:
    """Refresh the current player's deadline to now + TURN_TIMEOUT_MS."""
    turn = state.turn.model_copy(update={"turn_deadline_ms": now_ms + TURN_TIMEOUT_MS})
    return state.model_copy(update={"turn": turn})


def turn_time_remaining_ms(state: GameState, now_ms: int) -> int | None:
    deadline = state.turn.turn_deadline_ms
    if deadline is None:
        return None
    return max(0, deadline - now_ms)


def is_turn_expired(state: GameState, now_ms: int) -> bool:
    deadline = state.turn.turn_deadline_ms
    return (
        deadline is not None
        and now_ms >= deadline
        and state.turn.phase in ACTIVE_TURN_PHASES
    )
