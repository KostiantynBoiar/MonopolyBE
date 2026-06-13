from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase


async def ensure_indexes(db: AsyncIOMotorDatabase[Any]) -> None:
    await db.sessions.create_index([("status", 1), ("created_at", -1)])
    await db.sessions.create_index([("visibility", 1), ("status", 1), ("created_at", -1)])
    await db.sessions.create_index("invite_code", unique=True)
    await db.events.create_index([("session_id", 1), ("seq", 1)], unique=True)
    await db.users.create_index("email", unique=True, sparse=True)
    # Leaderboard ordering (rating desc, then games_played).
    await db.users.create_index([("rating", -1), ("games_played", -1)])
    await db.games.create_index("session_id", unique=True)
    # Refresh tokens: _id is the token hash (unique by construction); TTL auto-purges
    # expired rows; user_id index supports revoke-all.
    await db.refresh_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.refresh_tokens.create_index("user_id")
    # auth_identities: unique per provider + Telegram sub; user_id for lookups.
    await db.auth_identities.create_index(
        [("provider", 1), ("provider_user_id", 1)], unique=True
    )
    await db.auth_identities.create_index("user_id")
