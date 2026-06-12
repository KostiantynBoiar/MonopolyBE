from __future__ import annotations

from domain.game.enums import TurnPhase
from domain.game.rules.actions import compute_actions
from domain.game.schemas.state import AuctionState, GameState
from tests.domain.game.conftest import with_phase


def test_non_current_player_has_no_actions(two_player_game: GameState) -> None:
    # Current player is players[0]; players[1] is not on turn.
    state = with_phase(two_player_game, TurnPhase.PRE_ROLL)
    current = state.turn.current_player_id
    other = next(p.id for p in state.players if p.id != current)

    current_actions = compute_actions(state, current)
    other_actions = compute_actions(state, other)

    assert current_actions.can_roll is True
    # A non-current viewer can take no turn action.
    assert other_actions == type(other_actions)()  # all-False ActionSet


def test_post_roll_non_current_player_empty(two_player_game: GameState) -> None:
    state = with_phase(two_player_game, TurnPhase.POST_ROLL, pending_buy_position=None)
    other = next(p.id for p in state.players if p.id != state.turn.current_player_id)
    actions = compute_actions(state, other)
    assert actions.can_buy is False
    assert actions.can_end_turn is False
    assert actions.can_build is False


def test_auction_all_solvent_players_can_bid(two_player_game: GameState) -> None:
    p0, p1 = two_player_game.players
    auction = AuctionState(property_position=2, time_remaining_ms=10_000, started_at_ms=0)
    state = two_player_game.model_copy(update={"auction": auction})
    state = with_phase(state, TurnPhase.AUCTION)

    # Both players (current and non-current) can bid when no one is the high bidder.
    assert compute_actions(state, p0.id).can_bid is True
    assert compute_actions(state, p1.id).can_bid is True


def test_auction_high_bidder_cannot_bid_against_self(two_player_game: GameState) -> None:
    p0, p1 = two_player_game.players
    auction = AuctionState(
        property_position=2,
        time_remaining_ms=10_000,
        started_at_ms=0,
        highest_bid=100,
        highest_bidder_id=p0.id,
    )
    state = two_player_game.model_copy(update={"auction": auction})
    state = with_phase(state, TurnPhase.AUCTION)

    assert compute_actions(state, p0.id).can_bid is False  # already highest
    assert compute_actions(state, p1.id).can_bid is True


def test_auction_insufficient_funds_cannot_bid(two_player_game: GameState) -> None:
    p0, p1 = two_player_game.players
    # Drop p1's balance below the current high bid.
    players = list(two_player_game.players)
    players[1] = p1.model_copy(update={"balance": 50})
    auction = AuctionState(
        property_position=2,
        time_remaining_ms=10_000,
        started_at_ms=0,
        highest_bid=100,
        highest_bidder_id=p0.id,
    )
    state = two_player_game.model_copy(update={"players": tuple(players), "auction": auction})
    state = with_phase(state, TurnPhase.AUCTION)

    assert compute_actions(state, p1.id).can_bid is False  # can't afford > 100
