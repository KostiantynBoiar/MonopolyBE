from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar, Self
from urllib.parse import urlencode

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm
from motor.motor_asyncio import AsyncIOMotorDatabase
from redis.asyncio import Redis

from core.config import Settings
from core.exceptions import InvalidTelegramLoginError, TelegramUnavailableError
from core.security import create_access_token, generate_refresh_token, hash_refresh_token
from domain.user.schemas import User
from infra.mongo.auth_identities.repository import AuthIdentityRepository
from infra.mongo.refresh_tokens.repository import RefreshTokenRepository
from infra.mongo.users.repository import UserRepository
from infra.redis.oauth_state import OAuthStateStore
from protocol.rest.auth import AuthResponse, TokenResponse, UserPublic

_TELEGRAM_TOKEN_URL = "https://oauth.telegram.org/token"


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


class TelegramAuthService:
    # JWKS public keys cached across all instances in this process; refreshed on unknown kid.
    _jwks_cache: ClassVar[dict[str, Any]] = {}

    def __init__(
        self,
        settings: Settings,
        redis: Redis,  # type: ignore[type-arg]
        user_repo: UserRepository,
        auth_identities: AuthIdentityRepository,
        refresh_tokens: RefreshTokenRepository,
    ) -> None:
        self._settings = settings
        self._state_store = OAuthStateStore(redis)
        self._user_repo = user_repo
        self._auth_identities = auth_identities
        self._refresh_tokens = refresh_tokens

    @classmethod
    def from_db(
        cls,
        db: AsyncIOMotorDatabase[Any],
        settings: Settings,
        redis: Redis,  # type: ignore[type-arg]
    ) -> Self:
        return cls(
            settings=settings,
            redis=redis,
            user_repo=UserRepository(db),
            auth_identities=AuthIdentityRepository(db),
            refresh_tokens=RefreshTokenRepository(db),
        )

    # ------------------------------------------------------------------
    # Public interface — login flow
    # ------------------------------------------------------------------

    async def start(self) -> str:
        """Generate PKCE state, persist it, and return the Telegram authorization URL."""
        return await self._build_auth_url(linking_user_id=None)

    async def handle_callback(self, *, code: str, state: str) -> str:
        """
        Verify Telegram callback and return a frontend redirect URL.

        Login mode  → redirects to frontend_telegram_callback_url?code=<exchange_code>
        Connect mode → redirects to frontend_telegram_connect_url?telegram_linked=true
                       (or ?error=<reason> on failure)
        """
        state_data = await self._state_store.consume(state)
        if state_data is None:
            raise InvalidTelegramLoginError("Invalid or expired state")

        linking_user_id = state_data.get("linking_user_id") or None

        try:
            id_token = await self._exchange_telegram_code(code, state_data["code_verifier"])
            claims = await self._verify_id_token(id_token, state_data["nonce"])
        except (InvalidTelegramLoginError, TelegramUnavailableError):
            if linking_user_id is not None:
                return f"{self._settings.frontend_telegram_connect_url}?error=telegram_error"
            raise

        if linking_user_id is not None:
            return await self._handle_connect_callback(claims, linking_user_id)
        return await self._handle_login_callback(claims)

    async def exchange(self, code: str) -> AuthResponse:
        """Consume the single-use internal code and issue app tokens."""
        user_id = await self._state_store.consume_exchange_code(code)
        if user_id is None:
            raise InvalidTelegramLoginError("Invalid or expired exchange code")

        user = await self._user_repo.find_by_id(user_id)
        if user is None:
            raise InvalidTelegramLoginError("User not found")

        token = await self._issue_tokens(user.id)
        return AuthResponse(user=_to_public(user), token=token)

    # ------------------------------------------------------------------
    # Public interface — account linking flow
    # ------------------------------------------------------------------

    async def start_connect(self, user_id: str) -> str:
        """
        Like start(), but embeds the current user's ID in the state so the
        callback knows to link rather than log in.
        """
        return await self._build_auth_url(linking_user_id=user_id)

    # ------------------------------------------------------------------
    # Internal — shared URL builder
    # ------------------------------------------------------------------

    async def _build_auth_url(self, *, linking_user_id: str | None) -> str:
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(96)  # 128 url-safe chars, within PKCE 43–128 limit
        code_challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode("ascii")).digest()
            )
            .rstrip(b"=")
            .decode()
        )

        await self._state_store.store(
            state,
            nonce=nonce,
            code_verifier=code_verifier,
            linking_user_id=linking_user_id,
        )

        params = urlencode(
            {
                "client_id": self._settings.telegram_client_id,
                "redirect_uri": self._settings.telegram_redirect_uri,
                "response_type": "code",
                "scope": "openid profile",
                "state": state,
                "nonce": nonce,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"https://oauth.telegram.org/auth?{params}"

    # ------------------------------------------------------------------
    # Internal — callback branches
    # ------------------------------------------------------------------

    async def _handle_login_callback(self, claims: dict[str, Any]) -> str:
        """First-time login or returning Telegram user — create or reuse local account."""
        user = await self._get_or_create_user(claims)
        exchange_code = await self._state_store.store_exchange_code(user.id)
        return f"{self._settings.frontend_telegram_callback_url}?code={exchange_code}"

    async def _handle_connect_callback(
        self, claims: dict[str, Any], linking_user_id: str
    ) -> str:
        """Link Telegram to an existing account that the user is already logged in to."""
        connect_url = self._settings.frontend_telegram_connect_url
        telegram_sub = str(claims["sub"])

        # Check if this Telegram identity is already claimed by any account.
        existing = await self._auth_identities.find_by_provider("telegram", telegram_sub)
        if existing is not None:
            if existing.user_id == linking_user_id:
                # Already linked to this exact user — idempotent success.
                return f"{connect_url}?telegram_linked=true"
            return f"{connect_url}?error=telegram_account_already_linked"

        # Check if the target user already has a Telegram identity.
        user_identity = await self._auth_identities.find_by_user_and_provider(
            linking_user_id, "telegram"
        )
        if user_identity is not None:
            return f"{connect_url}?error=account_already_has_telegram"

        raw_username = claims.get("preferred_username")
        picture_url = str(claims["picture"]) if claims.get("picture") else None
        username = str(raw_username) if raw_username else None

        await self._auth_identities.create(
            user_id=linking_user_id,
            provider="telegram",
            provider_user_id=telegram_sub,
            username=username,
            picture_url=picture_url,
        )
        return f"{connect_url}?telegram_linked=true"

    # ------------------------------------------------------------------
    # Internal — Telegram OIDC mechanics
    # ------------------------------------------------------------------

    async def _exchange_telegram_code(self, code: str, code_verifier: str) -> str:
        auth_header = base64.b64encode(
            f"{self._settings.telegram_client_id}:{self._settings.telegram_client_secret}".encode()
        ).decode()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    _TELEGRAM_TOKEN_URL,
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": self._settings.telegram_redirect_uri,
                        "client_id": self._settings.telegram_client_id,
                        "code_verifier": code_verifier,
                    },
                    headers={"Authorization": f"Basic {auth_header}"},
                )
        except httpx.HTTPError as exc:
            raise TelegramUnavailableError("Telegram token endpoint unreachable") from exc

        if response.status_code != 200:
            raise TelegramUnavailableError(
                f"Telegram token exchange failed with HTTP {response.status_code}"
            )

        data: dict[str, Any] = response.json()
        id_token = data.get("id_token")
        if not isinstance(id_token, str):
            raise InvalidTelegramLoginError("No id_token in Telegram response")
        return id_token

    async def _get_signing_key(self, kid: str) -> Any:
        if kid in TelegramAuthService._jwks_cache:
            return TelegramAuthService._jwks_cache[kid]
        # Unknown kid — refresh the JWKS and try again.
        await self._refresh_jwks()
        if kid not in TelegramAuthService._jwks_cache:
            raise InvalidTelegramLoginError("Unknown JWKS signing key")
        return TelegramAuthService._jwks_cache[kid]

    async def _refresh_jwks(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self._settings.telegram_jwks_url)
                response.raise_for_status()
                jwks: dict[str, Any] = response.json()
        except httpx.HTTPError as exc:
            raise TelegramUnavailableError("Failed to fetch Telegram JWKS") from exc

        new_cache: dict[str, Any] = {}
        for key_data in jwks.get("keys", []):
            k = str(key_data.get("kid", ""))
            if k:
                new_cache[k] = RSAAlgorithm.from_jwk(json.dumps(key_data))
        TelegramAuthService._jwks_cache = new_cache

    async def _verify_id_token(self, id_token: str, nonce: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(id_token)
        except jwt.PyJWTError as exc:
            raise InvalidTelegramLoginError("Malformed ID token") from exc

        kid = str(header.get("kid", ""))
        signing_key = await self._get_signing_key(kid)

        try:
            claims: dict[str, Any] = jwt.decode(
                id_token,
                signing_key,
                algorithms=["RS256"],
                audience=self._settings.telegram_client_id,
                issuer=self._settings.telegram_issuer,
            )
        except jwt.PyJWTError as exc:
            raise InvalidTelegramLoginError("ID token verification failed") from exc

        if claims.get("nonce") != nonce:
            raise InvalidTelegramLoginError("Nonce mismatch")
        if not claims.get("sub"):
            raise InvalidTelegramLoginError("Missing sub claim")
        return claims

    async def _get_or_create_user(self, claims: dict[str, Any]) -> User:
        telegram_sub = str(claims["sub"])
        raw_name = claims.get("name")
        raw_username = claims.get("preferred_username")
        display_name = (
            str(raw_name)
            if raw_name
            else str(raw_username)
            if raw_username
            else "Telegram User"
        )
        username = str(raw_username) if raw_username else None
        picture_url = str(claims["picture"]) if claims.get("picture") else None

        identity = await self._auth_identities.find_by_provider("telegram", telegram_sub)
        if identity is not None:
            await self._auth_identities.update_profile(
                identity.id, username=username, picture_url=picture_url
            )
            user = await self._user_repo.find_by_id(identity.user_id)
            if user is None:
                raise InvalidTelegramLoginError("User record missing for existing identity")
            return user

        user = await self._user_repo.create_telegram_user(display_name=display_name)
        await self._auth_identities.create(
            user_id=user.id,
            provider="telegram",
            provider_user_id=telegram_sub,
            username=username,
            picture_url=picture_url,
        )
        return user

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
