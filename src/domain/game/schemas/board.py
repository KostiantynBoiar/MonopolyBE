from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from domain.game.enums import CornerVariant, PropertyColor, SpaceType


class RentTable(BaseModel):
    model_config = ConfigDict(frozen=True)

    base: int
    one_house: int
    two_houses: int
    three_houses: int
    four_houses: int
    hotel: int

    def amount_for(self, houses: int, has_hotel: bool) -> int:
        if has_hotel:
            return self.hotel
        if houses == 4:
            return self.four_houses
        if houses == 3:
            return self.three_houses
        if houses == 2:
            return self.two_houses
        if houses == 1:
            return self.one_house
        return self.base


class BoardSpace(BaseModel):
    model_config = ConfigDict(frozen=True)

    position: int
    type: SpaceType
    name: str
    color_group: PropertyColor | None = None
    price: int | None = None
    rent: RentTable | None = None
    house_cost: int | None = None
    mortgage_value: int | None = None
    corner: CornerVariant | None = None
    tax_amount: int | None = None
