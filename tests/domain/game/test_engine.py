from __future__ import annotations

from datetime import UTC, datetime

import pytest

from domain.game.engine import apply
from domain.game.exceptions import IllegalMove
from domain.game.enums import GameStatus, TurnPhase
from domain.game.rng import FixedClock
from domain.game.schemas.commands import BuyProperty, EndTurn, PassBuy, RollDice
from domain.game.schemas.state import GameState
from domain.game.setup import GameMember, new_game


class SequencedRandom:
    def __init__(self, values: list[int]) -> None:
        self._values = iter(values)

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
        rng=SequencedRandom([]),  # type: ignore[arg-type]
        clock=clock,
        starting_balance=1500,
    )


def _owned_by_p2(state: GameState, position: int) -> GameState:
    p1, p2 = state.players
    spaces = list(state.spaces)
    spaces[position] = spaces[position].model_copy(update={"owner_id": p2.id})
    players = list(state.players)
    owned = tuple(sorted(set(p2.owned_positions) | {position}))
    players[1] = p2.model_copy(update={"owned_positions": owned})
    return state.model_copy(update={"spaces": tuple(spaces), "players": tuple(players)})


def test_new_game_initial_state(two_player_game: GameState) -> None:
    state = two_player_game
    assert state.status == GameStatus.IN_PROGRESS
    assert len(state.players) == 2
    assert len(state.spaces) == 40
    assert state.turn.phase == TurnPhase.PRE_ROLL
    assert all(p.balance == 1500 for p in state.players)
    assert all(p.position == 0 for p in state.players)


def test_roll_moves_player(two_player_game: GameState, clock: FixedClock) -> None:
    player = two_player_game.players[0]
    rng = SequencedRandom([3, 4])

    new_state, _ = apply(
        two_player_game,
        RollDice(player_id=player.id),
        rng=rng,  # type: ignore[arg-type]
        clock=clock,
        go_salary=200,
    )

    assert new_state.players[0].position == 7
    assert new_state.turn.phase == TurnPhase.POST_ROLL


def test_passing_go_adds_salary(two_player_game: GameState, clock: FixedClock) -> None:
    player = two_player_game.players[0]
    players = list(two_player_game.players)
    players[0] = player.model_copy(update={"position": 35})
    state = two_player_game.model_copy(update={"players": tuple(players)})
    rng = SequencedRandom([3, 2])

    new_state, events = apply(
        state,
        RollDice(player_id=player.id),
        rng=rng,  # type: ignore[arg-type]
        clock=clock,
        go_salary=200,
    )

    assert new_state.players[0].position == 0
    assert new_state.players[0].balance == 1700
    assert any(e.__class__.__name__ == "PassedGo" for e in events)


def test_rent_payment(two_player_game: GameState, clock: FixedClock) -> None:
    state = _owned_by_p2(two_player_game, 1)
    p1 = state.players[0]
    rng = SequencedRandom([1, 0])

    new_state, events = apply(
        state,
        RollDice(player_id=p1.id),
        rng=rng,  # type: ignore[arg-type]
        clock=clock,
        go_salary=200,
    )

    assert new_state.players[0].balance == 1498
    assert new_state.players[1].balance == 1502
    assert any(e.__class__.__name__ == "RentPaid" for e in events)
    assert new_state.turn.phase == TurnPhase.MUST_PAY_RENT


def test_buy_property(two_player_game: GameState, clock: FixedClock) -> None:
    player = two_player_game.players[0]
    turn = two_player_game.turn.model_copy(
        update={"phase": TurnPhase.POST_ROLL, "pending_buy_position": 1}
    )
    state = two_player_game.model_copy(update={"turn": turn})

    new_state, events = apply(
        state,
        BuyProperty(player_id=player.id, position=1),
        rng=SequencedRandom([]),  # type: ignore[arg-type]
        clock=clock,
        go_salary=200,
    )

    assert new_state.spaces[1].owner_id == player.id
    assert new_state.players[0].balance == 1440
    assert 1 in new_state.players[0].owned_positions
    assert any(e.__class__.__name__ == "PropertyBought" for e in events)


def test_pass_buy(two_player_game: GameState, clock: FixedClock) -> None:
    player = two_player_game.players[0]
    turn = two_player_game.turn.model_copy(
        update={"phase": TurnPhase.POST_ROLL, "pending_buy_position": 1}
    )
    state = two_player_game.model_copy(update={"turn": turn})

    new_state, events = apply(
        state,
        PassBuy(player_id=player.id),
        rng=SequencedRandom([]),  # type: ignore[arg-type]
        clock=clock,
        go_salary=200,
    )

    assert new_state.turn.pending_buy_position is None
    assert new_state.spaces[1].owner_id is None
    assert any(e.__class__.__name__ == "BuyDeclined" for e in events)


def test_end_turn_rotates_player(two_player_game: GameState, clock: FixedClock) -> None:
    p1, p2 = two_player_game.players
    turn = two_player_game.turn.model_copy(
        update={
            "phase": TurnPhase.POST_ROLL,
            "current_player_id": p1.id,
            "pending_buy_position": None,
        }
    )
    state = two_player_game.model_copy(update={"turn": turn})

    new_state, _ = apply(
        state,
        EndTurn(player_id=p1.id),
        rng=SequencedRandom([]),  # type: ignore[arg-type]
        clock=clock,
        go_salary=200,
    )

    assert new_state.turn.current_player_id == p2.id
    assert new_state.turn.phase == TurnPhase.PRE_ROLL
    assert new_state.turn.turn_number == 2


def test_third_doubles_sends_to_jail(two_player_game: GameState, clock: FixedClock) -> None:
    player = two_player_game.players[0]
    turn = two_player_game.turn.model_copy(update={"doubles_streak": 2})
    state = two_player_game.model_copy(update={"turn": turn})
    rng = SequencedRandom([3, 3])

    new_state, events = apply(
        state,
        RollDice(player_id=player.id),
        rng=rng,  # type: ignore[arg-type]
        clock=clock,
        go_salary=200,
    )

    assert new_state.players[0].position == 10
    assert new_state.players[0].jail_status is not None
    assert any(e.__class__.__name__ == "SentToJail" for e in events)


def test_illegal_move_wrong_player(two_player_game: GameState, clock: FixedClock) -> None:
    wrong_player = two_player_game.players[1]
    with pytest.raises(IllegalMove, match="not your turn"):
        apply(
            two_player_game,
            RollDice(player_id=wrong_player.id),
            rng=SequencedRandom([]),  # type: ignore[arg-type]
            clock=clock,
            go_salary=200,
        )


def test_illegal_move_wrong_phase(two_player_game: GameState, clock: FixedClock) -> None:
    player = two_player_game.players[0]
    with pytest.raises(IllegalMove, match="cannot buy"):
        apply(
            two_player_game,
            BuyProperty(player_id=player.id, position=1),
            rng=SequencedRandom([]),  # type: ignore[arg-type]
            clock=clock,
            go_salary=200,
        )
