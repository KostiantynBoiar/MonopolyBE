from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import TypeAdapter

from application.services.game_service import GameService
from core.exceptions import GameNotFoundError, GameVersionConflictError
from domain.game.exceptions import IllegalMove
from domain.game.enums import GameStatus, TradeResponse
from domain.game.schemas.commands import (
    BuildHouse,
    BuyProperty,
    DeclareBankruptcy,
    EndTurn,
    Mortgage,
    PassBuy,
    PayJailFine,
    PlaceBid,
    ProposeTrade,
    RespondTrade,
    RollDice,
    SellHouse,
    Surrender,
    Unmortgage,
    UseJailCard,
)
from domain.game.schemas.state import TradeOffer
from protocol.ws.envelope import RawEnvelope, make_outbound
from protocol.ws.schemas import (
    AnimationContinuePayload,
    BuildHousePayload,
    BuyPropertyPayload,
    DeclareBankruptcyPayload,
    EndTurnPayload,
    MortgagePayload,
    PassBuyPayload,
    PayJailFinePayload,
    PlaceBidPayload,
    ProposeTradePayload,
    RespondTradePayload,
    RollDicePayload,
    SellHousePayload,
    SurrenderPayload,
    UnmortgagePayload,
    UseJailCardPayload,
)

if TYPE_CHECKING:
    from gateway.backplane import Backplane
    from gateway.connection import Connection

_roll_adapter: TypeAdapter[RollDicePayload] = TypeAdapter(RollDicePayload)
_buy_adapter: TypeAdapter[BuyPropertyPayload] = TypeAdapter(BuyPropertyPayload)
_pass_buy_adapter: TypeAdapter[PassBuyPayload] = TypeAdapter(PassBuyPayload)
_end_turn_adapter: TypeAdapter[EndTurnPayload] = TypeAdapter(EndTurnPayload)
_pay_jail_adapter: TypeAdapter[PayJailFinePayload] = TypeAdapter(PayJailFinePayload)
_use_jail_adapter: TypeAdapter[UseJailCardPayload] = TypeAdapter(UseJailCardPayload)
_build_adapter: TypeAdapter[BuildHousePayload] = TypeAdapter(BuildHousePayload)
_sell_adapter: TypeAdapter[SellHousePayload] = TypeAdapter(SellHousePayload)
_mortgage_adapter: TypeAdapter[MortgagePayload] = TypeAdapter(MortgagePayload)
_unmortgage_adapter: TypeAdapter[UnmortgagePayload] = TypeAdapter(UnmortgagePayload)
_propose_trade_adapter: TypeAdapter[ProposeTradePayload] = TypeAdapter(ProposeTradePayload)
_respond_trade_adapter: TypeAdapter[RespondTradePayload] = TypeAdapter(RespondTradePayload)
_place_bid_adapter: TypeAdapter[PlaceBidPayload] = TypeAdapter(PlaceBidPayload)
_declare_bankruptcy_adapter: TypeAdapter[DeclareBankruptcyPayload] = TypeAdapter(
    DeclareBankruptcyPayload
)
_animation_continue_adapter: TypeAdapter[AnimationContinuePayload] = TypeAdapter(
    AnimationContinuePayload
)
_surrender_adapter: TypeAdapter[SurrenderPayload] = TypeAdapter(SurrenderPayload)


def _game_service(conn: Connection) -> GameService:
    return GameService.from_db(conn.websocket.app.state.mongo.db)


async def _apply_and_publish(
    conn: Connection,
    backplane: Backplane,
    command: RollDice
    | BuyProperty
    | PassBuy
    | EndTurn
    | PayJailFine
    | UseJailCard
    | BuildHouse
    | SellHouse
    | Mortgage
    | Unmortgage
    | ProposeTrade
    | RespondTrade
    | PlaceBid
    | DeclareBankruptcy
    | Surrender,
) -> None:
    service = _game_service(conn)
    try:
        state, timeline = await service.apply_intent(conn.session_id, conn.user_id, command)
    except IllegalMove as exc:
        await conn.send_error("illegal_action", exc.message)
        return
    except GameNotFoundError:
        await conn.send_error("illegal_action", "no active game")
        return
    except GameVersionConflictError:
        await conn.send_error("illegal_action", "state conflict; resync from latest snapshot")
        return

    # Per-viewer broadcast: each member receives a snapshot scoped to themselves, plus the
    # (shared) animation timeline describing how this state was reached.
    await backplane.publish_game_state(conn.session_id, state.model_dump(mode="json"), timeline)

    if state.status == GameStatus.FINISHED:
        await _finish_session(conn, backplane, state)


async def _finish_session(conn: Connection, backplane: Backplane, state) -> None:
    """Flip the session to finished, apply ratings if ranked, and broadcast session.updated."""
    from application.services.session_service import SessionService
    from application.services.rating_service import RatingService
    from api.sessions.router import _broadcast_session_updated  # local import avoids cycle

    db = conn.websocket.app.state.mongo.db
    session = await SessionService.from_db(db).mark_finished(conn.session_id)
    if session is not None:
        if session.ranked:
            await RatingService.from_db(db).apply_for_finished_game(conn.session_id, state)
        await _broadcast_session_updated(backplane, session)


async def handle_game_roll_dice(
    conn: Connection,
    envelope: RawEnvelope,
    backplane: Backplane,
) -> None:
    _roll_adapter.validate_python(envelope.payload)
    await _apply_and_publish(conn, backplane, RollDice(player_id=""))


async def handle_game_buy_property(
    conn: Connection,
    envelope: RawEnvelope,
    backplane: Backplane,
) -> None:
    payload = _buy_adapter.validate_python(envelope.payload)
    await _apply_and_publish(
        conn,
        backplane,
        BuyProperty(player_id="", position=payload.position),
    )


async def handle_game_pass_buy(
    conn: Connection,
    envelope: RawEnvelope,
    backplane: Backplane,
) -> None:
    _pass_buy_adapter.validate_python(envelope.payload)
    await _apply_and_publish(conn, backplane, PassBuy(player_id=""))


async def handle_game_end_turn(
    conn: Connection,
    envelope: RawEnvelope,
    backplane: Backplane,
) -> None:
    _end_turn_adapter.validate_python(envelope.payload)
    await _apply_and_publish(conn, backplane, EndTurn(player_id=""))


async def handle_game_pay_jail_fine(
    conn: Connection,
    envelope: RawEnvelope,
    backplane: Backplane,
) -> None:
    _pay_jail_adapter.validate_python(envelope.payload)
    await _apply_and_publish(conn, backplane, PayJailFine(player_id=""))


async def handle_game_use_jail_card(
    conn: Connection,
    envelope: RawEnvelope,
    backplane: Backplane,
) -> None:
    _use_jail_adapter.validate_python(envelope.payload)
    await _apply_and_publish(conn, backplane, UseJailCard(player_id=""))


async def handle_game_build_house(
    conn: Connection,
    envelope: RawEnvelope,
    backplane: Backplane,
) -> None:
    payload = _build_adapter.validate_python(envelope.payload)
    await _apply_and_publish(
        conn, backplane, BuildHouse(player_id="", position=payload.position)
    )


async def handle_game_sell_house(
    conn: Connection,
    envelope: RawEnvelope,
    backplane: Backplane,
) -> None:
    payload = _sell_adapter.validate_python(envelope.payload)
    await _apply_and_publish(
        conn, backplane, SellHouse(player_id="", position=payload.position)
    )


async def handle_game_mortgage(
    conn: Connection,
    envelope: RawEnvelope,
    backplane: Backplane,
) -> None:
    payload = _mortgage_adapter.validate_python(envelope.payload)
    await _apply_and_publish(
        conn, backplane, Mortgage(player_id="", position=payload.position)
    )


async def handle_game_unmortgage(
    conn: Connection,
    envelope: RawEnvelope,
    backplane: Backplane,
) -> None:
    payload = _unmortgage_adapter.validate_python(envelope.payload)
    await _apply_and_publish(
        conn, backplane, Unmortgage(player_id="", position=payload.position)
    )


async def handle_game_propose_trade(
    conn: Connection,
    envelope: RawEnvelope,
    backplane: Backplane,
) -> None:
    payload = _propose_trade_adapter.validate_python(envelope.payload)

    def _to_offer(offer) -> TradeOffer:
        return TradeOffer(
            money=offer.money,
            positions=tuple(offer.positions),
            get_out_of_jail_cards=offer.get_out_of_jail_cards,
        )

    await _apply_and_publish(
        conn,
        backplane,
        ProposeTrade(
            player_id="",
            target_id=payload.target_id,
            proposer_offer=_to_offer(payload.proposer_offer),
            target_request=_to_offer(payload.target_request),
        ),
    )


async def handle_game_respond_trade(
    conn: Connection,
    envelope: RawEnvelope,
    backplane: Backplane,
) -> None:
    payload = _respond_trade_adapter.validate_python(envelope.payload)
    counter = None
    if payload.counter_offer is not None:
        counter = TradeOffer(
            money=payload.counter_offer.money,
            positions=tuple(payload.counter_offer.positions),
            get_out_of_jail_cards=payload.counter_offer.get_out_of_jail_cards,
        )
    await _apply_and_publish(
        conn,
        backplane,
        RespondTrade(
            player_id="",
            trade_id=payload.trade_id,
            response=TradeResponse(payload.response),
            counter_offer=counter,
        ),
    )


async def handle_game_place_bid(
    conn: Connection,
    envelope: RawEnvelope,
    backplane: Backplane,
) -> None:
    payload = _place_bid_adapter.validate_python(envelope.payload)
    await _apply_and_publish(
        conn, backplane, PlaceBid(player_id="", amount=payload.amount)
    )


async def handle_game_declare_bankruptcy(
    conn: Connection,
    envelope: RawEnvelope,
    backplane: Backplane,
) -> None:
    _declare_bankruptcy_adapter.validate_python(envelope.payload)
    await _apply_and_publish(conn, backplane, DeclareBankruptcy(player_id=""))


async def handle_game_surrender(
    conn: Connection,
    envelope: RawEnvelope,
    backplane: Backplane,
) -> None:
    _surrender_adapter.validate_python(envelope.payload)
    await _apply_and_publish(conn, backplane, Surrender(player_id=""))


async def handle_game_animation_continue(
    conn: Connection,
    envelope: RawEnvelope,
    backplane: Backplane,
) -> None:
    """Resume a paused animation. This is NOT a game command — it never touches the engine
    or game state. We authorize the sender (only the affected/current player) then
    re-broadcast a continue signal so every client un-pauses the same gate together."""
    payload = _animation_continue_adapter.validate_python(envelope.payload)
    service = _game_service(conn)
    allowed = await service.authorize_continue(
        conn.session_id, conn.user_id, payload.interaction_id
    )
    if not allowed:
        await conn.send_error("illegal_action", "not allowed to continue this animation")
        return
    msg = make_outbound(
        "game.animation_continue",
        AnimationContinuePayload(interaction_id=payload.interaction_id),
    )
    await backplane.publish(conn.session_id, msg)
