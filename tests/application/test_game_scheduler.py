from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from asgi_lifespan import LifespanManager

from application.services.game_scheduler import GameScheduler
from application.services.game_service import GameService
from application.services.session_service import SessionService
from core.config import get_settings
from core.security import hash_password
from domain.game.constants import AUCTION_DURATION_MS
from domain.game.rules.auction import start_auction
from domain.session.schemas import SessionVisibility
from infra.mongo.games.repository import GameRepository
from infra.mongo.users.repository import UserRepository


class FakeBackplane:
    def __init__(self) -> None:
        self.game_state_calls: list[str] = []
        self.publish_calls: list[str] = []

    async def publish_game_state(self, session_id: str, state_dict: dict) -> None:
        self.game_state_calls.append(session_id)

    async def publish(self, session_id: str, msg: dict) -> None:
        self.publish_calls.append(session_id)


@pytest.fixture
async def db():
    # Use the app lifespan (Motor bound to the test loop, like the infra tests), but
    # STOP the app's own background GameScheduler so it can't race the one under test.
    from main import create_app

    app = create_app()
    async with LifespanManager(app):
        await app.state.game_scheduler.stop()
        yield app.state.mongo.db


async def _started_game(db):
    users = UserRepository(db)
    host = await users.create(
        email=f"host_{uuid4().hex[:8]}@example.com",
        display_name="Host",
        password_hash=hash_password("password123"),
    )
    session = await SessionService.from_db(db).create(host.id, SessionVisibility.PUBLIC)
    await GameService.from_db(db).start_game(session)
    return session


async def _seed_auction(db, session_id: str, *, started_at_ms: int) -> None:
    repo = GameRepository(db)
    stored = await repo.find_by_session_id(session_id)
    assert stored is not None
    state = start_auction(stored.state, property_position=1, now_ms=started_at_ms)
    await repo.update_with_version(stored.game_id, state, stored.version, stored.rng_state)


@pytest.mark.asyncio
async def test_scheduler_skips_unexpired_auction(db) -> None:
    session = await _started_game(db)
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    await _seed_auction(db, session.id, started_at_ms=now_ms)  # mid-flight

    fake = FakeBackplane()
    scheduler = GameScheduler(db, fake, get_settings())  # type: ignore[arg-type]
    await scheduler._tick_one(session.id)

    # Auction not expired → no broadcast for this game, auction still present.
    # (in/not-in rather than == because the dev DB is shared across tests.)
    assert session.id not in fake.game_state_calls
    stored = await GameRepository(db).find_by_session_id(session.id)
    assert stored is not None and stored.state.auction is not None


@pytest.mark.asyncio
async def test_scheduler_resolves_expired_auction(db) -> None:
    session = await _started_game(db)
    expired_ms = int(
        (datetime.now(UTC) - timedelta(milliseconds=AUCTION_DURATION_MS + 5000)).timestamp()
        * 1000
    )
    await _seed_auction(db, session.id, started_at_ms=expired_ms)  # already expired

    fake = FakeBackplane()
    scheduler = GameScheduler(db, fake, get_settings())  # type: ignore[arg-type]
    await scheduler._tick_one(session.id)

    # Expired → resolved (no bids → property stays unowned) + a broadcast for this game.
    assert session.id in fake.game_state_calls
    stored = await GameRepository(db).find_by_session_id(session.id)
    assert stored is not None
    assert stored.state.auction is None
    assert stored.state.spaces[1].owner_id is None
