from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from domain.game.enums import GameMode
from domain.session.schemas import Session, SessionMember, SessionStatus, SessionVisibility
from infra.mongo.sessions.document import SessionDocument, SessionMemberDocument


def to_domain(doc: SessionDocument) -> Session:
    return Session(
        id=doc.id,
        invite_code=doc.invite_code,
        host_user_id=doc.host_user_id,
        status=doc.status,
        visibility=doc.visibility,
        game_mode=doc.game_mode,
        ranked=doc.ranked,
        members=tuple(
            SessionMember(
                user_id=m.user_id,
                display_name=m.display_name,
                role=m.role,
                joined_at=m.joined_at,
                rating=m.rating,
                calibration_complete=m.calibration_complete,
            )
            for m in doc.members
        ),
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def to_document(
    *,
    invite_code: str,
    host_user_id: str,
    status: SessionStatus,
    visibility: SessionVisibility,
    game_mode: GameMode = GameMode.NORMAL,
    ranked: bool = True,
    members: list[SessionMemberDocument],
    session_id: str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> SessionDocument:
    now = datetime.now(UTC)
    return SessionDocument(
        id=session_id or str(uuid4()),
        invite_code=invite_code,
        host_user_id=host_user_id,
        status=status,
        visibility=visibility,
        game_mode=game_mode,
        ranked=ranked,
        members=members,
        created_at=created_at or now,
        updated_at=updated_at or now,
    )


def document_to_mongo(doc: SessionDocument) -> dict[str, object]:
    payload = doc.model_dump()
    payload["_id"] = payload.pop("id")
    return payload


def document_from_mongo(raw: dict[str, object]) -> SessionDocument:
    members_raw = cast(list[dict[str, Any]], raw.get("members", []))
    members = [
        SessionMemberDocument(
            user_id=str(m["user_id"]),
            display_name=str(m["display_name"]),
            role=m["role"],
            joined_at=cast(datetime, m["joined_at"]),
            rating=int(m.get("rating", 800)),
            calibration_complete=bool(m.get("calibration_complete", False)),
        )
        for m in members_raw
    ]
    return SessionDocument(
        id=str(raw["_id"]),
        invite_code=str(raw["invite_code"]),
        host_user_id=str(raw["host_user_id"]),
        status=cast(Any, raw["status"]),
        visibility=cast(Any, raw["visibility"]),
        game_mode=cast(Any, raw.get("game_mode", GameMode.NORMAL.value)),
        ranked=bool(raw.get("ranked", True)),
        members=members,
        created_at=cast(datetime, raw["created_at"]),
        updated_at=cast(datetime, raw["updated_at"]),
    )
