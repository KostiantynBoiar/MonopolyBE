from __future__ import annotations

from domain.game.cards_data import ALL_CARDS
from domain.game.enums import CardKind
from domain.game.rng import FixedClock
from domain.game.rules.cards import draw_card, return_jail_card_to_deck
from domain.game.setup import GameMember, new_game
from tests.domain.game.conftest import SequencedRandom


class ShufflingRandom(SequencedRandom):
    def shuffle(self, xs: list) -> None:
        xs.reverse()


def test_draw_cycles_card_to_back(clock: FixedClock) -> None:
    state = new_game(
        game_id="g",
        session_code="X",
        members=[GameMember("u", "P")],
        rng=ShufflingRandom(),  # type: ignore[arg-type]
        clock=clock,
    )
    first_id = state.chance_deck[0]
    state, card = draw_card(state, CardKind.CHANCE, ShufflingRandom())  # type: ignore[arg-type]
    assert card.id == first_id
    assert state.chance_deck[-1] == first_id


def test_goojf_removed_from_deck(clock: FixedClock) -> None:
    state = new_game(
        game_id="g",
        session_code="X",
        members=[GameMember("u", "P")],
        rng=ShufflingRandom(),  # type: ignore[arg-type]
        clock=clock,
    )
    deck = ("chance_08",) + tuple(c for c in state.chance_deck if c != "chance_08")
    state = state.model_copy(update={"chance_deck": deck})
    state, card = draw_card(state, CardKind.CHANCE, ShufflingRandom())  # type: ignore[arg-type]
    assert card.id == "chance_08"
    assert "chance_08" not in state.chance_deck

    state = return_jail_card_to_deck(state, CardKind.CHANCE, "chance_08")
    assert "chance_08" in state.chance_deck


def test_all_cards_defined() -> None:
    assert len(ALL_CARDS) == 40
