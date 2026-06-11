from __future__ import annotations

from dataclasses import dataclass

from domain.game.board_data import board_for_mode
from domain.game.enums import GameMode
from domain.game.schemas.board import BoardSpace


@dataclass(frozen=True)
class GameConfig:
    mode: GameMode
    board: tuple[BoardSpace, ...]
    max_players: int
    dice_count: int
    start_position: int
    jail_position: int
    railroad_positions: frozenset[int]
    utility_positions: frozenset[int]
    starting_balance: int | None = None
    chance_deck: tuple[str, ...] | None = None
    chest_deck: tuple[str, ...] | None = None
    sudden_death_duration_ms: int | None = None

    @property
    def board_positions(self) -> tuple[int, ...]:
        return tuple(space.position for space in self.board)

    @property
    def board_size(self) -> int:
        return len(self.board)


_NORMAL_CONFIG = GameConfig(
    mode=GameMode.NORMAL,
    board=board_for_mode(GameMode.NORMAL),
    max_players=8,
    dice_count=2,
    start_position=1,
    jail_position=11,
    railroad_positions=frozenset({6, 16, 26, 36}),
    utility_positions=frozenset({13, 29}),
)

_DUEL_CONFIG = GameConfig(
    mode=GameMode.DUEL,
    board=board_for_mode(GameMode.DUEL),
    max_players=2,
    dice_count=1,
    start_position=1,
    jail_position=7,
    railroad_positions=frozenset({6, 14}),
    utility_positions=frozenset({10, 21}),
    starting_balance=1000,
    chance_deck=(
        "duel_chance_01",
        "duel_chance_02",
        "duel_chance_03",
        "duel_chance_04",
        "duel_chance_05",
        "duel_chance_06",
        "duel_chance_07",
        "duel_chance_08",
    ),
    chest_deck=(),
    sudden_death_duration_ms=15 * 60 * 1000,
)

_CONFIGS_BY_MODE: dict[GameMode, GameConfig] = {
    GameMode.NORMAL: _NORMAL_CONFIG,
    GameMode.DUEL: _DUEL_CONFIG,
}


def get_game_config(game_mode: GameMode) -> GameConfig:
    return _CONFIGS_BY_MODE[game_mode]
