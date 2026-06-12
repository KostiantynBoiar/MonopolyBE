from __future__ import annotations

from domain.game.board_data import get_board_space
from domain.game.constants import MORTGAGE_INTEREST
from domain.game.enums import GameStatus, TurnPhase
from domain.game.modes import get_game_config
from domain.game.schemas.state import GameState
from domain.game.rules.helpers import (
    get_player_by_id_from_state,
    refresh_all_net_worth,
    replace_space,
    space_at,
)


def resolve_bankruptcy(state: GameState, debtor_id: str) -> GameState:
    """Finalize bankruptcy: transfer assets to creditor or bank."""
    if state.bankruptcy is None or state.bankruptcy.debtor_id != debtor_id:
        return state

    creditor_id = state.bankruptcy.creditor_id
    debtor = get_player_by_id_from_state(state, debtor_id)
    players = list(state.players)
    spaces = list(state.spaces)
    chance_deck = state.chance_deck
    chest_deck = state.chest_deck

    debtor_idx = next(i for i, p in enumerate(players) if p.id == debtor_id)

    if creditor_id is not None:
        creditor = get_player_by_id_from_state(state, creditor_id)
        creditor_idx = next(i for i, p in enumerate(players) if p.id == creditor_id)

        transfer_cash = min(debtor.balance, state.bankruptcy.amount_owed)
        players[creditor_idx] = creditor.model_copy(
            update={"balance": creditor.balance + transfer_cash}
        )

        new_owned = list(creditor.owned_positions)
        for pos in debtor.owned_positions:
            ownership = space_at(spaces, pos)
            replace_space(spaces, pos, ownership.model_copy(update={"owner_id": creditor_id}))
            if ownership.is_mortgaged:
                cost = int(
                    (get_board_space(pos, state.game_mode).mortgage_value or 0) * MORTGAGE_INTEREST
                )
                c = get_player_by_id_from_state(
                    state.model_copy(update={"players": tuple(players)}), creditor_id
                )
                players[creditor_idx] = c.model_copy(update={"balance": c.balance - cost})
            new_owned.append(pos)

        players[creditor_idx] = players[creditor_idx].model_copy(
            update={
                "owned_positions": tuple(sorted(set(new_owned))),
                "get_out_of_jail_cards": (
                    creditor.get_out_of_jail_cards + debtor.get_out_of_jail_cards
                ),
            }
        )
    else:
        for _ in range(debtor.get_out_of_jail_cards):
            chance_deck = chance_deck + ("chance_08",)
            chest_deck = chest_deck + ("chest_05",)
        for pos in debtor.owned_positions:
            replace_space(
                spaces,
                pos,
                space_at(spaces, pos).model_copy(
                    update={
                        "owner_id": None,
                        "is_mortgaged": False,
                        "houses": 0,
                        "has_hotel": False,
                    }
                ),
            )

    players[debtor_idx] = debtor.model_copy(
        update={
            "balance": 0,
            "owned_positions": (),
            "get_out_of_jail_cards": 0,
            "jail_status": None,
            "is_bankrupt": True,
            "position": get_game_config(state.game_mode).start_position,
            "eliminated_at": state.turn.turn_number,
        }
    )

    new_state = state.model_copy(
        update={
            "players": refresh_all_net_worth(
                state.model_copy(update={"players": tuple(players), "spaces": tuple(spaces)})
            ),
            "spaces": tuple(spaces),
            "bankruptcy": None,
            "chance_deck": chance_deck,
            "chest_deck": chest_deck,
        }
    )
    resolved = check_win_condition(new_state)
    if resolved.status == GameStatus.FINISHED:
        return resolved
    # The bankrupt player was the current player; if the game continues, hand the turn to
    # the next active player. Otherwise current_player_id stays on the eliminated player
    # and the next end_turn fails (StopIteration over active players) → softlock.
    return advance_turn_off_player(resolved, debtor_id)


def advance_turn_off_player(state: GameState, eliminated_id: str) -> GameState:
    """Hand the turn to the next active player when the current player is eliminated
    (bankruptcy or surrender), so the turn never sticks on someone who's out."""
    players = list(state.players)
    n = len(players)
    start = next(i for i, p in enumerate(players) if p.id == eliminated_id)

    next_player = None
    wrapped = False
    for offset in range(1, n + 1):
        idx = start + offset
        candidate = players[idx % n]
        if not candidate.is_bankrupt:
            next_player = candidate
            wrapped = idx >= n
            break
    if next_player is None:
        return state  # no active players left (win condition already handled this)

    next_phase = (
        TurnPhase.JAIL_DECISION if next_player.jail_status is not None else TurnPhase.PRE_ROLL
    )
    turn = state.turn.model_copy(
        update={
            "current_player_id": next_player.id,
            "phase": next_phase,
            "turn_number": state.turn.turn_number + 1,
            "round_number": state.turn.round_number + (1 if wrapped else 0),
            "dice_roll": None,
            "doubles_streak": 0,
            "trade_offers_made": 0,
            "pending_buy_position": None,
        }
    )
    return state.model_copy(update={"turn": turn})


def check_win_condition(state: GameState) -> GameState:
    survivors = [p for p in state.players if not p.is_bankrupt]
    if len(survivors) == 1 and state.status == GameStatus.IN_PROGRESS:
        winner = survivors[0]
        turn = state.turn.model_copy(update={"phase": TurnPhase.GAME_OVER})
        return state.model_copy(
            update={
                "status": GameStatus.FINISHED,
                "winner_id": winner.id,
                "turn": turn,
            }
        )
    return state
