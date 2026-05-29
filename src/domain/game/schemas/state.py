from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from domain.game.enums import GameStatus, LogKind, TokenColor, TurnPhase


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
    auction: None = None
    trade: None = None
    active_card: None = None
    log: tuple[LogEntry, ...] = ()
