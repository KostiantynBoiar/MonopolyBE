from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from domain.game.constants import AUCTION_DURATION_MS
from domain.game.enums import TurnPhase
from domain.game.exceptions import IllegalMove
from domain.game.rng import FixedClock
from domain.game.rules.auction import place_bid, resolve_auction, start_auction
from domain.game.schemas.commands import AdvanceAuction, PlaceBid
from domain.game.schemas.state import AuctionBid, AuctionState, GameState
from tests.domain.game.conftest import apply_cmd, with_phase


def _auction_state(two_player_game: GameState, clock: FixedClock) -> GameState:
    now_ms = int(clock.now().timestamp() * 1000)
    return start_auction(two_player_game, property_position=1, now_ms=now_ms)


def test_place_bid_updates_highest(two_player_game: GameState, clock: FixedClock) -> None:
    state = _auction_state(two_player_game, clock)
    p1 = state.players[0]
    state = with_phase(state, TurnPhase.AUCTION, current_player_id=p1.id)

    new_state = place_bid(state, p1.id, 100)
    assert new_state.auction is not None
    assert new_state.auction.highest_bid == 100
    assert new_state.auction.highest_bidder_id == p1.id


def test_bid_must_exceed_highest(two_player_game: GameState, clock: FixedClock) -> None:
    state = _auction_state(two_player_game, clock)
    p1 = state.players[0]
    state = with_phase(state, TurnPhase.AUCTION, current_player_id=p1.id)
    state = place_bid(state, p1.id, 100)

    with pytest.raises(IllegalMove, match="bid must exceed"):
        place_bid(state, p1.id, 50)


def test_insolvent_bidder_rejected(two_player_game: GameState, clock: FixedClock) -> None:
    state = _auction_state(two_player_game, clock)
    p1 = state.players[0]
    broke = p1.model_copy(update={"balance": 10})
    players = (broke, state.players[1])
    state = state.model_copy(update={"players": players})
    state = with_phase(state, TurnPhase.AUCTION, current_player_id=p1.id)

    with pytest.raises(IllegalMove, match="insufficient"):
        place_bid(state, p1.id, 100)


def test_resolve_auction_with_winner(two_player_game: GameState, clock: FixedClock) -> None:
    state = _auction_state(two_player_game, clock)
    p1 = state.players[0]
    state = with_phase(state, TurnPhase.AUCTION, current_player_id=p1.id)
    state = place_bid(state, p1.id, 100)

    resolved = resolve_auction(state)
    assert resolved.auction is None
    assert resolved.spaces[1].owner_id == p1.id
    assert resolved.players[0].balance == 1400


def test_resolve_auction_no_bids(two_player_game: GameState, clock: FixedClock) -> None:
    state = _auction_state(two_player_game, clock)
    resolved = resolve_auction(state)
    assert resolved.auction is None
    assert resolved.spaces[1].owner_id is None


def test_advance_auction_when_expired(two_player_game: GameState) -> None:
    expired_clock = FixedClock(
        datetime(2026, 5, 29, 12, 1, 0, tzinfo=UTC)
    )
    started_ms = int(
        (expired_clock.now() - timedelta(milliseconds=AUCTION_DURATION_MS + 1000)).timestamp()
        * 1000
    )
    auction = AuctionState(
        property_position=1,
        time_remaining_ms=AUCTION_DURATION_MS,
        started_at_ms=started_ms,
        bids=(AuctionBid(player_id=two_player_game.players[0].id, amount=60),),
        highest_bid=60,
        highest_bidder_id=two_player_game.players[0].id,
    )
    state = two_player_game.model_copy(
        update={
            "auction": auction,
            "turn": two_player_game.turn.model_copy(update={"phase": TurnPhase.AUCTION}),
        }
    )

    new_state, _ = apply_cmd(state, AdvanceAuction(), expired_clock)
    assert new_state.auction is None
    assert new_state.spaces[1].owner_id == state.players[0].id


def test_advance_auction_noop_when_not_expired(
    two_player_game: GameState, clock: FixedClock
) -> None:
    # Auction started "now" → not expired; AdvanceAuction must be a no-op (the
    # scheduler relies on this to avoid spurious per-second broadcasts).
    state = _auction_state(two_player_game, clock)
    new_state, events = apply_cmd(state, AdvanceAuction(), clock)
    assert new_state.auction is not None
    assert new_state.spaces[1].owner_id is None
    assert events == []


def test_place_bid_via_engine(two_player_game: GameState, clock: FixedClock) -> None:
    state = _auction_state(two_player_game, clock)
    p2 = state.players[1]
    state = with_phase(state, TurnPhase.AUCTION, current_player_id=p2.id)

    new_state, _ = apply_cmd(state, PlaceBid(player_id=p2.id, amount=80), clock)
    assert new_state.auction is not None
    assert new_state.auction.highest_bid == 80


def test_non_current_player_can_bid_via_engine(
    two_player_game: GameState, clock: FixedClock
) -> None:
    # An auction is open to ALL solvent players, not just whoever's turn it is. The
    # current player is p1; p2 (not the current player) must still be able to bid —
    # the engine's "not your turn" guard must NOT apply to PlaceBid. (Regression: the
    # guard previously blocked every non-current bidder, so auctions never progressed.)
    state = _auction_state(two_player_game, clock)
    p1, p2 = state.players[0], state.players[1]
    state = with_phase(state, TurnPhase.AUCTION, current_player_id=p1.id)
    state, _ = apply_cmd(state, PlaceBid(player_id=p1.id, amount=60), clock)

    new_state, _ = apply_cmd(state, PlaceBid(player_id=p2.id, amount=80), clock)
    assert new_state.auction is not None
    assert new_state.auction.highest_bid == 80
    assert new_state.auction.highest_bidder_id == p2.id
