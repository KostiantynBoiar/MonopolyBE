from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from core.config import Settings


class MongoClient:
    def __init__(self) -> None:
        self._client: AsyncIOMotorClient[Any] | None = None
        self._db: AsyncIOMotorDatabase[Any] | None = None

    @property
    def client(self) -> AsyncIOMotorClient[Any]:
        if self._client is None:
            raise RuntimeError("MongoDB client is not connected")
        return self._client

    @property
    def db(self) -> AsyncIOMotorDatabase[Any]:
        if self._db is None:
            raise RuntimeError("MongoDB database is not connected")
        return self._db

    async def connect(self, settings: Settings) -> None:
        self._client = AsyncIOMotorClient(settings.mongodb_uri)
        self._db = self._client[settings.mongodb_db]
        await self.ping()

    async def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None
        self._db = None

    async def ping(self) -> None:
        await self.client.admin.command("ping")
