from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from domain.game.constants import AUCTION_DURATION_MS, TRADE_DURATION_MS
from domain.game.enums import GameStatus, TradeStatus, TurnPhase
from domain.game.exceptions import IllegalMove
from domain.game.schemas.state import AuctionBid, AuctionState, GameState
from domain.game.rules.helpers import get_player_by_id_from_state
from domain.game.board_data import get_board_space
from domain.game.rules.helpers import refresh_all_net_worth, update_player_net_worth


def start_auction(state: GameState, property_position: int, now_ms: int) -> GameState:
    auction = AuctionState(
        property_position=property_position,
        time_remaining_ms=AUCTION_DURATION_MS,
        started_at_ms=now_ms,
    )
    turn = state.turn.model_copy(
        update={
            "phase": TurnPhase.AUCTION,
            "pending_buy_position": None,
        }
    )
    return state.model_copy(update={"auction": auction, "turn": turn})


def place_bid(state: GameState, player_id: str, amount: int) -> GameState:
    if state.auction is None:
        raise IllegalMove("no active auction")
    if state.turn.phase != TurnPhase.AUCTION:
        raise IllegalMove("not in auction phase")

    player = get_player_by_id_from_state(state, player_id)
    if player.is_bankrupt or player.balance < amount:
        raise IllegalMove("insufficient funds for bid")
    if amount <= state.auction.highest_bid:
        raise IllegalMove("bid must exceed current highest bid")

    bid = AuctionBid(player_id=player_id, amount=amount)
    bids = state.auction.bids + (bid,)
    auction = state.auction.model_copy(
        update={
            "bids": bids,
            "highest_bid": amount,
            "highest_bidder_id": player_id,
        }
    )
    return state.model_copy(update={"auction": auction})


def resolve_auction(state: GameState) -> GameState:
    if state.auction is None:
        return state

    auction = state.auction
    position = auction.property_position
    spaces = list(state.spaces)
    players = list(state.players)

    if auction.highest_bidder_id is not None:
        bidder = get_player_by_id_from_state(state, auction.highest_bidder_id)
        board_space = get_board_space(position)
        price = auction.highest_bid
        bidder_idx = next(i for i, p in enumerate(players) if p.id == bidder.id)
        owned = list(bidder.owned_positions)
        owned.append(position)
        spaces[position] = spaces[position].model_copy(update={"owner_id": bidder.id})
        players[bidder_idx] = update_player_net_worth(
            bidder.model_copy(
                update={
                    "balance": bidder.balance - price,
                    "owned_positions": tuple(sorted(set(owned))),
                }
            ),
            tuple(spaces),
        )

    # If the auction was opened by passing on a doubles roll, the deferred extra roll is
    # granted once the auction resolves (return to PRE_ROLL); otherwise back to POST_ROLL.
    next_phase = TurnPhase.PRE_ROLL if state.turn.doubles_streak > 0 else TurnPhase.POST_ROLL
    turn = state.turn.model_copy(update={"phase": next_phase})
    return state.model_copy(
        update={
            "players": refresh_all_net_worth(
                state.model_copy(update={"players": tuple(players), "spaces": tuple(spaces)})
            ),
            "spaces": tuple(spaces),
            "auction": None,
            "turn": turn,
        }
    )


def auction_time_remaining(state: GameState, now_ms: int) -> int:
    if state.auction is None:
        return 0
    elapsed = now_ms - state.auction.started_at_ms
    return max(0, state.auction.time_remaining_ms - elapsed)


def is_auction_expired(state: GameState, now_ms: int) -> bool:
    return state.auction is not None and auction_time_remaining(state, now_ms) <= 0
