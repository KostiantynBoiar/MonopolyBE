from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from domain.game.enums import TradeResponse
from domain.game.schemas.state import TradeOffer


class RollDice(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str


class BuyProperty(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str
    position: int


class PassBuy(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str


class EndTurn(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str


class PayJailFine(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str


class UseJailCard(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str


class BuildHouse(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str
    position: int


class SellHouse(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str
    position: int


class Mortgage(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str
    position: int


class Unmortgage(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str
    position: int


class ProposeTrade(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str
    target_id: str
    proposer_offer: TradeOffer
    target_request: TradeOffer


class RespondTrade(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str
    trade_id: str
    response: TradeResponse
    counter_offer: TradeOffer | None = None


class PlaceBid(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str
    amount: int


class DeclareBankruptcy(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str


class AdvanceAuction(BaseModel):
    """System command applied when an auction timer expires."""

    model_config = ConfigDict(frozen=True)


class ExpireTrade(BaseModel):
    """System command applied when a trade offer expires."""

    model_config = ConfigDict(frozen=True)


PlayerCommand = (
    RollDice
    | BuyProperty
    | PassBuy
    | EndTurn
    | PayJailFine
    | UseJailCard
    | BuildHouse
    | SellHouse
    | Mortgage
    | Unmortgage
    | ProposeTrade
    | RespondTrade
    | PlaceBid
    | DeclareBankruptcy
)

SystemCommand = AdvanceAuction | ExpireTrade

GameCommand = PlayerCommand | SystemCommand
