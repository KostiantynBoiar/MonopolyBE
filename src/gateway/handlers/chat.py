from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from pydantic import TypeAdapter

from protocol.ws.envelope import RawEnvelope, make_outbound
from protocol.ws.messages import (
    ChatMessagePayload,
    ChatSendPayload,
    StickerMessagePayload,
    StickerSendPayload,
)

if TYPE_CHECKING:
    from gateway.backplane import Backplane
    from gateway.connection import Connection

_chat_send_adapter: TypeAdapter[ChatSendPayload] = TypeAdapter(ChatSendPayload)
_sticker_send_adapter: TypeAdapter[StickerSendPayload] = TypeAdapter(StickerSendPayload)


async def handle_chat_send(
    conn: Connection,
    envelope: RawEnvelope,
    backplane: Backplane,
) -> None:
    payload = _chat_send_adapter.validate_python(envelope.payload)
    outbound = make_outbound(
        "chat.message",
        ChatMessagePayload(
            message_id=uuid4().hex,
            from_user_id=conn.user_id,
            display_name=conn.display_name,
            text=payload.text,
            ts=datetime.now(UTC),
        ),
    )
    await backplane.publish(conn.session_id, outbound)


async def handle_sticker_send(
    conn: Connection,
    envelope: RawEnvelope,
    backplane: Backplane,
) -> None:
    payload = _sticker_send_adapter.validate_python(envelope.payload)
    outbound = make_outbound(
        "chat.sticker",
        StickerMessagePayload(
            message_id=uuid4().hex,
            from_user_id=conn.user_id,
            display_name=conn.display_name,
            sticker_url=payload.sticker_url,
            ts=datetime.now(UTC),
        ),
    )
    await backplane.publish(conn.session_id, outbound)


async def handle_pong(
    conn: Connection,
    envelope: RawEnvelope,
    backplane: Backplane,
) -> None:
    conn.last_pong_ts = datetime.now(UTC)
