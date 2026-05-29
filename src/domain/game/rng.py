from __future__ import annotations

import random
from datetime import datetime

from domain.game.constants import DICE_MAX, DICE_MIN


class Clock:
    def now(self) -> datetime: ...


class FixedClock:
    def __init__(self, ts: datetime) -> None:
        self._ts = ts

    def now(self) -> datetime:
        return self._ts


def roll_dice(rng: random.Random) -> tuple[int, int]:
    return rng.randint(DICE_MIN, DICE_MAX), rng.randint(DICE_MIN, DICE_MAX)
