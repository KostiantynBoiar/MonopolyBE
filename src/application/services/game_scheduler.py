from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime

import structlog
from motor.motor_asyncio import AsyncIOMotorDatabase

from application.services.game_service import GameService
from core.config import Settings, get_settings
from domain.game.engine import apply
from domain.game.rng import FixedClock
from domain.game.schemas.commands import AdvanceAuction, ExpireTrade
from gateway.backplane import Backplane
from infra.mongo.games.repository import GameRepository

logger = structlog.get_logger(__name__)


class GameScheduler:
    """Applies timed system commands for auctions and trade expiry."""

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        backplane: Backplane,
        settings: Settings,
    ) -> None:
        self._games = GameRepository(db)
        self._backplane = backplane
        self._settings = settings
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="game_scheduler")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self._tick()
            except Exception:
                logger.exception("game_scheduler_tick_failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=1.0)
                break
            except asyncio.TimeoutError:
                continue

    async def _tick(self) -> None:
        cursor = self._games._collection.find(
            {"state.status": "in_progress"},
            projection={"_id": 1, "session_id": 1},
        )
        async for doc in cursor:
            session_id = doc["session_id"]
            stored = await self._games.find_by_session_id(session_id)
            if stored is None:
                continue
            state = stored.state
            if state.auction is None and state.trade is None:
                continue

            rng = GameRepository.restore_rng(stored.rng_state)
            clock = FixedClock(datetime.now(UTC))
            command = None
            if state.auction is not None:
                command = AdvanceAuction()
            elif state.trade is not None and state.trade.expires_at <= clock.now():
                command = ExpireTrade()

            if command is None:
                continue

            new_state, _ = apply(
                state,
                command,
                rng=rng,
                clock=clock,
                go_salary=self._settings.go_salary,
                jail_fine=self._settings.jail_fine,
            )
            rng_state = GameRepository.serialize_rng(rng)
            updated = await self._games.update_with_version(
                stored.game_id,
                new_state,
                stored.version,
                rng_state,
            )
            if updated is not None:
                service = GameService(self._games, self._settings)
                outbound = service.snapshot_message(updated.state)
                await self._backplane.publish(session_id, outbound)
