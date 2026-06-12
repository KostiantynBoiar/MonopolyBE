from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from core.exceptions import DuplicateEmailError
from domain.user.schemas import User
from infra.mongo.users.mapper import document_from_mongo, document_to_mongo, to_document, to_domain


class UserRepository:
    def __init__(self, db: AsyncIOMotorDatabase[Any]) -> None:
        self._collection = db.users

    async def find_by_email(self, email: str) -> User | None:
        raw = await self._collection.find_one({"email": email.lower()})
        if raw is None:
            return None
        return to_domain(document_from_mongo(raw))

    async def find_by_id(self, user_id: str) -> User | None:
        raw = await self._collection.find_one({"_id": user_id})
        if raw is None:
            return None
        return to_domain(document_from_mongo(raw))

    async def find_password_hash_by_email(self, email: str) -> tuple[User, str] | None:
        raw = await self._collection.find_one({"email": email.lower()})
        if raw is None:
            return None
        doc = document_from_mongo(raw)
        return to_domain(doc), doc.password_hash

    async def create(self, email: str, display_name: str, password_hash: str) -> User:
        doc = to_document(
            email=email.lower(),
            display_name=display_name,
            password_hash=password_hash,
        )
        try:
            await self._collection.insert_one(document_to_mongo(doc))
        except DuplicateKeyError as exc:
            raise DuplicateEmailError("Email already registered") from exc
        return to_domain(doc)

    async def find_by_ids(self, user_ids: list[str]) -> dict[str, User]:
        if not user_ids:
            return {}
        users: dict[str, User] = {}
        async for raw in self._collection.find({"_id": {"$in": user_ids}}):
            user = to_domain(document_from_mongo(raw))
            users[user.id] = user
        return users

    async def update_rating(
        self, user_id: str, *, rating: int, games_played: int, calibration_complete: bool
    ) -> None:
        await self._collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "rating": rating,
                    "games_played": games_played,
                    "calibration_complete": calibration_complete,
                }
            },
        )

    async def top_by_rating(self, *, limit: int, offset: int) -> list[User]:
        # Only players who have actually played a game appear on the leaderboard.
        cursor = (
            self._collection.find({"games_played": {"$gte": 1}})
            .sort([("rating", -1), ("games_played", -1)])
            .skip(offset)
            .limit(limit)
        )
        return [to_domain(document_from_mongo(raw)) async for raw in cursor]
