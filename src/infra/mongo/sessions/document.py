from datetime import datetime

from pydantic import BaseModel, ConfigDict

from domain.game.enums import GameMode
from domain.session.schemas import MemberRole, SessionStatus, SessionVisibility


class SessionMemberDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: str
    display_name: str
    role: MemberRole
    joined_at: datetime
    rating: int = 800
    calibration_complete: bool = False


class SessionDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    invite_code: str
    host_user_id: str
    status: SessionStatus
    visibility: SessionVisibility
    game_mode: GameMode = GameMode.NORMAL
    ranked: bool = True
    members: list[SessionMemberDocument]
    created_at: datetime
    updated_at: datetime
