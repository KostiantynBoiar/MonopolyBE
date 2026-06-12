from __future__ import annotations

from typing import Any

import structlog
from motor.motor_asyncio import AsyncIOMotorDatabase

from domain.game.enums import GameStatus
from domain.game.schemas.state import GameState, PlayerState
from domain.rating.elo import Participant, compute_rating_changes
from infra.mongo.games.repository import GameRepository
from infra.mongo.users.repository import UserRepository

logger = structlog.get_logger(__name__)


class RatingService:
    """Applies ELO rating changes once a game finishes. Idempotent per game."""

    def __init__(self, users: UserRepository, games: GameRepository) -> None:
        self._users = users
        self._games = games

    @classmethod
    def from_db(cls, db: AsyncIOMotorDatabase[Any]) -> "RatingService":
        return cls(UserRepository(db), GameRepository(db))

    async def apply_for_finished_game(self, session_id: str, state: GameState) -> None:
        if state.status != GameStatus.FINISHED:
            return
        # Claim the game so ratings are applied exactly once (both finish paths may fire).
        if not await self._games.claim_for_rating(session_id):
            return

        placements = _placements(state.players)
        if len(placements) < 2:
            return

        user_ids = [user_id for user_id, _ in placements]
        users = await self._users.find_by_ids(user_ids)

        participants = [
            Participant(
                user_id=user_id,
                rating=users[user_id].rating,
                games_played=users[user_id].games_played,
                placement=place,
            )
            for user_id, place in placements
            if user_id in users
        ]
        results = compute_rating_changes(participants)

        for user_id, result in results.items():
            await self._users.update_rating(
                user_id,
                rating=result.new_rating,
                games_played=result.games_played,
                calibration_complete=result.calibration_complete,
            )
        logger.info(
            "ratings_applied",
            session_id=session_id,
            changes={uid: r.delta for uid, r in results.items()},
        )


def _placements(players: tuple[PlayerState, ...]) -> list[tuple[str, int]]:
    """Rank players: winner(s) first (not eliminated), then eliminated by most-recent
    elimination. Returns [(user_id, placement)] with placement 1 = winner."""
    survivors = [p for p in players if not p.is_bankrupt]
    eliminated = sorted(
        (p for p in players if p.is_bankrupt),
        key=lambda p: p.eliminated_at if p.eliminated_at is not None else -1,
        reverse=True,
    )
    ordered = survivors + eliminated
    return [(p.user_id, i + 1) for i, p in enumerate(ordered)]
