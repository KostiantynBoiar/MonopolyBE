import json
import secrets

from redis.asyncio import Redis


class OAuthStateStore:
    """Stores short-lived PKCE state and internal exchange codes in Redis."""

    _STATE_TTL = 600   # 10 minutes — enough to complete the browser redirect flow
    _EXCHANGE_TTL = 300  # 5 minutes — single-use code must be consumed quickly

    def __init__(self, redis: Redis) -> None:  # type: ignore[type-arg]
        self._redis = redis

    async def store(
        self,
        state: str,
        *,
        nonce: str,
        code_verifier: str,
        linking_user_id: str | None = None,
    ) -> None:
        """Persist PKCE state. Pass linking_user_id when this is an account-connect flow."""
        payload: dict[str, str] = {"nonce": nonce, "code_verifier": code_verifier}
        if linking_user_id is not None:
            payload["linking_user_id"] = linking_user_id
        key = f"telegram:state:{state}"
        await self._redis.set(key, json.dumps(payload), ex=self._STATE_TTL)

    async def consume(self, state: str) -> dict[str, str] | None:
        """Atomically read-and-delete the state entry. Returns None if missing/expired."""
        key = f"telegram:state:{state}"
        raw: str | None = await self._redis.getdel(key)
        if raw is None:
            return None
        result: dict[str, str] = json.loads(raw)
        return result

    async def store_exchange_code(self, user_id: str) -> str:
        """Create and persist a single-use internal exchange code."""
        code = secrets.token_urlsafe(32)
        key = f"telegram:exchange:{code}"
        await self._redis.set(key, user_id, ex=self._EXCHANGE_TTL)
        return code

    async def consume_exchange_code(self, code: str) -> str | None:
        """Atomically read-and-delete the exchange code. Returns user_id or None."""
        key = f"telegram:exchange:{code}"
        result: str | None = await self._redis.getdel(key)
        return result
