from __future__ import annotations

import random
from uuid import uuid4

from domain.game.constants import BANK_HOTELS, BANK_HOUSES, TOKEN_COLORS, TURN_TIMEOUT_MS
from domain.game.enums import GameMode, GameStatus, TurnPhase
from domain.game.modes import get_game_config
from domain.game.rng import Clock
from domain.game.rules.cards import initial_chance_deck, initial_chest_deck
from domain.game.schemas.state import (
    GameState,
    PlayerState,
    SpaceOwnership,
    TurnState,
)


class GameMember:
    def __init__(self, user_id: str, display_name: str, rating: int = 800) -> None:
        self.user_id = user_id
        self.display_name = display_name
        self.rating = rating


def new_game(
    *,
    game_id: str,
    session_code: str,
    members: list[GameMember],
    rng: random.Random,
    clock: Clock,
    starting_balance: int = 1500,
    game_mode: GameMode = GameMode.NORMAL,
) -> GameState:
    now = clock.now()
    config = get_game_config(game_mode)
    player_starting_balance = config.starting_balance or starting_balance
    member_order = list(members)
    rng.shuffle(member_order)

    players: list[PlayerState] = []
    for turn_order, member in enumerate(member_order):
        players.append(
            PlayerState(
                id=uuid4().hex,
                user_id=member.user_id,
                display_name=member.display_name,
                token=TOKEN_COLORS[turn_order % len(TOKEN_COLORS)],
                turn_order=turn_order,
                position=config.start_position,
                balance=player_starting_balance,
                net_worth=player_starting_balance,
                rating=member.rating,
            )
        )

    spaces = tuple(SpaceOwnership(position=space.position) for space in config.board)
    chance_deck = initial_chance_deck(rng, game_mode)
    chest_deck = initial_chest_deck(rng, game_mode)
    sudden_death_deadline_ms = None
    if config.sudden_death_duration_ms is not None:
        sudden_death_deadline_ms = int(now.timestamp() * 1000) + config.sudden_death_duration_ms

    current_player = players[0]
    return GameState(
        game_id=game_id,
        session_code=session_code,
        game_mode=game_mode,
        status=GameStatus.IN_PROGRESS,
        created_at=now,
        started_at=now,
        players=tuple(players),
        turn=TurnState(
            phase=TurnPhase.PRE_ROLL,
            current_player_id=current_player.id,
            turn_number=1,
            round_number=1,
            turn_deadline_ms=int(now.timestamp() * 1000) + TURN_TIMEOUT_MS,
        ),
        spaces=spaces,
        bank_houses=BANK_HOUSES,
        bank_hotels=BANK_HOTELS,
        chance_deck=chance_deck,
        chest_deck=chest_deck,
        sudden_death_deadline_ms=sudden_death_deadline_ms,
    )
