from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from core.constants import MAX_SESSION_MEMBERS
from domain.session.schemas import MemberRole, SessionStatus, SessionVisibility


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    visibility: SessionVisibility = SessionVisibility.PUBLIC


class JoinByCodeRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    invite_code: str = Field(min_length=8, max_length=12)


class HostSummary(BaseModel):
    id: str
    display_name: str


class SessionMemberResponse(BaseModel):
    user_id: str
    display_name: str
    role: MemberRole
    joined_at: datetime


class SessionSummary(BaseModel):
    id: str
    invite_code: str
    status: SessionStatus
    visibility: SessionVisibility
    member_count: int
    max_players: int = MAX_SESSION_MEMBERS
    host: HostSummary
    created_at: datetime


class SessionDetail(SessionSummary):
    members: list[SessionMemberResponse]
    your_role: MemberRole | None = None


class SessionListResponse(BaseModel):
    items: list[SessionSummary]
    next_cursor: str | None = None


class SessionCreateResponse(BaseModel):
    session: SessionDetail


class JoinSessionResponse(BaseModel):
    session: SessionDetail


class StartSessionResponse(BaseModel):
    session: SessionDetail
    status: Literal["in_progress"] = "in_progress"
