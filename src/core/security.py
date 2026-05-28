from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from core.config import Settings
from core.exceptions import UnauthorizedError
from protocol.rest.auth import TokenResponse


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: str, settings: Settings) -> TokenResponse:
    expires_in = settings.jwt_expire_minutes * 60
    expire_at = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "exp": expire_at}
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return TokenResponse(access_token=token, expires_in=expires_in)


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
