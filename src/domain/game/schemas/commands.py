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


class Surrender(BaseModel):
    """Voluntarily quit the game: properties return to the bank (free to buy again) and
    the player's cash is split equally among the remaining players. Distinct from
    bankruptcy (which transfers assets to a creditor)."""

    model_config = ConfigDict(frozen=True)

    player_id: str


class AdvanceAuction(BaseModel):
    """System command applied when an auction timer expires."""

    model_config = ConfigDict(frozen=True)


class ExpireTrade(BaseModel):
    """System command applied when a trade offer expires."""

    model_config = ConfigDict(frozen=True)


class TurnTimeout(BaseModel):
    """System command applied when the current player's turn timer expires (AFK)."""

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
    | Surrender
)

SystemCommand = AdvanceAuction | ExpireTrade | TurnTimeout

GameCommand = PlayerCommand | SystemCommand
