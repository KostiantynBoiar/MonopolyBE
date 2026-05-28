from pydantic import BaseModel, ConfigDict, Field

from protocol.ws.errors import WsErrorCode


class ChatSendPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1, max_length=1000)


class PongPayload(BaseModel):
    model_config = ConfigDict(frozen=True)


class WelcomePayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str
    your_seq_start: int


class ChatMessagePayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    from_user_id: str
    text: str


class PingPayload(BaseModel):
    model_config = ConfigDict(frozen=True)


class ErrorPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: WsErrorCode
    message: str
    ref_seq: int | None = None
