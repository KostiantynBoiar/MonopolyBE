from __future__ import annotations

from datetime import timedelta

import pytest

from domain.game.constants import MAX_TRADE_OFFERS_PER_TURN
from domain.game.enums import TradeResponse, TradeStatus, TurnPhase
from domain.game.exceptions import IllegalMove
from domain.game.rng import FixedClock
from domain.game.rules.actions import compute_actions
from domain.game.rules.bankruptcy import advance_turn_off_player
from domain.game.rules.helpers import space_at
from domain.game.rules.trade import expire_trade, propose_trade, respond_trade
from domain.game.schemas.commands import BuildHouse, EndTurn, ProposeTrade, RespondTrade
from domain.game.schemas.state import GameState, TradeOffer, TradeState
from tests.domain.game.conftest import apply_cmd, monopoly_brown, with_phase


def test_propose_trade(two_player_game: GameState, clock: FixedClock) -> None:
    p1, p2 = two_player_game.players
    # p1 owns Mediterranean (pos 2) via monopoly_brown; offer it to p2 for money.
    state = monopoly_brown(two_player_game, p1.id)
    state = with_phase(state, TurnPhase.POST_ROLL, current_player_id=p1.id)

    new_state = propose_trade(
        state,
        p1.id,
        p2.id,
        TradeOffer(money=0, positions=(2,), get_out_of_jail_cards=0),
        TradeOffer(money=100, positions=(), get_out_of_jail_cards=0),
        clock.now(),
    )
    assert new_state.trade is not None
    assert new_state.turn.phase == TurnPhase.TRADE_NEGOTIATION


def test_accept_trade_swaps_assets(two_player_game: GameState, clock: FixedClock) -> None:
    p1, p2 = two_player_game.players
    state = monopoly_brown(two_player_game, p1.id)
    state = with_phase(state, TurnPhase.POST_ROLL, current_player_id=p1.id)

    state = propose_trade(
        state,
        p1.id,
        p2.id,
        TradeOffer(money=0, positions=(2,), get_out_of_jail_cards=0),
        TradeOffer(money=200, positions=(), get_out_of_jail_cards=0),
        clock.now(),
    )
    trade_id = state.trade.id  # type: ignore[union-attr]

    accepted = respond_trade(
        state,
        p2.id,
        trade_id,
        TradeResponse.ACCEPT,
        None,
        clock.now(),
    )
    assert accepted.trade is None
    assert space_at(accepted.spaces, 2).owner_id == p2.id
    assert accepted.players[0].balance == 2200
    assert accepted.players[1].balance == 1300


def test_reject_trade(two_player_game: GameState, clock: FixedClock) -> None:
    p1, p2 = two_player_game.players
    state = with_phase(two_player_game, TurnPhase.POST_ROLL, current_player_id=p1.id)
    state = propose_trade(
        state,
        p1.id,
        p2.id,
        TradeOffer(),
        TradeOffer(),
        clock.now(),
    )
    trade_id = state.trade.id  # type: ignore[union-attr]

    rejected = respond_trade(
        state,
        p2.id,
        trade_id,
        TradeResponse.REJECT,
        None,
        clock.now(),
    )
    assert rejected.trade is None
    assert rejected.turn.phase == TurnPhase.POST_ROLL


def test_counter_trade(two_player_game: GameState, clock: FixedClock) -> None:
    p1, p2 = two_player_game.players
    state = with_phase(two_player_game, TurnPhase.POST_ROLL, current_player_id=p1.id)
    state = propose_trade(
        state,
        p1.id,
        p2.id,
        TradeOffer(money=50),
        TradeOffer(),
        clock.now(),
    )
    trade_id = state.trade.id  # type: ignore[union-attr]

    countered = respond_trade(
        state,
        p2.id,
        trade_id,
        TradeResponse.COUNTER,
        TradeOffer(money=100),
        clock.now(),
    )
    assert countered.trade is not None
    assert countered.trade.status == TradeStatus.COUNTERED
    assert countered.trade.target_request.money == 100


def test_cannot_trade_property_with_buildings(
    two_player_game: GameState, clock: FixedClock
) -> None:
    p1, p2 = two_player_game.players
    state = monopoly_brown(two_player_game, p1.id)
    state = with_phase(state, TurnPhase.POST_ROLL, current_player_id=p1.id)
    state, _ = apply_cmd(state, BuildHouse(player_id=p1.id, position=2), clock)

    with pytest.raises(IllegalMove, match="sell buildings"):
        propose_trade(
            state,
            p1.id,
            p2.id,
            TradeOffer(positions=(2,)),
            TradeOffer(),
            clock.now(),
        )


def test_expire_trade(two_player_game: GameState, clock: FixedClock) -> None:
    p1, p2 = two_player_game.players
    state = with_phase(two_player_game, TurnPhase.TRADE_NEGOTIATION, current_player_id=p1.id)
    trade = TradeState(
        id="trade-1",
        proposer_id=p1.id,
        target_id=p2.id,
        proposer_offer=TradeOffer(),
        target_request=TradeOffer(),
        status=TradeStatus.PENDING,
        expires_at=clock.now() - timedelta(seconds=1),
    )
    state = state.model_copy(update={"trade": trade})

    expired = expire_trade(state)
    assert expired.trade is None
    assert expired.turn.phase == TurnPhase.POST_ROLL


def test_propose_trade_via_engine(two_player_game: GameState, clock: FixedClock) -> None:
    p1, p2 = two_player_game.players
    state = with_phase(two_player_game, TurnPhase.POST_ROLL, current_player_id=p1.id)

    new_state, _ = apply_cmd(
        state,
        ProposeTrade(
            player_id=p1.id,
            target_id=p2.id,
            proposer_offer=TradeOffer(money=10),
            target_request=TradeOffer(),
        ),
        clock,
    )
    assert new_state.trade is not None


def test_respond_trade_via_engine(two_player_game: GameState, clock: FixedClock) -> None:
    p1, p2 = two_player_game.players
    state = with_phase(two_player_game, TurnPhase.POST_ROLL, current_player_id=p1.id)
    state, _ = apply_cmd(
        state,
        ProposeTrade(
            player_id=p1.id,
            target_id=p2.id,
            proposer_offer=TradeOffer(),
            target_request=TradeOffer(),
        ),
        clock,
    )
    trade_id = state.trade.id  # type: ignore[union-attr]

    rejected, _ = apply_cmd(
        state,
        RespondTrade(
            player_id=p2.id,
            trade_id=trade_id,
            response=TradeResponse.REJECT,
        ),
        clock,
    )
    assert rejected.trade is None


def test_fourth_trade_offer_rejected(two_player_game: GameState, clock: FixedClock) -> None:
    p1, p2 = two_player_game.players
    state = with_phase(two_player_game, TurnPhase.POST_ROLL, current_player_id=p1.id)

    # Propose and reject up to the per-turn cap; each proposal consumes one allowance.
    for _ in range(MAX_TRADE_OFFERS_PER_TURN):
        state = propose_trade(state, p1.id, p2.id, TradeOffer(), TradeOffer(), clock.now())
        trade_id = state.trade.id  # type: ignore[union-attr]
        state = respond_trade(state, p2.id, trade_id, TradeResponse.REJECT, None, clock.now())

    assert state.turn.trade_offers_made == MAX_TRADE_OFFERS_PER_TURN
    with pytest.raises(IllegalMove, match="limit reached"):
        propose_trade(state, p1.id, p2.id, TradeOffer(), TradeOffer(), clock.now())


def test_trade_counter_resets_next_turn(two_player_game: GameState, clock: FixedClock) -> None:
    p1, p2 = two_player_game.players
    state = with_phase(two_player_game, TurnPhase.POST_ROLL, current_player_id=p1.id)

    state = propose_trade(state, p1.id, p2.id, TradeOffer(), TradeOffer(), clock.now())
    trade_id = state.trade.id  # type: ignore[union-attr]
    state = respond_trade(state, p2.id, trade_id, TradeResponse.REJECT, None, clock.now())
    assert state.turn.trade_offers_made == 1

    ended, _ = apply_cmd(state, EndTurn(player_id=p1.id), clock)
    assert ended.turn.current_player_id == p2.id
    assert ended.turn.turn_number == state.turn.turn_number + 1
    assert ended.turn.trade_offers_made == 0


def test_counter_offer_does_not_consume_allowance(
    two_player_game: GameState, clock: FixedClock
) -> None:
    p1, p2 = two_player_game.players
    state = with_phase(two_player_game, TurnPhase.POST_ROLL, current_player_id=p1.id)

    state = propose_trade(state, p1.id, p2.id, TradeOffer(money=50), TradeOffer(), clock.now())
    assert state.turn.trade_offers_made == 1

    trade_id = state.trade.id  # type: ignore[union-attr]
    countered = respond_trade(
        state, p2.id, trade_id, TradeResponse.COUNTER, TradeOffer(money=100), clock.now()
    )
    # The target's counter is a response, not a new proposal, so the proposer's
    # per-turn allowance is unchanged.
    assert countered.turn.trade_offers_made == 1


def test_can_trade_false_at_limit(two_player_game: GameState, clock: FixedClock) -> None:
    p1, _ = two_player_game.players
    below = with_phase(
        two_player_game,
        TurnPhase.POST_ROLL,
        current_player_id=p1.id,
        trade_offers_made=MAX_TRADE_OFFERS_PER_TURN - 1,
    )
    assert compute_actions(below, p1.id).can_trade is True

    at_limit = with_phase(
        two_player_game,
        TurnPhase.POST_ROLL,
        current_player_id=p1.id,
        trade_offers_made=MAX_TRADE_OFFERS_PER_TURN,
    )
    assert compute_actions(at_limit, p1.id).can_trade is False


def test_advancing_turn_off_player_resets_trade_counter(
    two_player_game: GameState, clock: FixedClock
) -> None:
    p1, p2 = two_player_game.players
    state = with_phase(
        two_player_game,
        TurnPhase.POST_ROLL,
        current_player_id=p1.id,
        trade_offers_made=2,
    )
    # Shared turn-advance path used by turn-timeout and elimination.
    advanced = advance_turn_off_player(state, p1.id)
    assert advanced.turn.current_player_id == p2.id
    assert advanced.turn.trade_offers_made == 0
