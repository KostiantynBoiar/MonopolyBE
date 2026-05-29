from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import structlog
from redis.asyncio import Redis
from redis.asyncio.client import PubSub

from gateway.manager import ConnectionManager

logger = structlog.get_logger(__name__)


class Backplane:
    def __init__(self, redis_url: str, manager: ConnectionManager) -> None:
        self._url = redis_url
        self._manager = manager
        self._cmd: Redis[str] | None = None
        self._pubsub_source: Redis[str] | None = None
        self._pubsub: PubSub | None = None
        # session_id -> refcount of local connections subscribed
        self._subscriptions: dict[str, int] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._shutdown = False

    async def start(self) -> None:
        self._cmd = Redis.from_url(self._url, decode_responses=True)
        self._pubsub_source = Redis.from_url(self._url, decode_responses=True)
        self._pubsub = self._pubsub_source.pubsub()
        self._reader_task = asyncio.create_task(
            self._reader_loop(), name="backplane-reader"
        )

    async def stop(self) -> None:
        self._shutdown = True
        if self._reader_task:
            self._reader_task.cancel()
            await asyncio.gather(self._reader_task, return_exceptions=True)
        if self._pubsub:
            await self._pubsub.aclose()
        if self._pubsub_source:
            await self._pubsub_source.aclose()
        if self._cmd:
            await self._cmd.aclose()

    async def subscribe(self, session_id: str) -> None:
        count = self._subscriptions.get(session_id, 0)
        self._subscriptions[session_id] = count + 1
        if count == 0 and self._pubsub is not None:
            await self._pubsub.subscribe(f"session:{session_id}")

    async def unsubscribe(self, session_id: str) -> None:
        count = self._subscriptions.get(session_id, 0)
        if count <= 1:
            self._subscriptions.pop(session_id, None)
            if self._pubsub is not None:
                await self._pubsub.unsubscribe(f"session:{session_id}")
        else:
            self._subscriptions[session_id] = count - 1

    async def publish(self, session_id: str, msg: dict[str, Any]) -> None:
        if self._cmd is None:
            return
        seq = await self._cmd.incr(f"seq:{session_id}")
        msg["seq"] = seq
        await self._cmd.publish(f"session:{session_id}", json.dumps(msg))

    async def current_seq(self, session_id: str) -> int:
        if self._cmd is None:
            return 0
        val = await self._cmd.get(f"seq:{session_id}")
        return int(val) if val else 0

    async def _reader_loop(self) -> None:
        backoff = 1.0
        while not self._shutdown:
            try:
                if not self._subscriptions:
                    await asyncio.sleep(0.1)
                    continue
                await self._ensure_subscriptions()
                assert self._pubsub is not None
                async for message in self._pubsub.listen():
                    if self._shutdown:
                        return
                    if message["type"] != "message":
                        continue
                    backoff = 1.0
                    channel: str = message["channel"]
                    data: str = message["data"]
                    session_id = channel.removeprefix("session:")
                    await self._dispatch_to_local(session_id, data)
            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception("backplane_reader_error", backoff=backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
                await self._reconnect_pubsub()

    async def _ensure_subscriptions(self) -> None:
        if self._pubsub is None:
            return
        channels = [
            f"session:{sid}"
            for sid, count in self._subscriptions.items()
            if count > 0
        ]
        if channels:
            await self._pubsub.subscribe(*channels)

    async def _reconnect_pubsub(self) -> None:
        if self._pubsub is not None:
            try:
                await self._pubsub.aclose()
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
        for conn in self._manager.local_connections(session_id):
            ok = conn.enqueue(msg)
            if not ok:
                logger.warning(
                    "backplane_queue_full",
                    session_id=session_id,
                    user_id=conn.user_id,
                    connection_id=conn.connection_id,
                )
                await conn.close(1011)
