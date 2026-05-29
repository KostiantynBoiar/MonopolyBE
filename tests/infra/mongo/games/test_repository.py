from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI

from application.services.game_service import GameService
from application.services.session_service import SessionService
from domain.game.enums import TurnPhase
from domain.session.schemas import SessionVisibility
from infra.mongo.games.repository import GameRepository
from main import create_app


@pytest.fixture
async def mongo_app() -> FastAPI:
    application = create_app()
    async with LifespanManager(application):
        yield application


@pytest.fixture
async def game_repo(mongo_app: FastAPI) -> GameRepository:
    return GameRepository(mongo_app.state.mongo.db)


@pytest.fixture
async def game_service(mongo_app: FastAPI) -> GameService:
    return GameService.from_db(mongo_app.state.mongo.db)


@pytest.fixture
async def session_with_game(mongo_app: FastAPI, game_service: GameService):
    session_service = SessionService.from_db(mongo_app.state.mongo.db)
    from uuid import uuid4
    from core.config import get_settings
    from core.security import hash_password
    from infra.mongo.users.repository import UserRepository

    settings = get_settings()
    suffix = uuid4().hex[:8]
    users = UserRepository(mongo_app.state.mongo.db)
    host = await users.create(
        email=f"host_{suffix}@example.com",
        display_name="Host",
        password_hash=hash_password("password123"),
    )
    session = await session_service.create(host.id, visibility=SessionVisibility.PUBLIC)
    game_state = await game_service.start_game(session)
    return session, game_state


@pytest.mark.asyncio
async def test_update_with_version_success(game_repo: GameRepository, session_with_game) -> None:
    session, game_state = session_with_game
    stored = await game_repo.find_by_session_id(session.id)
    assert stored is not None

    new_turn = game_state.turn.model_copy(update={"phase": TurnPhase.POST_ROLL})
    updated_state = game_state.model_copy(update={"turn": new_turn})
    result = await game_repo.update_with_version(
        stored.game_id,
        updated_state,
        stored.version,
        stored.rng_state,
    )
    assert result is not None
    assert result.version == stored.version + 1
    assert result.state.turn.phase == TurnPhase.POST_ROLL


@pytest.mark.asyncio
async def test_update_with_version_stale_returns_none(
    game_repo: GameRepository,
    session_with_game,
) -> None:
    session, game_state = session_with_game
    stored = await game_repo.find_by_session_id(session.id)
    assert stored is not None

    new_turn = game_state.turn.model_copy(update={"phase": TurnPhase.POST_ROLL})
    updated_state = game_state.model_copy(update={"turn": new_turn})
    first = await game_repo.update_with_version(
        stored.game_id,
        updated_state,
        stored.version,
        stored.rng_state,
    )
    assert first is not None

    stale = await game_repo.update_with_version(
        stored.game_id,
        updated_state,
        stored.version,
        stored.rng_state,
    )
    assert stale is None
