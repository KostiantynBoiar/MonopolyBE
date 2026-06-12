from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase


class RefreshTokenRepository:
    """Stores only the *hash* of each refresh token (the raw value lives on the client).
    The token hash is the document `_id`, which gives the unique constraint for free; a
    TTL index on `expires_at` (see infra/mongo/indexes.py) auto-purges expired rows."""

    def __init__(self, db: AsyncIOMotorDatabase[Any]) -> None:
        self._collection = db.refresh_tokens

    async def insert(self, *, token_hash: str, user_id: str, expires_at: datetime) -> None:
        await self._collection.insert_one(
            {
                "_id": token_hash,
                "user_id": user_id,
                "expires_at": expires_at,
                "created_at": datetime.now(UTC),
            }
        )

    async def consume(self, token_hash: str) -> str | None:
        """Atomically validate + delete an unexpired token (single-use rotation).
        Returns the owning user_id, or None if missing/expired."""
        doc = await self._collection.find_one_and_delete(
            {"_id": token_hash, "expires_at": {"$gt": datetime.now(UTC)}}
        )
        return doc["user_id"] if doc else None

    async def revoke(self, token_hash: str) -> None:
        await self._collection.delete_one({"_id": token_hash})

    async def revoke_all_for_user(self, user_id: str) -> None:
        await self._collection.delete_many({"user_id": user_id})
