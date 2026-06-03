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
    reason: str


class TaxPaid(BaseModel):
    model_config = ConfigDict(frozen=True)

    player_id: str
    player_name: str
    position: int
    tax_name: str
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
    card_text: str
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
    entry_id = uuid4().hex
    match event:
        case PlayerMoved() as e:
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                player_id=e.player_id,
                player_name=e.player_name,
                player_token=e.player_token,
                text=f"rolled {e.dice_total} and moved to position {e.to_position}",
                ts=ts,
            )
        case PassedGo() as e:
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                player_id=e.player_id,
                player_name=e.player_name,
                text=f"passed GO and collected ${e.amount}",
                ts=ts,
            )
        case RentPaid() as e:
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                player_id=e.payer_id,
                player_name=e.payer_name,
                text=(
                    f"paid ${e.amount} rent on {e.property_name} "
                    f"to {e.owner_name}"
                ),
                ts=ts,
            )
        case PropertyBought() as e:
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                player_id=e.player_id,
                player_name=e.player_name,
                text=f"bought {e.property_name} for ${e.price}",
                ts=ts,
            )
        case BuyDeclined() as e:
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                player_id=e.player_id,
                player_name=e.player_name,
                text=f"declined to buy {e.property_name}",
                ts=ts,
            )
        case RolledDoubles() as e:
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                player_id=e.player_id,
                player_name=e.player_name,
                text=f"rolled doubles ({e.streak} in a row)",
                ts=ts,
            )
        case SentToJail() as e:
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                player_id=e.player_id,
                player_name=e.player_name,
                text=f"was sent to jail ({e.reason})",
                ts=ts,
            )
        case TaxPaid() as e:
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                player_id=e.player_id,
                player_name=e.player_name,
                text=f"paid ${e.amount} {e.tax_name}",
                ts=ts,
            )
        case TurnEnded() as e:
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                player_id=e.next_player_id,
                player_name=e.next_player_name,
                text=f"it is now {e.next_player_name}'s turn",
                ts=ts,
            )
        case CardDrawn() as e:
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                player_id=e.player_id,
                player_name=e.player_name,
                text=f"drew card: {e.card_text}",
                ts=ts,
            )
        case PlayerSurrendered() as e:
            reason = "ran out of time and surrendered" if e.reason == "afk" else "surrendered"
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                player_id=e.player_id,
                player_name=e.player_name,
                text=reason,
                ts=ts,
            )
        case TurnTimedOut() as e:
            return LogEntry(
                id=entry_id,
                kind=LogKind.EVENT,
                player_id=e.player_id,
                player_name=e.player_name,
                text=f"ran out of time (strike {e.strikes})",
                ts=ts,
            )
