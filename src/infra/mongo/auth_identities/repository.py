from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase

from infra.mongo.auth_identities.document import AuthIdentityDocument


class AuthIdentityRepository:
    def __init__(self, db: AsyncIOMotorDatabase[Any]) -> None:
        self._collection = db.auth_identities

    async def find_by_provider(
        self, provider: str, provider_user_id: str
    ) -> AuthIdentityDocument | None:
        raw = await self._collection.find_one(
            {"provider": provider, "provider_user_id": provider_user_id}
        )
        return self._from_raw(raw) if raw is not None else None

    async def find_by_user_and_provider(
        self, user_id: str, provider: str
    ) -> AuthIdentityDocument | None:
        raw = await self._collection.find_one({"user_id": user_id, "provider": provider})
        return self._from_raw(raw) if raw is not None else None

    async def create(
        self,
        *,
        user_id: str,
        provider: str,
        provider_user_id: str,
        username: str | None,
        picture_url: str | None,
    ) -> AuthIdentityDocument:
        now = datetime.now(UTC)
        doc = AuthIdentityDocument(
            id=str(uuid4()),
            user_id=user_id,
            provider=provider,
            provider_user_id=provider_user_id,
            username=username,
            picture_url=picture_url,
            created_at=now,
            updated_at=now,
        )
        payload = doc.model_dump()
        payload["_id"] = payload.pop("id")
        await self._collection.insert_one(payload)
        return doc

    async def update_profile(
        self, identity_id: str, *, username: str | None, picture_url: str | None
    ) -> None:
        await self._collection.update_one(
            {"_id": identity_id},
            {
                "$set": {
                    "username": username,
                    "picture_url": picture_url,
                    "updated_at": datetime.now(UTC),
                }
            },
        )

    @staticmethod
    def _from_raw(raw: dict[str, Any]) -> AuthIdentityDocument:
        raw_username = raw.get("username")
        raw_picture = raw.get("picture_url")
        return AuthIdentityDocument(
            id=str(raw["_id"]),
            user_id=str(raw["user_id"]),
            provider=str(raw["provider"]),
            provider_user_id=str(raw["provider_user_id"]),
            username=str(raw_username) if raw_username is not None else None,
            picture_url=str(raw_picture) if raw_picture is not None else None,
            created_at=cast(datetime, raw["created_at"]),
            updated_at=cast(datetime, raw["updated_at"]),
        )
