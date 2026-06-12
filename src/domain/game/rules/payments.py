from __future__ import annotations

from domain.game.schemas.events import GameEvent
from domain.game.enums import TurnPhase
from domain.game.schemas.state import BankruptcyState, GameState
from domain.game.rules.helpers import get_player_by_id_from_state, update_player_net_worth


def attempt_payment(
    state: GameState,
    payer_id: str,
    amount: int,
    *,
    creditor_id: str | None,
) -> tuple[GameState, list[GameEvent]]:
    """Pay amount from payer. If insufficient, enter bankrupt resolution."""
    events: list[GameEvent] = []
    if amount <= 0:
        return state, events

    payer = get_player_by_id_from_state(state, payer_id)
    if payer.balance >= amount:
        return _transfer_funds(state, payer_id, creditor_id, amount), events

    if state.bankruptcy is not None:
        return state, events

    bankruptcy = BankruptcyState(
        debtor_id=payer_id,
        creditor_id=creditor_id,
        amount_owed=amount,
    )
    turn = state.turn.model_copy(update={"phase": TurnPhase.BANKRUPT_RESOLUTION})
    return state.model_copy(update={"bankruptcy": bankruptcy, "turn": turn}), events


def try_settle_debt(state: GameState) -> GameState:
    """If debtor can now pay, settle and exit bankruptcy resolution."""
    if state.bankruptcy is None:
        return state
    debtor = get_player_by_id_from_state(state, state.bankruptcy.debtor_id)
    if debtor.balance >= state.bankruptcy.amount_owed:
        state = _transfer_funds(
            state,
            debtor.id,
            state.bankruptcy.creditor_id,
            state.bankruptcy.amount_owed,
        )
        phase = TurnPhase.POST_ROLL
        turn = state.turn.model_copy(update={"phase": phase})
        return state.model_copy(update={"bankruptcy": None, "turn": turn})
    return state


def _transfer_funds(
    state: GameState,
    payer_id: str,
    creditor_id: str | None,
    amount: int,
) -> GameState:
    players = list(state.players)
    payer_idx = next(i for i, p in enumerate(players) if p.id == payer_id)
    payer = players[payer_idx]
    players[payer_idx] = update_player_net_worth(
        payer.model_copy(update={"balance": payer.balance - amount}),
        state.spaces,
        state.game_mode,
    )
    if creditor_id is not None:
        creditor_idx = next(i for i, p in enumerate(players) if p.id == creditor_id)
        creditor = players[creditor_idx]
        players[creditor_idx] = update_player_net_worth(
            creditor.model_copy(update={"balance": creditor.balance + amount}),
            state.spaces,
            state.game_mode,
        )
    return state.model_copy(update={"players": tuple(players)})
