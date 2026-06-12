from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, cast

import structlog
from redis.asyncio import Redis
from redis.asyncio.client import PubSub

from gateway.manager import ConnectionManager

logger = structlog.get_logger(__name__)

# Internal envelope type carried over Redis for per-viewer game.state broadcasts.
# The full game state (incl. server-only deck order) travels server-to-server only;
# each node renders a client-safe, viewer-scoped frame for its local connections.
_GAME_STATE_BROADCAST = "__game_state_broadcast__"

# (state_dict, user_id, timeline) -> client game.state frame (without seq).
GameStateRenderer = Callable[[dict[str, Any], str, list[dict[str, Any]]], dict[str, Any]]


class Backplane:
    def __init__(self, redis_url: str, manager: ConnectionManager) -> None:
        self._url = redis_url
        self._manager = manager
        self._cmd: Redis | None = None
        self._pubsub_source: Redis | None = None
        self._pubsub: PubSub | None = None
        # session_id -> refcount of local connections subscribed
        self._subscriptions: dict[str, int] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._shutdown = False
        self._game_renderer: GameStateRenderer | None = None

    def set_game_state_renderer(self, renderer: GameStateRenderer) -> None:
        """Install the per-viewer renderer used to turn a broadcast game state into a
        client-safe, viewer-scoped game.state frame on the receiving node."""
        self._game_renderer = renderer

    async def start(self) -> None:
        # health_check_interval keeps the long-lived pub/sub connection alive and
        # lets redis-py detect a stale socket instead of hanging on idle reads.
        self._cmd = Redis.from_url(self._url, decode_responses=True, health_check_interval=30)
        self._pubsub_source = Redis.from_url(
            self._url, decode_responses=True, health_check_interval=30
        )
        self._pubsub = self._pubsub_source.pubsub()
        self._reader_task = asyncio.create_task(self._reader_loop(), name="backplane-reader")

    async def stop(self) -> None:
        self._shutdown = True
        if self._reader_task:
            self._reader_task.cancel()
            await asyncio.gather(self._reader_task, return_exceptions=True)
        if self._pubsub:
            await cast(Any, self._pubsub).aclose()
        if self._pubsub_source:
            await cast(Any, self._pubsub_source).aclose()
        if self._cmd:
            await cast(Any, self._cmd).aclose()

    async def subscribe(self, session_id: str) -> None:
        count = self._subscriptions.get(session_id, 0)
        if count == 0 and self._pubsub is not None:
            await self._pubsub.subscribe(f"session:{session_id}")
        self._subscriptions[session_id] = count + 1

    async def unsubscribe(self, session_id: str) -> None:
        count = self._subscriptions.get(session_id, 0)
        if count <= 1:
            if self._pubsub is not None:
                await self._pubsub.unsubscribe(f"session:{session_id}")
            self._subscriptions.pop(session_id, None)
        else:
            self._subscriptions[session_id] = count - 1

    async def publish(self, session_id: str, msg: dict[str, Any]) -> None:
        if self._cmd is None:
            return
        seq = await self._cmd.incr(f"seq:{session_id}")
        msg["seq"] = seq
        await self._cmd.publish(f"session:{session_id}", json.dumps(msg))

    async def publish_game_state(
        self,
        session_id: str,
        state_dict: dict[str, Any],
        timeline: list[dict[str, Any]] | None = None,
    ) -> None:
        """Broadcast a game state to all members, rendered per-viewer on receipt.
        The full state (with server-only fields) is carried over Redis; each node
        renders a client-safe, viewer-scoped game.state for its local connections,
        all sharing the single seq stamped here. `timeline` is identical for every
        viewer (it describes what happened) and is attached as-is."""
        if self._cmd is None:
            return
        seq = await self._cmd.incr(f"seq:{session_id}")
        envelope = {
            "type": _GAME_STATE_BROADCAST,
            "seq": seq,
            "state": state_dict,
            "timeline": timeline or [],
        }
        await self._cmd.publish(f"session:{session_id}", json.dumps(envelope))

    async def current_seq(self, session_id: str) -> int:
        if self._cmd is None:
            return 0
        val = await self._cmd.get(f"seq:{session_id}")
        return int(val) if val else 0

    async def _reader_loop(self) -> None:
        backoff = 1.0
        while not self._shutdown:
            try:
                if not self._subscriptions or self._pubsub is None:
                    await asyncio.sleep(0.2)
                    continue
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                backoff = 1.0
                if not message or message.get("type") != "message":
                    continue
                channel = str(message["channel"])
                session_id = channel.removeprefix("session:")
                await self._dispatch_to_local(session_id, str(message["data"]))
            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception("backplane_reader_error", backoff=backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
                await self._reconnect_pubsub()
                # New pub/sub object after reconnect → re-subscribe to all channels.
                await self._ensure_subscriptions()

    async def _ensure_subscriptions(self) -> None:
        if self._pubsub is None:
            return
        channels = [f"session:{sid}" for sid, count in self._subscriptions.items() if count > 0]
        if channels:
            await self._pubsub.subscribe(*channels)

    async def _reconnect_pubsub(self) -> None:
        if self._pubsub is not None:
            try:
                await cast(Any, self._pubsub).aclose()
            except Exception:
                pass
        if self._pubsub_source is not None:
            self._pubsub = self._pubsub_source.pubsub()
        logger.info("backplane_reconnected")

    async def _dispatch_to_local(self, session_id: str, data: str) -> None:
        try:
            msg: dict[str, Any] = json.loads(data)
        except json.JSONDecodeError:
            logger.warning("backplane_invalid_json", session_id=session_id)
            return

        if msg.get("type") == _GAME_STATE_BROADCAST:
            await self._dispatch_game_state(session_id, msg)
            return

        for conn in self._manager.local_connections(session_id):
            self._enqueue_or_close(session_id, conn, msg)

    async def _dispatch_game_state(self, session_id: str, msg: dict[str, Any]) -> None:
        renderer = self._game_renderer
        if renderer is None:
            return
        state_dict = msg["state"]
        timeline = msg.get("timeline") or []
        seq = msg.get("seq")
        for conn in self._manager.local_connections(session_id):
            try:
                frame = renderer(state_dict, conn.user_id, timeline)
            except Exception:
                logger.exception("game_state_render_failed", session_id=session_id)
                continue
            frame["seq"] = seq
            self._enqueue_or_close(session_id, conn, frame)

    def _enqueue_or_close(self, session_id: str, conn: Any, frame: dict[str, Any]) -> None:
        ok = conn.enqueue(frame)
        if not ok:
            logger.warning(
                "backplane_queue_full",
                session_id=session_id,
                user_id=conn.user_id,
                connection_id=conn.connection_id,
            )
            asyncio.create_task(conn.close(1011))
