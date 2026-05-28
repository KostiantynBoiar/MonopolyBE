from motor.motor_asyncio import AsyncIOMotorDatabase


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.sessions.create_index([("status", 1), ("created_at", -1)])
    await db.events.create_index([("session_id", 1), ("seq", 1)], unique=True)
    await db.users.create_index("email", unique=True)
