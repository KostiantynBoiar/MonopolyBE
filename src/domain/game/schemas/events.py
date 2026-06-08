from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from domain.game.enums import LogKind, TokenColor
from domain.game.schemas.state import LogEntry


class PlayerMoved(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str
    player_name: str
    player_token: TokenColor
    from_position: int
    to_position: int
    dice_total: int
    # Why the player moved — drives the animation timeline (speed/SFX). "dice" is a
    # normal roll-walk, "card" is a card-induced displacement (faster), "teleport"/"jail"
    # are instant. Defaults to "dice" so existing emitters/tests need no change.
    reason: Literal["dice", "card", "teleport", "jail"] = "dice"


class PassedGo(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str
    player_name: str
    amount: int


class RentPaid(BaseModel):
    model_config = ConfigDict(frozen=True)

    payer_id: str
    payer_name: str
    owner_id: str
    owner_name: str
    position: int
    property_name: str
    amount: int


class PropertyBought(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str
    player_name: str
    position: int
    property_name: str
    price: int


class BuyDeclined(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str
    player_name: str
    position: int
    property_name: str


class RolledDoubles(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str
    player_name: str
    streak: int


class SentToJail(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str
    player_name: str
    reason: Literal["doubles", "go_to_jail_space", "card"]


class TaxPaid(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str
    player_name: str
    position: int
    amount: int


class TurnEnded(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str
    player_name: str
    next_player_id: str
    next_player_name: str


class CardDrawn(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str
    player_name: str
    card_id: str
    kind: str


class PlayerSurrendered(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str
    player_name: str
    reason: str  # "voluntary" | "afk"


class TurnTimedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str
    player_name: str
    strikes: int


GameEvent = (
    PlayerMoved
    | PassedGo
    | RentPaid
    | PropertyBought
    | BuyDeclined
    | RolledDoubles
    | SentToJail
    | TaxPaid
    | TurnEnded
    | CardDrawn
    | PlayerSurrendered
    | TurnTimedOut
)


def event_to_log_entry(event: GameEvent, ts: datetime) -> LogEntry:
    """Map a typed game event to a structured, language-agnostic LogEntry. The frontend renders a
    localized string from `type` + the populated fields; the backend ships no English prose here."""
    entry_id = uuid4().hex
    match event:
        case PlayerMoved() as e:
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                type="player_moved",
                player_id=e.player_id,
                player_name=e.player_name,
                player_token=e.player_token,
                tile_id=e.to_position,
                # Card/teleport/jail moves aren't dice-driven (dice_total == 0); omit `rolled` so the
                # FE picks a "moved to X" template instead of "rolled 0 and moved".
                rolled=e.dice_total if e.reason == "dice" else None,
                ts=ts,
            )
        case PassedGo() as e:
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                type="passed_go",
                player_id=e.player_id,
                player_name=e.player_name,
                received=e.amount,
                ts=ts,
            )
        case RentPaid() as e:
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                type="rent_paid",
                player_id=e.payer_id,
                player_name=e.payer_name,
                opponent_id=e.owner_id,
                tile_id=e.position,
                spent=e.amount,
                ts=ts,
            )
        case PropertyBought() as e:
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                type="property_bought",
                player_id=e.player_id,
                player_name=e.player_name,
                tile_id=e.position,
                spent=e.price,
                ts=ts,
            )
        case BuyDeclined() as e:
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                type="buy_declined",
                player_id=e.player_id,
                player_name=e.player_name,
                tile_id=e.position,
                ts=ts,
            )
        case RolledDoubles() as e:
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                type="rolled_doubles",
                player_id=e.player_id,
                player_name=e.player_name,
                streak=e.streak,
                ts=ts,
            )
        case SentToJail() as e:
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                type="sent_to_jail",
                player_id=e.player_id,
                player_name=e.player_name,
                reason=e.reason,
                ts=ts,
            )
        case TaxPaid() as e:
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                type="tax_paid",
                player_id=e.player_id,
                player_name=e.player_name,
                tile_id=e.position,
                spent=e.amount,
                ts=ts,
            )
        case TurnEnded() as e:
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                type="turn_ended",
                player_id=e.next_player_id,
                player_name=e.next_player_name,
                ts=ts,
            )
        case CardDrawn() as e:
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                type="card_drawn",
                player_id=e.player_id,
                player_name=e.player_name,
                card_id=e.card_id,
                card_kind=e.kind,
                ts=ts,
            )
        case PlayerSurrendered() as e:
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                type="player_surrendered",
                player_id=e.player_id,
                player_name=e.player_name,
                reason=e.reason,
                ts=ts,
            )
        case TurnTimedOut() as e:
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                type="turn_timed_out",
                player_id=e.player_id,
                player_name=e.player_name,
                strikes=e.strikes,
                ts=ts,
            )
