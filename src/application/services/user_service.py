from typing import Self

from motor.motor_asyncio import AsyncIOMotorDatabase

from core.config import Settings
from core.exceptions import InvalidCredentialsError, NotFoundError
from core.security import create_access_token, hash_password, verify_password
from domain.user.model import User
from infra.mongo.users.repository import UserRepository
from protocol.rest.auth import (
    AuthResponse,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    UserPublic,
)


def _to_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        created_at=user.created_at,
    )


class UserService:
    def __init__(self, repository: UserRepository, settings: Settings) -> None:
        self._repository = repository
        self._settings = settings

    @classmethod
    def from_db(cls, db: AsyncIOMotorDatabase, settings: Settings) -> Self:
        return cls(UserRepository(db), settings)

    async def register(self, data: RegisterRequest) -> AuthResponse:
        password_hash = hash_password(data.password)
        user = await self._repository.create(
            email=data.email,
            display_name=data.display_name,
            password_hash=password_hash,
        )
        token = create_access_token(user.id, self._settings)
        return AuthResponse(user=_to_public(user), token=token)

    async def login(self, data: LoginRequest) -> AuthResponse:
        result = await self._repository.find_password_hash_by_email(data.email)
        if result is None:
            raise InvalidCredentialsError()

        user, password_hash = result
        if not verify_password(data.password, password_hash):
            raise InvalidCredentialsError()

        token = create_access_token(user.id, self._settings)
        return AuthResponse(user=_to_public(user), token=token)

    async def get_me(self, user_id: str) -> MeResponse:
        user = await self._repository.find_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return MeResponse(user=_to_public(user))
