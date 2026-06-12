"""Backend-authored animation timeline.

The engine resolves an entire turn in one `apply()` call and returns an ordered
`list[GameEvent]`. `build_timeline` projects that event list into an ordered sequence of
animation instructions the frontend replays verbatim — no client-side snapshot diffing.
The timeline is a *visual replay* of how the authoritative state was reached; the state
itself remains the source of truth.
"""
from __future__ import annotations

from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict

from domain.game.cards_data import ALL_CARDS
from domain.game.schemas.cards import ActiveCard
from domain.game.schemas.commands import GameCommand, RollDice
from domain.game.schemas.events import CardDrawn, GameEvent, PlayerMoved, SentToJail
from domain.game.schemas.state import GameState


class RollDiceAnimation(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["roll_dice"] = "roll_dice"
    player_id: str
    die1: int
    die2: int
    is_doubles: bool


class MoveAnimation(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["move"] = "move"
    player_id: str
    from_position: int
    to_position: int
    speed: Literal["normal", "fast"]
    reason: Literal["dice", "card", "teleport", "jail"]


class ShowCardAnimation(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["show_card"] = "show_card"
    card: ActiveCard


class WaitForPlayerAnimation(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["wait_for_player"] = "wait_for_player"
    interaction_id: str


AnimationInstruction = Union[
    RollDiceAnimation,
    MoveAnimation,
    ShowCardAnimation,
    WaitForPlayerAnimation,
]


def card_interaction_id(turn_number: int, card_id: str) -> str:
    """Deterministic id tying a card pause to its turn, so a stale `animation_continue`
    can't resume a different gate."""
    return f"{turn_number}:{card_id}"


def build_timeline(
    command: GameCommand,
    state_after: GameState,
    events: list[GameEvent],
) -> list[dict[str, Any]]:
    """Project an apply() result into an ordered animation timeline (snake_case dicts).

    Order mirrors the event stream:
      roll_dice (if a dice command) → move(dice) → show_card + wait_for_player → move(card)

    A player sent to jail this turn is *snapped* there on commit (no walk), matching the
    frontend's long-standing behaviour — so we suppress their move instructions.
    """
    instructions: list[BaseModel] = []

    if isinstance(command, RollDice) and state_after.turn.dice_roll is not None:
        d = state_after.turn.dice_roll
        instructions.append(
            RollDiceAnimation(
                player_id=command.player_id,
                die1=d.die1,
                die2=d.die2,
                is_doubles=d.is_doubles,
            )
        )

    jailed = {e.player_id for e in events if isinstance(e, SentToJail)}

    for event in events:
        if isinstance(event, PlayerMoved):
            if event.player_id in jailed:
                continue  # don't animate walking into jail
            instructions.append(
                MoveAnimation(
                    player_id=event.player_id,
                    from_position=event.from_position,
                    to_position=event.to_position,
                    speed="fast" if event.reason == "card" else "normal",
                    reason=event.reason,
                )
            )
        elif isinstance(event, CardDrawn):
            card_def = ALL_CARDS.get(event.card_id)
            if card_def is None:
                continue
            card = ActiveCard(
                id=card_def.id,
                kind=card_def.kind,
                effect=card_def.effect,
                drawer_id=event.player_id,
            )
            instructions.append(ShowCardAnimation(card=card))
            instructions.append(
                WaitForPlayerAnimation(
                    interaction_id=card_interaction_id(state_after.turn.turn_number, event.card_id)
                )
            )

    return [i.model_dump(mode="json") for i in instructions]
