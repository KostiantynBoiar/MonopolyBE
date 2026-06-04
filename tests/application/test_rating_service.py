"""RatingService: applies ELO on finish, idempotently, against real Mongo."""
from __future__ import annotations

import random
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from asgi_lifespan import LifespanManager

from application.services.rating_service import RatingService
from core.security import hash_password
from domain.game.enums import GameStatus, TurnPhase
from domain.game.rng import FixedClock
from domain.game.schemas.state import GameState
from domain.game.setup import GameMember, new_game
from infra.mongo.games.repository import GameRepository
from infra.mongo.users.repository import UserRepository
from main import create_app


@pytest.fixture
async def db():
    app = create_app()
    async with LifespanManager(app):
        await app.state.game_scheduler.stop()
        yield app.state.mongo.db


async def _user(db, name: str):
    return await UserRepository(db).create(
        email=f"{name}_{uuid4().hex[:8]}@example.com",
        display_name=name.title(),
        password_hash=hash_password("password123"),
    )


def _finished_two_player(alice_id: str, bob_id: str) -> GameState:
    """Build a finished game: Alice wins, Bob eliminated."""
    state = new_game(
        game_id="g",
        session_code="TYC-RT",
        members=[GameMember(alice_id, "Alice"), GameMember(bob_id, "Bob")],
        rng=random.Random(1),
        clock=FixedClock(datetime(2026, 6, 4, 12, 0, 0, tzinfo=UTC)),
        starting_balance=1500,
    )
    by_user = {p.user_id: p for p in state.players}
    players = []
    for p in state.players:
        if p.user_id == bob_id:
            players.append(p.model_copy(update={"is_bankrupt": True, "eliminated_at": 7}))
        else:
            players.append(p)
    winner_player = by_user[alice_id]
    return state.model_copy(
        update={
            "players": tuple(players),
            "status": GameStatus.FINISHED,
            "winner_id": winner_player.id,
            "turn": state.turn.model_copy(update={"phase": TurnPhase.GAME_OVER}),
        }
    )


async def _seed_game(db, session_id: str, state: GameState) -> None:
    rng = random.Random(1)
    doc = GameRepository.build_document(
        game_id=uuid4().hex,
        session_id=session_id,
        seed=1,
        rng_state=GameRepository.serialize_rng(rng),
        state=state,
    )
    await GameRepository(db).insert(doc)


@pytest.mark.asyncio
async def test_winner_gains_loser_loses_and_games_increment(db) -> None:
    alice = await _user(db, "alice")
    bob = await _user(db, "bob")
    session_id = uuid4().hex
    state = _finished_two_player(alice.id, bob.id)
    await _seed_game(db, session_id, state)

    await RatingService.from_db(db).apply_for_finished_game(session_id, state)

    users = UserRepository(db)
    a2 = await users.find_by_id(alice.id)
    b2 = await users.find_by_id(bob.id)
    assert a2.rating > 800 and b2.rating < 800
    assert a2.games_played == 1 and b2.games_played == 1
    # First game → still provisional.
    assert a2.calibration_complete is False


@pytest.mark.asyncio
async def test_idempotent_second_apply_is_noop(db) -> None:
    alice = await _user(db, "alice")
    bob = await _user(db, "bob")
    session_id = uuid4().hex
    state = _finished_two_player(alice.id, bob.id)
    await _seed_game(db, session_id, state)

    svc = RatingService.from_db(db)
    await svc.apply_for_finished_game(session_id, state)
    rating_after_first = (await UserRepository(db).find_by_id(alice.id)).rating

    await svc.apply_for_finished_game(session_id, state)  # claim fails → no-op
    a = await UserRepository(db).find_by_id(alice.id)
    assert a.rating == rating_after_first
    assert a.games_played == 1


@pytest.mark.asyncio
async def test_calibration_completes_after_three_games(db) -> None:
    alice = await _user(db, "alice")
    bob = await _user(db, "bob")
    users = UserRepository(db)
    for _ in range(3):
        session_id = uuid4().hex
        state = _finished_two_player(alice.id, bob.id)
        await _seed_game(db, session_id, state)
        await RatingService.from_db(db).apply_for_finished_game(session_id, state)

    a = await users.find_by_id(alice.id)
    assert a.games_played == 3
    assert a.calibration_complete is True
