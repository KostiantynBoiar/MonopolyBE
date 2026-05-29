import asyncio
from typing import Any

from core.constants import WS_SEND_QUEUE_MAX_SIZE


class SendQueue:
    def __init__(self) -> None:
        self._q: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(
            maxsize=WS_SEND_QUEUE_MAX_SIZE
        )

    def put(self, message: dict[str, Any]) -> bool:
        """Enqueue a message. Returns False if the queue is full."""
        try:
            self._q.put_nowait(message)
            return True
        except asyncio.QueueFull:
            return False

    def put_sentinel(self) -> None:
        """Enqueue None to signal the send loop to exit cleanly."""
        try:
            self._q.put_nowait(None)
        except asyncio.QueueFull:
            pass

    async def get(self) -> dict[str, Any] | None:
        return await self._q.get()
