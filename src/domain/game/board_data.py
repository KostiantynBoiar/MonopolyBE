from __future__ import annotations

from domain.game.constants import (
    HOUSE_COST_BROWN_CYAN,
    HOUSE_COST_GREEN_BLUE,
    HOUSE_COST_PINK_ORANGE,
    HOUSE_COST_RED_YELLOW,
    INCOME_TAX_AMOUNT,
    LUXURY_TAX_AMOUNT,
    PURCHASABLE_TYPES,
    RAILROAD_MORTGAGE_VALUE,
    RAILROAD_PRICE,
    UTILITY_MORTGAGE_VALUE,
    UTILITY_PRICE,
)
from domain.game.enums import CornerVariant, PropertyColor, SpaceType
from domain.game.schemas.board import BoardSpace, RentTable


def _rent(
    base: int,
    one: int,
    two: int,
    three: int,
    four: int,
    hotel: int,
) -> RentTable:
    return RentTable(
        base=base,
        one_house=one,
        two_houses=two,
        three_houses=three,
        four_houses=four,
        hotel=hotel,
    )


def _street(
    position: int,
    name: str,
    price: int,
    color: PropertyColor,
    rent: RentTable,
    house_cost: int,
) -> BoardSpace:
    return BoardSpace(
        position=position,
        type=SpaceType.PROPERTY,
        name=name,
        color_group=color,
        price=price,
        rent=rent,
        house_cost=house_cost,
        mortgage_value=price // 2,
    )


def _railroad(position: int, name: str) -> BoardSpace:
    return BoardSpace(
        position=position,
        type=SpaceType.RAILROAD,
        name=name,
        price=RAILROAD_PRICE,
        mortgage_value=RAILROAD_MORTGAGE_VALUE,
    )


def _utility(position: int, name: str) -> BoardSpace:
    return BoardSpace(
        position=position,
        type=SpaceType.UTILITY,
        name=name,
        price=UTILITY_PRICE,
        mortgage_value=UTILITY_MORTGAGE_VALUE,
    )


BOARD: tuple[BoardSpace, ...] = (
    BoardSpace(
        position=0,
        type=SpaceType.CORNER,
        name="TYCOON",
        corner=CornerVariant.GO,
    ),
    _street(
        1,
        "Mediterranean Ave",
        60,
        PropertyColor.BROWN,
        _rent(2, 10, 30, 90, 160, 250),
        HOUSE_COST_BROWN_CYAN,
    ),
    BoardSpace(position=2, type=SpaceType.CHEST, name="Community Chest"),
    _street(
        3,
        "Baltic Ave",
        60,
        PropertyColor.BROWN,
        _rent(4, 20, 60, 180, 320, 450),
        HOUSE_COST_BROWN_CYAN,
    ),
    BoardSpace(
        position=4,
        type=SpaceType.TAX,
        name="Income Tax",
        tax_amount=INCOME_TAX_AMOUNT,
    ),
    _railroad(5, "Reading Railroad"),
    _street(
        6,
        "Oriental Ave",
        100,
        PropertyColor.CYAN,
        _rent(6, 30, 90, 270, 400, 550),
        HOUSE_COST_BROWN_CYAN,
    ),
    BoardSpace(position=7, type=SpaceType.CHANCE, name="Chance"),
    _street(
        8,
        "Vermont Ave",
        100,
        PropertyColor.CYAN,
        _rent(6, 30, 90, 270, 400, 550),
        HOUSE_COST_BROWN_CYAN,
    ),
    _street(
        9,
        "Connecticut Ave",
        120,
        PropertyColor.CYAN,
        _rent(8, 40, 100, 300, 450, 600),
        HOUSE_COST_BROWN_CYAN,
    ),
    BoardSpace(
        position=10,
        type=SpaceType.CORNER,
        name="Just Visiting",
        corner=CornerVariant.JAIL,
    ),
    _street(
        11,
        "St. Charles Place",
        140,
        PropertyColor.PINK,
        _rent(10, 50, 150, 450, 625, 750),
        HOUSE_COST_PINK_ORANGE,
    ),
    _utility(12, "Electric Company"),
    _street(
        13,
        "States Ave",
        140,
        PropertyColor.PINK,
        _rent(10, 50, 150, 450, 625, 750),
        HOUSE_COST_PINK_ORANGE,
    ),
    _street(
        14,
        "Virginia Ave",
        160,
        PropertyColor.PINK,
        _rent(12, 60, 180, 500, 700, 900),
        HOUSE_COST_PINK_ORANGE,
    ),
    _railroad(15, "Pennsylvania Railroad"),
    _street(
        16,
        "St. James Place",
        180,
        PropertyColor.ORANGE,
        _rent(14, 70, 200, 550, 750, 950),
        HOUSE_COST_PINK_ORANGE,
    ),
    BoardSpace(position=17, type=SpaceType.CHEST, name="Community Chest"),
    _street(
        18,
        "Tennessee Ave",
        180,
        PropertyColor.ORANGE,
        _rent(14, 70, 200, 550, 750, 950),
        HOUSE_COST_PINK_ORANGE,
    ),
    _street(
        19,
        "New York Ave",
        200,
        PropertyColor.ORANGE,
        _rent(16, 80, 220, 600, 800, 1000),
        HOUSE_COST_PINK_ORANGE,
    ),
    BoardSpace(
        position=20,
        type=SpaceType.CORNER,
        name="Free Parking",
        corner=CornerVariant.PARKING,
    ),
    _street(
        21,
        "Kentucky Ave",
        220,
        PropertyColor.RED,
        _rent(18, 90, 250, 700, 875, 1050),
        HOUSE_COST_RED_YELLOW,
    ),
    BoardSpace(position=22, type=SpaceType.CHANCE, name="Chance"),
    _street(
        23,
        "Indiana Ave",
        220,
        PropertyColor.RED,
        _rent(18, 90, 250, 700, 875, 1050),
        HOUSE_COST_RED_YELLOW,
    ),
    _street(
        24,
        "Illinois Ave",
        240,
        PropertyColor.RED,
        _rent(20, 100, 300, 750, 925, 1100),
        HOUSE_COST_RED_YELLOW,
    ),
    _railroad(25, "B&O Railroad"),
    _street(
        26,
        "Atlantic Ave",
        260,
        PropertyColor.YELLOW,
        _rent(22, 110, 330, 800, 975, 1150),
        HOUSE_COST_RED_YELLOW,
    ),
    _street(
        27,
        "Ventnor Ave",
        260,
        PropertyColor.YELLOW,
        _rent(22, 110, 330, 800, 975, 1150),
        HOUSE_COST_RED_YELLOW,
    ),
    _utility(28, "Water Works"),
    _street(
        29,
        "Marvin Gardens",
        280,
        PropertyColor.YELLOW,
        _rent(24, 120, 360, 850, 1025, 1200),
        HOUSE_COST_RED_YELLOW,
    ),
    BoardSpace(
        position=30,
        type=SpaceType.CORNER,
        name="Go to Jail",
        corner=CornerVariant.GOTO_JAIL,
    ),
    _street(
        31,
        "Pacific Ave",
        300,
        PropertyColor.GREEN,
        _rent(26, 130, 390, 900, 1100, 1275),
        HOUSE_COST_GREEN_BLUE,
    ),
    _street(
        32,
        "North Carolina Ave",
        300,
        PropertyColor.GREEN,
        _rent(26, 130, 390, 900, 1100, 1275),
        HOUSE_COST_GREEN_BLUE,
    ),
    BoardSpace(position=33, type=SpaceType.CHEST, name="Community Chest"),
    _street(
        34,
        "Pennsylvania Ave",
        320,
        PropertyColor.GREEN,
        _rent(28, 150, 450, 1000, 1200, 1400),
        HOUSE_COST_GREEN_BLUE,
    ),
    _railroad(35, "Short Line Railroad"),
    BoardSpace(position=36, type=SpaceType.CHANCE, name="Chance"),
    _street(
        37,
        "Park Place",
        350,
        PropertyColor.BLUE,
        _rent(35, 175, 500, 1100, 1300, 1500),
        HOUSE_COST_GREEN_BLUE,
    ),
    BoardSpace(
        position=38,
        type=SpaceType.TAX,
        name="Luxury Tax",
        tax_amount=LUXURY_TAX_AMOUNT,
    ),
    _street(
        39,
        "Boardwalk",
        400,
        PropertyColor.BLUE,
        _rent(50, 200, 600, 1400, 1700, 2000),
        HOUSE_COST_GREEN_BLUE,
    ),
)

BOARD_BY_POSITION: dict[int, BoardSpace] = {space.position: space for space in BOARD}


def is_purchasable(position: int) -> bool:
    space = BOARD_BY_POSITION[position]
    return space.type in PURCHASABLE_TYPES


def get_board_space(position: int) -> BoardSpace:
    return BOARD_BY_POSITION[position]
