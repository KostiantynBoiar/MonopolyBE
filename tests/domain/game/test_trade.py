from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from domain.game.enums import TradeResponse, TradeStatus, TurnPhase
from domain.game.exceptions import IllegalMove
from domain.game.rng import FixedClock
from domain.game.rules.trade import expire_trade, propose_trade, respond_trade
from domain.game.schemas.commands import BuildHouse, ProposeTrade, RespondTrade
from domain.game.schemas.state import TradeOffer, TradeState
from tests.domain.game.conftest import apply_cmd, monopoly_brown, with_phase


def test_propose_trade(two_player_game: GameState, clock: FixedClock) -> None:
    p1, p2 = two_player_game.players
    # p1 owns Mediterranean (pos 1) via monopoly_brown; offer it to p2 for money.
    state = monopoly_brown(two_player_game, p1.id)
    state = with_phase(state, TurnPhase.POST_ROLL, current_player_id=p1.id)

    new_state = propose_trade(
        state,
        p1.id,
        p2.id,
        TradeOffer(money=0, positions=(1,), get_out_of_jail_cards=0),
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
        TradeOffer(money=0, positions=(1,), get_out_of_jail_cards=0),
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
    assert accepted.spaces[1].owner_id == p2.id
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


def test_cannot_trade_property_with_buildings(two_player_game: GameState, clock: FixedClock) -> None:
    p1, p2 = two_player_game.players
    state = monopoly_brown(two_player_game, p1.id)
    state = with_phase(state, TurnPhase.POST_ROLL, current_player_id=p1.id)
    state, _ = apply_cmd(state, BuildHouse(player_id=p1.id, position=1), clock)

    with pytest.raises(IllegalMove, match="sell buildings"):
        propose_trade(
            state,
            p1.id,
            p2.id,
            TradeOffer(positions=(1,)),
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
