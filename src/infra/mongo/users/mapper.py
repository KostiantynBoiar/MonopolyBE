from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from domain.rating.constants import INITIAL_RATING
from domain.user.schemas import User
from infra.mongo.users.document import UserDocument


def to_domain(doc: UserDocument) -> User:
    return User(
        id=doc.id,
        email=doc.email,
        display_name=doc.display_name,
        created_at=doc.created_at,
        rating=doc.rating,
        games_played=doc.games_played,
        calibration_complete=doc.calibration_complete,
    )


def to_document(
    *,
    email: str,
    display_name: str,
    password_hash: str,
    user_id: str | None = None,
    created_at: datetime | None = None,
) -> UserDocument:
    return UserDocument(
        id=user_id or str(uuid4()),
        email=email,
        display_name=display_name,
        password_hash=password_hash,
        created_at=created_at or datetime.now(UTC),
    )


def document_to_mongo(doc: UserDocument) -> dict[str, Any]:
    # exclude_none keeps the email sparse index valid for Telegram users
    payload = doc.model_dump(exclude_none=True)
    payload["_id"] = payload.pop("id")
    return payload


def document_from_mongo(raw: dict[str, Any]) -> UserDocument:
    rating = cast(Any, raw.get("rating", INITIAL_RATING))
    games_played = cast(Any, raw.get("games_played", 0))
    raw_email = raw.get("email")
    raw_hash = raw.get("password_hash")
    return UserDocument(
        id=str(raw["_id"]),
        email=str(raw_email) if raw_email is not None else None,
        display_name=str(raw["display_name"]),
        password_hash=str(raw_hash) if raw_hash is not None else None,
        created_at=cast(datetime, raw["created_at"]),
        rating=int(rating),
        games_played=int(games_played),
        calibration_complete=bool(raw.get("calibration_complete", False)),
    )
