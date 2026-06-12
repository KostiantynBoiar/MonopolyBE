from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import Any, cast

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from domain.game.schemas.state import GameState
from infra.mongo.games.document import GameDocument
from infra.mongo.games.mapper import (
    document_from_mongo,
    document_to_mongo,
    state_to_dict,
    to_document,
    to_domain,
)


def _serialize_rng_state(rng: random.Random) -> list[int | tuple[int, ...]]:
    state = rng.getstate()
    version, internal_state, gauss = state
    return cast(list[int | tuple[int, ...]], [version, tuple(internal_state), gauss])


def _restore_rng(rng_state: list[int | tuple[int, ...]]) -> random.Random:
    rng = random.Random()
    version = rng_state[0]
    internal = tuple(cast(tuple[int, ...], rng_state[1]))
    gauss = cast(float | None, rng_state[2])
    rng.setstate((cast(int, version), internal, gauss))
    return rng


class StoredGame:
    def __init__(
        self,
        *,
        game_id: str,
        session_id: str,
        seed: int,
        rng_state: list[int | tuple[int, ...]],
        version: int,
        state: GameState,
    ) -> None:
        self.game_id = game_id
        self.session_id = session_id
        self.seed = seed
        self.rng_state = rng_state
        self.version = version
        self.state = state


class GameRepository:
    def __init__(self, db: AsyncIOMotorDatabase[Any]) -> None:
        self._collection = db.games

    async def insert(self, doc: GameDocument) -> StoredGame:
        await self._collection.insert_one(document_to_mongo(doc))
        state, seed, version, rng_state = to_domain(doc)
        return StoredGame(
            game_id=doc.id,
            session_id=doc.session_id,
            seed=seed,
            rng_state=rng_state,
            version=version,
            state=state,
        )

    async def find_by_session_id(self, session_id: str) -> StoredGame | None:
        raw = await self._collection.find_one({"session_id": session_id})
        if raw is None:
            return None
        doc = document_from_mongo(raw)
        state, seed, version, rng_state = to_domain(doc)
        return StoredGame(
            game_id=doc.id,
            session_id=doc.session_id,
            seed=seed,
            rng_state=rng_state,
            version=version,
            state=state,
        )

    async def update_with_version(
        self,
        game_id: str,
        state: GameState,
        expected_version: int,
        rng_state: list[int | tuple[int, ...]],
    ) -> StoredGame | None:
        now = datetime.now(UTC)
        raw = await self._collection.find_one_and_update(
            {"_id": game_id, "version": expected_version},
            {
                "$set": {
                    "state": state_to_dict(state),
                    "rng_state": rng_state,
                    "updated_at": now,
                },
                "$inc": {"version": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        if raw is None:
            return None
        doc = document_from_mongo(raw)
        stored_state, seed, version, stored_rng = to_domain(doc)
        return StoredGame(
            game_id=doc.id,
            session_id=doc.session_id,
            seed=seed,
            rng_state=stored_rng,
            version=version,
            state=stored_state,
        )

    async def claim_for_rating(self, session_id: str) -> bool:
        """Atomically mark a game as rated. Returns True only on the FIRST claim, so the
        rating update runs exactly once even if both finish paths fire (or one retries)."""
        result = await self._collection.find_one_and_update(
            {"session_id": session_id, "rated": {"$ne": True}},
            {"$set": {"rated": True}},
        )
        return result is not None

    @staticmethod
    def build_document(
        *,
        game_id: str,
        session_id: str,
        seed: int,
        rng_state: list[int | tuple[int, ...]],
        state: GameState,
    ) -> GameDocument:
        return to_document(
            game_id=game_id,
            session_id=session_id,
            seed=seed,
            rng_state=rng_state,
            state=state,
            version=0,
        )

    @staticmethod
    def serialize_rng(rng: random.Random) -> list[int | tuple[int, ...]]:
        return _serialize_rng_state(rng)

    @staticmethod
    def restore_rng(rng_state: list[int | tuple[int, ...]]) -> random.Random:
        return _restore_rng(rng_state)
