import asyncio

import structlog
from fastapi import APIRouter, WebSocket

from application.services.game_service import GameService
from application.services.session_service import SessionService
from core.config import get_settings
from core.constants import WS_DISCONNECT_GRACE_S
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

# Grace period before a disconnected member is removed from a WAITING room. Avoids
# evicting players on transient drops — React StrictMode remounts, tab switches, brief
# network blips. Cancelled if they reconnect within the window. (Process-local, which is
# fine single-instance; see docs/game-protocol limitations.)
_pending_removals: dict[tuple[str, str], asyncio.Task] = {}


async def _remove_if_still_gone(
    manager: ConnectionManager,
    backplane: Backplane,
    session_service: SessionService,
    session_id: str,
    user_id: str,
) -> None:
    """Remove a member from a WAITING room iff they have no live connection here.
    Deletes the room when it empties; in-progress games are never touched."""
    if any(c.user_id == user_id for c in manager.local_connections(session_id)):
        return  # reconnected (or another tab is live)
    try:
        session = await session_service.assert_member(session_id, user_id)
    except NotMemberError:
        return
    if session.status != SessionStatus.WAITING:
        return
    remaining = await session_service.leave(session_id, user_id)
    if remaining is not None:
        from api.sessions.router import _broadcast_session_updated

        await _broadcast_session_updated(backplane, remaining)


async def _grace_then_remove(
    manager: ConnectionManager,
    backplane: Backplane,
    session_service: SessionService,
    session_id: str,
    user_id: str,
    key: tuple[str, str],
) -> None:
    try:
        await asyncio.sleep(WS_DISCONNECT_GRACE_S)
        await _remove_if_still_gone(manager, backplane, session_service, session_id, user_id)
    except asyncio.CancelledError:
        pass  # reconnected within the grace window
    except Exception:
        logger.exception("disconnect_cleanup_failed", session_id=session_id, user_id=user_id)
    finally:
        _pending_removals.pop(key, None)


def _schedule_removal(
    manager: ConnectionManager,
    backplane: Backplane,
    session_service: SessionService,
    session_id: str,
    user_id: str,
) -> None:
    """On disconnect: if the user has no other live connection here, schedule a
    grace-delayed removal (no-op if one is already pending)."""
    if any(c.user_id == user_id for c in manager.local_connections(session_id)):
        return
    key = (session_id, user_id)
    if key in _pending_removals:
        return
    _pending_removals[key] = asyncio.create_task(
        _grace_then_remove(manager, backplane, session_service, session_id, user_id, key)
    )


def _cancel_pending_removal(session_id: str, user_id: str) -> None:
    """On (re)connect: cancel any pending removal for this user+session."""
    task = _pending_removals.pop((session_id, user_id), None)
    if task is not None:
        task.cancel()


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

    # Echo the "bearer" subprotocol the client offered (Sec-WebSocket-Protocol:
    # bearer,<token>). Strict clients (Safari/Firefox) FAIL the connection if the server
    # accepts without selecting one of the offered subprotocols, which manifests as an
    # instant client-side handshake failure → reconnect storm. We only reach here when the
    # client offered "bearer,<token>" (we return 4401 above otherwise), so this is always
    # the correct selection.
    await websocket.accept(subprotocol="bearer")

    manager: ConnectionManager = websocket.app.state.manager
    backplane: Backplane = websocket.app.state.backplane

    conn = Connection(websocket, session_id, user_id, display_name)
    manager.register(conn)
    # Reconnected within the grace window → don't evict them.
    _cancel_pending_removal(session_id, user_id)
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
        _schedule_removal(manager, backplane, session_service, session_id, user_id)
        logger.info(
            "ws_disconnected",
            session_id=session_id,
            user_id=user_id,
            connection_id=conn.connection_id,
        )
