from redis.asyncio import Redis

from core.config import Settings


class RedisClient:
    def __init__(self) -> None:
        self._client: Redis | None = None

    @property
    def client(self) -> Redis:
        if self._client is None:
            raise RuntimeError("Redis client is not connected")
        return self._client

    async def connect(self, settings: Settings) -> None:
        self._client = Redis.from_url(settings.redis_url, decode_responses=True)
        await self.ping()

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.aclose()
        self._client = None

    async def ping(self) -> None:
        pong = await self.client.ping()
        if pong is not True:
            raise RuntimeError("Redis ping failed")
