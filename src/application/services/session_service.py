from motor.motor_asyncio import AsyncIOMotorDatabase
from typing_extensions import Self

from core.exceptions import NotFoundError
from infra.mongo.users.repository import UserRepository


class NotMemberError(NotFoundError):
    def __init__(self, session_id: str, user_id: str) -> None:
        super().__init__(f"User {user_id} is not a member of session {session_id}")


class SessionService:
    def __init__(self, user_repo: UserRepository) -> None:
        self._users = user_repo

    @classmethod
    def from_db(cls, db: AsyncIOMotorDatabase) -> Self:  # type: ignore[type-arg]
        return cls(UserRepository(db))

    async def assert_member(self, session_id: str, user_id: str) -> None:
        # TODO(sessions): check actual session membership once Session collection exists
        user = await self._users.find_by_id(user_id)
        if user is None:
            raise NotMemberError(session_id, user_id)
