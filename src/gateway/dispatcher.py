from __future__ import annotations

import json

from gateway.backplane import Backplane
from gateway.connection import Connection
import structlog
from pydantic import ValidationError

from core.constants import WS_PROTOCOL_VERSION
from gateway.handlers import HANDLERS
from protocol.ws.envelope import RawEnvelope

logger = structlog.get_logger(__name__)


async def dispatch(conn: Connection, raw: str, backplane: Backplane) -> None:
    log = logger.bind(
        session_id=conn.session_id,
        user_id=conn.user_id,
        connection_id=conn.connection_id,
    )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        await conn.send_error("malformed", "Invalid JSON")
        return

    try:
        envelope = RawEnvelope.model_validate(data)
    except ValidationError as exc:
        await conn.send_error("malformed", "Invalid message shape")
        log.debug("dispatch_malformed", errors=exc.error_count())
        return

    if envelope.v != WS_PROTOCOL_VERSION:
        await conn.send_error_then_close(
            "unsupported_version",
            f"Expected protocol version {WS_PROTOCOL_VERSION}, got {envelope.v}",
            4400,
        )
        return

    handler = HANDLERS.get(envelope.type)
    if handler is None:
        await conn.send_error("unknown_type", f"Unknown message type: {envelope.type}")
        log.debug("dispatch_unknown_type", msg_type=envelope.type)
        return

    try:
        await handler(conn, envelope, backplane)
    except ValidationError as exc:
        await conn.send_error("malformed", "Invalid payload for message type")
        log.debug("dispatch_payload_invalid", msg_type=envelope.type, errors=exc.error_count())
    except Exception:
        log.exception("dispatch_handler_error", msg_type=envelope.type)
        await conn.send_error("internal", "Internal server error")
