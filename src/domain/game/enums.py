from enum import StrEnum


class SpaceType(StrEnum):
    CORNER = "corner"
    PROPERTY = "property"
    RAILROAD = "railroad"
    UTILITY = "utility"
    CHANCE = "chance"
    CHEST = "chest"
    TAX = "tax"


class CornerVariant(StrEnum):
    GO = "go"
    JAIL = "jail"
    PARKING = "parking"
    GOTO_JAIL = "gotojail"


class PropertyColor(StrEnum):
    BROWN = "brown"
    CYAN = "cyan"
    PINK = "pink"
    ORANGE = "orange"
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"
    BLUE = "blue"


class GameStatus(StrEnum):
    LOBBY = "lobby"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"


class TurnPhase(StrEnum):
    PRE_ROLL = "pre_roll"
    JAIL_DECISION = "jail_decision"
    POST_ROLL = "post_roll"
    MUST_PAY_RENT = "must_pay_rent"
    DRAWING_CARD = "drawing_card"
    AUCTION = "auction"
    TRADE_NEGOTIATION = "trade_negotiation"
    BANKRUPT_RESOLUTION = "bankrupt_resolution"
    GAME_OVER = "game_over"


class TokenColor(StrEnum):
    BLUE = "blue"
    RED = "red"
    GREEN = "green"
    YELLOW = "yellow"
    ORANGE = "orange"
    PINK = "pink"
    CYAN = "cyan"
    BROWN = "brown"
    GOLD = "gold"
    INK = "ink"


class LogKind(StrEnum):
    EVENT = "event"
    CHAT = "chat"
    STICKER = "sticker"
