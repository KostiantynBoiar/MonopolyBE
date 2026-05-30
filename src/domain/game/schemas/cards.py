from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from domain.game.enums import CardKind


class AdvanceToEffect(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["advance_to"] = "advance_to"
    position: int
    collect_go_bonus: bool = True


class AdvanceToNearestEffect(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["advance_to_nearest"] = "advance_to_nearest"
    space_type: Literal["railroad", "utility"]
    pay_double: bool = False


class GoToJailEffect(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["go_to_jail"] = "go_to_jail"


class GoBackEffect(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["go_back"] = "go_back"
    spaces: int


class CollectEffect(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["collect"] = "collect"
    amount: int


class PayEffect(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["pay"] = "pay"
    amount: int


class CollectFromEachPlayerEffect(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["collect_from_each_player"] = "collect_from_each_player"
    amount: int


class PayEachPlayerEffect(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["pay_each_player"] = "pay_each_player"
    amount: int


class GetOutOfJailFreeEffect(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["get_out_of_jail_free"] = "get_out_of_jail_free"


class RepairsEffect(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["repairs"] = "repairs"
    per_house: int
    per_hotel: int


CardEffect = Annotated[
    AdvanceToEffect
    | AdvanceToNearestEffect
    | GoToJailEffect
    | GoBackEffect
    | CollectEffect
    | PayEffect
    | CollectFromEachPlayerEffect
    | PayEachPlayerEffect
    | GetOutOfJailFreeEffect
    | RepairsEffect,
    Field(discriminator="type"),
]


class CardDef(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    kind: CardKind
    text: str
    effect: CardEffect


class ActiveCard(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    kind: CardKind
    text: str
    effect: CardEffect
    drawer_id: str
