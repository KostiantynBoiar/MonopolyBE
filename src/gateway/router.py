import structlog
from fastapi import APIRouter, WebSocket

from application.services.session_service import NotMemberError, SessionService
from core.config import get_settings
from core.exceptions import NotFoundError, UnauthorizedError
from core.security import decode_access_token
from gateway.backplane import Backplane
from gateway.connection import Connection
from gateway.manager import ConnectionManager
from protocol.ws.envelope import make_outbound
from protocol.ws.messages import WelcomePayload

logger = structlog.get_logger(__name__)

ws_router = APIRouter()


def _extract_token(websocket: WebSocket) -> str | None:
    header = websocket.headers.get("sec-websocket-protocol", "")
    parts = [p.strip() for p in header.split(",")]
    if len(parts) >= 2 and parts[0] == "bearer":
        return parts[1]
    return None


@ws_router.websocket("/ws/sessions/{session_id}")
async def ws_endpoint(websocket: WebSocket, session_id: str) -> None:
    settings = get_settings()

    token = _extract_token(websocket)
    if token is None:
        await websocket.close(code=4401)
        return

    try:
        user_id = decode_access_token(token, settings)
    except UnauthorizedError:
        await websocket.close(code=4401)
        return

    session_service = SessionService.from_db(websocket.app.state.mongo.db)
    try:
        await session_service.assert_member(session_id, user_id)
    except (NotFoundError, NotMemberError):
        await websocket.close(code=4403)
        return

    await websocket.accept()

    manager: ConnectionManager = websocket.app.state.manager
    backplane: Backplane = websocket.app.state.backplane

    conn = Connection(websocket, session_id, user_id)
    manager.register(conn)
    await backplane.subscribe(session_id)

    seq_start = await backplane.current_seq(session_id)
    welcome = make_outbound(
        "system.welcome",
        WelcomePayload(session_id=session_id, your_seq_start=seq_start),
    )
    conn.enqueue(welcome)

    logger.info(
        "ws_connected",
        session_id=session_id,
        user_id=user_id,
        connection_id=conn.connection_id,
    )

    try:
        await conn.run(backplane)
    finally:
        manager.unregister(conn)
        await backplane.unsubscribe(session_id)
        logger.info(
            "ws_disconnected",
            session_id=session_id,
            user_id=user_id,
            connection_id=conn.connection_id,
        )
