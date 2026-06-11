from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from domain.game.enums import GameMode
from domain.game.modes import get_game_config


class SessionStatus(StrEnum):
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"


class SessionVisibility(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"


class MemberRole(StrEnum):
    HOST = "host"
    PLAYER = "player"


class SessionMember(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: str
    display_name: str
    role: MemberRole
    joined_at: datetime
    # Rating snapshot at join (shown in the lobby/waiting room).
    rating: int = 800
    calibration_complete: bool = False


class Session(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    invite_code: str
    host_user_id: str
    status: SessionStatus
    visibility: SessionVisibility
    game_mode: GameMode = GameMode.NORMAL
    ranked: bool = True
    members: tuple[SessionMember, ...]
    created_at: datetime
    updated_at: datetime

    def has_member(self, user_id: str) -> bool:
        return any(member.user_id == user_id for member in self.members)

    def member_count(self) -> int:
        return len(self.members)

    @property
    def max_players(self) -> int:
        return get_game_config(self.game_mode).max_players

    def is_full(self) -> bool:
        return self.member_count() >= self.max_players

    def get_member(self, user_id: str) -> SessionMember | None:
        for member in self.members:
            if member.user_id == user_id:
                return member
        return None

    def is_host(self, user_id: str) -> bool:
        member = self.get_member(user_id)
        return member is not None and member.role == MemberRole.HOST
