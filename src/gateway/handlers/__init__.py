from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable

from gateway.handlers.chat import handle_chat_send, handle_pong, handle_sticker_send

if TYPE_CHECKING:
    from gateway.backplane import Backplane
    from gateway.connection import Connection
    from protocol.ws.envelope import RawEnvelope

    HandlerFunc = Callable[[Connection, RawEnvelope, Backplane], Awaitable[None]]

HANDLERS: dict[str, Any] = {
    "chat.send": handle_chat_send,
    "chat.sticker_send": handle_sticker_send,
    "connection.pong": handle_pong,
}
