from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from domain.game.enums import GameMode
from domain.session.schemas import MemberRole, SessionStatus, SessionVisibility


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    visibility: SessionVisibility = SessionVisibility.PUBLIC
    ranked: bool = True
    game_mode: GameMode = GameMode.NORMAL


class JoinByCodeRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    invite_code: str = Field(min_length=8, max_length=12)


class HostSummary(BaseModel):
    id: str
    display_name: str
    rating: int = 800
    calibration_complete: bool = False


class SessionMemberResponse(BaseModel):
    user_id: str
    display_name: str
    role: MemberRole
    joined_at: datetime
    rating: int = 800
    calibration_complete: bool = False


class SessionSummary(BaseModel):
    id: str
    invite_code: str
    status: SessionStatus
    visibility: SessionVisibility
    game_mode: GameMode = GameMode.NORMAL
    ranked: bool = True
    member_count: int
    max_players: int
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
