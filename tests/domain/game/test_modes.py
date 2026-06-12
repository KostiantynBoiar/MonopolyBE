from __future__ import annotations

from domain.game.enums import GameMode, TurnPhase
from domain.game.rng import FixedClock
from domain.game.rules.helpers import space_at
from domain.game.schemas.commands import BuyProperty, RollDice
from domain.game.setup import GameMember, new_game
from tests.domain.game.conftest import SequencedRandom, apply_cmd


def test_duel_game_setup_uses_local_board_and_rules(clock: FixedClock) -> None:
    state = new_game(
        game_id="duel-1",
        session_code="TYC-DUEL",
        members=[GameMember("u1", "One"), GameMember("u2", "Two")],
        rng=SequencedRandom(),  # type: ignore[arg-type]
        clock=clock,
        game_mode=GameMode.DUEL,
    )

    assert state.game_mode == GameMode.DUEL
    assert [space.position for space in state.spaces] == list(range(1, 25))
    assert [player.position for player in state.players] == [1, 1]
    assert [player.balance for player in state.players] == [1000, 1000]
    assert state.chest_deck == ()
    assert state.sudden_death_deadline_ms is not None


def test_duel_roll_uses_one_die(clock: FixedClock) -> None:
    state = new_game(
        game_id="duel-2",
        session_code="TYC-DUEL",
        members=[GameMember("u1", "One"), GameMember("u2", "Two")],
        rng=SequencedRandom(),  # type: ignore[arg-type]
        clock=clock,
        game_mode=GameMode.DUEL,
    )
    player = state.players[0]

    rolled, _ = apply_cmd(state, RollDice(player_id=player.id), clock, rng_values=[3])

    assert rolled.turn.dice_roll is not None
    assert rolled.turn.dice_roll.die1 == 3
    assert rolled.turn.dice_roll.die2 == 0
    assert rolled.players[0].position == 4


def test_duel_buy_uses_position_ids_not_tuple_indexes(clock: FixedClock) -> None:
    state = new_game(
        game_id="duel-3",
        session_code="TYC-DUEL",
        members=[GameMember("u1", "One"), GameMember("u2", "Two")],
        rng=SequencedRandom(),  # type: ignore[arg-type]
        clock=clock,
        game_mode=GameMode.DUEL,
    )
    player = state.players[0]
    turn = state.turn.model_copy(
        update={"phase": TurnPhase.POST_ROLL, "pending_buy_position": 23}
    )
    state = state.model_copy(update={"turn": turn})

    bought, _ = apply_cmd(state, BuyProperty(player_id=player.id, position=23), clock)

    assert space_at(bought.spaces, 23).owner_id == player.id
    assert 23 in bought.players[0].owned_positions
