from __future__ import annotations

from domain.game.enums import CardKind
from domain.game.schemas.cards import (
    AdvanceToEffect,
    AdvanceToNearestEffect,
    CardDef,
    CollectEffect,
    CollectFromEachPlayerEffect,
    GetOutOfJailFreeEffect,
    GoBackEffect,
    GoToJailEffect,
    PayEachPlayerEffect,
    PayEffect,
    RepairsEffect,
)

CHANCE_CARDS: tuple[CardDef, ...] = (
    CardDef(
        id="chance_01",
        kind=CardKind.CHANCE,
        effect=AdvanceToEffect(position=0, collect_go_bonus=True),
    ),
    CardDef(
        id="chance_02",
        kind=CardKind.CHANCE,
        effect=AdvanceToEffect(position=24, collect_go_bonus=True),
    ),
    CardDef(
        id="chance_03",
        kind=CardKind.CHANCE,
        effect=AdvanceToEffect(position=11, collect_go_bonus=True),
    ),
    CardDef(
        id="chance_04",
        kind=CardKind.CHANCE,
        effect=AdvanceToNearestEffect(space_type="utility", pay_double=False),
    ),
    CardDef(
        id="chance_05",
        kind=CardKind.CHANCE,
        effect=AdvanceToNearestEffect(space_type="railroad", pay_double=True),
    ),
    CardDef(
        id="chance_06",
        kind=CardKind.CHANCE,
        effect=AdvanceToNearestEffect(space_type="railroad", pay_double=True),
    ),
    CardDef(
        id="chance_07",
        kind=CardKind.CHANCE,
        effect=CollectEffect(amount=50),
    ),
    CardDef(
        id="chance_08",
        kind=CardKind.CHANCE,
        effect=GetOutOfJailFreeEffect(),
    ),
    CardDef(
        id="chance_09",
        kind=CardKind.CHANCE,
        effect=GoBackEffect(spaces=3),
    ),
    CardDef(
        id="chance_10",
        kind=CardKind.CHANCE,
        effect=GoToJailEffect(),
    ),
    CardDef(
        id="chance_11",
        kind=CardKind.CHANCE,
        effect=RepairsEffect(per_house=25, per_hotel=100),
    ),
    CardDef(
        id="chance_12",
        kind=CardKind.CHANCE,
        effect=PayEffect(amount=15),
    ),
    CardDef(
        id="chance_13",
        kind=CardKind.CHANCE,
        effect=AdvanceToEffect(position=5, collect_go_bonus=True),
    ),
    CardDef(
        id="chance_14",
        kind=CardKind.CHANCE,
        effect=AdvanceToEffect(position=39, collect_go_bonus=False),
    ),
    CardDef(
        id="chance_15",
        kind=CardKind.CHANCE,
        effect=PayEachPlayerEffect(amount=50),
    ),
    CardDef(
        id="chance_16",
        kind=CardKind.CHANCE,
        effect=CollectEffect(amount=150),
    ),
)

COMMUNITY_CHEST_CARDS: tuple[CardDef, ...] = (
    CardDef(
        id="chest_01",
        kind=CardKind.COMMUNITY_CHEST,
        effect=AdvanceToEffect(position=0, collect_go_bonus=True),
    ),
    CardDef(
        id="chest_02",
        kind=CardKind.COMMUNITY_CHEST,
        effect=CollectEffect(amount=200),
    ),
    CardDef(
        id="chest_03",
        kind=CardKind.COMMUNITY_CHEST,
        effect=PayEffect(amount=50),
    ),
    CardDef(
        id="chest_04",
        kind=CardKind.COMMUNITY_CHEST,
        effect=CollectEffect(amount=50),
    ),
    CardDef(
        id="chest_05",
        kind=CardKind.COMMUNITY_CHEST,
        effect=GetOutOfJailFreeEffect(),
    ),
    CardDef(
        id="chest_06",
        kind=CardKind.COMMUNITY_CHEST,
        effect=GoToJailEffect(),
    ),
    CardDef(
        id="chest_07",
        kind=CardKind.COMMUNITY_CHEST,
        effect=CollectEffect(amount=100),
    ),
    CardDef(
        id="chest_08",
        kind=CardKind.COMMUNITY_CHEST,
        effect=CollectEffect(amount=20),
    ),
    CardDef(
        id="chest_09",
        kind=CardKind.COMMUNITY_CHEST,
        effect=CollectFromEachPlayerEffect(amount=10),
    ),
    CardDef(
        id="chest_10",
        kind=CardKind.COMMUNITY_CHEST,
        effect=CollectEffect(amount=100),
    ),
    CardDef(
        id="chest_11",
        kind=CardKind.COMMUNITY_CHEST,
        effect=PayEffect(amount=100),
    ),
    CardDef(
        id="chest_12",
        kind=CardKind.COMMUNITY_CHEST,
        effect=PayEffect(amount=150),
    ),
    CardDef(
        id="chest_13",
        kind=CardKind.COMMUNITY_CHEST,
        effect=CollectEffect(amount=25),
    ),
    CardDef(
        id="chest_14",
        kind=CardKind.COMMUNITY_CHEST,
        effect=RepairsEffect(per_house=40, per_hotel=115),
    ),
    CardDef(
        id="chest_15",
        kind=CardKind.COMMUNITY_CHEST,
        effect=CollectEffect(amount=10),
    ),
    CardDef(
        id="chest_16",
        kind=CardKind.COMMUNITY_CHEST,
        effect=CollectEffect(amount=100),
    ),
)

ALL_CARDS: dict[str, CardDef] = {
    card.id: card for card in (*CHANCE_CARDS, *COMMUNITY_CHEST_CARDS)
}

DEFAULT_CHANCE_DECK: tuple[str, ...] = tuple(c.id for c in CHANCE_CARDS)
DEFAULT_CHEST_DECK: tuple[str, ...] = tuple(c.id for c in COMMUNITY_CHEST_CARDS)
