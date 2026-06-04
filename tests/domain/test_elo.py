"""Placement-based ELO math (domain.rating.elo)."""
from __future__ import annotations

from domain.rating.constants import CALIBRATION_CAP, RATING_FLOOR, REGULAR_CAP
from domain.rating.elo import Participant, compute_rating_changes


def _p(uid: str, rating: int, games: int, place: int) -> Participant:
    return Participant(user_id=uid, rating=rating, games_played=games, placement=place)


def test_two_equal_players_regular_swing_is_about_24() -> None:
    # Both calibrated, equal ratings → winner +24, loser -24 (within the ±23-25 target).
    res = compute_rating_changes([_p("a", 800, 5, 1), _p("b", 800, 5, 2)])
    assert res["a"].delta == 24
    assert res["b"].delta == -24
    assert abs(res["a"].delta) <= REGULAR_CAP


def test_two_equal_players_calibration_swing_is_large() -> None:
    res = compute_rating_changes([_p("a", 800, 0, 1), _p("b", 800, 0, 2)])
    assert res["a"].delta == 60  # 120 * 0.5
    assert res["b"].delta == -60
    assert abs(res["a"].delta) <= CALIBRATION_CAP


def test_four_player_equal_field_placement_scaling() -> None:
    res = compute_rating_changes([
        _p("a", 800, 9, 1),
        _p("b", 800, 9, 2),
        _p("c", 800, 9, 3),
        _p("d", 800, 9, 4),
    ])
    assert res["a"].delta == 24
    assert res["b"].delta == 8
    assert res["c"].delta == -8
    assert res["d"].delta == -24
    # Equal field → symmetric, conserves total.
    assert sum(r.delta for r in res.values()) == 0


def test_beating_stronger_opponent_yields_more_than_beating_weaker() -> None:
    upset = compute_rating_changes([_p("a", 800, 9, 1), _p("b", 1200, 9, 2)])["a"].delta
    easy = compute_rating_changes([_p("a", 800, 9, 1), _p("b", 400, 9, 2)])["a"].delta
    assert upset > easy
    assert upset <= REGULAR_CAP  # capped


def test_regular_cap_enforced_on_big_upset() -> None:
    # Huge rating gap, calibrated → would exceed cap, must be clamped.
    res = compute_rating_changes([_p("a", 400, 9, 1), _p("b", 2000, 9, 2)])
    assert res["a"].delta == REGULAR_CAP


def test_rating_floor() -> None:
    res = compute_rating_changes([_p("a", RATING_FLOOR + 5, 9, 2), _p("b", RATING_FLOOR + 5, 9, 1)])
    assert res["a"].new_rating >= RATING_FLOOR


def test_calibration_completes_after_three_games() -> None:
    res = compute_rating_changes([_p("a", 800, 2, 1), _p("b", 800, 2, 2)])
    assert res["a"].games_played == 3
    assert res["a"].calibration_complete is True
    res2 = compute_rating_changes([_p("a", 800, 1, 1), _p("b", 800, 1, 2)])
    assert res2["a"].calibration_complete is False


def test_single_participant_no_change() -> None:
    assert compute_rating_changes([_p("a", 800, 0, 1)]) == {}
