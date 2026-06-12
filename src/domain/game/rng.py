from __future__ import annotations

import random
from datetime import datetime
from typing import Protocol

from domain.game.constants import DICE_MAX, DICE_MIN


class Clock(Protocol):
    def now(self) -> datetime: ...


class FixedClock:
    def __init__(self, ts: datetime) -> None:
        self._ts = ts

    def now(self) -> datetime:
        return self._ts


def roll_dice(rng: random.Random) -> tuple[int, int]:
    return rng.randint(DICE_MIN, DICE_MAX), rng.randint(DICE_MIN, DICE_MAX)


def roll_dice_count(rng: random.Random, dice_count: int) -> tuple[int, int]:
    die1 = rng.randint(DICE_MIN, DICE_MAX)
    if dice_count == 1:
        return die1, 0
    return die1, rng.randint(DICE_MIN, DICE_MAX)
