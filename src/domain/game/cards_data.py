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
        text="Advance to GO (Collect $200)",
        effect=AdvanceToEffect(position=0, collect_go_bonus=True),
    ),
    CardDef(
        id="chance_02",
        kind=CardKind.CHANCE,
        text="Advance to Illinois Ave. If you pass GO, collect $200",
        effect=AdvanceToEffect(position=24, collect_go_bonus=True),
    ),
    CardDef(
        id="chance_03",
        kind=CardKind.CHANCE,
        text="Advance to St. Charles Place. If you pass GO, collect $200",
        effect=AdvanceToEffect(position=11, collect_go_bonus=True),
    ),
    CardDef(
        id="chance_04",
        kind=CardKind.CHANCE,
        text="Advance token to nearest Utility. If unowned, you may buy it.",
        effect=AdvanceToNearestEffect(space_type="utility", pay_double=False),
    ),
    CardDef(
        id="chance_05",
        kind=CardKind.CHANCE,
        text="Advance token to nearest Railroad. Pay owner twice the rental.",
        effect=AdvanceToNearestEffect(space_type="railroad", pay_double=True),
    ),
    CardDef(
        id="chance_06",
        kind=CardKind.CHANCE,
        text="Advance token to nearest Railroad. Pay owner twice the rental.",
        effect=AdvanceToNearestEffect(space_type="railroad", pay_double=True),
    ),
    CardDef(
        id="chance_07",
        kind=CardKind.CHANCE,
        text="Bank pays you dividend of $50",
        effect=CollectEffect(amount=50),
    ),
    CardDef(
        id="chance_08",
        kind=CardKind.CHANCE,
        text="Get Out of Jail Free",
        effect=GetOutOfJailFreeEffect(),
    ),
    CardDef(
        id="chance_09",
        kind=CardKind.CHANCE,
        text="Go Back 3 Spaces",
        effect=GoBackEffect(spaces=3),
    ),
    CardDef(
        id="chance_10",
        kind=CardKind.CHANCE,
        text="Go to Jail. Go directly to Jail. Do not pass GO, do not collect $200",
        effect=GoToJailEffect(),
    ),
    CardDef(
        id="chance_11",
        kind=CardKind.CHANCE,
        text="Make general repairs on all your property — For each house pay $25 — For each hotel pay $100",
        effect=RepairsEffect(per_house=25, per_hotel=100),
    ),
    CardDef(
        id="chance_12",
        kind=CardKind.CHANCE,
        text="Speeding fine $15",
        effect=PayEffect(amount=15),
    ),
    CardDef(
        id="chance_13",
        kind=CardKind.CHANCE,
        text="Take a trip to Reading Railroad. If you pass GO, collect $200",
        effect=AdvanceToEffect(position=5, collect_go_bonus=True),
    ),
    CardDef(
        id="chance_14",
        kind=CardKind.CHANCE,
        text="Take a walk on the Boardwalk. Advance token to Boardwalk",
        effect=AdvanceToEffect(position=39, collect_go_bonus=False),
    ),
    CardDef(
        id="chance_15",
        kind=CardKind.CHANCE,
        text="You have been elected Chairman of the Board. Pay each player $50",
        effect=PayEachPlayerEffect(amount=50),
    ),
    CardDef(
        id="chance_16",
        kind=CardKind.CHANCE,
        text="Your building loan matures. Collect $150",
        effect=CollectEffect(amount=150),
    ),
)

COMMUNITY_CHEST_CARDS: tuple[CardDef, ...] = (
    CardDef(
        id="chest_01",
        kind=CardKind.COMMUNITY_CHEST,
        text="Advance to GO (Collect $200)",
        effect=AdvanceToEffect(position=0, collect_go_bonus=True),
    ),
    CardDef(
        id="chest_02",
        kind=CardKind.COMMUNITY_CHEST,
        text="Bank error in your favor. Collect $200",
        effect=CollectEffect(amount=200),
    ),
    CardDef(
        id="chest_03",
        kind=CardKind.COMMUNITY_CHEST,
        text="Doctor's fees. Pay $50",
        effect=PayEffect(amount=50),
    ),
    CardDef(
        id="chest_04",
        kind=CardKind.COMMUNITY_CHEST,
        text="From sale of stock you get $50",
        effect=CollectEffect(amount=50),
    ),
    CardDef(
        id="chest_05",
        kind=CardKind.COMMUNITY_CHEST,
        text="Get Out of Jail Free",
        effect=GetOutOfJailFreeEffect(),
    ),
    CardDef(
        id="chest_06",
        kind=CardKind.COMMUNITY_CHEST,
        text="Go to Jail. Go directly to Jail. Do not pass GO, do not collect $200",
        effect=GoToJailEffect(),
    ),
    CardDef(
        id="chest_07",
        kind=CardKind.COMMUNITY_CHEST,
        text="Holiday Fund matures. Collect $100",
        effect=CollectEffect(amount=100),
    ),
    CardDef(
        id="chest_08",
        kind=CardKind.COMMUNITY_CHEST,
        text="Income tax refund. Collect $20",
        effect=CollectEffect(amount=20),
    ),
    CardDef(
        id="chest_09",
        kind=CardKind.COMMUNITY_CHEST,
        text="It is your birthday. Collect $10 from every player",
        effect=CollectFromEachPlayerEffect(amount=10),
    ),
    CardDef(
        id="chest_10",
        kind=CardKind.COMMUNITY_CHEST,
        text="Life insurance matures. Collect $100",
        effect=CollectEffect(amount=100),
    ),
    CardDef(
        id="chest_11",
        kind=CardKind.COMMUNITY_CHEST,
        text="Pay hospital fees of $100",
        effect=PayEffect(amount=100),
    ),
    CardDef(
        id="chest_12",
        kind=CardKind.COMMUNITY_CHEST,
        text="Pay school fees of $150",
        effect=PayEffect(amount=150),
    ),
    CardDef(
        id="chest_13",
        kind=CardKind.COMMUNITY_CHEST,
        text="Receive $25 consultancy fee",
        effect=CollectEffect(amount=25),
    ),
    CardDef(
        id="chest_14",
        kind=CardKind.COMMUNITY_CHEST,
        text="You are assessed for street repairs — $40 per house, $115 per hotel",
        effect=RepairsEffect(per_house=40, per_hotel=115),
    ),
    CardDef(
        id="chest_15",
        kind=CardKind.COMMUNITY_CHEST,
        text="You have won second prize in a beauty contest. Collect $10",
        effect=CollectEffect(amount=10),
    ),
    CardDef(
        id="chest_16",
        kind=CardKind.COMMUNITY_CHEST,
        text="You inherit $100",
        effect=CollectEffect(amount=100),
    ),
)

ALL_CARDS: dict[str, CardDef] = {
    card.id: card for card in (*CHANCE_CARDS, *COMMUNITY_CHEST_CARDS)
}

DEFAULT_CHANCE_DECK: tuple[str, ...] = tuple(c.id for c in CHANCE_CARDS)
DEFAULT_CHEST_DECK: tuple[str, ...] = tuple(c.id for c in COMMUNITY_CHEST_CARDS)
