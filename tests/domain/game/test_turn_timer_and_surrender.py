"""Turn timer (AFK strikes → auto-surrender) and voluntary surrender."""
from __future__ import annotations

from datetime import UTC, datetime

from domain.game.constants import MAX_AFK_STRIKES, TURN_TIMEOUT_MS
from domain.game.enums import GameStatus, TurnPhase
from domain.game.rng import FixedClock
from domain.game.rules.surrender import resolve_surrender
from domain.game.schemas.commands import RollDice, Surrender, TurnTimeout
from domain.game.schemas.state import GameState
from domain.game.setup import GameMember, new_game
from tests.domain.game.conftest import SequencedRandom, apply_cmd, with_ownership


def _game(clock: FixedClock, n: int) -> GameState:
    members = [GameMember(f"u{i}", chr(65 + i)) for i in range(n)]
    return new_game(
        game_id="g", session_code="TYC-T", members=members,
        rng=SequencedRandom(), clock=clock, starting_balance=1500,  # type: ignore[arg-type]
    )


def _expire(state: GameState, clock: FixedClock) -> GameState:
    # Force the deadline into the past so is_turn_expired() is true.
    now_ms = int(clock.now().timestamp() * 1000)
    turn = state.turn.model_copy(update={"turn_deadline_ms": now_ms - 1})
    return state.model_copy(update={"turn": turn})


def test_new_game_sets_turn_deadline(clock: FixedClock) -> None:
    state = _game(clock, 2)
    expected = int(clock.now().timestamp() * 1000) + TURN_TIMEOUT_MS
    assert state.turn.turn_deadline_ms == expected


def test_action_refreshes_deadline_and_clears_strikes(clock: FixedClock) -> None:
    state = _game(clock, 2)
    p1 = state.players[0]
    state = state.model_copy(
        update={"players": (p1.model_copy(update={"afk_strikes": 1}), state.players[1])}
    )
    later = FixedClock(datetime(2026, 6, 3, 12, 0, 30, tzinfo=UTC))
    new_state, _ = apply_cmd(state, RollDice(player_id=p1.id), later, rng_values=[1, 2])
    assert new_state.players[0].afk_strikes == 0
    assert new_state.turn.turn_deadline_ms == int(later.now().timestamp() * 1000) + TURN_TIMEOUT_MS


def test_turn_timeout_skips_and_records_strike(clock: FixedClock) -> None:
    state = _expire(_game(clock, 3), clock)
    a, b, c = state.players
    after, _ = apply_cmd(state, TurnTimeout(), clock)
    # A got a strike and the turn moved to the next player; A is still in the game.
    assert after.players[0].afk_strikes == 1
    assert after.players[0].is_bankrupt is False
    assert after.turn.current_player_id == b.id


def test_three_strikes_auto_surrenders(clock: FixedClock) -> None:
    state = _game(clock, 3)
    a, b, c = state.players
    # Give A two prior strikes and some property; this timeout is the 3rd → surrender.
    state = with_ownership(state, 1, a.id)  # Mediterranean Ave
    players = list(state.players)
    players[0] = players[0].model_copy(update={"afk_strikes": MAX_AFK_STRIKES - 1, "balance": 900})
    state = state.model_copy(update={"players": tuple(players)})
    state = _expire(state, clock)

    after, _ = apply_cmd(state, TurnTimeout(), clock)

    assert after.players[0].is_bankrupt is True  # eliminated
    assert after.spaces[1].owner_id is None  # property freed (buyable again)
    # A's $900 split equally between B and C (+450 each).
    assert after.players[1].balance == 1500 + 450
    assert after.players[2].balance == 1500 + 450
    assert after.turn.current_player_id != a.id  # turn moved off the surrendered player


def test_voluntary_surrender_frees_properties_and_splits_cash(clock: FixedClock) -> None:
    state = _game(clock, 3)
    a, b, c = state.players
    state = with_ownership(state, 3, a.id)  # Baltic Ave
    players = list(state.players)
    players[0] = players[0].model_copy(update={"balance": 901})  # odd → remainder distributed
    state = state.model_copy(update={"players": tuple(players)})

    after, _ = apply_cmd(state, Surrender(player_id=a.id), clock)

    assert after.players[0].is_bankrupt is True
    assert after.players[0].balance == 0
    assert after.spaces[3].owner_id is None
    # 901 split between 2 players → 451 + 450 (remainder of 1 goes to the first recipient).
    assert {after.players[1].balance, after.players[2].balance} == {1500 + 451, 1500 + 450}


def test_surrender_in_two_player_game_ends_it(clock: FixedClock) -> None:
    state = _game(clock, 2)
    a, b = state.players
    after, _ = apply_cmd(state, Surrender(player_id=a.id), clock)
    assert after.status == GameStatus.FINISHED
    assert after.winner_id == b.id
