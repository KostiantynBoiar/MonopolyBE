from datetime import datetime

from pydantic import BaseModel, ConfigDict

from domain.session.schemas import MemberRole, SessionStatus, SessionVisibility


class SessionMemberDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: str
    display_name: str
    role: MemberRole
    joined_at: datetime


class SessionDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    invite_code: str
    host_user_id: str
    status: SessionStatus
    visibility: SessionVisibility
    members: list[SessionMemberDocument]
    created_at: datetime
    updated_at: datetime
