"""Animation timeline projection (domain.game.animation.build_timeline)."""
from __future__ import annotations

from domain.game.animation import build_timeline, card_interaction_id
from domain.game.cards_data import ALL_CARDS
from domain.game.enums import CardKind, TurnPhase
from domain.game.rng import FixedClock
from domain.game.schemas.cards import AdvanceToEffect
from domain.game.schemas.commands import EndTurn, RollDice
from domain.game.schemas.events import CardDrawn, PlayerMoved, SentToJail, TurnEnded
from domain.game.schemas.state import DiceRoll, GameState
from tests.domain.game.conftest import apply_cmd, with_deck_top, with_phase

_ADVANCE_CARD = next(
    cid for cid, c in ALL_CARDS.items() if isinstance(c.effect, AdvanceToEffect)
)


def _moved(player, frm: int, to: int, *, reason: str = "dice") -> PlayerMoved:
    return PlayerMoved(
        player_id=player.id,
        player_name=player.display_name,
        player_token=player.token,
        from_position=frm,
        to_position=to,
        dice_total=to - frm,
        reason=reason,
    )


def test_roll_then_walk(two_player_game: GameState) -> None:
    state = two_player_game
    p1 = state.players[0]
    state = with_phase(
        state, TurnPhase.POST_ROLL, dice_roll=DiceRoll(die1=2, die2=3, is_doubles=False)
    )
    timeline = build_timeline(RollDice(player_id=p1.id), state, [_moved(p1, 0, 5)])

    assert [i["type"] for i in timeline] == ["roll_dice", "move"]
    assert timeline[0]["die1"] == 2 and timeline[0]["die2"] == 3
    assert timeline[1]["reason"] == "dice"
    assert timeline[1]["speed"] == "normal"
    assert timeline[1]["to_position"] == 5


def test_card_show_wait_then_card_move(two_player_game: GameState) -> None:
    state = two_player_game
    p1 = state.players[0]
    card = ALL_CARDS[_ADVANCE_CARD]
    state = with_phase(
        state,
        TurnPhase.POST_ROLL,
        dice_roll=DiceRoll(die1=2, die2=3, is_doubles=False),
        turn_number=4,
    )
    events = [
        _moved(p1, 0, 7),  # dice walk onto Chance
        CardDrawn(
            player_id=p1.id,
            player_name=p1.display_name,
            card_id=card.id,
            kind="chance",
        ),
        _moved(p1, 7, 39, reason="card"),  # card displacement
    ]
    timeline = build_timeline(RollDice(player_id=p1.id), state, events)

    assert [i["type"] for i in timeline] == [
        "roll_dice",
        "move",
        "show_card",
        "wait_for_player",
        "move",
    ]
    assert timeline[2]["card"]["id"] == card.id
    assert timeline[3]["interaction_id"] == card_interaction_id(4, card.id)
    assert timeline[4]["reason"] == "card"
    assert timeline[4]["speed"] == "fast"


def test_jail_suppresses_move(two_player_game: GameState) -> None:
    state = two_player_game
    p1 = state.players[0]
    state = with_phase(
        state, TurnPhase.POST_ROLL, dice_roll=DiceRoll(die1=4, die2=4, is_doubles=True)
    )
    events = [
        _moved(p1, 22, 30),  # walked onto Go-To-Jail corner...
        SentToJail(player_id=p1.id, player_name=p1.display_name, reason="go_to_jail_space"),
    ]
    timeline = build_timeline(RollDice(player_id=p1.id), state, events)

    # Dice still spin, but we don't animate walking into jail — snap on commit.
    assert [i["type"] for i in timeline] == ["roll_dice"]


def test_non_roll_command_has_empty_timeline(two_player_game: GameState) -> None:
    state = two_player_game
    p1 = state.players[0]
    events = [
        TurnEnded(
            player_id=p1.id,
            player_name=p1.display_name,
            next_player_id=state.players[1].id,
            next_player_name=state.players[1].display_name,
        )
    ]
    assert build_timeline(EndTurn(player_id=p1.id), state, events) == []


def test_engine_emits_card_move_and_timeline(
    two_player_game: GameState, clock: FixedClock
) -> None:
    # End to end through the engine: land on Chance (pos 7) and draw an "advance to" card.
    state = with_deck_top(two_player_game, CardKind.CHANCE, _ADVANCE_CARD)
    p1 = state.players[0]

    new_state, events = apply_cmd(
        state, RollDice(player_id=p1.id), clock, rng_values=[3, 4]
    )

    moves = [e for e in events if isinstance(e, PlayerMoved)]
    assert any(m.reason == "dice" and m.to_position == 7 for m in moves)
    assert any(m.reason == "card" for m in moves)  # the card displaced the player

    timeline = build_timeline(RollDice(player_id=p1.id), new_state, events)
    types = [i["type"] for i in timeline]
    assert types[0] == "roll_dice"
    assert "show_card" in types and "wait_for_player" in types
