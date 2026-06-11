from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog
from motor.motor_asyncio import AsyncIOMotorDatabase

from core.config import Settings
from domain.game.engine import apply
from domain.game.enums import GameStatus
from domain.game.rng import FixedClock
from domain.game.rules.auction import is_auction_expired
from domain.game.rules.turn_timer import is_turn_expired
from domain.game.schemas.commands import AdvanceAuction, ExpireTrade, TurnTimeout
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
            # One malformed/stale game must not abort processing of all the others.
            try:
                await self._tick_one(doc["session_id"])
            except Exception:
                logger.exception("game_scheduler_game_failed", session_id=doc.get("session_id"))

    async def _tick_one(self, session_id: str) -> None:
        stored = await self._games.find_by_session_id(session_id)
        if stored is None:
            return
        state = stored.state

        now = datetime.now(UTC)
        now_ms = int(now.timestamp() * 1000)

        # Only act when a timer is actually due — otherwise we'd bump the version
        # and re-broadcast an unchanged state every tick.
        command = None
        if state.auction is not None and is_auction_expired(state, now_ms):
            command = AdvanceAuction()
        elif state.trade is not None and state.trade.expires_at <= now:
            command = ExpireTrade()
        elif is_turn_expired(state, now_ms):
            command = TurnTimeout()

        if command is None:
            return

        rng = GameRepository.restore_rng(stored.rng_state)
        clock = FixedClock(now)
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
            await self._backplane.publish_game_state(
                session_id, updated.state.model_dump(mode="json")
            )
            if updated.state.status == GameStatus.FINISHED:
                await self._finish_session(session_id, updated.state)

    async def _finish_session(self, session_id: str, state) -> None:
        from application.services.session_service import SessionService
        from application.services.rating_service import RatingService
        from api.sessions.router import _broadcast_session_updated

        db = self._games._collection.database
        await RatingService.from_db(db).apply_for_finished_game(session_id, state)
        session = await SessionService.from_db(db).mark_finished(session_id)
        if session is not None:
            await _broadcast_session_updated(self._backplane, session)
