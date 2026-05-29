from __future__ import annotations

from pydantic import BaseModel, ConfigDict


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


GameCommand = RollDice | BuyProperty | PassBuy | EndTurn
