from domain.game.enums import SpaceType, TokenColor

STARTING_BALANCE = 1500
GO_SALARY = 200
JAIL_FINE = 50
BANK_HOUSES = 32
BANK_HOTELS = 12
MORTGAGE_INTEREST = 0.10
HOUSE_SELL_RATIO = 0.5
AUCTION_DURATION_MS = 30_000
TRADE_DURATION_MS = 60_000
CARD_LANDING_RECURSION_LIMIT = 3

# Per-player turn timer: the current player has this long to make their next move
# (refreshed on each action). On expiry the GameScheduler force-ends their turn and
# records an AFK strike; at MAX_AFK_STRIKES the player is auto-surrendered.
TURN_TIMEOUT_MS = 90_000
MAX_AFK_STRIKES = 3

BOARD_SIZE = 40
GO_POSITION = 0
JAIL_POSITION = 10
GOTO_JAIL_POSITION = 30

RAILROAD_POSITIONS: frozenset[int] = frozenset({5, 15, 25, 35})
UTILITY_POSITIONS: frozenset[int] = frozenset({12, 28})

RAILROAD_PRICE = 200
RAILROAD_MORTGAGE_VALUE = 100
UTILITY_PRICE = 150
UTILITY_MORTGAGE_VALUE = 75

INCOME_TAX_AMOUNT = 200
LUXURY_TAX_AMOUNT = 100

RAILROAD_RENTS: tuple[int, ...] = (25, 50, 100, 200)
MAX_RAILROADS_OWNED = 4
UTILITY_RENT_MULTIPLIER_ONE = 4
UTILITY_RENT_MULTIPLIER_TWO = 10

DOUBLES_JAIL_THRESHOLD = 3
JAIL_TURNS_INITIAL = 3

DICE_MIN = 1
DICE_MAX = 6

MONOPOLY_RENT_MULTIPLIER = 2
HOTEL_HOUSE_COUNT = 5

HOUSE_COST_BROWN_CYAN = 50
HOUSE_COST_PINK_ORANGE = 100
HOUSE_COST_RED_YELLOW = 150
HOUSE_COST_GREEN_BLUE = 200

PURCHASABLE_TYPES: frozenset[SpaceType] = frozenset(
    {SpaceType.PROPERTY, SpaceType.RAILROAD, SpaceType.UTILITY}
)

TOKEN_COLORS: tuple[TokenColor, ...] = (
    TokenColor.BLUE,
    TokenColor.RED,
    TokenColor.GREEN,
    TokenColor.YELLOW,
    TokenColor.ORANGE,
    TokenColor.PINK,
    TokenColor.CYAN,
    TokenColor.BROWN,
    TokenColor.GOLD,
    TokenColor.INK,
)
