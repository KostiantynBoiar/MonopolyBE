from typing import Annotated

from fastapi import APIRouter, Depends, Query

from application.dependencies import get_session_service
from application.services.session_service import SessionService
from core.dependencies import get_current_user_id
from domain.session.model import Session
from protocol.rest.sessions import (
    CreateSessionRequest,
    HostSummary,
    JoinByCodeRequest,
    JoinSessionResponse,
    SessionCreateResponse,
    SessionDetail,
    SessionListResponse,
    SessionMemberResponse,
    SessionSummary,
    StartSessionResponse,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _to_summary(session: Session) -> SessionSummary:
    host_member = next(
        (m for m in session.members if m.user_id == session.host_user_id),
        session.members[0],
    )
    return SessionSummary(
        id=session.id,
        invite_code=session.invite_code,
        status=session.status,
        visibility=session.visibility,
        member_count=session.member_count(),
        host=HostSummary(id=host_member.user_id, display_name=host_member.display_name),
        created_at=session.created_at,
    )


def _to_detail(session: Session, user_id: str | None = None) -> SessionDetail:
    summary = _to_summary(session)
    member = session.get_member(user_id) if user_id else None
    return SessionDetail(
        **summary.model_dump(),
        members=[
            SessionMemberResponse(
                user_id=m.user_id,
                display_name=m.display_name,
                role=m.role,
                joined_at=m.joined_at,
            )
            for m in session.members
        ],
        your_role=member.role if member else None,
    )


@router.post("", response_model=SessionCreateResponse, status_code=201)
async def create_session(
    body: CreateSessionRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> SessionCreateResponse:
    session = await service.create(user_id, visibility=body.visibility)
    return SessionCreateResponse(session=_to_detail(session, user_id))


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[SessionService, Depends(get_session_service)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> SessionListResponse:
    sessions, next_cursor = await service.list_public_lobby(limit=limit, cursor=cursor)
    return SessionListResponse(
        items=[_to_summary(s) for s in sessions],
        next_cursor=next_cursor,
    )


@router.get("/by-code/{invite_code}", response_model=SessionDetail)
async def get_session_by_code(
    invite_code: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> SessionDetail:
    session = await service.get_by_code(invite_code, user_id)
    return _to_detail(session, user_id)


@router.post("/join-by-code", response_model=JoinSessionResponse)
async def join_by_code(
    body: JoinByCodeRequest,
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> JoinSessionResponse:
    session = await service.join_by_code(body.invite_code, user_id)
    return JoinSessionResponse(session=_to_detail(session, user_id))


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> SessionDetail:
    session = await service.get(session_id, user_id)
    return _to_detail(session, user_id)


@router.post("/{session_id}/join", response_model=JoinSessionResponse)
async def join_session(
    session_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> JoinSessionResponse:
    session = await service.join(session_id, user_id)
    return JoinSessionResponse(session=_to_detail(session, user_id))


@router.post("/{session_id}/leave", status_code=204)
async def leave_session(
    session_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> None:
    await service.leave(session_id, user_id)


@router.delete("/{session_id}/members/{target_user_id}", response_model=SessionDetail)
async def kick_member(
    session_id: str,
    target_user_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> SessionDetail:
    session = await service.kick(session_id, user_id, target_user_id)
    return _to_detail(session, user_id)


@router.post("/{session_id}/start", response_model=StartSessionResponse)
async def start_session(
    session_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> StartSessionResponse:
    session = await service.start(session_id, user_id)
    return StartSessionResponse(session=_to_detail(session, user_id))
