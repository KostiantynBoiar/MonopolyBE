"""Surrender: a player voluntarily quits (or is auto-surrendered after going AFK).

Unlike bankruptcy (assets transfer to a creditor), on surrender the player's properties
return to the bank — free to buy again — and their cash is split equally among the
remaining players.
"""
from __future__ import annotations

from domain.game.enums import GameStatus
from domain.game.schemas.state import GameState
from domain.game.rules.bankruptcy import advance_turn_off_player, check_win_condition
from domain.game.rules.helpers import get_player_by_id_from_state, refresh_all_net_worth


def resolve_surrender(state: GameState, player_id: str) -> GameState:
    player = get_player_by_id_from_state(state, player_id)
    if player.is_bankrupt:
        return state  # already out of the game

    players = list(state.players)
    spaces = list(state.spaces)
    idx = next(i for i, p in enumerate(players) if p.id == player_id)
    bank_houses = state.bank_houses
    bank_hotels = state.bank_hotels
    chance_deck = state.chance_deck
    chest_deck = state.chest_deck

    # Properties return to the bank — unowned, unmortgaged, buildings cleared → buyable.
    for pos in player.owned_positions:
        ownership = spaces[pos]
        if ownership.has_hotel:
            bank_hotels += 1
        else:
            bank_houses += ownership.houses
        spaces[pos] = ownership.model_copy(
            update={"owner_id": None, "houses": 0, "has_hotel": False, "is_mortgaged": False}
        )

    # Get-out-of-jail cards go back to the decks (same as bankruptcy's bank path).
    for _ in range(player.get_out_of_jail_cards):
        chance_deck = chance_deck + ("chance_08",)
        chest_deck = chest_deck + ("chest_05",)

    # Split the surrendering player's cash equally among the remaining active players;
    # distribute the remainder one-by-one so the total is conserved.
    recipients = [i for i, p in enumerate(players) if p.id != player_id and not p.is_bankrupt]
    cash = player.balance
    if recipients and cash > 0:
        share, remainder = divmod(cash, len(recipients))
        for n, ri in enumerate(recipients):
            extra = 1 if n < remainder else 0
            recipient = players[ri]
            players[ri] = recipient.model_copy(update={"balance": recipient.balance + share + extra})

    # Eliminate the player.
    players[idx] = player.model_copy(
        update={
            "balance": 0,
            "owned_positions": (),
            "get_out_of_jail_cards": 0,
            "jail_status": None,
            "is_bankrupt": True,
        }
    )

    new_state = state.model_copy(
        update={
            "players": refresh_all_net_worth(
                state.model_copy(update={"players": tuple(players), "spaces": tuple(spaces)})
            ),
            "spaces": tuple(spaces),
            "bank_houses": bank_houses,
            "bank_hotels": bank_hotels,
            "chance_deck": chance_deck,
            "chest_deck": chest_deck,
        }
    )

    resolved = check_win_condition(new_state)
    if resolved.status == GameStatus.FINISHED:
        return resolved
    # If the player surrendered on their own turn, move play to the next active player.
    if resolved.turn.current_player_id == player_id:
        return advance_turn_off_player(resolved, player_id)
    return resolved
