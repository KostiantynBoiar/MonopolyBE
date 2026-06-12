"""event_to_log_entry: typed game events -> structured, language-agnostic LogEntry.

The backend no longer ships English prose for events; each entry carries a `type` discriminator plus
structured identifiers the frontend localizes. These tests pin the field mapping per event type and
assert `text` is never populated for events.
"""

from __future__ import annotations

from datetime import UTC, datetime

from domain.game.enums import LogKind, TokenColor
from domain.game.schemas.events import (
    BuyDeclined,
    CardDrawn,
    PassedGo,
    PlayerMoved,
    PlayerSurrendered,
    PropertyBought,
    RentPaid,
    RolledDoubles,
    SentToJail,
    TaxPaid,
    TurnEnded,
    TurnTimedOut,
    event_to_log_entry,
)

_TS = datetime(2026, 6, 8, tzinfo=UTC)


def _entry(event):
    e = event_to_log_entry(event, _TS)
    # Every event entry is a localizable EVENT with a `type` and no rendered prose.
    assert e.kind is LogKind.EVENT
    assert e.type is not None
    assert e.text is None
    assert e.ts == _TS
    assert e.id  # a fresh id is minted
    return e


def test_player_moved_dice_carries_roll() -> None:
    e = _entry(
        PlayerMoved(
            player_id="p1",
            player_name="Ann",
            player_token=TokenColor.BLUE,
            from_position=1,
            to_position=8,
            dice_total=7,
        )
    )
    assert e.type == "player_moved"
    assert e.player_id == "p1"
    assert e.player_token is TokenColor.BLUE
    assert e.tile_id == 8
    assert e.rolled == 7


def test_player_moved_card_omits_roll() -> None:
    # A card-induced displacement isn't dice-driven (dice_total == 0): `rolled` must be omitted so the
    # FE renders "moved to X" rather than "rolled 0 and moved".
    e = _entry(
        PlayerMoved(
            player_id="p1",
            player_name="Ann",
            player_token=TokenColor.RED,
            from_position=8,
            to_position=40,
            dice_total=0,
            reason="card",
        )
    )
    assert e.tile_id == 40
    assert e.rolled is None


def test_passed_go() -> None:
    e = _entry(PassedGo(player_id="p1", player_name="Ann", amount=200))
    assert e.type == "passed_go"
    assert e.received == 200


def test_rent_paid() -> None:
    e = _entry(
        RentPaid(
            payer_id="p1",
            payer_name="Ann",
            owner_id="p2",
            owner_name="Bo",
            position=5,
            property_name="Reading RR",
            amount=25,
        )
    )
    assert e.type == "rent_paid"
    assert e.player_id == "p1"
    assert e.opponent_id == "p2"
    assert e.tile_id == 5
    assert e.spent == 25


def test_property_bought() -> None:
    e = _entry(
        PropertyBought(
            player_id="p1",
            player_name="Ann",
            position=14,
            property_name="Virginia Ave",
            price=160,
        )
    )
    assert e.type == "property_bought"
    assert e.tile_id == 14
    assert e.spent == 160


def test_buy_declined() -> None:
    e = _entry(
        BuyDeclined(player_id="p1", player_name="Ann", position=14, property_name="Virginia")
    )
    assert e.type == "buy_declined"
    assert e.tile_id == 14
    assert e.spent is None


def test_rolled_doubles() -> None:
    e = _entry(RolledDoubles(player_id="p1", player_name="Ann", streak=2))
    assert e.type == "rolled_doubles"
    assert e.streak == 2


def test_sent_to_jail_reason_is_a_code() -> None:
    e = _entry(SentToJail(player_id="p1", player_name="Ann", reason="doubles"))
    assert e.type == "sent_to_jail"
    assert e.reason == "doubles"


def test_tax_paid() -> None:
    e = _entry(TaxPaid(player_id="p1", player_name="Ann", position=4, amount=200))
    assert e.type == "tax_paid"
    assert e.tile_id == 4
    assert e.spent == 200


def test_turn_ended_points_at_next_player() -> None:
    e = _entry(
        TurnEnded(
            player_id="p1",
            player_name="Ann",
            next_player_id="p2",
            next_player_name="Bo",
        )
    )
    assert e.type == "turn_ended"
    assert e.player_id == "p2"


def test_card_drawn_references_card_not_text() -> None:
    e = _entry(CardDrawn(player_id="p1", player_name="Ann", card_id="chance_06", kind="chance"))
    assert e.type == "card_drawn"
    assert e.card_id == "chance_06"
    assert e.card_kind == "chance"


def test_player_surrendered() -> None:
    e = _entry(PlayerSurrendered(player_id="p1", player_name="Ann", reason="afk"))
    assert e.type == "player_surrendered"
    assert e.reason == "afk"


def test_turn_timed_out() -> None:
    e = _entry(TurnTimedOut(player_id="p1", player_name="Ann", strikes=2))
    assert e.type == "turn_timed_out"
    assert e.strikes == 2
