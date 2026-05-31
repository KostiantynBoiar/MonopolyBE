from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from domain.game.engine import apply
from domain.game.enums import CardKind, TurnPhase
from domain.game.rng import Clock, FixedClock
from domain.game.schemas.commands import GameCommand
from domain.game.schemas.events import GameEvent
from domain.game.schemas.state import GameState, JailStatus, PlayerState
from domain.game.setup import GameMember, new_game

GO_SALARY = 200
JAIL_FINE = 50


class SequencedRandom:
    def __init__(self, values: list[int] | None = None) -> None:
        self._values = iter(values or [])

    def randint(self, _a: int, _b: int) -> int:
        return next(self._values)

    def shuffle(self, _xs: list) -> None:
        pass


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(datetime(2026, 5, 29, 12, 0, 0, tzinfo=UTC))


@pytest.fixture
def two_player_game(clock: FixedClock) -> GameState:
    return new_game(
        game_id="game-1",
        session_code="TYC-TEST",
        members=[
            GameMember("user-a", "Alice"),
            GameMember("user-b", "Bob"),
        ],
        rng=SequencedRandom(),  # type: ignore[arg-type]
        clock=clock,
        starting_balance=1500,
    )


def player_by_idx(state: GameState, idx: int) -> PlayerState:
    return state.players[idx]


def with_player_at(state: GameState, player_idx: int, position: int) -> GameState:
    players = list(state.players)
    players[player_idx] = players[player_idx].model_copy(update={"position": position})
    return state.model_copy(update={"players": tuple(players)})


def with_ownership(
    state: GameState,
    position: int,
    owner_id: str,
    **space_kwargs: Any,
) -> GameState:
    spaces = list(state.spaces)
    spaces[position] = spaces[position].model_copy(
        update={"owner_id": owner_id, **space_kwargs}
    )
    owner = next(p for p in state.players if p.id == owner_id)
    owned = tuple(sorted(set(owner.owned_positions) | {position}))
    players = list(state.players)
    idx = next(i for i, p in enumerate(players) if p.id == owner_id)
    players[idx] = owner.model_copy(update={"owned_positions": owned})
    return state.model_copy(update={"spaces": tuple(spaces), "players": tuple(players)})


def with_monopoly(
    state: GameState,
    player_id: str,
    positions: tuple[int, ...],
    *,
    balance: int | None = None,
) -> GameState:
    for pos in positions:
        state = with_ownership(state, pos, player_id)
    if balance is not None:
        players = list(state.players)
        idx = next(i for i, p in enumerate(players) if p.id == player_id)
        players[idx] = players[idx].model_copy(update={"balance": balance})
        state = state.model_copy(update={"players": tuple(players)})
    return state


def with_jailed(
    state: GameState,
    player_id: str,
    turns_remaining: int = 3,
) -> GameState:
    players = list(state.players)
    idx = next(i for i, p in enumerate(players) if p.id == player_id)
    players[idx] = players[idx].model_copy(
        update={"jail_status": JailStatus(turns_remaining=turns_remaining)}
    )
    return state.model_copy(update={"players": tuple(players)})


def with_phase(state: GameState, phase: TurnPhase, **turn_kwargs: Any) -> GameState:
    turn = state.turn.model_copy(update={"phase": phase, **turn_kwargs})
    return state.model_copy(update={"turn": turn})


def with_deck_top(state: GameState, kind: CardKind, card_id: str) -> GameState:
    if kind == CardKind.CHANCE:
        deck = (card_id,) + tuple(c for c in state.chance_deck if c != card_id)
        return state.model_copy(update={"chance_deck": deck})
    deck = (card_id,) + tuple(c for c in state.chest_deck if c != card_id)
    return state.model_copy(update={"chest_deck": deck})


def owned_by_p2(state: GameState, position: int) -> GameState:
    return with_ownership(state, position, state.players[1].id)


def monopoly_brown(state: GameState, player_id: str | None = None) -> GameState:
    pid = player_id or state.players[0].id
    return with_monopoly(state, pid, (1, 3), balance=2000)


def apply_cmd(
    state: GameState,
    command: GameCommand,
    clock: Clock,
    *,
    rng_values: list[int] | None = None,
    go_salary: int = GO_SALARY,
    jail_fine: int = JAIL_FINE,
) -> tuple[GameState, list[GameEvent]]:
    return apply(
        state,
        command,
        rng=SequencedRandom(rng_values),  # type: ignore[arg-type]
        clock=clock,
        go_salary=go_salary,
        jail_fine=jail_fine,
    )
