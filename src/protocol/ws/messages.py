from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from protocol.rest.sessions import SessionDetail
from protocol.ws.errors import WsErrorCode

# Stickers are served from the FE under /stickers/<pack>/<file>. Restrict the URL
# to exactly that two-segment shape: the pack segment excludes dots so a leading
# ".." cannot climb out of /stickers/ when the FE resolves the path.
STICKER_URL_PATTERN = r"^/stickers/[\w-]+/[\w.-]+$"


class ChatSendPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1, max_length=1000)


class StickerSendPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    sticker_url: str = Field(min_length=1, max_length=256, pattern=STICKER_URL_PATTERN)


class PongPayload(BaseModel):
    model_config = ConfigDict(frozen=True)


class WelcomePayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str
    your_seq_start: int


class ChatMessagePayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    message_id: str
    from_user_id: str
    display_name: str
    text: str
    ts: datetime


class StickerMessagePayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    message_id: str
    from_user_id: str
    display_name: str
    sticker_url: str
    ts: datetime


class SessionUpdatedPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    # Broadcast to every member, so `session.your_role` is left None here; each
    # client derives its own role from `session.members`.
    session: SessionDetail


class PingPayload(BaseModel):
    model_config = ConfigDict(frozen=True)


class ErrorPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: WsErrorCode
    message: str
    ref_seq: int | None = None
