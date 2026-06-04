from datetime import UTC, datetime
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


def document_to_mongo(doc: UserDocument) -> dict[str, object]:
    payload = doc.model_dump()
    payload["_id"] = payload.pop("id")
    return payload


def document_from_mongo(raw: dict[str, object]) -> UserDocument:
    return UserDocument(
        id=str(raw["_id"]),
        email=str(raw["email"]),
        display_name=str(raw["display_name"]),
        password_hash=str(raw["password_hash"]),
        created_at=raw["created_at"],  # type: ignore[arg-type]
        # Defaults keep users created before the rating feature readable.
        rating=int(raw.get("rating", INITIAL_RATING)),  # type: ignore[arg-type]
        games_played=int(raw.get("games_played", 0)),  # type: ignore[arg-type]
        calibration_complete=bool(raw.get("calibration_complete", False)),
    )
