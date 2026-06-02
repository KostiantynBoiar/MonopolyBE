from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from core.constants import STICKER_URL_PATTERN
from protocol.rest.sessions import SessionDetail
from protocol.ws.errors import WsErrorCode


class ChatSendPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1, max_length=1000)


class StickerSendPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    sticker_url: str = Field(min_length=1, max_length=256, pattern=STICKER_URL_PATTERN)


class PongPayload(BaseModel):
    model_config = ConfigDict(frozen=True)


class AnimationContinuePayload(BaseModel):
    """Sent by the affected player to resume a paused animation, and re-broadcast by the
    server to all members so every client un-pauses the same gate together."""

    model_config = ConfigDict(frozen=True)

    interaction_id: str = Field(min_length=1, max_length=128)


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

    session: SessionDetail


class PingPayload(BaseModel):
    model_config = ConfigDict(frozen=True)


class ErrorPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: WsErrorCode
    message: str
    ref_seq: int | None = None


class RollDicePayload(BaseModel):
    model_config = ConfigDict(frozen=True)


class BuyPropertyPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=0, le=39)


class PassBuyPayload(BaseModel):
    model_config = ConfigDict(frozen=True)


class EndTurnPayload(BaseModel):
    model_config = ConfigDict(frozen=True)


class PayJailFinePayload(BaseModel):
    model_config = ConfigDict(frozen=True)


class UseJailCardPayload(BaseModel):
    model_config = ConfigDict(frozen=True)


class BuildHousePayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=0, le=39)


class SellHousePayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=0, le=39)


class MortgagePayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=0, le=39)


class UnmortgagePayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    position: int = Field(ge=0, le=39)


class TradeOfferPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    money: int = Field(ge=0)
    positions: list[int] = Field(default_factory=list)
    get_out_of_jail_cards: int = Field(default=0, ge=0)


class ProposeTradePayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    target_id: str
    proposer_offer: TradeOfferPayload
    target_request: TradeOfferPayload


class RespondTradePayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    trade_id: str
    response: str
    counter_offer: TradeOfferPayload | None = None


class PlaceBidPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    amount: int = Field(gt=0)


class DeclareBankruptcyPayload(BaseModel):
    model_config = ConfigDict(frozen=True)
