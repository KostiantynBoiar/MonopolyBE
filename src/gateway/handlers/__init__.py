from __future__ import annotations

from collections.abc import Awaitable, Callable

from gateway.handlers.chat import handle_chat_send, handle_pong, handle_sticker_send
from gateway.handlers.game import (
    handle_game_animation_continue,
    handle_game_build_house,
    handle_game_buy_property,
    handle_game_declare_bankruptcy,
    handle_game_end_turn,
    handle_game_mortgage,
    handle_game_pass_buy,
    handle_game_pay_jail_fine,
    handle_game_place_bid,
    handle_game_propose_trade,
    handle_game_respond_trade,
    handle_game_roll_dice,
    handle_game_sell_house,
    handle_game_unmortgage,
    handle_game_use_jail_card,
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
    "game.pay_jail_fine": handle_game_pay_jail_fine,
    "game.use_jail_card": handle_game_use_jail_card,
    "game.build_house": handle_game_build_house,
    "game.sell_house": handle_game_sell_house,
    "game.mortgage": handle_game_mortgage,
    "game.unmortgage": handle_game_unmortgage,
    "game.propose_trade": handle_game_propose_trade,
    "game.respond_trade": handle_game_respond_trade,
    "game.place_bid": handle_game_place_bid,
    "game.declare_bankruptcy": handle_game_declare_bankruptcy,
    "game.animation_continue": handle_game_animation_continue,
}
