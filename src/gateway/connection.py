from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog
from starlette.websockets import WebSocket, WebSocketDisconnect

from gateway.backpressure import SendQueue
from gateway.dispatcher import dispatch
from protocol.ws.envelope import make_outbound
from protocol.ws.errors import WsErrorCode
from protocol.ws.messages import ErrorPayload, PingPayload

if TYPE_CHECKING:
    from gateway.backplane import Backplane

logger = structlog.get_logger(__name__)

HEARTBEAT_INTERVAL_S = 20
HEARTBEAT_TIMEOUT_S = 25


class Connection:
    def __init__(
        self,
        websocket: WebSocket,
        session_id: str,
        user_id: str,
        display_name: str,
    ) -> None:
        self.websocket = websocket
        self.session_id = session_id
        self.user_id = user_id
        self.display_name = display_name
        self.connection_id = uuid4().hex
        self.last_pong_ts: datetime = datetime.now(UTC)
        self._queue = SendQueue()
        self._closed = False

    def enqueue(self, msg: dict[str, Any]) -> bool:
        return self._queue.put(msg)

    async def send_error(self, code: WsErrorCode, message: str) -> None:
        msg = make_outbound("system.error", ErrorPayload(code=code, message=message))
        ok = self._queue.put(msg)
        if not ok:
            logger.warning(
                "send_error_queue_full",
                session_id=self.session_id,
                user_id=self.user_id,
                connection_id=self.connection_id,
                error_code=code,
            )

    async def send_error_then_close(
        self, code: WsErrorCode, message: str, close_code: int
    ) -> None:
        """Send an error on the wire, then close (for fatal protocol errors)."""
        if self._closed:
            return
        msg = make_outbound("system.error", ErrorPayload(code=code, message=message))
        try:
            await self.websocket.send_text(json.dumps(msg))
        except Exception:
            pass
        await self.close(close_code)

    async def close(self, code: int) -> None:
        if self._closed:
            return
        self._closed = True
        self._queue.put_sentinel()
        try:
            await self.websocket.close(code=code)
        except Exception:
            pass

    async def run(self, backplane: Backplane) -> None:
        log = logger.bind(
            session_id=self.session_id,
            user_id=self.user_id,
            connection_id=self.connection_id,
        )
        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._send_loop(log), name="send-loop")
                tg.create_task(self._recv_loop(backplane, log), name="recv-loop")
                tg.create_task(self._heartbeat_loop(log), name="heartbeat")
        except* (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except* Exception as eg:
            log.exception("connection_task_error", errors=str(eg))
        finally:
            self._closed = True
            self._queue.put_sentinel()

    async def _send_loop(self, log: Any) -> None:
        while True:
            msg = await self._queue.get()
            if msg is None:
                break
            try:
                await self.websocket.send_text(json.dumps(msg))
            except WebSocketDisconnect:
                break
            except Exception:
                log.exception("send_loop_error")
                break

    async def _recv_loop(self, backplane: Backplane, log: Any) -> None:
        try:
            while True:
                text = await self.websocket.receive_text()
                await dispatch(self, text, backplane)
        except WebSocketDisconnect:
            log.info("connection_closed_by_client")

    async def _heartbeat_loop(self, log: Any) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_S)
            ping = make_outbound("connection.ping", PingPayload())
            ok = self._queue.put(ping)
            if not ok:
                log.warning("heartbeat_queue_full")
                await self.close(1011)
                return
            elapsed = (datetime.now(UTC) - self.last_pong_ts).total_seconds()
            if elapsed > HEARTBEAT_TIMEOUT_S:
                log.info("heartbeat_timeout", elapsed=elapsed)
                await self.close(1001)
                return
