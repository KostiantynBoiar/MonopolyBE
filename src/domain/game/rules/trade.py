from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from domain.game.constants import MAX_TRADE_OFFERS_PER_TURN, TRADE_DURATION_MS
from domain.game.enums import TradeResponse, TradeStatus, TurnPhase
from domain.game.exceptions import IllegalMove
from domain.game.schemas.state import GameState, PlayerState, SpaceOwnership, TradeOffer, TradeState
from domain.game.rules.helpers import (
    get_player_by_id_from_state,
    refresh_all_net_worth,
    replace_space,
    space_at,
)


def validate_trade_offer(state: GameState, player_id: str, offer: TradeOffer) -> None:
    player = get_player_by_id_from_state(state, player_id)
    if offer.money > player.balance:
        raise IllegalMove("insufficient money in trade offer")
    if offer.get_out_of_jail_cards > player.get_out_of_jail_cards:
        raise IllegalMove("insufficient jail cards in trade offer")
    for pos in offer.positions:
        ownership = space_at(state.spaces, pos)
        if ownership.owner_id != player_id:
            raise IllegalMove("cannot trade property you do not own")
        if ownership.houses > 0 or ownership.has_hotel:
            raise IllegalMove("must sell buildings before trading property")


def propose_trade(
    state: GameState,
    proposer_id: str,
    target_id: str,
    proposer_offer: TradeOffer,
    target_request: TradeOffer,
    clock_now: datetime,
) -> GameState:
    if proposer_id == target_id:
        raise IllegalMove("cannot trade with yourself")
    if state.trade is not None:
        raise IllegalMove("a trade is already in progress")
    if state.turn.trade_offers_made >= MAX_TRADE_OFFERS_PER_TURN:
        raise IllegalMove("trade offer limit reached for this turn")
    get_player_by_id_from_state(state, target_id)
    validate_trade_offer(state, proposer_id, proposer_offer)
    validate_trade_offer(state, target_id, target_request)

    trade = TradeState(
        id=uuid4().hex,
        proposer_id=proposer_id,
        target_id=target_id,
        proposer_offer=proposer_offer,
        target_request=target_request,
        status=TradeStatus.PENDING,
        expires_at=clock_now + timedelta(milliseconds=TRADE_DURATION_MS),
    )
    turn = state.turn.model_copy(
        update={
            "phase": TurnPhase.TRADE_NEGOTIATION,
            "trade_offers_made": state.turn.trade_offers_made + 1,
        }
    )
    return state.model_copy(update={"trade": trade, "turn": turn})


def respond_trade(
    state: GameState,
    player_id: str,
    trade_id: str,
    response: TradeResponse,
    counter_offer: TradeOffer | None,
    clock_now: datetime,
) -> GameState:
    if state.trade is None or state.trade.id != trade_id:
        raise IllegalMove("trade not found")

    trade = state.trade
    if response == TradeResponse.REJECT:
        turn = state.turn.model_copy(update={"phase": TurnPhase.POST_ROLL})
        return state.model_copy(update={"trade": None, "turn": turn})

    if response == TradeResponse.COUNTER:
        if player_id != trade.target_id or counter_offer is None:
            raise IllegalMove("invalid counter offer")
        validate_trade_offer(state, trade.proposer_id, counter_offer)
        new_trade = trade.model_copy(
            update={
                "target_request": counter_offer,
                "status": TradeStatus.COUNTERED,
                "expires_at": clock_now + timedelta(milliseconds=TRADE_DURATION_MS),
            }
        )
        return state.model_copy(update={"trade": new_trade})

    if response == TradeResponse.ACCEPT:
        responder_id = player_id
        if responder_id not in (trade.proposer_id, trade.target_id):
            raise IllegalMove("not a party to this trade")
        return _execute_trade(state, trade)

    raise IllegalMove("unknown trade response")


def expire_trade(state: GameState) -> GameState:
    if state.trade is None:
        return state
    turn = state.turn.model_copy(update={"phase": TurnPhase.POST_ROLL})
    return state.model_copy(update={"trade": None, "turn": turn})


def _execute_trade(state: GameState, trade: TradeState) -> GameState:
    validate_trade_offer(state, trade.proposer_id, trade.proposer_offer)
    validate_trade_offer(state, trade.target_id, trade.target_request)

    proposer = get_player_by_id_from_state(state, trade.proposer_id)
    target = get_player_by_id_from_state(state, trade.target_id)
    players = list(state.players)
    spaces = list(state.spaces)

    p_idx = next(i for i, p in enumerate(players) if p.id == proposer.id)
    t_idx = next(i for i, p in enumerate(players) if p.id == target.id)

    proposer, target, spaces = _transfer_offer(
        proposer, target, spaces, trade.proposer_offer, trade.target_id, trade.proposer_id
    )
    target, proposer, spaces = _transfer_offer(
        target, proposer, spaces, trade.target_request, trade.proposer_id, trade.target_id
    )

    net_delta = trade.target_request.money - trade.proposer_offer.money
    proposer = proposer.model_copy(update={"balance": proposer.balance + net_delta})
    target = target.model_copy(update={"balance": target.balance - net_delta})

    jail_delta = (
        trade.target_request.get_out_of_jail_cards - trade.proposer_offer.get_out_of_jail_cards
    )
    proposer = proposer.model_copy(
        update={"get_out_of_jail_cards": proposer.get_out_of_jail_cards + jail_delta}
    )
    target = target.model_copy(
        update={"get_out_of_jail_cards": target.get_out_of_jail_cards - jail_delta}
    )

    players[p_idx] = proposer
    players[t_idx] = target

    turn = state.turn.model_copy(update={"phase": TurnPhase.POST_ROLL})
    return state.model_copy(
        update={
            "players": refresh_all_net_worth(
                state.model_copy(update={"players": tuple(players), "spaces": tuple(spaces)})
            ),
            "spaces": tuple(spaces),
            "trade": None,
            "turn": turn,
        }
    )


def _transfer_offer(
    giver: PlayerState,
    receiver: PlayerState,
    spaces: list[SpaceOwnership],
    offer: TradeOffer,
    receiver_id: str,
    giver_id: str,
) -> tuple[PlayerState, PlayerState, list[SpaceOwnership]]:
    giver_owned = set(giver.owned_positions)
    receiver_owned = set(receiver.owned_positions)
    for pos in offer.positions:
        giver_owned.discard(pos)
        receiver_owned.add(pos)
        replace_space(
            spaces, pos, space_at(spaces, pos).model_copy(update={"owner_id": receiver_id})
        )
    giver = giver.model_copy(update={"owned_positions": tuple(sorted(giver_owned))})
    receiver = receiver.model_copy(update={"owned_positions": tuple(sorted(receiver_owned))})
    return giver, receiver, spaces
