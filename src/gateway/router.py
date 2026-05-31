import structlog
from fastapi import APIRouter, WebSocket

from application.services.game_service import GameService
from application.services.session_service import SessionService
from core.config import get_settings
from core.exceptions import NotMemberError, UnauthorizedError
from core.security import decode_access_token
from domain.session.schemas import SessionStatus
from gateway.backplane import Backplane
from gateway.connection import Connection
from gateway.manager import ConnectionManager
from protocol.ws.envelope import make_outbound
from protocol.ws.schemas import WelcomePayload

logger = structlog.get_logger(__name__)

ws_router = APIRouter()


async def _cleanup_on_disconnect(
    manager: ConnectionManager,
    backplane: Backplane,
    session_service: SessionService,
    session_id: str,
    user_id: str,
) -> None:
    """When the last connection for a user drops from a WAITING room, treat it as a
    leave: remove the member, reassign host if needed, and delete the room when empty.
    In-progress games are left untouched (players are expected to reconnect)."""
    # Local presence only (single-instance assumption — see docs/game-protocol limitations).
    if any(c.user_id == user_id for c in manager.local_connections(session_id)):
        return
    try:
        session = await session_service.assert_member(session_id, user_id)
        if session.status != SessionStatus.WAITING:
            return
        remaining = await session_service.leave(session_id, user_id)
        if remaining is not None:
            from api.sessions.router import _broadcast_session_updated

            await _broadcast_session_updated(backplane, remaining)
    except NotMemberError:
        return
    except Exception:
        logger.exception("disconnect_cleanup_failed", session_id=session_id, user_id=user_id)


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
        session = await session_service.assert_member(session_id, user_id)
    except NotMemberError:
        await websocket.close(code=4403)
        return

    member = session.get_member(user_id)
    display_name = member.display_name if member else user_id

    await websocket.accept(subprotocol="bearer")

    manager: ConnectionManager = websocket.app.state.manager
    backplane: Backplane = websocket.app.state.backplane

    conn = Connection(websocket, session_id, user_id, display_name)
    manager.register(conn)
    await backplane.subscribe(session_id)

    seq_start = await backplane.current_seq(session_id)
    welcome = make_outbound(
        "system.welcome",
        WelcomePayload(session_id=session_id, your_seq_start=seq_start),
    )
    conn.enqueue(welcome)

    game_service = GameService.from_db(websocket.app.state.mongo.db, get_settings())
    game_state = await game_service.get_active_game(session_id)
    if game_state is not None:
        conn.enqueue(game_service.snapshot_message(game_state, viewer_user_id=user_id))

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
        await _cleanup_on_disconnect(manager, backplane, session_service, session_id, user_id)
        logger.info(
            "ws_disconnected",
            session_id=session_id,
            user_id=user_id,
            connection_id=conn.connection_id,
        )
