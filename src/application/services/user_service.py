from datetime import UTC, datetime, timedelta
from typing import Any, Self

from motor.motor_asyncio import AsyncIOMotorDatabase

from core.config import Settings
from core.exceptions import DuplicateEmailError, InvalidCredentialsError, NotFoundError, UnauthorizedError
from core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from domain.user.schemas import User
from infra.mongo.refresh_tokens.repository import RefreshTokenRepository
from infra.mongo.users.repository import UserRepository
from protocol.rest.auth import (
    AuthResponse,
    LinkEmailRequest,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)
from protocol.rest.leaderboard import LeaderboardEntry, LeaderboardResponse


def _to_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        created_at=user.created_at,
        rating=user.rating,
        games_played=user.games_played,
        calibration_complete=user.calibration_complete,
    )


class UserService:
    def __init__(
        self,
        repository: UserRepository,
        settings: Settings,
        refresh_tokens: RefreshTokenRepository,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._refresh_tokens = refresh_tokens

    @classmethod
    def from_db(cls, db: AsyncIOMotorDatabase[Any], settings: Settings) -> Self:
        return cls(UserRepository(db), settings, RefreshTokenRepository(db))

    async def leaderboard(self, *, limit: int, offset: int) -> LeaderboardResponse:
        users = await self._repository.top_by_rating(limit=limit, offset=offset)
        return LeaderboardResponse(
            items=[
                LeaderboardEntry(
                    rank=offset + i + 1,
                    user_id=user.id,
                    display_name=user.display_name,
                    rating=user.rating,
                    games_played=user.games_played,
                    calibration_complete=user.calibration_complete,
                )
                for i, user in enumerate(users)
            ]
        )

    async def register(self, data: RegisterRequest) -> AuthResponse:
        password_hash = hash_password(data.password)
        user = await self._repository.create(
            email=data.email,
            display_name=data.display_name,
            password_hash=password_hash,
        )
        token = await self._issue_tokens(user.id)
        return AuthResponse(user=_to_public(user), token=token)

    async def login(self, data: LoginRequest) -> AuthResponse:
        result = await self._repository.find_password_hash_by_email(data.email)
        if result is None:
            raise InvalidCredentialsError()

        user, password_hash = result
        if not verify_password(data.password, password_hash):
            raise InvalidCredentialsError()

        token = await self._issue_tokens(user.id)
        return AuthResponse(user=_to_public(user), token=token)

    async def refresh(self, refresh_token: str) -> AuthResponse:
        """Single-use rotation: consume the old refresh token, issue a fresh pair."""
        user_id = await self._refresh_tokens.consume(hash_refresh_token(refresh_token))
        if user_id is None:
            raise UnauthorizedError("Invalid or expired refresh token")
        user = await self._repository.find_by_id(user_id)
        if user is None:
            raise UnauthorizedError("Invalid or expired refresh token")
        token = await self._issue_tokens(user.id)
        return AuthResponse(user=_to_public(user), token=token)

    async def logout(self, refresh_token: str) -> None:
        await self._refresh_tokens.revoke(hash_refresh_token(refresh_token))

    async def link_email(self, user_id: str, data: LinkEmailRequest) -> MeResponse:
        """Add an email + password to an account that was created via Telegram."""
        # Reject if the email is taken by a different account.
        existing = await self._repository.find_by_email(data.email)
        if existing is not None and existing.id != user_id:
            raise DuplicateEmailError()
        password_hash = hash_password(data.password)
        await self._repository.set_email_and_password(
            user_id, email=data.email.lower(), password_hash=password_hash
        )
        user = await self._repository.find_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return MeResponse(user=_to_public(user))

    async def get_me(self, user_id: str) -> MeResponse:
        user = await self._repository.find_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return MeResponse(user=_to_public(user))

    async def _issue_tokens(self, user_id: str) -> TokenResponse:
        access = create_access_token(user_id, self._settings)
        raw_refresh = generate_refresh_token()
        refresh_days = self._settings.refresh_token_expire_days
        await self._refresh_tokens.insert(
            token_hash=hash_refresh_token(raw_refresh),
            user_id=user_id,
            expires_at=datetime.now(UTC) + timedelta(days=refresh_days),
        )
        return TokenResponse(
            access_token=access,
            expires_in=self._settings.jwt_expire_minutes * 60,
            refresh_token=raw_refresh,
            refresh_expires_in=refresh_days * 86_400,
        )
