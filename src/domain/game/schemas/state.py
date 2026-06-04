from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from domain.game.enums import GameStatus, LogKind, TokenColor, TradeStatus, TurnPhase
from domain.game.schemas.cards import ActiveCard


class DiceRoll(BaseModel):
    model_config = ConfigDict(frozen=True)

    die1: int
    die2: int
    is_doubles: bool


class JailStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    turns_remaining: int


class ActionSet(BaseModel):
    model_config = ConfigDict(frozen=True)

    can_roll: bool = False
    can_buy: bool = False
    can_build: bool = False
    can_mortgage: bool = False
    can_unmortgage: bool = False
    can_trade: bool = False
    can_end_turn: bool = False
    can_pay_jail_fine: bool = False
    can_use_jail_card: bool = False
    can_bid: bool = False
    can_declare_bankruptcy: bool = False
    can_surrender: bool = False


class SpaceOwnership(BaseModel):
    model_config = ConfigDict(frozen=True)

    position: int
    owner_id: str | None = None
    houses: int = 0
    has_hotel: bool = False
    is_mortgaged: bool = False


class PlayerState(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    user_id: str
    display_name: str
    token: TokenColor
    avatar_url: str | None = None
    turn_order: int
    position: int = 0
    balance: int
    owned_positions: tuple[int, ...] = ()
    get_out_of_jail_cards: int = 0
    jail_status: JailStatus | None = None
    is_bankrupt: bool = False
    is_connected: bool = True
    net_worth: int = 0
    # ELO rating at game start (snapshot — ratings only change when a game finishes).
    rating: int = 800
    # Consecutive turn-timer expirations (AFK). Reset to 0 when the player acts; at
    # MAX_AFK_STRIKES the player is auto-surrendered.
    afk_strikes: int = 0
    # Turn number at which this player was eliminated (bankruptcy/surrender), or None if
    # still in the game. Used to derive finish placement for rating.
    eliminated_at: int | None = None


class TurnState(BaseModel):
    model_config = ConfigDict(frozen=True)

    phase: TurnPhase
    current_player_id: str
    turn_number: int = 1
    round_number: int = 1
    dice_roll: DiceRoll | None = None
    doubles_streak: int = 0
    actions_available: ActionSet = Field(default_factory=ActionSet)
    pending_buy_position: int | None = None
    # Absolute epoch-ms deadline for the current player's next action. The GameScheduler
    # force-ends the turn once now >= this. Refreshed on every applied command.
    turn_deadline_ms: int | None = None


class LogEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    kind: LogKind
    text: str
    ts: datetime
    player_id: str | None = None
    player_name: str | None = None
    player_token: TokenColor | None = None
    sticker_url: str | None = None


class AuctionBid(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str
    amount: int


class AuctionState(BaseModel):
    model_config = ConfigDict(frozen=True)

    property_position: int
    bids: tuple[AuctionBid, ...] = ()
    highest_bid: int = 0
    highest_bidder_id: str | None = None
    time_remaining_ms: int = 0
    started_at_ms: int = 0


class TradeOffer(BaseModel):
    model_config = ConfigDict(frozen=True)

    money: int = 0
    positions: tuple[int, ...] = ()
    get_out_of_jail_cards: int = 0


class TradeState(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    proposer_id: str
    target_id: str
    proposer_offer: TradeOffer
    target_request: TradeOffer
    status: TradeStatus
    expires_at: datetime


class BankruptcyState(BaseModel):
    model_config = ConfigDict(frozen=True)

    debtor_id: str
    creditor_id: str | None = None
    amount_owed: int


class GameState(BaseModel):
    model_config = ConfigDict(frozen=True)

    game_id: str
    session_code: str
    status: GameStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    winner_id: str | None = None
    players: tuple[PlayerState, ...]
    turn: TurnState
    spaces: tuple[SpaceOwnership, ...]
    auction: AuctionState | None = None
    trade: TradeState | None = None
    active_card: ActiveCard | None = None
    bankruptcy: BankruptcyState | None = None
    bank_houses: int = 32
    bank_hotels: int = 12
    chance_deck: tuple[str, ...] = ()
    chest_deck: tuple[str, ...] = ()
    log: tuple[LogEntry, ...] = ()
