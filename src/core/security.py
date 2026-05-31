import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from core.config import Settings
from core.exceptions import UnauthorizedError


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def generate_refresh_token() -> str:
    """Opaque, high-entropy refresh token handed to the client (raw value)."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """Only the hash is persisted, so a DB leak can't be replayed as a valid token."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: str, settings: Settings) -> str:
    """Mint a short-lived access JWT (returns the encoded token string)."""
    expire_at = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "exp": expire_at}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> str:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid or expired token") from exc

    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise UnauthorizedError("Invalid or expired token")
    return user_id
