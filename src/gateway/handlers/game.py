from __future__ import annotations

from pydantic import TypeAdapter

from application.services.game_service import GameService
from core.exceptions import GameNotFoundError, GameVersionConflictError
from domain.game.exceptions import IllegalMove
from domain.game.schemas.commands import BuyProperty, EndTurn, PassBuy, RollDice
from protocol.ws.envelope import RawEnvelope
from protocol.ws.schemas import (
    BuyPropertyPayload,
    EndTurnPayload,
    PassBuyPayload,
    RollDicePayload,
)

_roll_adapter: TypeAdapter[RollDicePayload] = TypeAdapter(RollDicePayload)
_buy_adapter: TypeAdapter[BuyPropertyPayload] = TypeAdapter(BuyPropertyPayload)
_pass_buy_adapter: TypeAdapter[PassBuyPayload] = TypeAdapter(PassBuyPayload)
_end_turn_adapter: TypeAdapter[EndTurnPayload] = TypeAdapter(EndTurnPayload)


def _game_service(conn: Connection) -> GameService:
    return GameService.from_db(conn.websocket.app.state.mongo.db)


async def _apply_and_publish(
    conn: Connection,
    backplane: Backplane,
    command: RollDice | BuyProperty | PassBuy | EndTurn,
) -> None:
    service = _game_service(conn)
    try:
        state = await service.apply_intent(conn.session_id, conn.user_id, command)
    except IllegalMove as exc:
        await conn.send_error("illegal_action", exc.message)
        return
    except GameNotFoundError:
        await conn.send_error("illegal_action", "no active game")
        return
    except GameVersionConflictError:
        await conn.send_error("illegal_action", "state conflict; resync from latest snapshot")
        return

    outbound = service.snapshot_message(state)
    await backplane.publish(conn.session_id, outbound)


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
