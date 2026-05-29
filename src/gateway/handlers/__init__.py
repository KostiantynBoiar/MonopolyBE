from __future__ import annotations

from collections.abc import Awaitable, Callable

from gateway.handlers.chat import handle_chat_send, handle_pong, handle_sticker_send
from gateway.handlers.game import (
    handle_game_buy_property,
    handle_game_end_turn,
    handle_game_pass_buy,
    handle_game_roll_dice,
)

HandlerFunc = Callable[..., Awaitable[None]]

HANDLERS: dict[str, HandlerFunc] = {
    "chat.send": handle_chat_send,
    "chat.sticker_send": handle_sticker_send,
    "connection.pong": handle_pong,
    "game.roll_dice": handle_game_roll_dice,
    "game.buy_property": handle_game_buy_property,
    "game.pass_buy": handle_game_pass_buy,
    "game.end_turn": handle_game_end_turn,
}
