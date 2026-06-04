"""Placement-based ELO for multiplayer games (pure — no IO, fully testable).

Standard 1v1 ELO generalized to N players: each player's expected score is the mean of
their pairwise win probabilities against the field, and their actual score comes from
finishing placement (1st → 1.0, last → 0.0, evenly spaced). The per-game change uses a
larger K + cap during a player's calibration window, then a smaller steady-state value.
"""
from __future__ import annotations

from dataclasses import dataclass

from domain.rating.constants import (
    CALIBRATION_CAP,
    CALIBRATION_GAMES,
    CALIBRATION_K,
    RATING_FLOOR,
    REGULAR_CAP,
    REGULAR_K,
)


@dataclass(frozen=True)
class Participant:
    user_id: str
    rating: int
    games_played: int
    placement: int  # 1 = winner … N = last


@dataclass(frozen=True)
class RatingResult:
    user_id: str
    old_rating: int
    new_rating: int
    delta: int
    games_played: int
    calibration_complete: bool


def _expected_score(rating: int, opponents: list[int]) -> float:
    if not opponents:
        return 0.5
    return sum(1.0 / (1.0 + 10 ** ((opp - rating) / 400.0)) for opp in opponents) / len(opponents)


def _clamp(value: int, cap: int) -> int:
    return max(-cap, min(cap, value))


def compute_rating_changes(participants: list[Participant]) -> dict[str, RatingResult]:
    """Return user_id → RatingResult for every participant of a finished game."""
    n = len(participants)
    if n < 2:
        return {}

    results: dict[str, RatingResult] = {}
    for player in participants:
        opponents = [p.rating for p in participants if p.user_id != player.user_id]
        expected = _expected_score(player.rating, opponents)
        # placement 1 → 1.0, placement n → 0.0
        actual = (n - player.placement) / (n - 1)

        provisional = player.games_played < CALIBRATION_GAMES
        k = CALIBRATION_K if provisional else REGULAR_K
        cap = CALIBRATION_CAP if provisional else REGULAR_CAP

        delta = _clamp(round(k * (actual - expected)), cap)
        new_rating = max(RATING_FLOOR, player.rating + delta)
        new_games = player.games_played + 1

        results[player.user_id] = RatingResult(
            user_id=player.user_id,
            old_rating=player.rating,
            new_rating=new_rating,
            delta=new_rating - player.rating,
            games_played=new_games,
            calibration_complete=new_games >= CALIBRATION_GAMES,
        )
    return results
