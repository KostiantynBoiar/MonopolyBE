from datetime import UTC, datetime
from uuid import uuid4

from domain.session.schemas import Session, SessionMember, SessionStatus, SessionVisibility
from infra.mongo.sessions.document import SessionDocument, SessionMemberDocument


def to_domain(doc: SessionDocument) -> Session:
    return Session(
        id=doc.id,
        invite_code=doc.invite_code,
        host_user_id=doc.host_user_id,
        status=doc.status,
        visibility=doc.visibility,
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
        members=members,
        created_at=created_at or now,
        updated_at=updated_at or now,
    )


def document_to_mongo(doc: SessionDocument) -> dict[str, object]:
    payload = doc.model_dump()
    payload["_id"] = payload.pop("id")
    return payload


def document_from_mongo(raw: dict[str, object]) -> SessionDocument:
    members_raw = raw.get("members", [])
    members = [
        SessionMemberDocument(
            user_id=str(m["user_id"]),
            display_name=str(m["display_name"]),
            role=m["role"],  # type: ignore[arg-type]
            joined_at=m["joined_at"],  # type: ignore[arg-type]
            rating=int(m.get("rating", 800)),
            calibration_complete=bool(m.get("calibration_complete", False)),
        )
        for m in members_raw  # type: ignore[union-attr]
    ]
    return SessionDocument(
        id=str(raw["_id"]),
        invite_code=str(raw["invite_code"]),
        host_user_id=str(raw["host_user_id"]),
        status=raw["status"],  # type: ignore[arg-type]
        visibility=raw["visibility"],  # type: ignore[arg-type]
        members=members,
        created_at=raw["created_at"],  # type: ignore[arg-type]
        updated_at=raw["updated_at"],  # type: ignore[arg-type]
    )
