from __future__ import annotations

from domain.game.enums import CardKind, TurnPhase
from domain.game.rng import FixedClock
from domain.game.rules.cards import draw_and_apply
from domain.game.rules.helpers import replace_space, space_at
from domain.game.schemas.commands import RollDice
from domain.game.schemas.state import DiceRoll, GameState
from tests.domain.game.conftest import (
    SequencedRandom,
    apply_cmd,
    monopoly_brown,
    with_deck_top,
    with_ownership,
    with_phase,
    with_player_at,
)


def test_advance_to_passing_go(two_player_game: GameState, clock: FixedClock) -> None:
    p1 = two_player_game.players[0]
    state = with_player_at(two_player_game, 0, 6)
    state = with_deck_top(state, CardKind.CHANCE, "chance_01")
    state = with_phase(state, TurnPhase.PRE_ROLL, current_player_id=p1.id)

    new_state, events = apply_cmd(
        state,
        RollDice(player_id=p1.id),
        clock,
        rng_values=[1, 1],
    )
    assert new_state.players[0].position == 1
    assert new_state.players[0].balance == 1700
    assert any(e.__class__.__name__ == "PassedGo" for e in events)


def test_advance_to_boardwalk_no_go_bonus(two_player_game: GameState, clock: FixedClock) -> None:
    p1 = two_player_game.players[0]
    state = with_player_at(two_player_game, 0, 36)
    state = with_deck_top(state, CardKind.CHANCE, "chance_14")
    state = with_phase(state, TurnPhase.PRE_ROLL, current_player_id=p1.id)
    balance_before = state.players[0].balance

    new_state, events = apply_cmd(
        state,
        RollDice(player_id=p1.id),
        clock,
        rng_values=[1, 0],
    )
    assert new_state.players[0].position == 40
    assert new_state.players[0].balance == balance_before
    assert not any(e.__class__.__name__ == "PassedGo" for e in events)


def test_collect_card(two_player_game: GameState, clock: FixedClock) -> None:
    p1 = two_player_game.players[0]
    state = with_player_at(two_player_game, 0, 6)
    state = with_deck_top(state, CardKind.CHANCE, "chance_07")
    state = with_phase(state, TurnPhase.PRE_ROLL, current_player_id=p1.id)

    new_state, _ = apply_cmd(state, RollDice(player_id=p1.id), clock, rng_values=[1, 1])
    assert new_state.players[0].balance == 1550


def test_pay_card(two_player_game: GameState, clock: FixedClock) -> None:
    # Start at pos 16 (PA Railroad); roll [1,1]=2 -> pos 18 (Community Chest)
    p1 = two_player_game.players[0]
    state = with_player_at(two_player_game, 0, 16)
    state = with_deck_top(state, CardKind.COMMUNITY_CHEST, "chest_03")  # Pay $50
    state = with_phase(state, TurnPhase.PRE_ROLL, current_player_id=p1.id)

    new_state, _ = apply_cmd(state, RollDice(player_id=p1.id), clock, rng_values=[1, 1])
    assert new_state.players[0].balance == 1450


def test_go_to_jail_card(two_player_game: GameState, clock: FixedClock) -> None:
    p1 = two_player_game.players[0]
    state = with_player_at(two_player_game, 0, 6)
    state = with_deck_top(state, CardKind.CHANCE, "chance_10")
    state = with_phase(state, TurnPhase.PRE_ROLL, current_player_id=p1.id)

    new_state, _ = apply_cmd(state, RollDice(player_id=p1.id), clock, rng_values=[1, 1])
    assert new_state.players[0].position == 11
    assert new_state.players[0].jail_status is not None
    assert new_state.turn.phase == TurnPhase.POST_ROLL
    assert new_state.turn.doubles_streak == 0


def test_get_out_of_jail_free_card(two_player_game: GameState, clock: FixedClock) -> None:
    p1 = two_player_game.players[0]
    dice = DiceRoll(die1=3, die2=3, is_doubles=False)
    state = with_deck_top(two_player_game, CardKind.CHANCE, "chance_08")
    state, _, _, _ = draw_and_apply(
        state,
        p1,
        CardKind.CHANCE,
        rng=SequencedRandom(),  # type: ignore[arg-type]
        dice_roll=dice,
        go_salary=200,
        jail_fine=50,
    )
    assert state.players[0].get_out_of_jail_cards == 1


def test_collect_from_each_player(two_player_game: GameState, clock: FixedClock) -> None:
    p1 = two_player_game.players[0]
    state = with_player_at(two_player_game, 0, 16)
    state = with_deck_top(state, CardKind.COMMUNITY_CHEST, "chest_09")
    state = with_phase(state, TurnPhase.PRE_ROLL, current_player_id=p1.id)

    new_state, _ = apply_cmd(state, RollDice(player_id=p1.id), clock, rng_values=[1, 1])
    assert new_state.players[0].balance == 1510
    assert new_state.players[1].balance == 1490


def test_pay_each_player(two_player_game: GameState, clock: FixedClock) -> None:
    # Start at pos 22 (Kentucky); roll [1,1]=2 -> pos 24 which is Indiana, not Chance.
    # Instead start at pos 21 (Free Parking); roll [1,1]=2 -> pos 23 (Chance).
    p1 = two_player_game.players[0]
    state = with_player_at(two_player_game, 0, 21)
    state = with_deck_top(state, CardKind.CHANCE, "chance_15")  # Pay each player $50
    state = with_phase(state, TurnPhase.PRE_ROLL, current_player_id=p1.id)

    new_state, _ = apply_cmd(state, RollDice(player_id=p1.id), clock, rng_values=[1, 1])
    assert new_state.players[0].balance == 1450
    assert new_state.players[1].balance == 1550


def test_repairs_card(two_player_game: GameState, clock: FixedClock) -> None:
    p1 = two_player_game.players[0]
    state = monopoly_brown(two_player_game, p1.id)
    spaces = list(state.spaces)
    replace_space(spaces, 2, space_at(spaces, 2).model_copy(update={"houses": 2}))
    state = state.model_copy(update={"spaces": tuple(spaces)})
    state = with_player_at(state, 0, 6)
    state = with_deck_top(state, CardKind.CHANCE, "chance_11")
    state = with_phase(state, TurnPhase.PRE_ROLL, current_player_id=p1.id)

    new_state, _ = apply_cmd(state, RollDice(player_id=p1.id), clock, rng_values=[1, 1])
    assert new_state.players[0].balance == 1950


def test_active_card_cleared_on_next_command(two_player_game: GameState, clock: FixedClock) -> None:
    # Start at pos 6 (Railroad); roll [1,1]=2 -> pos 8 (Chance) -> draws collect $50 card.
    # Then manually set phase to POST_ROLL and EndTurn to clear active_card.
    from domain.game.schemas.commands import EndTurn

    p1 = two_player_game.players[0]
    state = with_player_at(two_player_game, 0, 6)
    state = with_deck_top(state, CardKind.CHANCE, "chance_07")  # Collect $50
    state = with_phase(state, TurnPhase.PRE_ROLL, current_player_id=p1.id)

    after_card, _ = apply_cmd(state, RollDice(player_id=p1.id), clock, rng_values=[1, 1])
    # After landing on Chance and drawing a collect card, active_card is set and
    # phase should be POST_ROLL (no pending buy at pos 8).
    assert after_card.active_card is not None

    # EndTurn clears active_card on the next command.
    state_post = after_card.model_copy(
        update={
            "turn": after_card.turn.model_copy(
                update={"phase": TurnPhase.POST_ROLL, "pending_buy_position": None}
            )
        }
    )
    after_end, _ = apply_cmd(state_post, EndTurn(player_id=p1.id), clock)
    assert after_end.active_card is None


def test_advance_to_nearest_railroad_double_rent(
    two_player_game: GameState, clock: FixedClock
) -> None:
    # p2 owns B&O Railroad. Player 1 starts at pos 21 (Free Parking),
    # rolls [1,1]=2 -> pos 23 (Chance) -> advance_to_nearest railroad.
    # From pos 23, nearest railroad is pos 26.
    p1, p2 = two_player_game.players
    state = with_ownership(two_player_game, 26, p2.id)
    state = with_player_at(state, 0, 21)
    state = with_deck_top(state, CardKind.CHANCE, "chance_05")  # advance to nearest RR, pay double
    state = with_phase(state, TurnPhase.PRE_ROLL, current_player_id=p1.id)

    new_state, events = apply_cmd(state, RollDice(player_id=p1.id), clock, rng_values=[1, 1])
    # Lands on Chance (23), draws card -> advances to nearest railroad (26, owned by p2)
    assert new_state.players[0].position == 26
    assert any(e.__class__.__name__ == "RentPaid" for e in events)
    rent_event = next(e for e in events if e.__class__.__name__ == "RentPaid")
    # p2 owns 1 railroad → base rent = 25, doubled by card → 50
    assert rent_event.amount == 50


def test_go_to_jail_corner(two_player_game: GameState, clock: FixedClock) -> None:
    # Start at pos 29 (Water Works), roll [1,1]=2 -> pos 31 (Go to Jail corner).
    # Player gets moved to jail (position 11), not left at position 31.
    p1 = two_player_game.players[0]
    state = with_player_at(two_player_game, 0, 29)
    state = with_phase(state, TurnPhase.PRE_ROLL, current_player_id=p1.id)

    new_state, _ = apply_cmd(state, RollDice(player_id=p1.id), clock, rng_values=[1, 1])
    assert new_state.players[0].position == 11  # Sent to Jail tile (Just Visiting)
    assert new_state.players[0].jail_status is not None
    assert new_state.turn.phase == TurnPhase.POST_ROLL
    assert new_state.turn.doubles_streak == 0
